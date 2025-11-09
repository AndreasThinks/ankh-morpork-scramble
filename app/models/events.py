"""
Event models for structured game logging.

This module defines structured event types for comprehensive game logging,
replacing the simple string-based event_log with rich, queryable event data.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field

from app.models.actions import DiceRoll
from app.models.pitch import Position


class EventType(str, Enum):
    """Types of game events."""
    # Movement
    MOVE = "move"
    DODGE = "dodge"
    RUSH = "rush"
    STAND_UP = "stand_up"

    # Ball handling
    PICKUP = "pickup"
    DROP = "drop"
    PASS = "pass"
    CATCH = "catch"
    SCATTER = "scatter"
    HANDOFF = "handoff"

    # Combat
    BLOCK = "block"
    KNOCKDOWN = "knockdown"
    ARMOR_BREAK = "armor_break"
    INJURY = "injury"
    CASUALTY = "casualty"
    FOUL = "foul"

    # Game flow
    KICKOFF = "kickoff"
    TOUCHDOWN = "touchdown"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    HALF_START = "half_start"
    HALF_END = "half_end"
    GAME_START = "game_start"
    GAME_END = "game_end"

    # Special
    TURNOVER = "turnover"
    REROLL = "reroll"


class EventResult(str, Enum):
    """Outcome of an event."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TURNOVER = "turnover"
    NEUTRAL = "neutral"  # For informational events like scatter


class GameEvent(BaseModel):
    """
    Structured game event with full context.

    Captures all information about a game event including timing,
    participants, dice rolls, and outcomes.
    """
    # Identity
    event_id: str = Field(description="Unique event identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="When event occurred")

    # Context
    game_id: str = Field(description="Game this event belongs to")
    half: int = Field(description="Which half (1 or 2)")
    turn_number: int = Field(description="Turn number within half (0-8)")
    active_team_id: str = Field(description="Team whose turn it is")

    # Event details
    event_type: EventType = Field(description="Type of event")
    result: EventResult = Field(description="Outcome of event")

    # Participants
    player_id: Optional[str] = Field(None, description="Primary player involved")
    player_name: Optional[str] = Field(None, description="Player name for display")
    target_player_id: Optional[str] = Field(None, description="Secondary player (e.g., block target)")
    target_player_name: Optional[str] = Field(None, description="Target player name")

    # Location
    from_position: Optional[Position] = Field(None, description="Starting position")
    to_position: Optional[Position] = Field(None, description="Ending position")

    # Dice & mechanics
    dice_rolls: list[DiceRoll] = Field(default_factory=list, description="All dice rolls for this event")
    modifiers: dict[str, int] = Field(default_factory=dict, description="Applied modifiers")
    target_number: Optional[int] = Field(None, description="Target number needed")

    # Event-specific data
    details: dict[str, Any] = Field(default_factory=dict, description="Event-specific details")

    # Narrative
    description: str = Field(description="Human-readable description")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TurnoverReason(str, Enum):
    """Specific reasons for turnovers."""
    FAILED_DODGE = "failed_dodge"
    FAILED_RUSH = "failed_rush"
    FAILED_PICKUP = "failed_pickup"
    FAILED_CATCH = "failed_catch"
    FUMBLED_PASS = "fumbled_pass"
    BALL_CARRIER_DOWN = "ball_carrier_down"
    THROW_TEAMMATE_FAILED = "throw_teammate_failed"


class InjuryResult(str, Enum):
    """Injury outcomes."""
    NONE = "none"
    STUNNED = "stunned"
    KNOCKED_OUT = "ko"
    CASUALTY = "casualty"


class BlockOutcome(str, Enum):
    """Block dice results."""
    ATTACKER_DOWN = "attacker_down"
    BOTH_DOWN = "both_down"
    PUSH = "push"
    DEFENDER_STUMBLES = "defender_stumbles"
    DEFENDER_DOWN = "defender_down"


class PassOutcome(str, Enum):
    """Pass accuracy results."""
    ACCURATE = "accurate"
    INACCURATE = "inaccurate"
    WILDLY_INACCURATE = "wildly_inaccurate"
    FUMBLE = "fumble"


class GameStatistics(BaseModel):
    """
    Aggregated game statistics.

    Tracks cumulative stats for teams and players throughout the game.
    """
    game_id: str

    # Team stats
    team_stats: dict[str, "TeamStats"] = Field(default_factory=dict)

    # Player stats
    player_stats: dict[str, "PlayerStats"] = Field(default_factory=dict)

    # Dice statistics
    total_dice_rolls: int = 0
    dice_by_type: dict[str, int] = Field(default_factory=dict)
    success_by_type: dict[str, int] = Field(default_factory=dict)

    # Turnover analysis
    turnovers_by_reason: dict[str, int] = Field(default_factory=dict)


class TeamStats(BaseModel):
    """Statistics for a single team."""
    team_id: str
    team_name: str

    # Offensive stats
    touchdowns: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    pickups_attempted: int = 0
    pickups_succeeded: int = 0
    handoffs: int = 0

    # Defensive stats
    blocks_thrown: int = 0
    knockdowns: int = 0
    armor_breaks: int = 0
    casualties_caused: int = 0
    interceptions: int = 0

    # Negative stats
    turnovers: int = 0
    fumbles: int = 0
    failed_dodges: int = 0
    players_injured: int = 0
    players_ko: int = 0
    players_casualties: int = 0

    # Possession
    turns_with_ball: int = 0


class PlayerStats(BaseModel):
    """Statistics for a single player."""
    player_id: str
    player_name: str
    team_id: str

    # Actions
    moves: int = 0
    dodges_attempted: int = 0
    dodges_succeeded: int = 0
    blocks_thrown: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    catches_attempted: int = 0
    catches_succeeded: int = 0
    pickups_attempted: int = 0
    pickups_succeeded: int = 0

    # Combat results
    knockdowns_caused: int = 0
    casualties_caused: int = 0
    times_knocked_down: int = 0
    times_injured: int = 0

    # Scoring
    touchdowns: int = 0

    # Special
    turnovers_caused: int = 0
    mvp_votes: int = 0
