"""Pydantic response models for MCP tools"""
from pydantic import BaseModel, Field
from typing import Optional


class JoinGameResponse(BaseModel):
    """Response model for join_game tool"""
    success: bool = Field(description="Whether the join operation succeeded")
    team_id: str = Field(description="The team ID that joined")
    players_ready: bool = Field(description="Whether both teams have players ready")
    game_started: bool = Field(description="Whether the game has started")
    phase: str = Field(description="Current game phase")
    message: str = Field(description="Human-readable status message")


class EndTurnResponse(BaseModel):
    """Response model for end_turn tool"""
    success: bool = Field(description="Whether the turn was ended successfully")
    turn_ended: str = Field(description="Team ID whose turn was ended")
    new_active_team: str = Field(description="Team ID that is now active")
    turn_number: Optional[int] = Field(description="Current turn number")
    message: str = Field(description="Human-readable status message")


class UseRerollResponse(BaseModel):
    """Response model for use_reroll tool"""
    success: bool = Field(description="Whether the reroll was used successfully")
    team_id: str = Field(description="Team ID that used the reroll")
    rerolls_remaining: int = Field(description="Number of rerolls remaining")
    message: str = Field(description="Human-readable status message")


class GameHistoryResponse(BaseModel):
    """Response model for get_history tool"""
    game_id: str = Field(description="Game identifier")
    total_events: int = Field(description="Total number of events in the log")
    events: list[str] = Field(description="List of event messages")


class SendMessageResponse(BaseModel):
    """Response model for send_message tool"""
    success: bool = Field(description="Whether the message was sent successfully")
    message: dict = Field(description="The message that was sent")


class GetMessagesResponse(BaseModel):
    """Response model for get_messages tool"""
    game_id: str = Field(description="Game identifier")
    count: int = Field(description="Number of messages returned")
    messages: list = Field(description="List of message objects")


class PlacePlayersResponse(BaseModel):
    """Response model for place_players tool"""
    success: bool = Field(description="Whether players were placed successfully")
    team_id: str = Field(description="Team ID that placed players")
    players_placed: int = Field(description="Number of players placed")
    message: str = Field(description="Human-readable status message")


class ReadyToPlayResponse(BaseModel):
    """Response model for ready_to_play tool"""
    success: bool = Field(description="Whether team marked ready successfully")
    team_id: str = Field(description="Team ID that is ready")
    team_ready: bool = Field(description="Whether this team is ready")
    both_teams_ready: bool = Field(description="Whether both teams are ready")
    game_started: bool = Field(description="Whether the game has started")
    message: str = Field(description="Human-readable status message")


class HealthCheckResponse(BaseModel):
    """Response model for health check resource"""
    status: str = Field(description="Health status (healthy/unhealthy)")
    active_games: int = Field(description="Number of active games")
    total_games: int = Field(description="Total number of games")
    version: str = Field(description="MCP server version")
