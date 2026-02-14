"""Agent reasoning and routing nodes for the LangGraph graph."""

import logging
from typing import Literal

from langchain_core.messages import SystemMessage, ToolMessage
from langchain_litellm import ChatLiteLLM
from langgraph.graph import END
from langgraph.types import interrupt

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def create_agent_node(llm: ChatLiteLLM, tools: list):
    """Create the agent node function with tools bound to the LLM."""
    llm_with_tools = llm.bind_tools(tools)

    async def agent_node(state: AgentState) -> dict:
        """Call the LLM with conversation history and available tools."""
        user_id = state.get("user_id", "")
        system_content = SYSTEM_PROMPT
        if user_id:
            system_content += (
                f"\n\nIMPORTANT: The current user's ID is '{user_id}'. "
                "You MUST pass this as the 'user_id' parameter in EVERY tool call "
                "to ensure data isolation. Never omit the user_id parameter."
            )
        messages = [SystemMessage(content=system_content)] + state["messages"]
        response = await llm_with_tools.ainvoke(messages)
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
