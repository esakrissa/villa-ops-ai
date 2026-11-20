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


# Models offered in the composer's model picker. Only those whose provider key
# is configured are shown/accepted.
CHAT_MODELS: list[dict[str, str]] = [
    {"id": "gemini/gemini-3.5-flash", "label": "Gemini 3.5 Flash", "key": "gemini_api_key"},
    {"id": "xiaomi_mimo/mimo-v2.6-pro", "label": "MiMo 2.6 Pro", "key": "xiaomi_mimo_api_key"},
]


def available_models() -> list[dict]:
    """Picker models with a configured API key; the default model is flagged."""
    models = [m for m in CHAT_MODELS if getattr(settings, m["key"], "")]
    return [{"id": m["id"], "label": m["label"], "default": m["id"] == settings.default_llm_model} for m in models]


def resolve_model(requested: str | None) -> str:
    """Return the requested model if it's offered and configured, else the default."""
    if requested and any(m["id"] == requested for m in available_models()):
        return requested
    return settings.default_llm_model


def get_mcp_sources() -> list[tuple[str, str]]:
    """Return ``(source, url)`` pairs for every MCP server the agent uses."""
    # Primary: VillaOps MCP server (docker-compose overrides to http://mcp:8001/mcp)
    sources = [("villaops", settings.mcp_server_url)]
    # Optional: market data MCP servers (Booking.com, Airbnb, Tripadvisor) from mcp-servers/
    for source, url in (
        ("booking", settings.booking_mcp_url),
        ("airbnb", settings.airbnb_mcp_url),
        ("tripadvisor", settings.tripadvisor_mcp_url),
    ):
        if url:
            sources.append((source, url))
    # Optional: Exa hosted MCP server for web search
    if settings.exa_api_key:
        sources.append(("exa", f"https://mcp.exa.ai/mcp?exaApiKey={settings.exa_api_key}"))
    return sources


async def list_agent_tools() -> list[dict]:
    """Discover every tool the agent can use, tagged with its source.

    Used by the UI's tool toggle menu. Unreachable sources are skipped.
    """
    tools: list[dict] = []
    for source, url in get_mcp_sources():
        try:
            for tool in await load_mcp_tools(url):
                description = (tool.description or "").strip().splitlines()[0] if tool.description else ""
                tools.append({"name": tool.name, "description": description, "source": source})
        except Exception:
            logger.warning("Could not list tools from %s source", source, exc_info=True)
    return tools


async def create_agent(checkpointer=None, disabled_tools: set[str] | None = None, model: str | None = None):
    """Create and return the compiled VillaOps AI agent graph.

    1. Loads MCP tools from the MCP server (Streamable HTTP)
    2. Creates a ChatLiteLLM instance with the configured model
    3. Builds a StateGraph with agent + tool nodes
    4. Returns the compiled graph

    Args:
        checkpointer: Optional LangGraph checkpointer for HITL persistence.
                     Required for interrupt()/Command(resume=...) support.
        disabled_tools: Tool names the user switched off in the UI; they are
                     not bound to the LLM for this run.
        model: Primary LLM picked in the UI (see ``resolve_model``).
    """
    primary_model = resolve_model(model)
    # Set API keys for LiteLLM
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.openrouter_api_key:
        os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
    if settings.xiaomi_mimo_api_key:
        os.environ["XIAOMI_MIMO_API_KEY"] = settings.xiaomi_mimo_api_key

    # Load MCP tools as LangChain tools (non-fatal per URL)
    tools = await load_mcp_tools([url for _, url in get_mcp_sources()])
    if disabled_tools:
        tools = [t for t in tools if t.name not in disabled_tools]
        logger.info("Disabled by user: %s", sorted(disabled_tools))
    logger.info("Loaded %d MCP tools", len(tools))

    # Build fallback model list for LiteLLM — if the primary model is
    # unreachable, requests are retried against the next available provider.
    fallback_models = []
    if settings.gemini_api_key:
        fallback_models.extend(
            m for m in [settings.default_llm_model, *settings.gemini_fallback_models] if m != primary_model
        )
    mimo_model = "xiaomi_mimo/mimo-v2.6-pro"
    if settings.xiaomi_mimo_api_key and primary_model != mimo_model:
        fallback_models.append(mimo_model)
    if settings.anthropic_api_key:
        fallback_models.append("anthropic/claude-sonnet-4-20250514")
    if settings.openai_api_key:
        fallback_models.append("openai/gpt-4o-mini")
    if settings.openrouter_api_key:
        fallback_models.append(settings.openrouter_fallback_model)

    fallback_models = [m for m in dict.fromkeys(fallback_models) if m != primary_model]
    if fallback_models:
        logger.info("LLM fallbacks configured: %s", fallback_models)

    # Create one LLM per model via LiteLLM (supports Gemini, Claude, GPT via
    # unified API). The agent node chains them with LangChain's with_fallbacks(),
    # which (unlike LiteLLM's `fallbacks` kwarg) also works while streaming.
    llms = [
        ChatLiteLLM(
            model=model_id,
            temperature=1.0,
            max_tokens=4096,
            max_retries=0,  # fail over to the next model instead of retrying
            # Without a timeout a hung Gemini request blocks for ~10 min and
            # with_fallbacks() never gets a chance to try the next model.
            request_timeout=30,
        )
        for model_id in dict.fromkeys([primary_model, *fallback_models])
    ]

    # Build the graph
    graph = StateGraph(AgentState)

    # Add nodes
    agent_node = create_agent_node(llms, tools, disabled_tools)

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
