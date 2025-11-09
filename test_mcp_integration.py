#!/usr/bin/env python3
"""
Integration test for MCP client connection.

This script tests that agents can connect to the MCP server and load tools.
Run with: uv run python test_mcp_integration.py

Prerequisites:
1. Game server must be running: uv run uvicorn app.main:app --reload
2. ANTHROPIC_API_KEY must be set
"""

import asyncio
import os
import sys

from app.agents.langgraph import ScrambleAgent


async def test_mcp_connection():
    """Test MCP client connection and tool loading"""

    print("=" * 70)
    print("MCP CLIENT INTEGRATION TEST")
    print("=" * 70)
    print()

    # Check API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENROUTER_API_KEY not set")
        print("Set it with: export OPENROUTER_API_KEY=your_key")
        return False

    print("✓ API key found")
    print()

    # Test configuration
    game_id = "test_mcp_game"
    mcp_url = "http://localhost:8000/mcp"
    model = os.getenv("OPENROUTER_MODEL", "openrouter/auto")

    print(f"Configuration:")
    print(f"  Game ID: {game_id}")
    print(f"  MCP URL: {mcp_url}")
    print(f"  Model: {model}")
    print()

    try:
        # Create agent
        print("1. Creating agent...")
        agent = ScrambleAgent(
            game_id=game_id,
            team_id="team1",
            team_name="Test Team",
            mcp_url=mcp_url,
            model=model,
            api_key=api_key,
        )
        print("   ✓ Agent created")
        print()

        # Initialize (connect to MCP server)
        print("2. Initializing agent (connecting to MCP server)...")
        await agent.initialize()
        print(f"   ✓ Connected successfully")
        print(f"   ✓ Loaded {len(agent.tools)} MCP tools")
        print()

        # List tools
        print("3. Available MCP tools:")
        for i, tool in enumerate(agent.tools, 1):
            tool_name = getattr(tool, "name", str(tool))
            print(f"   {i:2d}. {tool_name}")
        print()

        # Verify agent is ready
        print("4. Verifying agent is ready...")
        if agent.agent is None:
            print("   ❌ ERROR: Agent not properly initialized")
            return False
        print("   ✓ Agent is ready to play")
        print()

        print("=" * 70)
        print("✓ ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("The MCP client integration is working correctly.")
        print()
        print("Next steps:")
        print("1. Run a full match: python -m app.agents.langgraph.launch")
        print("2. Watch the game at: http://localhost:8000/ui")
        print()

        return True

    except ConnectionError as e:
        print(f"\n❌ CONNECTION ERROR: {e}")
        print()
        print("Is the game server running?")
        print("Start it with: uv run uvicorn app.main:app --reload")
        return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print()
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run the integration test"""
    success = asyncio.run(test_mcp_connection())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
