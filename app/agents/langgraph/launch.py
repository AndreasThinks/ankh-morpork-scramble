"""
Launch script for LangGraph-based Scramble agents.

This is the main entry point for starting agent matches.
"""

import asyncio
import os
import sys
from typing import Optional

from .scramble_agent import ScrambleAgent
from .game_runner import GameRunner, TournamentRunner


async def launch_match(
    game_id: str = "demo_game",
    mcp_url: str = "http://localhost:8000/mcp",
    model: str = "claude-sonnet-4-5-20250929",
    api_key: Optional[str] = None,
    poll_interval: float = 2.0,
    tournament_mode: bool = False,
    num_games: int = 1,
):
    """
    Launch a two-agent match.

    Args:
        game_id: Game identifier
        mcp_url: MCP server URL
        model: LLM model to use
        api_key: Anthropic API key (or use ANTHROPIC_API_KEY env var)
        poll_interval: Seconds between game state polls
        tournament_mode: Run multiple games in sequence
        num_games: Number of games (if tournament_mode=True)
    """
    # Get API key
    if not api_key:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: ANTHROPIC_API_KEY not set!")
            print("Set it via environment variable or pass as argument")
            sys.exit(1)

    print(f"🎮 Launching Ankh-Morpork Scramble Match")
    print(f"   Game ID: {game_id}")
    print(f"   MCP URL: {mcp_url}")
    print(f"   Model: {model}")
    print(f"   Poll Interval: {poll_interval}s")
    print()

    # Create agents
    print("Creating agents...")

    agent1 = ScrambleAgent(
        game_id=game_id,
        team_id="team1",
        team_name="City Watch Constables",
        mcp_url=mcp_url,
        model=model,
        api_key=api_key,
    )

    agent2 = ScrambleAgent(
        game_id=game_id,
        team_id="team2",
        team_name="Unseen University Wizards",
        mcp_url=mcp_url,
        model=model,
        api_key=api_key,
    )

    agents = [agent1, agent2]

    # Initialize agents (connect to MCP server and load tools)
    print("\n🔌 Initializing agents (connecting to MCP server)...")
    init_tasks = [agent.initialize() for agent in agents]
    init_results = await asyncio.gather(*init_tasks, return_exceptions=True)

    for agent, result in zip(agents, init_results):
        if isinstance(result, Exception):
            print(f"   ✗ {agent.team_name} initialization failed: {result}")
            sys.exit(1)
        else:
            print(f"   ✓ {agent.team_name} initialized with {len(agent.tools)} tools")

    # Join game
    print("\n🔗 Agents joining game...")
    join_tasks = [agent.join_game() for agent in agents]
    join_results = await asyncio.gather(*join_tasks, return_exceptions=True)

    for agent, result in zip(agents, join_results):
        if isinstance(result, Exception):
            print(f"   ✗ {agent.team_name} failed to join: {result}")
        elif "error" in result:
            print(f"   ✗ {agent.team_name} failed to join: {result['error']}")
        else:
            print(f"   ✓ {agent.team_name} joined successfully")

    print()

    # Run game(s)
    if tournament_mode:
        tournament = TournamentRunner(agents, num_games=num_games)
        await tournament.run_tournament()
    else:
        runner = GameRunner(agents, poll_interval=poll_interval)
        await runner.run_game()


async def launch_single_agent(
    game_id: str,
    team_id: str,
    team_name: str,
    mcp_url: str = "http://localhost:8000/mcp",
    model: str = "claude-sonnet-4-5-20250929",
    api_key: Optional[str] = None,
):
    """
    Launch a single agent (for testing or manual opponent).

    Args:
        game_id: Game identifier
        team_id: Team identifier (e.g., "team1")
        team_name: Human-readable team name
        mcp_url: MCP server URL
        model: LLM model to use
        api_key: Anthropic API key
    """
    if not api_key:
        api_key = os.getenv("ANTHROPIC_API_KEY")

    print(f"🎮 Launching single agent: {team_name}")

    agent = ScrambleAgent(
        game_id=game_id,
        team_id=team_id,
        team_name=team_name,
        mcp_url=mcp_url,
        model=model,
        api_key=api_key,
    )

    # Initialize agent
    print("🔌 Initializing agent...")
    await agent.initialize()
    print(f"✓ Loaded {len(agent.tools)} MCP tools")

    # Join game
    await agent.join_game()

    # Run with single agent
    runner = GameRunner([agent])
    await runner.run_game()


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Launch Ankh-Morpork Scramble AI agents"
    )

    parser.add_argument(
        "--game-id",
        type=str,
        default="demo_game",
        help="Game identifier (default: demo_game)",
    )

    parser.add_argument(
        "--mcp-url",
        type=str,
        default="http://localhost:8000/mcp",
        help="MCP server URL (default: http://localhost:8000/mcp)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="claude-sonnet-4-5-20250929",
        help="LLM model to use (default: claude-sonnet-4-5-20250929)",
    )

    parser.add_argument(
        "--api-key",
        type=str,
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)",
    )

    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between game state polls (default: 2.0)",
    )

    parser.add_argument(
        "--tournament",
        action="store_true",
        help="Run tournament mode (multiple games)",
    )

    parser.add_argument(
        "--num-games",
        type=int,
        default=1,
        help="Number of games in tournament mode (default: 1)",
    )

    parser.add_argument(
        "--single-agent",
        action="store_true",
        help="Run single agent mode (for testing)",
    )

    parser.add_argument(
        "--team-id",
        type=str,
        default="team1",
        help="Team ID for single agent mode (default: team1)",
    )

    parser.add_argument(
        "--team-name",
        type=str,
        default="Test Team",
        help="Team name for single agent mode (default: Test Team)",
    )

    args = parser.parse_args()

    # Run appropriate mode
    if args.single_agent:
        asyncio.run(
            launch_single_agent(
                game_id=args.game_id,
                team_id=args.team_id,
                team_name=args.team_name,
                mcp_url=args.mcp_url,
                model=args.model,
                api_key=args.api_key,
            )
        )
    else:
        asyncio.run(
            launch_match(
                game_id=args.game_id,
                mcp_url=args.mcp_url,
                model=args.model,
                api_key=args.api_key,
                poll_interval=args.poll_interval,
                tournament_mode=args.tournament,
                num_games=args.num_games,
            )
        )


if __name__ == "__main__":
    main()
