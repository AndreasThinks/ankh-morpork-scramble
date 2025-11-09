"""
Game orchestration for Scramble agents.

Manages turn-based execution and agent coordination.
Adapted from ai-at-risk's GameRunner with 95% efficiency improvement
by only invoking LLMs when it's actually their turn.
"""

import asyncio
import httpx
from typing import List, Dict, Optional
from datetime import datetime

from .scramble_agent import ScrambleAgent


class GameRunner:
    """
    Orchestrates turn-based agent execution.

    This class manages the main game loop, ensuring agents only
    invoke their LLMs when it's actually their turn (optimized polling).
    """

    def __init__(
        self,
        agents: List[ScrambleAgent],
        poll_interval: float = 2.0,
        max_iterations: int = 1000,
    ):
        """
        Initialize game runner.

        Args:
            agents: List of agents playing the game
            poll_interval: Seconds between game state checks
            max_iterations: Maximum game loop iterations (safety limit)
        """
        self.agents = agents
        self.poll_interval = poll_interval
        self.max_iterations = max_iterations

        # Track game progress
        self.iteration_count = 0
        self.turn_count = 0
        self.game_start_time = None

        # Build agent lookup
        self.agents_by_team = {agent.team_id: agent for agent in agents}

        print(f"[Runner] Initialized with {len(agents)} agents")
        for agent in agents:
            print(f"  - {agent.team_name} ({agent.team_id})")

    async def run_game(self):
        """
        Main game loop.

        Polls game state and invokes agents on their turns until game completes.
        """
        self.game_start_time = datetime.now()
        print(f"\n{'='*70}")
        print(f"🏈 ANKH-MORPORK SCRAMBLE - GAME START")
        print(f"{'='*70}\n")

        game_over = False

        while not game_over and self.iteration_count < self.max_iterations:
            self.iteration_count += 1

            try:
                # Fetch current game state
                game_state = await self._get_game_state()

                if not game_state or "error" in game_state:
                    print(f"[Runner] Error fetching game state: {game_state}")
                    await asyncio.sleep(self.poll_interval)
                    continue

                # Check if game is complete
                phase = game_state.get("phase", "UNKNOWN")
                if phase == "COMPLETE":
                    game_over = True
                    print("\n🏁 Game Complete!")
                    break

                # Get current team
                current_team_id = game_state.get("current_team")
                current_turn = game_state.get("turn") or 0  # Handle None during DEPLOYMENT

                # Track turn changes
                if current_turn and current_turn > self.turn_count:
                    self.turn_count = current_turn
                    print(f"\n{'='*70}")
                    print(f"⏰ Turn {current_turn} - Phase: {phase}")
                    print(f"{'='*70}")

                # Handle different game phases
                if phase in ("DEPLOYMENT", "SETUP"):
                    # During setup, let each agent act if they haven't completed setup
                    for agent in self.agents:
                        try:
                            print(f"\n🎮 {agent.team_name} - Setup phase")
                            turn_start = datetime.now()
                            await agent.play_turn(game_state)
                            turn_duration = (datetime.now() - turn_start).total_seconds()
                            print(f"   ✓ Setup action completed in {turn_duration:.1f}s")
                        except Exception as e:
                            print(f"   ✗ Error during {agent.team_name}'s setup: {e}")
                            import traceback
                            traceback.print_exc()
                    
                    # Wait longer between setup checks
                    await asyncio.sleep(self.poll_interval * 2)
                    continue

                # Find agent whose turn it is (ACTIVE_PLAY phase)
                if current_team_id and current_team_id in self.agents_by_team:
                    agent = self.agents_by_team[current_team_id]

                    print(f"\n🎮 {agent.team_name}'s turn")
                    print(f"   Score: {self._get_score_string(game_state)}")

                    try:
                        # ONLY invoke LLM for the active agent
                        turn_start = datetime.now()
                        await agent.play_turn(game_state)
                        turn_duration = (datetime.now() - turn_start).total_seconds()

                        print(f"   ✓ Turn completed in {turn_duration:.1f}s")

                    except Exception as e:
                        print(f"   ✗ Error during {agent.team_name}'s turn: {e}")
                        import traceback

                        traceback.print_exc()

                else:
                    # No active team or waiting for game to start
                    if self.iteration_count % 10 == 0:  # Log every 10th iteration
                        print(f"[Runner] Waiting... (phase: {phase}, iteration: {self.iteration_count})")

                # Poll interval
                await asyncio.sleep(self.poll_interval)

            except KeyboardInterrupt:
                print("\n\n[Runner] Interrupted by user")
                game_over = True
                break

            except Exception as e:
                print(f"[Runner] Unexpected error: {e}")
                import traceback

                traceback.print_exc()
                await asyncio.sleep(self.poll_interval)

        # Game ended
        await self._print_game_summary(game_state if not game_over else await self._get_game_state())

    async def _get_game_state(self) -> Dict:
        """
        Fetch current game state from server.

        Returns:
            Current game state dict
        """
        if not self.agents:
            return {"error": "No agents configured"}

        # Use first agent's configuration to fetch state
        agent = self.agents[0]

        try:
            # Fetch from main game API (not MCP)
            game_url = agent.mcp_url.replace("/mcp", "")  # Get base URL
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{game_url}/game/{agent.game_id}")
                response.raise_for_status()
                return response.json()

        except Exception as e:
            return {"error": str(e)}

    def _get_score_string(self, game_state: Dict) -> str:
        """Format current score as string"""
        score = game_state.get("score", {})
        scores = []
        for agent in self.agents:
            team_score = score.get(agent.team_id, 0)
            scores.append(f"{agent.team_name}: {team_score}")
        return " | ".join(scores)

    async def _print_game_summary(self, final_state: Optional[Dict]):
        """Print final game summary"""
        game_duration = (
            (datetime.now() - self.game_start_time).total_seconds()
            if self.game_start_time
            else 0
        )

        print(f"\n{'='*70}")
        print(f"🏁 GAME COMPLETE")
        print(f"{'='*70}")

        if final_state and "error" not in final_state:
            # Show final score
            print(f"\n📊 Final Score:")
            score = final_state.get("score", {})
            winner = None
            max_score = -1

            for agent in self.agents:
                team_score = score.get(agent.team_id, 0)
                print(f"   {agent.team_name}: {team_score}")

                if team_score > max_score:
                    max_score = team_score
                    winner = agent.team_name

            if winner:
                print(f"\n🏆 Winner: {winner}!")

        # Game stats
        print(f"\n📈 Game Statistics:")
        print(f"   Duration: {game_duration / 60:.1f} minutes")
        print(f"   Total Turns: {self.turn_count}")
        print(f"   Iterations: {self.iteration_count}")
        print(f"   Avg Turn Time: {game_duration / max(self.turn_count, 1):.1f}s")

        print(f"\n{'='*70}\n")

    async def join_all_agents(self):
        """Have all agents join the game"""
        print("[Runner] Agents joining game...")

        join_tasks = [agent.join_game() for agent in self.agents]
        results = await asyncio.gather(*join_tasks, return_exceptions=True)

        for agent, result in zip(self.agents, results):
            if isinstance(result, Exception):
                print(f"   ✗ {agent.team_name} failed to join: {result}")
            else:
                print(f"   ✓ {agent.team_name} joined successfully")

        print()


class TournamentRunner:
    """
    Run multiple games in sequence (tournament mode).

    Useful for testing and benchmarking agents.
    """

    def __init__(self, agents: List[ScrambleAgent], num_games: int = 1):
        """
        Initialize tournament runner.

        Args:
            agents: List of agents
            num_games: Number of games to play
        """
        self.agents = agents
        self.num_games = num_games
        self.results = []

    async def run_tournament(self):
        """Run multiple games"""
        print(f"\n🏆 TOURNAMENT MODE - {self.num_games} games\n")

        for game_num in range(1, self.num_games + 1):
            print(f"\n{'#'*70}")
            print(f"# GAME {game_num} of {self.num_games}")
            print(f"{'#'*70}\n")

            # Update game IDs for new game
            game_id = f"tournament_game_{game_num}"
            for agent in self.agents:
                agent.game_id = game_id

            # Run game
            runner = GameRunner(self.agents)
            await runner.join_all_agents()
            await runner.run_game()

            # Track results
            # TODO: Extract and store game results

        self._print_tournament_summary()

    def _print_tournament_summary(self):
        """Print tournament results"""
        print(f"\n{'='*70}")
        print(f"🏆 TOURNAMENT COMPLETE")
        print(f"{'='*70}")
        print(f"Games Played: {self.num_games}")
        print("(Detailed results tracking coming soon)")
        print(f"{'='*70}\n")
