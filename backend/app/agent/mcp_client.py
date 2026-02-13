"""MCP-to-LangChain tool bridge.

Connects to the MCP server via Streamable HTTP, discovers tools dynamically,
and wraps each MCP tool as a LangChain StructuredTool for use in LangGraph.
"""

import logging
from typing import Any

from langchain_core.tools import StructuredTool
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel, Field, create_model

logger = logging.getLogger(__name__)

# Map JSON Schema types to Python types
JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


def _build_args_model(tool_name: str, input_schema: dict) -> type[BaseModel]:
    """Build a Pydantic model from an MCP tool's JSON Schema inputSchema."""
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    fields: dict[str, Any] = {}
    for prop_name, prop_schema in properties.items():
        python_type = JSON_TYPE_MAP.get(prop_schema.get("type", "string"), str)
        description = prop_schema.get("description", "")
        default = ... if prop_name in required else None

        if prop_name not in required:
            python_type = python_type | None  # type: ignore[assignment]

        fields[prop_name] = (python_type, Field(default=default, description=description))

    model_name = f"{tool_name.title().replace('_', '')}Args"
    return create_model(model_name, **fields)


async def _call_mcp_tool(mcp_url: str, tool_name: str, **kwargs: Any) -> str:
    """Call an MCP tool via a fresh Streamable HTTP connection."""
    # Filter out None values — MCP tools treat missing params as unset
    args = {k: v for k, v in kwargs.items() if v is not None}
    async with streamable_http_client(mcp_url) as (read, write, _), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool(tool_name, args)
        return result.content[0].text


async def load_mcp_tools(mcp_url: str) -> list[StructuredTool]:
    """Connect to MCP server, discover tools, and return LangChain-compatible tools."""
    async with streamable_http_client(mcp_url) as (read, write, _), ClientSession(read, write) as session:
            await session.initialize()
            tools_response = await session.list_tools()

    langchain_tools = []
    for mcp_tool in tools_response.tools:
        args_model = _build_args_model(mcp_tool.name, mcp_tool.inputSchema)

        # Create a closure for this specific tool — default args capture current values
        async def tool_fn(_tool_name=mcp_tool.name, _mcp_url=mcp_url, **kwargs):
            return await _call_mcp_tool(_mcp_url, _tool_name, **kwargs)

        lc_tool = StructuredTool(
            name=mcp_tool.name,
            description=mcp_tool.description or f"MCP tool: {mcp_tool.name}",
            coroutine=tool_fn,
            args_schema=args_model,
        )
        langchain_tools.append(lc_tool)

    logger.info(f"Loaded {len(langchain_tools)} MCP tools: {[t.name for t in langchain_tools]}")
    return langchain_tools
