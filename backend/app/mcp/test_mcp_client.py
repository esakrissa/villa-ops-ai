"""Quick MCP client test — run inside the Docker network.

Usage (inside backend container):
    python -m app.mcp.test_mcp_client
"""

import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

# Streamable HTTP endpoint — mounted at /mcp on the MCP service
MCP_URL = "http://mcp:8001/mcp"


async def main():
    async with streamable_http_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print(f"\n=== Available Tools ({len(tools.tools)}) ===")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")

            # Test booking_search
            print("\n=== Test: booking_search (all bookings) ===")
            result = await session.call_tool("booking_search", {"limit": 5})
            print(result.content[0].text)

            # Test booking_search with status filter
            print("\n=== Test: booking_search (confirmed only) ===")
            result = await session.call_tool("booking_search", {"status": "confirmed", "limit": 3})
            print(result.content[0].text)

            # Test guest_lookup
            print("\n=== Test: guest_lookup (all guests) ===")
            result = await session.call_tool("guest_lookup", {"limit": 3})
            print(result.content[0].text)

            # Test guest_lookup with name search
            print("\n=== Test: guest_lookup (search by name) ===")
            result = await session.call_tool(
                "guest_lookup", {"name": "sarah", "include_bookings": True}
            )
            print(result.content[0].text)

            print("\nAll MCP tool tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
