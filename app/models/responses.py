"""Pydantic response models used by MCP tool handlers."""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.game_state import GameMessage


class JoinGameResponse(BaseModel):
    """Response returned when a team joins a game."""

    success: bool = Field(..., description="Whether the join request succeeded")
    team_id: str = Field(..., description="ID of the team that joined")
    players_ready: bool = Field(..., description="Whether both teams have joined")
    game_started: bool = Field(..., description="Whether the game has already started")
    phase: str = Field(..., description="Current game phase")
    message: str = Field(..., description="Human-readable status message")


class EndTurnResponse(BaseModel):
    """Response returned after ending a turn."""

    success: bool = Field(..., description="Whether the turn end succeeded")
    turn_ended: str = Field(..., description="ID of the team that ended their turn")
    new_active_team: str = Field(..., description="ID of the new active team")
    turn_number: Optional[int] = Field(
        None, description="Turn number for the active team after ending the turn"
    )
    message: str = Field(..., description="Human-readable status message")


class UseRerollResponse(BaseModel):
    """Response returned after using a reroll."""

    success: bool = Field(..., description="Whether the reroll usage succeeded")
    team_id: str = Field(..., description="Team that used the reroll")
    rerolls_remaining: int = Field(..., description="How many rerolls remain")
    message: str = Field(..., description="Human-readable status message")


class HistoryResponse(BaseModel):
    """Response containing a slice of the game history."""

    game_id: str = Field(..., description="Game identifier")
    total_events: int = Field(..., description="Total number of events recorded")
    events: List[str] = Field(default_factory=list, description="Recent event log entries")


class SendMessageResponse(BaseModel):
    """Response returned when sending an in-game message."""

    success: bool = Field(..., description="Whether the message was accepted")
    message: GameMessage = Field(..., description="Message payload that was recorded")


class MessagesResponse(BaseModel):
    """Response containing chat messages for a game."""

    game_id: str = Field(..., description="Game identifier")
    count: int = Field(..., description="Number of messages returned")
    messages: List[GameMessage] = Field(default_factory=list, description="Messages returned")


class PlacePlayersResponse(BaseModel):
    """Response returned after placing players during deployment."""

    success: bool = Field(..., description="Whether player placement succeeded")
    team_id: str = Field(..., description="Team that placed players")
    players_placed: int = Field(..., description="Number of players that were positioned")
    message: str = Field(..., description="Human-readable status message")


class ReadyToPlayResponse(BaseModel):
    """Response returned when a team marks themselves ready to play."""

    success: bool = Field(..., description="Whether the ready state was accepted")
    team_id: str = Field(..., description="Team that is ready to play")
    team_ready: bool = Field(..., description="Whether this team is ready")
    both_teams_ready: bool = Field(..., description="Whether both teams are ready")
    game_started: bool = Field(..., description="Whether the game has now started")
    message: str = Field(..., description="Human-readable status message")


