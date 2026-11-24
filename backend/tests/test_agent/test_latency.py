"""Tests for the agent latency fixes: history trimming, first-token failover, tool cache, model options."""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from app.agent import mcp_client, nodes
from app.agent.llm_options import llm_extra_kwargs
from app.api.v1.chat import HISTORY_MAX_MESSAGES, OLD_TOOL_RESULT_MAX_CHARS, trim_history

pytestmark = pytest.mark.asyncio


class TestTrimHistory:
    def test_short_history_unchanged(self) -> None:
        history = [HumanMessage("hi"), AIMessage("hello")]
        assert trim_history(history) == history

    def test_long_history_starts_at_user_turn(self) -> None:
        history = []
        for i in range(HISTORY_MAX_MESSAGES):
            history += [
                HumanMessage(f"q{i}"),
                AIMessage("", tool_calls=[{"name": "kb_search", "args": {}, "id": f"c{i}"}]),
                ToolMessage("r", tool_call_id=f"c{i}"),
                AIMessage(f"a{i}"),
            ]
        trimmed = trim_history(history)
        assert len(trimmed) <= HISTORY_MAX_MESSAGES
        assert isinstance(trimmed[0], HumanMessage)
        assert trimmed[-1].content == f"a{HISTORY_MAX_MESSAGES - 1}"

    def test_large_tool_results_truncated(self) -> None:
        big = "x" * (OLD_TOOL_RESULT_MAX_CHARS * 3)
        trimmed = trim_history([HumanMessage("q"), ToolMessage(big, tool_call_id="1")])
        assert len(trimmed[1].content) < len(big)
        assert trimmed[1].content.endswith("[truncated earlier tool result]")


class _FakeModel:
    """Streams chunks after an optional delay before the first one."""

    def __init__(self, text: str, first_delay: float = 0.0, fail: bool = False):
        self.text, self.first_delay, self.fail = text, first_delay, fail
        self.called = False

    async def astream(self, _messages):
        self.called = True
        if self.fail:
            raise RuntimeError("503 overloaded")
        await asyncio.sleep(self.first_delay)
        for word in self.text.split(" "):
            yield AIMessageChunk(content=word + " ")


class TestFirstTokenDeadline:
    async def test_fast_model_used(self) -> None:
        msg = await nodes.invoke_with_first_token_deadline([_FakeModel("hello there"), _FakeModel("backup")], [])
        assert msg.content.strip() == "hello there"
        assert isinstance(msg, AIMessage)

    async def test_stalled_model_falls_over(self) -> None:
        slow, backup = _FakeModel("slow", first_delay=5), _FakeModel("fast answer")
        with patch.object(nodes, "FIRST_TOKEN_DEADLINE_S", 0.05):
            msg = await nodes.invoke_with_first_token_deadline([slow, backup], [])
        assert msg.content.strip() == "fast answer"

    async def test_error_falls_over(self) -> None:
        msg = await nodes.invoke_with_first_token_deadline([_FakeModel("", fail=True), _FakeModel("ok")], [])
        assert msg.content.strip() == "ok"

    async def test_last_model_has_no_deadline(self) -> None:
        with patch.object(nodes, "FIRST_TOKEN_DEADLINE_S", 0.01):
            msg = await nodes.invoke_with_first_token_deadline(
                [_FakeModel("a", first_delay=1), _FakeModel("late but final", first_delay=0.05)], []
            )
        assert msg.content.strip() == "late but final"

    async def test_tool_call_chunks_merge_into_tool_calls(self) -> None:
        class ToolModel:
            async def astream(self, _messages):
                yield AIMessageChunk(content="", tool_call_chunks=[{"name": "kb_search", "args": '{"query"', "id": "c1", "index": 0}])
                yield AIMessageChunk(content="", tool_call_chunks=[{"name": None, "args": ': "pets"}', "id": None, "index": 0}])

        msg = await nodes.invoke_with_first_token_deadline([ToolModel(), _FakeModel("x")], [])
        assert msg.tool_calls == [{"name": "kb_search", "args": {"query": "pets"}, "id": "c1", "type": "tool_call"}]


class TestToolCache:
    async def test_cached_within_ttl_and_parallel(self) -> None:
        mcp_client.clear_tools_cache()
        calls: list[str] = []

        async def fake_load(url):
            calls.append(url)
            return [SimpleNamespace(name=f"tool-{url}")]

        with patch.object(mcp_client, "_load_tools_from_url", side_effect=fake_load):
            first = await mcp_client.load_mcp_tools(["a", "b"], ttl=60)
            second = await mcp_client.load_mcp_tools(["a", "b"], ttl=60)
        assert [t.name for t in first] == [t.name for t in second] == ["tool-a", "tool-b"]
        assert sorted(calls) == ["a", "b"]  # second call served from cache
        mcp_client.clear_tools_cache()

    async def test_failing_source_skipped_and_not_cached(self) -> None:
        mcp_client.clear_tools_cache()

        async def fake_load(url):
            if url == "bad":
                raise ConnectionError("down")
            return [SimpleNamespace(name="ok")]

        with patch.object(mcp_client, "_load_tools_from_url", side_effect=fake_load):
            assert [t.name for t in await mcp_client.load_mcp_tools(["bad", "good"], ttl=60)] == ["ok"]
        assert "bad" not in mcp_client._tools_cache
        mcp_client.clear_tools_cache()


class TestLlmOptions:
    def test_openrouter_sorts_by_latency(self) -> None:
        assert llm_extra_kwargs("openrouter/openai/gpt-6-luna") == {"extra_body": {"provider": {"sort": "latency"}}}

    def test_other_providers_untouched(self) -> None:
        assert llm_extra_kwargs("gemini/gemini-3.5-flash") == {}
