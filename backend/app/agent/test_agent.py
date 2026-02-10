"""Test the VillaOps AI agent — run inside the backend container.

Usage:
    python -m app.agent.test_agent
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)


async def main():
    from app.agent import create_agent

    print("\n=== Creating VillaOps AI Agent ===")
    agent = await create_agent()
    print("Agent created successfully!")

    # Test 1: Simple booking query (should use booking_search)
    print("\n=== Test 1: Search confirmed bookings ===")
    result = await agent.ainvoke({
        "messages": [("user", "Show me all confirmed bookings")]
    })
    print(f"Agent response:\n{result['messages'][-1].content}")

    # Test 2: Guest lookup (should use guest_lookup)
    print("\n=== Test 2: Guest lookup ===")
    result = await agent.ainvoke({
        "messages": [("user", "Find information about guest Sarah Chen")]
    })
    print(f"Agent response:\n{result['messages'][-1].content}")

    # Test 3: Property availability (should use property_manage)
    print("\n=== Test 3: Check property availability ===")
    result = await agent.ainvoke({
        "messages": [("user", "Is Le Ayu Villa Canggu available from June 1 to June 10, 2027?")]
    })
    print(f"Agent response:\n{result['messages'][-1].content}")

    # Test 4: Multi-step reasoning
    print("\n=== Test 4: Multi-step query ===")
    result = await agent.ainvoke({
        "messages": [("user", "What properties have pending bookings? Show me the details.")]
    })
    print(f"Agent response:\n{result['messages'][-1].content}")

    print("\n=== All agent tests completed! ===")


if __name__ == "__main__":
    asyncio.run(main())
