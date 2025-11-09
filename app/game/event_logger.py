"""
Event logging service for structured game events.

This module provides the EventLogger class which creates and manages
structured game events, replacing the simple string-based logging.
"""

import uuid
from datetime import datetime
from typing import Optional, Any
from app.models.events import (
    GameEvent,
    EventType,
    EventResult,
    TurnoverReason,
    InjuryResult,
    BlockOutcome,
    PassOutcome,
)
from app.models.actions import DiceRoll
from app.models.pitch import Position
from app.models.game_state import GameState


class EventLogger:
    """
    Service for creating and managing structured game events.

    The EventLogger captures all game events with full context,
    dice rolls, and outcomes in a structured format.
    """

    def __init__(self, game_state: GameState):
        """
        Initialize the event logger.

        Args:
            game_state: The game state to log events for
        """
        self.game_state = game_state

    def _create_event(
        self,
        event_type: EventType,
        result: EventResult,
        description: str,
        player_id: Optional[str] = None,
        target_player_id: Optional[str] = None,
        from_position: Optional[Position] = None,
        to_position: Optional[Position] = None,
        dice_rolls: Optional[list[DiceRoll]] = None,
        modifiers: Optional[dict[str, int]] = None,
        target_number: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> GameEvent:
        """
        Create a game event with current context.

        Args:
            event_type: Type of event
            result: Outcome of event
            description: Human-readable description
            player_id: Primary player involved
            target_player_id: Secondary player (for blocks, etc.)
            from_position: Starting position
            to_position: Ending position
            dice_rolls: Dice rolls associated with event
            modifiers: Applied modifiers
            target_number: Target number needed for success
            details: Event-specific details

        Returns:
            Created GameEvent
        """
        # Get player names
        player_name = None
        if player_id and player_id in self.game_state.players:
            player = self.game_state.players[player_id]
            player_name = f"{player.position_name} #{player.number}"

        target_player_name = None
        if target_player_id and target_player_id in self.game_state.players:
            target = self.game_state.players[target_player_id]
            target_player_name = f"{target.position_name} #{target.number}"

        # Create event
        event = GameEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            game_id=self.game_state.game_id,
            half=self.game_state.turn.half if self.game_state.turn else 1,
            turn_number=self.game_state.turn.team_turn if self.game_state.turn else 0,
            active_team_id=self.game_state.turn.active_team_id if self.game_state.turn else "",
            event_type=event_type,
            result=result,
            player_id=player_id,
            player_name=player_name,
            target_player_id=target_player_id,
            target_player_name=target_player_name,
            from_position=from_position,
            to_position=to_position,
            dice_rolls=dice_rolls or [],
            modifiers=modifiers or {},
            target_number=target_number,
            details=details or {},
            description=description,
        )

        return event

    def log_event(self, event: GameEvent) -> None:
        """
        Add an event to the game state.

        Args:
            event: The event to log
        """
        self.game_state.events.append(event)

    # Movement events

    def log_move(
        self,
        player_id: str,
        from_pos: Position,
        to_pos: Position,
        carrying_ball: bool = False,
    ) -> GameEvent:
        """Log a player movement."""
        ball_text = " [carrying ball]" if carrying_ball else ""
        description = f"{self._get_player_name(player_id)} moved from {from_pos} to {to_pos}{ball_text}"

        event = self._create_event(
            event_type=EventType.MOVE,
            result=EventResult.SUCCESS,
            description=description,
            player_id=player_id,
            from_position=from_pos,
            to_position=to_pos,
            details={"carrying_ball": carrying_ball},
        )
        self.log_event(event)
        return event

    def log_dodge(
        self,
        player_id: str,
        position: Position,
        dice_roll: DiceRoll,
        success: bool,
    ) -> GameEvent:
        """Log a dodge attempt."""
        result_text = "✅ SUCCESS" if success else "❌ FAILED"
        description = f"{self._get_player_name(player_id)} dodge at {position}: {result_text}"

        event = self._create_event(
            event_type=EventType.DODGE,
            result=EventResult.SUCCESS if success else EventResult.FAILURE,
            description=description,
            player_id=player_id,
            to_position=position,
            dice_rolls=[dice_roll],
            target_number=dice_roll.target,
            modifiers=dice_roll.modifiers,
        )
        self.log_event(event)
        return event

    def log_rush(
        self,
        player_id: str,
        position: Position,
        dice_roll: DiceRoll,
        success: bool,
    ) -> GameEvent:
        """Log a rush (GFI) attempt."""
        result_text = "✅ SUCCESS" if success else "❌ FAILED"
        description = f"{self._get_player_name(player_id)} rush at {position}: {result_text}"

        event = self._create_event(
            event_type=EventType.RUSH,
            result=EventResult.SUCCESS if success else EventResult.FAILURE,
            description=description,
            player_id=player_id,
            to_position=position,
            dice_rolls=[dice_roll],
            target_number=dice_roll.target,
        )
        self.log_event(event)
        return event

    def log_stand_up(self, player_id: str) -> GameEvent:
        """Log a player standing up."""
        description = f"{self._get_player_name(player_id)} stands up"

        event = self._create_event(
            event_type=EventType.STAND_UP,
            result=EventResult.SUCCESS,
            description=description,
            player_id=player_id,
        )
        self.log_event(event)
        return event

    # Ball handling events

    def log_pickup(
        self,
        player_id: str,
        position: Position,
        dice_roll: Optional[DiceRoll],
        success: bool,
    ) -> GameEvent:
        """Log a pickup attempt."""
        if dice_roll:
            result_text = "✅ SUCCESS" if success else "❌ FAILED"
            description = f"{self._get_player_name(player_id)} pickup at {position}: {result_text}"
            dice_rolls = [dice_roll]
        else:
            description = f"{self._get_player_name(player_id)} picked up ball at {position} (no roll needed)"
            dice_rolls = []

        event = self._create_event(
            event_type=EventType.PICKUP,
            result=EventResult.SUCCESS if success else EventResult.FAILURE,
            description=description,
            player_id=player_id,
            to_position=position,
            dice_rolls=dice_rolls,
            target_number=dice_roll.target if dice_roll else None,
            modifiers=dice_roll.modifiers if dice_roll else {},
        )
        self.log_event(event)
        return event

    def log_drop(
        self,
        player_id: str,
        position: Position,
        reason: str = "fumble",
    ) -> GameEvent:
        """Log a ball drop."""
        description = f"{self._get_player_name(player_id)} dropped the ball at {position} ({reason})"

        event = self._create_event(
            event_type=EventType.DROP,
            result=EventResult.FAILURE,
            description=description,
            player_id=player_id,
            from_position=position,
            details={"reason": reason},
        )
        self.log_event(event)
        return event

    def log_scatter(
        self,
        from_pos: Position,
        to_pos: Position,
        dice_roll: DiceRoll,
    ) -> GameEvent:
        """Log ball scatter."""
        direction = self._get_direction(dice_roll.result)
        description = f"Ball scattered from {from_pos} to {to_pos} (direction: {direction})"

        event = self._create_event(
            event_type=EventType.SCATTER,
            result=EventResult.NEUTRAL,
            description=description,
            from_position=from_pos,
            to_position=to_pos,
            dice_rolls=[dice_roll],
            details={"direction": direction},
        )
        self.log_event(event)
        return event

    def log_pass(
        self,
        player_id: str,
        from_pos: Position,
        to_pos: Position,
        dice_roll: DiceRoll,
        outcome: PassOutcome,
    ) -> GameEvent:
        """Log a pass attempt."""
        outcome_emoji = {
            PassOutcome.ACCURATE: "🎯",
            PassOutcome.INACCURATE: "📍",
            PassOutcome.WILDLY_INACCURATE: "💨",
            PassOutcome.FUMBLE: "🤦",
        }

        description = (
            f"{self._get_player_name(player_id)} pass from {from_pos} to {to_pos}: "
            f"{outcome_emoji.get(outcome, '')} {outcome.value.upper()}"
        )

        result = EventResult.SUCCESS if outcome == PassOutcome.ACCURATE else EventResult.PARTIAL
        if outcome == PassOutcome.FUMBLE:
            result = EventResult.FAILURE

        event = self._create_event(
            event_type=EventType.PASS,
            result=result,
            description=description,
            player_id=player_id,
            from_position=from_pos,
            to_position=to_pos,
            dice_rolls=[dice_roll],
            target_number=dice_roll.target,
            modifiers=dice_roll.modifiers,
            details={"outcome": outcome.value},
        )
        self.log_event(event)
        return event

    def log_catch(
        self,
        player_id: str,
        position: Position,
        dice_roll: Optional[DiceRoll],
        success: bool,
    ) -> GameEvent:
        """Log a catch attempt."""
        if dice_roll:
            result_text = "✅ CAUGHT" if success else "❌ DROPPED"
            description = f"{self._get_player_name(player_id)} catch at {position}: {result_text}"
            dice_rolls = [dice_roll]
        else:
            description = f"{self._get_player_name(player_id)} caught ball at {position} (no roll needed)"
            dice_rolls = []

        event = self._create_event(
            event_type=EventType.CATCH,
            result=EventResult.SUCCESS if success else EventResult.FAILURE,
            description=description,
            player_id=player_id,
            to_position=position,
            dice_rolls=dice_rolls,
            target_number=dice_roll.target if dice_roll else None,
            modifiers=dice_roll.modifiers if dice_roll else {},
        )
        self.log_event(event)
        return event

    def log_handoff(
        self,
        from_player_id: str,
        to_player_id: str,
        position: Position,
    ) -> GameEvent:
        """Log a handoff."""
        description = (
            f"{self._get_player_name(from_player_id)} handed off to "
            f"{self._get_player_name(to_player_id)} at {position}"
        )

        event = self._create_event(
            event_type=EventType.HANDOFF,
            result=EventResult.SUCCESS,
            description=description,
            player_id=from_player_id,
            target_player_id=to_player_id,
            to_position=position,
        )
        self.log_event(event)
        return event

    # Combat events

    def log_block(
        self,
        attacker_id: str,
        defender_id: str,
        dice_roll: DiceRoll,
        outcome: BlockOutcome,
        chosen_result: Optional[BlockOutcome] = None,
    ) -> GameEvent:
        """Log a block."""
        outcome_emoji = {
            BlockOutcome.ATTACKER_DOWN: "😵",
            BlockOutcome.BOTH_DOWN: "💥",
            BlockOutcome.PUSH: "➡️",
            BlockOutcome.DEFENDER_STUMBLES: "😮",
            BlockOutcome.DEFENDER_DOWN: "💫",
        }

        if chosen_result:
            description = (
                f"{self._get_player_name(attacker_id)} blocks {self._get_player_name(defender_id)}: "
                f"{outcome_emoji.get(chosen_result, '')} {chosen_result.value.upper()}"
            )
        else:
            description = (
                f"{self._get_player_name(attacker_id)} blocks {self._get_player_name(defender_id)}: "
                f"{outcome_emoji.get(outcome, '')} {outcome.value.upper()}"
            )

        event = self._create_event(
            event_type=EventType.BLOCK,
            result=EventResult.SUCCESS,
            description=description,
            player_id=attacker_id,
            target_player_id=defender_id,
            dice_rolls=[dice_roll],
            details={
                "outcome": outcome.value,
                "chosen_result": chosen_result.value if chosen_result else None,
            },
        )
        self.log_event(event)
        return event

    def log_knockdown(
        self,
        player_id: str,
        position: Position,
        attacker_id: Optional[str] = None,
    ) -> GameEvent:
        """Log a player being knocked down."""
        if attacker_id:
            description = (
                f"{self._get_player_name(player_id)} knocked down by "
                f"{self._get_player_name(attacker_id)} at {position}"
            )
        else:
            description = f"{self._get_player_name(player_id)} knocked down at {position}"

        event = self._create_event(
            event_type=EventType.KNOCKDOWN,
            result=EventResult.NEUTRAL,
            description=description,
            player_id=player_id,
            target_player_id=attacker_id,
            to_position=position,
        )
        self.log_event(event)
        return event

    def log_armor_check(
        self,
        player_id: str,
        dice_roll: DiceRoll,
        broken: bool,
        armor_value: int,
    ) -> GameEvent:
        """Log an armor check."""
        result_text = "💔 BROKEN" if broken else "🛡️ HOLDS"
        description = (
            f"{self._get_player_name(player_id)} armor check: "
            f"rolled {dice_roll.result} vs AV {armor_value} - {result_text}"
        )

        event = self._create_event(
            event_type=EventType.ARMOR_BREAK,
            result=EventResult.FAILURE if broken else EventResult.SUCCESS,
            description=description,
            player_id=player_id,
            dice_rolls=[dice_roll],
            details={"armor_value": armor_value, "broken": broken},
        )
        self.log_event(event)
        return event

    def log_injury(
        self,
        player_id: str,
        dice_roll: DiceRoll,
        injury: InjuryResult,
    ) -> GameEvent:
        """Log an injury result."""
        injury_emoji = {
            InjuryResult.STUNNED: "😵",
            InjuryResult.KNOCKED_OUT: "🤕",
            InjuryResult.CASUALTY: "🚑",
        }

        description = (
            f"{self._get_player_name(player_id)} injury: "
            f"{injury_emoji.get(injury, '')} {injury.value.upper()}"
        )

        event = self._create_event(
            event_type=EventType.INJURY,
            result=EventResult.NEUTRAL,
            description=description,
            player_id=player_id,
            dice_rolls=[dice_roll],
            details={"injury": injury.value},
        )
        self.log_event(event)
        return event

    def log_foul(
        self,
        attacker_id: str,
        defender_id: str,
    ) -> GameEvent:
        """Log a foul/boot action."""
        description = f"{self._get_player_name(attacker_id)} fouls {self._get_player_name(defender_id)}"

        event = self._create_event(
            event_type=EventType.FOUL,
            result=EventResult.SUCCESS,
            description=description,
            player_id=attacker_id,
            target_player_id=defender_id,
        )
        self.log_event(event)
        return event

    # Game flow events

    def log_kickoff(self, ball_position: Position) -> GameEvent:
        """Log a kickoff."""
        description = f"⚡ Kickoff! Ball lands at {ball_position}"

        event = self._create_event(
            event_type=EventType.KICKOFF,
            result=EventResult.NEUTRAL,
            description=description,
            to_position=ball_position,
        )
        self.log_event(event)
        return event

    def log_touchdown(self, player_id: str, team_id: str, position: Position) -> GameEvent:
        """Log a touchdown."""
        team_name = self._get_team_name(team_id)
        description = f"🏈 TOUCHDOWN! {self._get_player_name(player_id)} scores for {team_name}!"

        event = self._create_event(
            event_type=EventType.TOUCHDOWN,
            result=EventResult.SUCCESS,
            description=description,
            player_id=player_id,
            to_position=position,
            details={"team_id": team_id, "team_name": team_name},
        )
        self.log_event(event)
        return event

    def log_turnover(self, reason: TurnoverReason, player_id: Optional[str] = None) -> GameEvent:
        """Log a turnover."""
        reason_text = {
            TurnoverReason.FAILED_DODGE: "Failed dodge",
            TurnoverReason.FAILED_RUSH: "Failed rush (GFI)",
            TurnoverReason.FAILED_PICKUP: "Failed pickup",
            TurnoverReason.FAILED_CATCH: "Failed catch",
            TurnoverReason.FUMBLED_PASS: "Fumbled pass",
            TurnoverReason.BALL_CARRIER_DOWN: "Ball carrier knocked down",
            TurnoverReason.THROW_TEAMMATE_FAILED: "Throw teammate failed",
        }

        player_text = f" - {self._get_player_name(player_id)}" if player_id else ""
        description = f"🔄 TURNOVER: {reason_text.get(reason, reason.value)}{player_text}"

        event = self._create_event(
            event_type=EventType.TURNOVER,
            result=EventResult.TURNOVER,
            description=description,
            player_id=player_id,
            details={"reason": reason.value},
        )
        self.log_event(event)
        return event

    def log_turn_start(self, team_id: str, turn_number: int, half: int) -> GameEvent:
        """Log the start of a turn."""
        team_name = self._get_team_name(team_id)
        description = f"--- Turn {turn_number} - {team_name} ---"

        event = self._create_event(
            event_type=EventType.TURN_START,
            result=EventResult.NEUTRAL,
            description=description,
            details={"team_id": team_id, "team_name": team_name, "turn": turn_number, "half": half},
        )
        self.log_event(event)
        return event

    def log_turn_end(self, team_id: str) -> GameEvent:
        """Log the end of a turn."""
        team_name = self._get_team_name(team_id)
        description = f"Turn ended for {team_name}"

        event = self._create_event(
            event_type=EventType.TURN_END,
            result=EventResult.NEUTRAL,
            description=description,
            details={"team_id": team_id, "team_name": team_name},
        )
        self.log_event(event)
        return event

    def log_half_start(self, half: int) -> GameEvent:
        """Log the start of a half."""
        description = f"## 📊 Half {half}"

        event = self._create_event(
            event_type=EventType.HALF_START,
            result=EventResult.NEUTRAL,
            description=description,
            details={"half": half},
        )
        self.log_event(event)
        return event

    def log_half_end(self, half: int) -> GameEvent:
        """Log the end of a half."""
        description = f"End of Half {half}"

        event = self._create_event(
            event_type=EventType.HALF_END,
            result=EventResult.NEUTRAL,
            description=description,
            details={"half": half},
        )
        self.log_event(event)
        return event

    def log_game_start(self, team1_name: str, team2_name: str) -> GameEvent:
        """Log the start of a game."""
        description = f"# 🏈 Game Start: {team1_name} vs {team2_name}"

        event = self._create_event(
            event_type=EventType.GAME_START,
            result=EventResult.NEUTRAL,
            description=description,
            details={"team1": team1_name, "team2": team2_name},
        )
        self.log_event(event)
        return event

    def log_game_end(self, winner_id: Optional[str] = None) -> GameEvent:
        """Log the end of a game."""
        if winner_id:
            winner_name = self._get_team_name(winner_id)
            description = f"# 🏆 Game Over - {winner_name} wins!"
        else:
            description = "# Game Over - Draw!"

        event = self._create_event(
            event_type=EventType.GAME_END,
            result=EventResult.NEUTRAL,
            description=description,
            details={"winner_id": winner_id},
        )
        self.log_event(event)
        return event

    # Helper methods

    def _get_player_name(self, player_id: str) -> str:
        """Get a formatted player name."""
        if player_id in self.game_state.players:
            player = self.game_state.players[player_id]
            return f"{player.position_name} #{player.number}"
        return f"Player {player_id}"

    def _get_team_name(self, team_id: str) -> str:
        """Get a team name."""
        if team_id == self.game_state.team1.id:
            return self.game_state.team1.name
        elif team_id == self.game_state.team2.id:
            return self.game_state.team2.name
        return team_id

    def _get_direction(self, dice_result: int) -> str:
        """Get scatter direction name from dice result."""
        directions = {
            1: "N",
            2: "NE",
            3: "E",
            4: "SE",
            5: "S",
            6: "SW",
            7: "W",
            8: "NW",
        }
        return directions.get(dice_result, "?")
