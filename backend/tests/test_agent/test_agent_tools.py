"""Agent integration tests — verify tool selection for various queries.

These are FULL-STACK integration tests that require:
1. GEMINI_API_KEY set in environment
2. MCP server running at MCP_SERVER_URL (http://mcp:8001/mcp in Docker)
3. Seeded data in the production database (villa_ops)

They do NOT use the test database or conftest fixtures.
Run inside the backend Docker container on EC2.
"""

import os

import pytest

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not os.getenv("GEMINI_API_KEY"),
        reason="GEMINI_API_KEY not set — skipping agent integration tests",
    ),
]


def _extract_tool_names(messages) -> list[str]:
    """Extract tool names from AIMessage.tool_calls in a result's messages."""
    names = []
    for m in messages:
        if hasattr(m, "tool_calls") and m.tool_calls:
            for tc in m.tool_calls:
                names.append(tc["name"])
    return names


class TestAgentToolSelection:
    """Test that the agent selects the right tools for different queries."""

    async def test_booking_query_uses_booking_search(self):
        """Agent should use booking_search for booking-related queries."""
        from app.agent import create_agent

        agent = await create_agent()
        result = await agent.ainvoke({
            "messages": [("user", "Show me all confirmed bookings")]
        })
        tool_names = _extract_tool_names(result["messages"])
        assert len(tool_names) > 0, "Agent did not call any tools"
        assert "booking_search" in tool_names

    async def test_guest_query_uses_guest_lookup(self):
        """Agent should use guest_lookup for guest-related queries."""
        from app.agent import create_agent

        agent = await create_agent()
        result = await agent.ainvoke({
            "messages": [("user", "Find information about guest Sarah Chen")]
        })
        tool_names = _extract_tool_names(result["messages"])
        assert len(tool_names) > 0, "Agent did not call any tools"
        assert "guest_lookup" in tool_names

    async def test_analytics_query_uses_booking_analytics(self):
        """Agent should use booking_analytics for analytics questions."""
        from app.agent import create_agent

        agent = await create_agent()
        result = await agent.ainvoke({
            "messages": [(
                "user",
                "Use the booking_analytics tool to get me the occupancy rate "
                "and revenue summary for all properties in the last 30 days."
            )]
        })
        tool_names = _extract_tool_names(result["messages"])
        assert len(tool_names) > 0, "Agent did not call any tools"
        assert "booking_analytics" in tool_names

    async def test_notification_query_uses_send_notification(self):
        """Agent should use send_notification for notification requests."""
        from app.agent import create_agent

        agent = await create_agent()
        result = await agent.ainvoke({
            "messages": [(
                "user",
                "Use guest_lookup to find Sarah Chen's guest ID, then use the "
                "send_notification tool to send her a check_in_reminder notification."
            )]
        })
        tool_names = _extract_tool_names(result["messages"])
        assert len(tool_names) > 0, "Agent did not call any tools"
        assert "send_notification" in tool_names
