"""Agent reasoning and routing nodes for the LangGraph graph."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

from langchain_core.messages import AIMessageChunk, BaseMessage, SystemMessage, ToolMessage, message_chunk_to_message
from langchain_litellm import ChatLiteLLM
from langgraph.graph import END
from langgraph.types import interrupt

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.state import AgentState

logger = logging.getLogger(__name__)

# Bali / WITA timezone (UTC+8)
BALI_TZ = timezone(timedelta(hours=8))

# Seconds to wait for a model's first token before abandoning that request and
# trying the next one. Models usually answer in 1-3 s but a provider host can
# stall for 20-100 s before the first token; a retry almost always lands on a fast one.
# LiteLLM's request_timeout doesn't cover a stream that never starts.
FIRST_TOKEN_DEADLINE_S = 8.0


def _has_output(chunk: AIMessageChunk) -> bool:
    return bool(chunk.content or chunk.tool_call_chunks)


async def invoke_with_first_token_deadline(models: list, messages: list[BaseMessage]) -> BaseMessage:
    """Stream from each model in turn; move on if no output arrives in time.

    Nothing has been streamed to the user when an attempt is abandoned, so
    failover never shows duplicate partial text. The last model gets no
    deadline. Errors (503, rate limits) also fail over.
    """
    last_error: BaseException | None = None
    for i, model in enumerate(models):
        is_last = i == len(models) - 1
        stream = model.astream(messages)
        received: list[AIMessageChunk] = []

        async def first_output() -> None:
            async for chunk in stream:  # noqa: B023 — awaited before the loop advances
                received.append(chunk)  # noqa: B023
                if _has_output(chunk):
                    return

        try:
            await asyncio.wait_for(first_output(), timeout=None if is_last else FIRST_TOKEN_DEADLINE_S)
            async for chunk in stream:
                received.append(chunk)
        except TimeoutError as e:
            logger.warning("Model #%d gave no output within %.0fs — trying the next one", i, FIRST_TOKEN_DEADLINE_S)
            last_error = e
            await stream.aclose()
            continue
        except Exception as e:
            logger.warning("Model #%d failed (%r) — trying the next one", i, e)
            last_error = e
            await stream.aclose()
            if is_last:
                raise
            continue

        if not received:
            continue
        merged = received[0]
        for chunk in received[1:]:
            merged = merged + chunk
        return message_chunk_to_message(merged)

    raise last_error or RuntimeError("No model produced a response")


def create_agent_node(
    llm: ChatLiteLLM | list[ChatLiteLLM],
    tools: list,
    disabled_tools: set[str] | None = None,
):
    """Create the agent node function with tools bound to the LLM.

    Accepts a single LLM or a list ordered by preference — later entries are
    used as fallbacks when an earlier model errors (e.g. 503 overloaded).
    """
    llms = llm if isinstance(llm, list) else [llm]
    bound = [m.bind_tools(tools) for m in llms]

    async def agent_node(state: AgentState) -> dict:
        """Call the LLM with conversation history and available tools."""
        user_id = state.get("user_id", "")

        # Inject current Bali time into system prompt
        now_bali = datetime.now(BALI_TZ)
        time_context = (
            f"\n\n## Current Time\n"
            f"Current date and time in Bali (WITA, UTC+8): "
            f"{now_bali.strftime('%A, %B %d, %Y at %H:%M')}.\n"
            f"Use this as the reference for 'today', 'tomorrow', 'this week', etc."
        )
        system_content = SYSTEM_PROMPT + time_context
        if disabled_tools:
            system_content += (
                "\n\n## Disabled Tools\n"
                f"The user has switched off these tools: {', '.join(sorted(disabled_tools))}. "
                "Do not call them. If a request needs one, say which tool is turned off and that "
                "they can re-enable it from the tools menu in the chat composer."
            )

        if user_id:
            system_content += (
                f"\n\nIMPORTANT: The current user's ID is '{user_id}'. "
                "You MUST pass this as the 'user_id' parameter in EVERY VillaOps tool call "
                "to ensure data isolation. Never omit the user_id parameter on tools that accept it."
            )
        messages = [SystemMessage(content=system_content)] + state["messages"]
        if len(bound) == 1:
            response = await bound[0].ainvoke(messages)
        else:
            response = await invoke_with_first_token_deadline(bound, messages)
        return {"messages": [response]}

    return agent_node


def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """Route to tool execution if the LLM made tool calls, otherwise end."""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END


def create_tools_node_with_confirmation(standard_tool_node, destructive_tools: set[str]):
    """Create a tools node that interrupts for confirmation on destructive tools.

    For non-destructive tools, delegates to the standard ToolNode.
    For destructive tools (e.g. property_delete, guest_delete), uses
    LangGraph's interrupt() to pause execution until the user confirms.

    Args:
        standard_tool_node: A ToolNode instance for executing tools.
        destructive_tools: Set of tool names requiring confirmation.
    """

    async def tools_node(state: AgentState) -> dict:
        """Execute tools, interrupting for confirmation on destructive operations."""
        messages = state["messages"]
        last_msg = messages[-1]

        if not last_msg.tool_calls:
            return {"messages": []}

        # Check if any tool call is destructive
        has_destructive = any(
            tc["name"] in destructive_tools for tc in last_msg.tool_calls
        )

        if not has_destructive:
            # No destructive tools — use standard tool node
            return await standard_tool_node.ainvoke(state)

        # Process tool calls, interrupting for destructive ones
        results = []
        for tc in last_msg.tool_calls:
            if tc["name"] in destructive_tools:
                # Interrupt: send confirmation payload to the client
                decision = interrupt({
                    "type": "destructive_action",
                    "tool_name": tc["name"],
                    "args": tc["args"],
                    "message": f"Are you sure you want to {tc['name'].replace('_', ' ')}?",
                })

                if decision.get("action") != "approve":
                    logger.info("Tool %s cancelled by user", tc["name"])
                    results.append(ToolMessage(
                        content="Action cancelled by user.",
                        tool_call_id=tc["id"],
                        name=tc["name"],
                    ))
                    continue

            # Execute the tool via standard tool node (single tool call)
            single_msg = last_msg.model_copy()
            single_msg.tool_calls = [tc]
            single_state = {**state, "messages": [*messages[:-1], single_msg]}
            result = await standard_tool_node.ainvoke(single_state)
            result_msgs = result.get("messages", [])
            logger.info("Tool %s executed", tc["name"])
            results.extend(result_msgs)

        return {"messages": results}

    return tools_node
