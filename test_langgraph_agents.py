#!/usr/bin/env python3
"""
Test script for LangGraph agents.

This script verifies the implementation without requiring the full game server.
"""

import asyncio
from app.agents.langgraph.state import ScrambleAgentState
from app.agents.langgraph.narrator import ScrambleNarrator, GameStateChange
from app.agents.langgraph.memory_policy import ScrambleMemoryPolicy
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


async def test_narrator():
    """Test the game state narrator"""
    print("=" * 70)
    print("TEST 1: Game State Narrator")
    print("=" * 70)

    narrator = ScrambleNarrator()

    # Initial state
    state1 = {
        "phase": "PLAYING",
        "turn": 1,
        "teams": {
            "team1": {
                "name": "City Watch",
                "players": {
                    "p1": {
                        "name": "Constable #1",
                        "position": {"x": 5, "y": 7},
                        "status": "ACTIVE",
                    },
                    "p2": {
                        "name": "Constable #2",
                        "position": {"x": 6, "y": 7},
                        "status": "ACTIVE",
                    },
                },
                "rerolls": 3,
            },
            "team2": {
                "name": "Wizards",
                "players": {
                    "p3": {
                        "name": "Wizard #1",
                        "position": {"x": 10, "y": 7},
                        "status": "ACTIVE",
                    }
                },
            },
        },
        "ball": {"carrier_id": None, "position": {"x": 13, "y": 7}},
        "score": {"team1": 0, "team2": 0},
    }

    # Generate first turn update
    narrative1 = narrator.generate_turn_update("test_game", "team1", state1)
    print("\nTurn 1 Narrative:")
    print(narrative1)

    # Second state with changes
    state2 = {
        "phase": "PLAYING",
        "turn": 2,
        "teams": {
            "team1": {
                "name": "City Watch",
                "players": {
                    "p1": {
                        "name": "Constable #1",
                        "position": {"x": 6, "y": 8},  # MOVED
                        "status": "ACTIVE",
                    },
                    "p2": {
                        "name": "Constable #2",
                        "position": {"x": 6, "y": 7},
                        "status": "KO",  # STATUS CHANGED
                    },
                },
                "rerolls": 2,  # USED REROLL
            },
            "team2": {
                "name": "Wizards",
                "players": {
                    "p3": {
                        "name": "Wizard #1",
                        "position": {"x": 10, "y": 7},
                        "status": "ACTIVE",
                    }
                },
            },
        },
        "ball": {"carrier_id": "p1", "position": None},  # BALL PICKED UP
        "score": {"team1": 0, "team2": 0},
    }

    narrative2 = narrator.generate_turn_update("test_game", "team1", state2)
    print("\nTurn 2 Narrative (with changes):")
    print(narrative2)

    # Third state with score
    state3 = {
        "phase": "PLAYING",
        "turn": 3,
        "teams": state2["teams"],
        "ball": {"carrier_id": None, "position": {"x": 1, "y": 7}},
        "score": {"team1": 1, "team2": 0},  # SCORED!
    }

    narrative3 = narrator.generate_turn_update("test_game", "team1", state3)
    print("\nTurn 3 Narrative (score!):")
    print(narrative3)

    print("\n✓ Narrator test passed!\n")


async def test_memory_policy():
    """Test the memory policy"""
    print("=" * 70)
    print("TEST 2: Memory Policy")
    print("=" * 70)

    policy = ScrambleMemoryPolicy(max_tokens=1000, keep_recent_exchanges=2)

    # Create a lot of messages
    messages = [
        SystemMessage(content="You are a game-playing agent."),
        HumanMessage(content="Turn 1: The game has started."),
        AIMessage(content="I will move player 1 forward."),
        HumanMessage(content="Turn 2: Player moved successfully."),
        AIMessage(content="I will block the opponent."),
        HumanMessage(content="Turn 3: Block successful."),
        AIMessage(content="I will pass the ball."),
        HumanMessage(content="Turn 4: Pass intercepted! TURNOVER"),
        AIMessage(content="Oh no! I'll try to recover."),
        HumanMessage(content="Turn 5: Opponent scored! TOUCHDOWN"),
        AIMessage(content="I need a new strategy."),
    ]

    print(f"\nOriginal message count: {len(messages)}")

    # Check status
    status = policy.get_compression_status(messages)
    print(f"Token usage: {status['current_tokens']} / {status['max_tokens']}")
    print(f"Needs trimming: {status['needs_trimming']}")

    # Trim if needed
    if status["needs_trimming"]:
        trimmed = policy.trim_conversation(messages)
        print(f"\nTrimmed message count: {len(trimmed)}")
        print(f"Reduction: {len(messages) - len(trimmed)} messages")

        # Check that system message and critical messages are kept
        has_system = any(isinstance(m, SystemMessage) for m in trimmed)
        has_critical = any("TOUCHDOWN" in str(m.content) for m in trimmed)

        print(f"System message preserved: {has_system}")
        print(f"Critical message preserved: {has_critical}")

        assert has_system, "System message should be preserved"
        assert has_critical, "Critical messages should be preserved"

    print("\n✓ Memory policy test passed!\n")


async def test_state_structure():
    """Test the state structure"""
    print("=" * 70)
    print("TEST 3: Agent State Structure")
    print("=" * 70)

    # Create a state
    state: ScrambleAgentState = {
        "messages": [SystemMessage(content="Test")],
        "game_id": "test_game",
        "team_id": "team1",
        "current_turn": 1,
        "current_phase": "PLAYING",
        "context": {"test": "value"},
        "last_action": {"action": "MOVE"},
        "game_state_snapshot": {},
        "ball_carrier_id": "p1",
        "team_score": 0,
        "opponent_score": 0,
        "rerolls_remaining": 3,
        "players_on_pitch": 11,
        "total_tokens": 500,
        "needs_compression": False,
    }

    print(f"\nState structure:")
    print(f"  Game: {state['game_id']}")
    print(f"  Team: {state['team_id']}")
    print(f"  Turn: {state['current_turn']}")
    print(f"  Phase: {state['current_phase']}")
    print(f"  Score: {state['team_score']} - {state['opponent_score']}")
    print(f"  Ball carrier: {state['ball_carrier_id']}")
    print(f"  Players on pitch: {state['players_on_pitch']}")
    print(f"  Rerolls: {state['rerolls_remaining']}")
    print(f"  Messages: {len(state['messages'])}")

    print("\n✓ State structure test passed!\n")


async def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("LANGGRAPH AGENT IMPLEMENTATION TESTS")
    print("=" * 70 + "\n")

    try:
        await test_state_structure()
        await test_narrator()
        await test_memory_policy()

        print("=" * 70)
        print("✓ ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. Start the game server: uv run uvicorn app.main:app --reload")
        print("2. Run agents: python -m app.agents.langgraph.launch")
        print()

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
