"""LangGraph graph definition for the VillaOps AI agent.

Builds a StateGraph with agent + tool nodes and conditional routing.
The agent node calls the LLM; if it requests tool calls, the tool node
executes them (with HITL interrupt for destructive tools) and loops back.

Flow:
    START → agent → [has tool_calls?]
                      ├─ YES → tools → agent (loop)
                      └─ NO  → END
"""

import asyncio
import logging
import os

from langchain_litellm import ChatLiteLLM
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.llm_options import llm_extra_kwargs
from app.agent.mcp_client import load_mcp_tools
from app.agent.nodes import create_agent_node, create_tools_node_with_confirmation, should_continue
from app.agent.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)

# Names of MCP tools that require human confirmation before execution
DESTRUCTIVE_TOOLS = {"property_delete", "guest_delete"}


# Models offered in the composer's model picker (all via OpenRouter). Only those
# whose provider key is configured are shown/accepted. Benchmarked 2026-11-24 on
# the full agent prompt (26 tools, ~11k tokens): every model below answers a
# tool-using step in ~1.5-3 s and picked the right tool 3/3 times.
CHAT_MODELS: list[dict[str, str]] = [
    # Paid (cheap): ~$0.002-0.006 per chat message
    {"id": "openrouter/openai/gpt-6-luna", "label": "GPT-6 Luna", "key": "openrouter_api_key"},
    {"id": "openrouter/anthropic/claude-haiku-5.5", "label": "Claude Haiku 5.5", "key": "openrouter_api_key"},
    {"id": "openrouter/google/gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash-Lite", "key": "openrouter_api_key"},
    # Free (OpenRouter free tier: rate-limited per minute/day)
    {"id": "openrouter/nvidia/nemotron-3.5-lightning:free", "label": "Nemotron 3.5 Lightning · free", "key": "openrouter_api_key"},
    {"id": "openrouter/dots-studio/dots-3-note-preview:free", "label": "Dots 3 Note · free", "key": "openrouter_api_key"},
    {"id": "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free", "label": "Nemotron 3 Ultra 550B · free", "key": "openrouter_api_key"},
    {"id": "openrouter/recursive/flint-v1.0:free", "label": "Flint 1.0 · free", "key": "openrouter_api_key"},
    {"id": "openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "label": "Nemotron 3 Nano Omni · free", "key": "openrouter_api_key"},
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
    sources = get_mcp_sources()
    results = await asyncio.gather(*(load_mcp_tools(url) for _, url in sources), return_exceptions=True)
    for (source, _url), loaded in zip(sources, results, strict=True):
        if isinstance(loaded, BaseException):
            logger.warning("Could not list tools from %s source: %r", source, loaded)
            continue
        for tool in loaded:
            description = (tool.description or "").strip().splitlines()[0] if tool.description else ""
            tools.append({"name": tool.name, "description": description, "source": source})
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
    if settings.openrouter_api_key:
        os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key

    # Load MCP tools as LangChain tools (non-fatal per URL, cached per server)
    tools = await load_mcp_tools([url for _, url in get_mcp_sources()])
    if disabled_tools:
        tools = [t for t in tools if t.name not in disabled_tools]
        logger.info("Disabled by user: %s", sorted(disabled_tools))
    logger.info("Loaded %d MCP tools", len(tools))

    # Primary, the primary again (a stalled stream is usually one slow provider
    # host — OpenRouter routes the retry elsewhere), then the fallback chain.
    # The agent node moves on when a model gives no output within
    # FIRST_TOKEN_DEADLINE_S or errors (rate limit, 503).
    model_ids = [primary_model, primary_model]
    model_ids += [m for m in dict.fromkeys(settings.llm_fallback_models) if m != primary_model]
    logger.info("LLM chain: %s", model_ids)

    llms = [
        ChatLiteLLM(
            model=model_id,
            temperature=1.0,
            max_tokens=4096,
            max_retries=0,  # fail over to the next model instead of retrying
            # Without a timeout a hung request blocks for ~10 min
            request_timeout=30,
            model_kwargs=llm_extra_kwargs(model_id),
            streaming=True,
        )
        for model_id in model_ids
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
