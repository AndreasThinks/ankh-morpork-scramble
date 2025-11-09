"""Game manager - orchestrates game state and rules"""
import logging
import uuid
from typing import Optional
from app.models.game_state import GameState, TurnState
from app.models.team import Team, TEAM_ROSTERS
from app.models.player import Player, PlayerPosition
from app.models.enums import TeamType, GamePhase
from app.models.pitch import Position
from app.models.actions import (
    BudgetStatus,
    PurchaseResult,
    AvailablePosition,
    AvailablePositionsResponse
)
from app.state.action_executor import ActionExecutor
from app.game.event_logger import EventLogger
from app.game.log_saver import LogSaver


logger = logging.getLogger("app.game.manager")


class GameManager:
    """Manages game creation, state transitions, and rule enforcement"""

    def __init__(self, auto_save_logs: bool = True):
        self.games: dict[str, GameState] = {}
        self.executor = ActionExecutor()
        self.log_saver = LogSaver()
        self.auto_save_logs = auto_save_logs
    
    def create_game(self, game_id: Optional[str] = None) -> GameState:
        """Create a new game"""
        if game_id is None:
            game_id = str(uuid.uuid4())
        
        # Create placeholder teams - will be set during join
        # Teams start with no rerolls; they must purchase them during deployment
        team1 = Team(
            id="team1",
            name="Team 1",
            team_type=TeamType.CITY_WATCH
        )

        team2 = Team(
            id="team2",
            name="Team 2",
            team_type=TeamType.UNSEEN_UNIVERSITY
        )
        
        game_state = GameState(
            game_id=game_id,
            phase=GamePhase.SETUP,
            team1=team1,
            team2=team2
        )

        self.games[game_id] = game_state
        logger.info("Created new game %s with default rosters", game_id)
        return game_state
    
    def get_game(self, game_id: str) -> Optional[GameState]:
        """Get game by ID"""
        return self.games.get(game_id)
    
    def setup_team(
        self,
        game_id: str,
        team_id: str,
        team_type: TeamType,
        player_positions: dict[str, str]  # position_key -> count
    ) -> GameState:
        """Set up a team with players"""
        game_state = self.get_game(game_id)
        if not game_state:
            raise ValueError(f"Game {game_id} not found")
        
        team = game_state.get_team_by_id(team_id)
        team.team_type = team_type
        
        roster = TEAM_ROSTERS[team_type]

        # Create players
        player_count = 0
        for position_key, count_str in player_positions.items():
            count = int(count_str)
            if position_key not in roster.positions:
                raise ValueError(f"Invalid position: {position_key}")

            position = roster.positions[position_key]

            for i in range(count):
                player_id = f"{team_id}_player_{player_count}"
                player = Player(
                    id=player_id,
                    team_id=team_id,
                    position=position,
                    skills=list(position.skills),
                    number=player_count + 1,
                )

                game_state.players[player_id] = player
                team.player_ids.append(player_id)
                player_count += 1

        logger.info(
            "Configured team %s (%s) with %d players for game %s",
            team_id,
            team_type.value,
            player_count,
            game_id,
        )
        return game_state
    
    def place_players(
        self,
        game_id: str,
        team_id: str,
        positions: dict[str, Position]
    ) -> GameState:
        """Place players on the pitch during deployment"""
        game_state = self.get_game(game_id)
        if not game_state:
            raise ValueError(f"Game {game_id} not found")
        
        # Validate and place players
        for player_id, position in positions.items():
            player = game_state.get_player(player_id)
            
            if player.team_id != team_id:
                raise ValueError(f"Player {player_id} does not belong to team {team_id}")

            game_state.pitch.player_positions[player_id] = position

        logger.info(
            "Placed %d players for %s in game %s",
            len(positions),
            team_id,
            game_id,
        )
        return game_state
    
    def start_game(self, game_id: str) -> GameState:
        """Start the game"""
        game_state = self.get_game(game_id)
        if not game_state:
            raise ValueError(f"Game {game_id} not found")

        if game_state.phase != GamePhase.SETUP:
            raise ValueError("Game must be in setup phase to start")

        game_state.start_game()

        # Place ball at center of pitch
        ball_pos = Position(x=13, y=7)
        game_state.pitch.place_ball(ball_pos)

        # Log game events
        event_logger = EventLogger(game_state)
        event_logger.log_game_start(game_state.team1.name, game_state.team2.name)
        event_logger.log_half_start(1)
        event_logger.log_turn_start(game_state.team1.id, 1, 1)
        event_logger.log_kickoff(ball_pos)

        logger.info(
            "Game %s started: %s vs %s",
            game_id,
            game_state.team1.name,
            game_state.team2.name,
        )

        return game_state
    
    def end_turn(self, game_id: str) -> GameState:
        """End the current turn and switch to other team"""
        game_state = self.get_game(game_id)
        if not game_state:
            raise ValueError(f"Game {game_id} not found")

        if not game_state.turn:
            raise ValueError("No active turn")

        if game_state.phase == GamePhase.CONCLUDED:
            raise ValueError("Cannot end turn on a concluded game")

        # Log turn end for current team
        event_logger = EventLogger(game_state)
        current_team_id = game_state.turn.active_team_id
        event_logger.log_turn_end(current_team_id)

        game_state.switch_turn()

        # Log turn start for new team (if game not ended)
        if game_state.phase not in [GamePhase.CONCLUDED, GamePhase.INTERMISSION]:
            event_logger = EventLogger(game_state)  # Recreate with updated turn
            event_logger.log_turn_start(
                game_state.turn.active_team_id,
                game_state.turn.team_turn,
                game_state.turn.half
            )

        game_state.add_event(f"Turn ended. Now {game_state.get_active_team().name}'s turn")

        logger.info(
            "Game %s turn advanced to team %s (turn %s)",
            game_id,
            game_state.turn.active_team_id,
            game_state.turn.team_turn,
        )

        # Auto-save logs after each turn
        if self.auto_save_logs:
            self._save_game_logs(game_state)

        return game_state
    
    def get_budget_status(self, game_id: str, team_id: str) -> BudgetStatus:
        """Get budget status for a team"""
        game_state = self.get_game(game_id)
        if not game_state:
            raise ValueError(f"Game {game_id} not found")

        team = game_state.get_team_by_id(team_id)

        return BudgetStatus(
            initial=team.budget_initial,
            spent=team.budget_spent,
            remaining=team.budget_remaining,
            purchases=list(team.purchase_history)
        )

    def get_available_positions(
        self,
        game_id: str,
        team_id: str
    ) -> AvailablePositionsResponse:
        """Get available positions for purchase"""
        game_state = self.get_game(game_id)
        if not game_state:
            raise ValueError(f"Game {game_id} not found")

        team = game_state.get_team_by_id(team_id)
        roster = TEAM_ROSTERS[team.team_type]

        # Count existing players by position
        position_counts: dict[str, int] = {}
        for player_id in team.player_ids:
            player = game_state.get_player(player_id)
            position_key = self._get_position_key(player.position, roster)
            position_counts[position_key] = position_counts.get(position_key, 0) + 1

        # Build available positions list
        available_positions = []
        for position_key, position in roster.positions.items():
            # Determine quantity limit from rules
            quantity_limit = self._get_position_limit(position_key, team.team_type)
            quantity_owned = position_counts.get(position_key, 0)

            available_positions.append(AvailablePosition(
                position_key=position_key,
                role=position.role,
                cost=position.cost,
                quantity_limit=quantity_limit,
                quantity_owned=quantity_owned,
                can_afford=team.can_afford(position.cost),
                stats={
                    "ma": position.ma,
                    "st": position.st,
                    "ag": position.ag,
                    "pa": position.pa,
                    "av": position.av,
                    "skills": [s.value for s in position.skills]
                }
            ))

        budget_status = self.get_budget_status(game_id, team_id)

        return AvailablePositionsResponse(
            team_id=team_id,
            team_type=team.team_type.value,
            budget_status=budget_status,
            positions=available_positions,
            reroll_cost=roster.reroll_cost,
            rerolls_owned=team.rerolls_total,
            rerolls_max=roster.max_rerolls,
            can_afford_reroll=team.can_afford(roster.reroll_cost)
        )

    def _get_position_key(self, position: PlayerPosition, roster) -> str:
        """Find the position key for a player's position"""
        for key, pos in roster.positions.items():
            if pos.role == position.role:
                return key
        return "unknown"

    def _get_position_limit(self, position_key: str, team_type: TeamType) -> int:
        """Get the quantity limit for a position from roster definition"""
        roster = TEAM_ROSTERS.get(team_type)
        if not roster:
            return 0
        position = roster.positions.get(position_key)
        if not position:
            return 0
        return position.max_quantity

    def buy_player(
        self,
        game_id: str,
        team_id: str,
        position_key: str
    ) -> PurchaseResult:
        """Buy a player for a team"""
        game_state = self.get_game(game_id)
        if not game_state:
            raise ValueError(f"Game {game_id} not found")

        if game_state.phase != GamePhase.SETUP:
            raise ValueError(
                "Can only purchase players during deployment/setup phase"
            )

        team = game_state.get_team_by_id(team_id)
        roster = TEAM_ROSTERS[team.team_type]

        # Validate position exists
        if position_key not in roster.positions:
            raise ValueError(
                f"Invalid position '{position_key}' for {team.team_type.value}"
            )

        position = roster.positions[position_key]

        # Check quantity limit
        position_counts: dict[str, int] = {}
        for player_id in team.player_ids:
            player = game_state.get_player(player_id)
            key = self._get_position_key(player.position, roster)
            position_counts[key] = position_counts.get(key, 0) + 1

        current_count = position_counts.get(position_key, 0)
        max_allowed = self._get_position_limit(position_key, team.team_type)

        if current_count >= max_allowed:
            raise ValueError(
                f"Cannot exceed limit of {max_allowed} {position.role}(s)"
            )

        # Purchase the player
        team.purchase_player(position.role, position.cost)

        # Create the player
        player_count = len(team.player_ids)
        player_id = f"{team_id}_player_{player_count}"
        player = Player(
            id=player_id,
            team_id=team_id,
            position=position,
            skills=list(position.skills),
            number=player_count + 1,
        )

        game_state.players[player_id] = player
        team.player_ids.append(player_id)

        logger.info(
            "Team %s purchased %s for %d gold (game %s)",
            team_id,
            position.role,
            position.cost,
            game_id
        )

        budget_status = self.get_budget_status(game_id, team_id)

        return PurchaseResult(
            success=True,
            item_purchased=f"{position.role} (Player ID: {player_id})",
            cost=position.cost,
            budget_status=budget_status,
            message=f"Successfully purchased {position.role}. {budget_status.remaining}g remaining."
        )

    def buy_reroll(self, game_id: str, team_id: str) -> PurchaseResult:
        """Buy a team reroll"""
        game_state = self.get_game(game_id)
        if not game_state:
            raise ValueError(f"Game {game_id} not found")

        if game_state.phase != GamePhase.SETUP:
            raise ValueError(
                "Can only purchase rerolls during deployment/setup phase"
            )

        team = game_state.get_team_by_id(team_id)
        roster = TEAM_ROSTERS[team.team_type]

        # Purchase the reroll (validates budget and limit)
        team.purchase_reroll(roster.reroll_cost)

        logger.info(
            "Team %s purchased team reroll for %d gold (game %s)",
            team_id,
            roster.reroll_cost,
            game_id
        )

        budget_status = self.get_budget_status(game_id, team_id)

        return PurchaseResult(
            success=True,
            item_purchased=f"Team Reroll (Total: {team.rerolls_total})",
            cost=roster.reroll_cost,
            budget_status=budget_status,
            message=f"Successfully purchased team reroll. {budget_status.remaining}g remaining."
        )

    def check_scoring(self, game_id: str) -> Optional[str]:
        """Check if a team has scored and handle it"""
        game_state = self.get_game(game_id)
        if not game_state:
            return None

        if not game_state.pitch.ball_carrier:
            return None

        carrier = game_state.get_player(game_state.pitch.ball_carrier)
        carrier_pos = game_state.pitch.player_positions.get(carrier.id)

        if not carrier_pos:
            return None

        # Check if in end zone
        # Team 1 scores in x >= 23, Team 2 scores in x <= 2
        scored_team = None

        if carrier.team_id == game_state.team1.id and carrier_pos.x >= 23:
            scored_team = game_state.team1
        elif carrier.team_id == game_state.team2.id and carrier_pos.x <= 2:
            scored_team = game_state.team2

        if scored_team:
            scored_team.add_score()

            # Log touchdown
            event_logger = EventLogger(game_state)
            event_logger.log_touchdown(carrier.id, scored_team.id, carrier_pos)

            game_state.add_event(f"{scored_team.name} scored!")

            # Reset for new drive
            game_state.pitch.ball_carrier = None
            ball_pos = Position(x=13, y=7)
            game_state.pitch.place_ball(ball_pos)

            # Log kickoff
            event_logger.log_kickoff(ball_pos)

            logger.info(
                "Game %s: %s scored (score %s-%s)",
                game_id,
                scored_team.name,
                game_state.team1.score,
                game_state.team2.score,
            )

            # Auto-save logs after touchdown
            if self.auto_save_logs:
                self._save_game_logs(game_state)

            return scored_team.id

        return None

    def _save_game_logs(self, game_state: GameState) -> None:
        """Save game logs to disk (internal helper)."""
        try:
            self.log_saver.save_game_log(game_state)
            logger.debug("Saved logs for game %s", game_state.game_id)
        except Exception as e:
            logger.error("Failed to save logs for game %s: %s", game_state.game_id, e)

    def export_game_log(self, game_id: str, format: str = "markdown") -> Optional[str]:
        """
        Export game log in the specified format.

        Args:
            game_id: Game ID to export
            format: Export format ("markdown" or "json")

        Returns:
            Log content or None if not found
        """
        game_state = self.get_game(game_id)
        if not game_state:
            # Try to load from disk
            if format == "markdown":
                return self.log_saver.get_markdown_log(game_id)
            return None

        # Save current state
        if self.auto_save_logs:
            self._save_game_logs(game_state)

        # Return requested format
        if format == "markdown":
            return self.log_saver.get_markdown_log(game_id)
        elif format == "json":
            import json
            from app.game.log_formatter import MarkdownLogFormatter
            from app.game.statistics import StatisticsAggregator

            events_data = {
                "game_id": game_state.game_id,
                "events": [event.model_dump(mode="json") for event in game_state.events],
            }
            return json.dumps(events_data, indent=2)

        return None
