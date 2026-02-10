"""Quick MCP client test — run inside the Docker network.

Usage (inside backend container):
    python -m app.mcp.test_mcp_client
"""

import asyncio
import json

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

            # ----------------------------------------------------------
            # Day 6 tools — booking_search + guest_lookup
            # ----------------------------------------------------------
            print("\n=== Test: booking_search (all bookings) ===")
            result = await session.call_tool("booking_search", {"limit": 5})
            print(result.content[0].text)

            print("\n=== Test: booking_search (confirmed only) ===")
            result = await session.call_tool("booking_search", {"status": "confirmed", "limit": 3})
            print(result.content[0].text)

            print("\n=== Test: guest_lookup (all guests) ===")
            result = await session.call_tool("guest_lookup", {"limit": 3})
            print(result.content[0].text)

            print("\n=== Test: guest_lookup (search by name) ===")
            result = await session.call_tool(
                "guest_lookup", {"name": "sarah", "include_bookings": True}
            )
            print(result.content[0].text)

            # ----------------------------------------------------------
            # Day 7 tools — booking_create, booking_update, property_manage
            # ----------------------------------------------------------

            # Get a property_id and guest_id from seeded data
            result = await session.call_tool("booking_search", {"limit": 1})
            data = json.loads(result.content[0].text)
            property_id = data["bookings"][0]["property_id"]
            print(f"\nUsing property_id: {property_id}")

            result = await session.call_tool("guest_lookup", {"limit": 1})
            guest_data = json.loads(result.content[0].text)
            guest_id = guest_data["guests"][0]["id"]
            print(f"Using guest_id: {guest_id}")

            # --- booking_create (success) ---
            print("\n=== Test: booking_create (new booking) ===")
            result = await session.call_tool("booking_create", {
                "property_id": property_id,
                "guest_id": guest_id,
                "check_in": "2026-12-01",
                "check_out": "2026-12-05",
                "num_guests": 2,
                "status": "pending",
                "total_price": "1500.00",
                "special_requests": "Late check-in after 10pm",
            })
            create_result = json.loads(result.content[0].text)
            print(result.content[0].text)
            assert create_result.get("booking") is not None, "booking_create should return a booking"
            assert "id" in create_result["booking"], "created booking should have an id"
            created_booking_id = create_result["booking"]["id"]
            print(f"  Created booking ID: {created_booking_id}")

            # --- booking_create (date conflict) ---
            print("\n=== Test: booking_create (date conflict) ===")
            result = await session.call_tool("booking_create", {
                "property_id": property_id,
                "guest_id": guest_id,
                "check_in": "2026-12-02",
                "check_out": "2026-12-04",
            })
            conflict_result = json.loads(result.content[0].text)
            print(result.content[0].text)
            assert "error" in conflict_result, "overlapping booking should return error"
            print("  Conflict correctly detected!")

            # --- booking_update (confirm) ---
            print("\n=== Test: booking_update (confirm booking) ===")
            result = await session.call_tool("booking_update", {
                "booking_id": created_booking_id,
                "status": "confirmed",
            })
            update_result = json.loads(result.content[0].text)
            print(result.content[0].text)
            assert update_result["booking"]["status"] == "confirmed", "status should be confirmed"
            print("  Status updated to confirmed!")

            # --- booking_update (cancel) ---
            print("\n=== Test: booking_update (cancel booking) ===")
            result = await session.call_tool("booking_update", {
                "booking_id": created_booking_id,
                "status": "cancelled",
            })
            cancel_result = json.loads(result.content[0].text)
            print(result.content[0].text)
            assert cancel_result["booking"]["status"] == "cancelled", "status should be cancelled"
            print("  Booking cancelled!")

            # --- property_manage (check_availability — available) ---
            print("\n=== Test: property_manage (check_availability — free dates) ===")
            result = await session.call_tool("property_manage", {
                "action": "check_availability",
                "property_id": property_id,
                "check_in": "2027-06-01",
                "check_out": "2027-06-10",
            })
            avail_result = json.loads(result.content[0].text)
            print(result.content[0].text)
            assert avail_result["available"] is True, "far-future dates should be available"
            print("  Availability confirmed!")

            # --- property_manage (check_availability — conflict) ---
            # First create a booking to conflict with
            result = await session.call_tool("booking_create", {
                "property_id": property_id,
                "guest_id": guest_id,
                "check_in": "2027-03-01",
                "check_out": "2027-03-10",
                "status": "confirmed",
            })
            temp_booking = json.loads(result.content[0].text)
            temp_booking_id = temp_booking["booking"]["id"]

            print("\n=== Test: property_manage (check_availability — conflict) ===")
            result = await session.call_tool("property_manage", {
                "action": "check_availability",
                "property_id": property_id,
                "check_in": "2027-03-05",
                "check_out": "2027-03-15",
            })
            conflict_avail = json.loads(result.content[0].text)
            print(result.content[0].text)
            assert conflict_avail["available"] is False, "overlapping dates should not be available"
            assert len(conflict_avail["conflicts"]) > 0, "should list conflicting bookings"
            print("  Conflict correctly detected!")

            # Clean up temp booking
            await session.call_tool("booking_update", {
                "booking_id": temp_booking_id,
                "status": "cancelled",
            })

            # --- property_manage (update_pricing) ---
            print("\n=== Test: property_manage (update_pricing) ===")
            result = await session.call_tool("property_manage", {
                "action": "update_pricing",
                "property_id": property_id,
                "base_price_per_night": "350.00",
            })
            pricing_result = json.loads(result.content[0].text)
            print(result.content[0].text)
            assert pricing_result["new_price"] == "350.00", "new price should be 350.00"
            print("  Pricing updated!")

            print("\n=== All MCP tool tests passed! ===")


if __name__ == "__main__":
    asyncio.run(main())
