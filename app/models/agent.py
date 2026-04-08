"""Agent identity models for versus mode."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class AgentIdentity(BaseModel):
    """Persistent agent record stored in SQLite."""
    agent_id: str
    name: str
    model: Optional[str] = None
    token_hash: str  # bcrypt hash — never returned to clients
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentContext(BaseModel):
    """Resolved agent context injected by auth dependency."""
    agent_id: str
    name: str
    team_id: Optional[str] = None  # set once matched to a game


class JoinRequest(BaseModel):
    """POST /versus/join body."""
    # New agent: provide name (and optional model)
    name: Optional[str] = None
    model: Optional[str] = None
    # Returning agent: provide token
    token: Optional[str] = None


class JoinResponse(BaseModel):
    """Response from POST /versus/join."""
    agent_id: str
    name: str
    status: str  # "waiting", "matched", or "playing"
    token: Optional[str] = None  # ONLY on first registration, never again
    game_id: Optional[str] = None
    team_id: Optional[str] = None
    opponent_name: Optional[str] = None
    scheduled_start: Optional[datetime] = None  # ISO UTC — ack deadline when matched
    poll_interval_seconds: Optional[int] = None  # hint: how often to poll


class LobbyStatusResponse(BaseModel):
    """Response from GET /versus/lobby/status."""
    agent_id: str
    name: str
    status: str  # "waiting", "matched", "playing", "not_in_lobby"
    game_id: Optional[str] = None
    team_id: Optional[str] = None
    opponent_name: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    poll_interval_seconds: Optional[int] = None
