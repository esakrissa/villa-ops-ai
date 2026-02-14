"""LangGraph graph definition for the VillaOps AI agent.

Builds a StateGraph with agent + tool nodes and conditional routing.
The agent node calls the LLM; if it requests tool calls, the tool node
executes them (with HITL interrupt for destructive tools) and loops back.

Flow:
    START → agent → [has tool_calls?]
                      ├─ YES → tools → agent (loop)
                      └─ NO  → END
"""

import logging
import os

from langchain_litellm import ChatLiteLLM
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.mcp_client import load_mcp_tools
from app.agent.nodes import create_agent_node, create_tools_node_with_confirmation, should_continue
from app.agent.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)

# Names of MCP tools that require human confirmation before execution
DESTRUCTIVE_TOOLS = {"property_delete", "guest_delete"}


async def create_agent(checkpointer=None):
    """Create and return the compiled VillaOps AI agent graph.

    1. Loads MCP tools from the MCP server (Streamable HTTP)
    2. Creates a ChatLiteLLM instance with the configured model
    3. Builds a StateGraph with agent + tool nodes
    4. Returns the compiled graph

    Args:
        checkpointer: Optional LangGraph checkpointer for HITL persistence.
                     Required for interrupt()/Command(resume=...) support.
    """
    # Set API keys for LiteLLM
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key

    # MCP URL — docker-compose.yml overrides to http://mcp:8001/mcp inside Docker
    mcp_url = settings.mcp_server_url

    # Load MCP tools as LangChain tools
    tools = await load_mcp_tools(mcp_url)
    logger.info("Loaded %d MCP tools", len(tools))

    # Create LLM via LiteLLM (supports Gemini, Claude, GPT via unified API)
    llm = ChatLiteLLM(
        model=settings.default_llm_model,
        temperature=1.0,
        max_tokens=4096,
    )

    # Build the graph
    graph = StateGraph(AgentState)

    # Add nodes
    agent_node = create_agent_node(llm, tools)

    # Use custom tools node with HITL interrupt for destructive operations,
    # falling back to standard ToolNode for non-destructive tools
    standard_tool_node = ToolNode(tools)
    tools_with_confirmation = create_tools_node_with_confirmation(
        standard_tool_node, DESTRUCTIVE_TOOLS
    )

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_with_confirmation)

    # Add edges
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    # Compile with optional checkpointer
    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("Agent graph compiled (checkpointer=%s)", type(checkpointer).__name__ if checkpointer else "none")

    return compiled
