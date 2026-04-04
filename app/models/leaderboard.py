"""Leaderboard data models."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, computed_field


class GameResult(BaseModel):
    """One completed match result written to data/results.jsonl."""
    game_id: str
    played_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    team1_name: str
    team1_model: str = "unknown"
    team1_score: int
    team2_name: str
    team2_model: str = "unknown"
    team2_score: int
    team1_casualties: int = 0
    team2_casualties: int = 0
    team1_turnovers: int = 0
    team2_turnovers: int = 0
    winner_model: Optional[str] = None   # None = draw
    winner_team: Optional[str] = None    # None = draw


class ModelLeaderboardEntry(BaseModel):
    """Aggregated stats for one model across all games."""
    model_id: str
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    goals_for: int = 0
    goals_against: int = 0
    score_diff: int = 0
    casualties_caused: int = 0
    turnovers: int = 0

    @computed_field
    @property
    def win_pct(self) -> float:
        return round(self.wins / self.games, 3) if self.games else 0.0


class TeamLeaderboardEntry(BaseModel):
    """Aggregated stats for one team name across all games."""
    team_name: str
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    goals_for: int = 0
    goals_against: int = 0
    score_diff: int = 0


class LeaderboardResponse(BaseModel):
    """Response shape for GET /leaderboard."""
    total_games: int
    by_model: list[ModelLeaderboardEntry]
    by_team: list[TeamLeaderboardEntry]
