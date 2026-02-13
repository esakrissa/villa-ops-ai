"""Unit tests for agent routing nodes (should_continue)."""

from langchain_core.messages import AIMessage

from app.agent.nodes import should_continue


class TestShouldContinue:
    """Test the should_continue routing function."""

    def test_returns_tools_when_tool_calls_present(self):
        msg = AIMessage(
            content="",
            tool_calls=[{"name": "booking_search", "args": {"query": "test"}, "id": "tc_1"}],
        )
        state = {"messages": [msg]}
        assert should_continue(state) == "tools"

    def test_returns_end_when_no_tool_calls(self):
        msg = AIMessage(content="Here is your answer.")
        state = {"messages": [msg]}
        assert should_continue(state) == "__end__"

    def test_returns_end_when_empty_tool_calls(self):
        msg = AIMessage(content="Done.", tool_calls=[])
        state = {"messages": [msg]}
        assert should_continue(state) == "__end__"

    def test_returns_tools_with_multiple_tool_calls(self):
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "booking_search", "args": {}, "id": "tc_1"},
                {"name": "guest_lookup", "args": {}, "id": "tc_2"},
            ],
        )
        state = {"messages": [msg]}
        assert should_continue(state) == "tools"

    def test_uses_last_message_only(self):
        """should_continue should only look at the last message in state."""
        first = AIMessage(
            content="",
            tool_calls=[{"name": "booking_search", "args": {}, "id": "tc_1"}],
        )
        last = AIMessage(content="All done, no more tools needed.")
        state = {"messages": [first, last]}
        assert should_continue(state) == "__end__"
