"""Tests for user-disabled tools: prompt notice, tool filtering, and the tools endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool

from app.agent.graph import create_agent, get_mcp_sources, list_agent_tools
from app.agent.nodes import create_agent_node


def _fake_llm():
    """LLM stub whose bind_tools() returns a runnable that records the prompt."""
    bound = MagicMock()
    bound.ainvoke = AsyncMock(return_value=AIMessage(content="ok"))
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=bound)
    return llm, bound


def _tool(name: str) -> StructuredTool:
    async def _run(**_):
        return "ok"

    return StructuredTool.from_function(coroutine=_run, name=name, description=f"{name} tool")


@pytest.mark.asyncio
class TestDisabledToolsPrompt:
    async def test_system_prompt_lists_disabled_tools(self):
        llm, bound = _fake_llm()
        node = create_agent_node(llm, [], disabled_tools={"property_list", "guest_delete"})
        await node({"messages": [HumanMessage("hi")], "user_id": ""})

        system = bound.ainvoke.call_args.args[0][0]
        assert isinstance(system, SystemMessage)
        assert "## Disabled Tools" in system.content
        assert "guest_delete, property_list" in system.content

    async def test_no_notice_when_nothing_disabled(self):
        llm, bound = _fake_llm()
        node = create_agent_node(llm, [])
        await node({"messages": [HumanMessage("hi")], "user_id": ""})
        assert "Disabled Tools" not in bound.ainvoke.call_args.args[0][0].content


@pytest.mark.asyncio
class TestCreateAgentFiltersTools:
    async def test_disabled_tools_are_not_bound(self):
        tools = [_tool("booking_search"), _tool("property_list"), _tool("guest_delete")]
        with (
            patch("app.agent.graph.load_mcp_tools", AsyncMock(return_value=tools)),
            patch("app.agent.graph.create_agent_node") as node_factory,
        ):
            node_factory.return_value = AsyncMock()
            await create_agent(disabled_tools={"property_list"})

        bound_tools = node_factory.call_args.args[1]
        assert [t.name for t in bound_tools] == ["booking_search", "guest_delete"]
        assert node_factory.call_args.args[2] == {"property_list"}


@pytest.mark.asyncio
class TestListAgentTools:
    async def test_tags_tools_with_source_and_skips_failing_sources(self):
        async def fake_load(url):
            if "exa" in url:
                raise ConnectionError("exa down")
            return [_tool("booking_search")]

        with (
            patch("app.agent.graph.get_mcp_sources", return_value=[("villaops", "http://mcp"), ("exa", "https://exa")]),
            patch("app.agent.graph.load_mcp_tools", side_effect=fake_load),
        ):
            tools = await list_agent_tools()

        assert tools == [{"name": "booking_search", "description": "booking_search tool", "source": "villaops"}]


class TestMcpSources:
    def test_market_sources_are_added_only_when_configured(self):
        with patch("app.agent.graph.settings") as s:
            s.mcp_server_url = "http://mcp:8001/mcp"
            s.booking_mcp_url = "http://booking-mcp:8002/mcp"
            s.airbnb_mcp_url = ""
            s.tripadvisor_mcp_url = "http://tripadvisor-mcp:8004/mcp"
            s.exa_api_key = ""
            sources = get_mcp_sources()

        assert sources == [
            ("villaops", "http://mcp:8001/mcp"),
            ("booking", "http://booking-mcp:8002/mcp"),
            ("tripadvisor", "http://tripadvisor-mcp:8004/mcp"),
        ]


@pytest.mark.asyncio
class TestToolsEndpoint:
    async def test_requires_auth(self, client):
        response = await client.get("/api/v1/chat/tools")
        assert response.status_code in (401, 403)

    async def test_returns_tools(self, client, auth_headers):
        fake = [{"name": "booking_search", "description": "Search bookings.", "source": "villaops"}]
        with patch("app.api.v1.chat.list_agent_tools", AsyncMock(return_value=fake)):
            response = await client.get("/api/v1/chat/tools", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == fake
