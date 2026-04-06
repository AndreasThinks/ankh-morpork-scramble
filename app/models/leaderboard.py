"""Leaderboard data models."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, computed_field


class GameResult(BaseModel):
    """One completed match result written to data/results.jsonl."""
    game_id: str
    played_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Teams and models
    team1_name: str
    team1_model: str = "unknown"
    team1_score: int
    team2_name: str
    team2_model: str = "unknown"
    team2_score: int
    winner_model: Optional[str] = None   # None = draw
    winner_team: Optional[str] = None    # None = draw

    # Combat stats
    team1_casualties: int = 0
    team2_casualties: int = 0
    team1_blocks: int = 0
    team2_blocks: int = 0

    # Ball-handling stats
    team1_passes_attempted: int = 0
    team2_passes_attempted: int = 0
    team1_passes_completed: int = 0
    team2_passes_completed: int = 0
    team1_pickups_attempted: int = 0
    team2_pickups_attempted: int = 0
    team1_pickups_succeeded: int = 0
    team2_pickups_succeeded: int = 0

    # Risk stats
    team1_turnovers: int = 0
    team2_turnovers: int = 0
    team1_failed_dodges: int = 0
    team2_failed_dodges: int = 0

    # Strategy message stats (verbosity proxy)
    team1_messages_sent: int = 0
    team2_messages_sent: int = 0
    team1_total_message_chars: int = 0
    team2_total_message_chars: int = 0

    # Agent identity — populated for versus games, None for arena games
    team1_agent_id:   Optional[str] = None
    team1_agent_name: Optional[str] = None
    team2_agent_id:   Optional[str] = None
    team2_agent_name: Optional[str] = None


class ModelLeaderboardEntry(BaseModel):
    """Aggregated stats for one model across all games."""
    model_id: str

    # Results
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    goals_for: int = 0
    goals_against: int = 0
    score_diff: int = 0

    # Raw accumulated counts
    casualties_caused: int = 0
    blocks_thrown: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    pickups_attempted: int = 0
    pickups_succeeded: int = 0
    turnovers: int = 0
    failed_dodges: int = 0
    messages_sent: int = 0
    total_message_chars: int = 0

    # ── Computed per-game rates ────────────────────────────────────────────

    @computed_field
    @property
    def win_pct(self) -> float:
        return round(self.wins / self.games, 3) if self.games else 0.0

    @computed_field
    @property
    def aggression(self) -> float:
        """Blocks thrown per game."""
        return round(self.blocks_thrown / self.games, 2) if self.games else 0.0

    @computed_field
    @property
    def recklessness(self) -> float:
        """Turnovers per game."""
        return round(self.turnovers / self.games, 2) if self.games else 0.0

    @computed_field
    @property
    def ball_craft(self) -> float:
        """Successful passes + pickups per game."""
        return round(
            (self.passes_completed + self.pickups_succeeded) / self.games, 2
        ) if self.games else 0.0

    @computed_field
    @property
    def lethality(self) -> float:
        """Casualties caused per game."""
        return round(self.casualties_caused / self.games, 2) if self.games else 0.0

    @computed_field
    @property
    def verbosity(self) -> float:
        """Average strategy message length in characters."""
        return round(self.total_message_chars / self.messages_sent, 1) if self.messages_sent else 0.0

    @computed_field
    @property
    def efficiency(self) -> float:
        """Goals per game divided by turnover rate (higher = scoring despite turnovers)."""
        if not self.games:
            return 0.0
        gf_per_game = self.goals_for / self.games
        to_per_game = self.turnovers / self.games
        return round(gf_per_game / max(to_per_game, 0.5), 2)

    @computed_field
    @property
    def pass_completion_pct(self) -> float:
        """Pass completion percentage (0–100)."""
        return round(
            100 * self.passes_completed / self.passes_attempted, 1
        ) if self.passes_attempted else 0.0


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


class AgentLeaderboardEntry(BaseModel):
    """Aggregated stats for one named agent across all games."""
    agent_id: str
    agent_name: str
    model: str = "unknown"

    # Results
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    forfeits: int = 0
    goals_for: int = 0
    goals_against: int = 0
    score_diff: int = 0

    # Raw accumulated counts
    casualties_caused: int = 0
    blocks_thrown: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    pickups_attempted: int = 0
    pickups_succeeded: int = 0
    turnovers: int = 0
    failed_dodges: int = 0
    messages_sent: int = 0
    total_message_chars: int = 0

    # ── Computed per-game rates ────────────────────────────────────────────

    @computed_field
    @property
    def win_pct(self) -> float:
        return round(self.wins / self.games, 3) if self.games else 0.0

    @computed_field
    @property
    def aggression(self) -> float:
        """Blocks thrown per game."""
        return round(self.blocks_thrown / self.games, 2) if self.games else 0.0

    @computed_field
    @property
    def recklessness(self) -> float:
        """Turnovers per game."""
        return round(self.turnovers / self.games, 2) if self.games else 0.0

    @computed_field
    @property
    def ball_craft(self) -> float:
        """Successful passes + pickups per game."""
        return round(
            (self.passes_completed + self.pickups_succeeded) / self.games, 2
        ) if self.games else 0.0

    @computed_field
    @property
    def lethality(self) -> float:
        """Casualties caused per game."""
        return round(self.casualties_caused / self.games, 2) if self.games else 0.0

    @computed_field
    @property
    def verbosity(self) -> float:
        """Average strategy message length in characters."""
        return round(self.total_message_chars / self.messages_sent, 1) if self.messages_sent else 0.0

    @computed_field
    @property
    def efficiency(self) -> float:
        """Goals per game divided by turnover rate."""
        if not self.games:
            return 0.0
        gf_per_game = self.goals_for / self.games
        to_per_game = self.turnovers / self.games
        return round(gf_per_game / max(to_per_game, 0.5), 2)

    @computed_field
    @property
    def pass_completion_pct(self) -> float:
        """Pass completion percentage (0–100)."""
        return round(
            100 * self.passes_completed / self.passes_attempted, 1
        ) if self.passes_attempted else 0.0


class LeaderboardResponse(BaseModel):
    """Response shape for GET /leaderboard and GET /versus/leaderboard."""
    total_games: int
    by_agent: list[AgentLeaderboardEntry] = []
    by_model: list[ModelLeaderboardEntry]
    by_team: list[TeamLeaderboardEntry]
