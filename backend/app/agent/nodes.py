"""Agent reasoning and routing nodes for the LangGraph graph."""

from typing import Literal

from langchain_core.messages import SystemMessage
from langchain_litellm import ChatLiteLLM
from langgraph.graph import END

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.state import AgentState


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
