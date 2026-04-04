"""Persistent leaderboard — append-only JSONL + in-memory aggregation."""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.leaderboard import (
    GameResult, ModelLeaderboardEntry, TeamLeaderboardEntry, LeaderboardResponse
)

logger = logging.getLogger("app.leaderboard")

# Use /data (Railway volume mount) when available, otherwise fall back to
# the local data/ directory for development. Set DATA_DIR env var to override.
_DATA_DIR = Path(os.getenv("DATA_DIR", "/data" if Path("/data").is_mount() else "data"))
_DEFAULT_PATH = _DATA_DIR / "results.jsonl"


class LeaderboardStore:
    """
    Thread-safe append-only JSONL store.

    Gotcha: safe for single-process uvicorn only. Multi-worker deployments
    would need an external lock (e.g. a file lock via fcntl or portalocker).
    """

    def __init__(self, path: Path = _DEFAULT_PATH):
        self.path = path
        self._lock = threading.Lock()
        self._recorded_ids: set[str] = set()
        self._load_recorded_ids()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(self, result: GameResult) -> None:
        """Append one GameResult to the JSONL file. Idempotent on duplicate game_id."""
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Idempotency guard: skip if this game_id is already present
            if self._is_recorded(result.game_id):
                logger.debug("Game %s already recorded — skipping.", result.game_id)
                return
            line = result.model_dump_json() + "\n"
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line)
            # Add to cache after successful write
            self._recorded_ids.add(result.game_id)
            logger.info(
                "Recorded result: %s %d-%d %s (models: %s vs %s)",
                result.team1_name, result.team1_score,
                result.team2_score, result.team2_name,
                result.team1_model, result.team2_model,
            )

    def _load_recorded_ids(self) -> None:
        """Load all game IDs from disk into memory cache (called once at init)."""
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    game_id = obj.get("game_id")
                    if game_id:
                        self._recorded_ids.add(game_id)
                except json.JSONDecodeError:
                    continue

    def _is_recorded(self, game_id: str) -> bool:
        """Check if a game_id already exists (O(1) lookup in memory cache)."""
        return game_id in self._recorded_ids

    # ------------------------------------------------------------------
    # Read / aggregate
    # ------------------------------------------------------------------

    def load_all(self) -> list[GameResult]:
        """Load all results from disk."""
        if not self.path.exists():
            return []
        results = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(GameResult.model_validate_json(line))
                except Exception as exc:
                    logger.warning("Skipping malformed leaderboard line: %s", exc)
        return results

    def get_leaderboard(self) -> LeaderboardResponse:
        """Aggregate all results and return a LeaderboardResponse."""
        results = self.load_all()

        model_map: dict[str, ModelLeaderboardEntry] = {}
        team_map: dict[str, TeamLeaderboardEntry] = {}

        for r in results:
            # ---- determine outcomes ----
            if r.team1_score > r.team2_score:
                t1_outcome, t2_outcome = "win", "loss"
            elif r.team2_score > r.team1_score:
                t1_outcome, t2_outcome = "loss", "win"
            else:
                t1_outcome = t2_outcome = "draw"

            # ---- model aggregation ----
            for (model_id, score_for, score_against, outcome,
                 casualties, blocks,
                 passes_att, passes_comp,
                 pickups_att, pickups_succ,
                 turnovers, failed_dodges,
                 messages_sent, total_message_chars) in [
                (
                    r.team1_model, r.team1_score, r.team2_score, t1_outcome,
                    r.team1_casualties, r.team1_blocks,
                    r.team1_passes_attempted, r.team1_passes_completed,
                    r.team1_pickups_attempted, r.team1_pickups_succeeded,
                    r.team1_turnovers, r.team1_failed_dodges,
                    r.team1_messages_sent, r.team1_total_message_chars,
                ),
                (
                    r.team2_model, r.team2_score, r.team1_score, t2_outcome,
                    r.team2_casualties, r.team2_blocks,
                    r.team2_passes_attempted, r.team2_passes_completed,
                    r.team2_pickups_attempted, r.team2_pickups_succeeded,
                    r.team2_turnovers, r.team2_failed_dodges,
                    r.team2_messages_sent, r.team2_total_message_chars,
                ),
            ]:
                if model_id not in model_map:
                    model_map[model_id] = ModelLeaderboardEntry(model_id=model_id)
                entry = model_map[model_id]
                entry.games += 1
                entry.goals_for += score_for
                entry.goals_against += score_against
                entry.score_diff += score_for - score_against
                entry.casualties_caused += casualties
                entry.blocks_thrown += blocks
                entry.passes_attempted += passes_att
                entry.passes_completed += passes_comp
                entry.pickups_attempted += pickups_att
                entry.pickups_succeeded += pickups_succ
                entry.turnovers += turnovers
                entry.failed_dodges += failed_dodges
                entry.messages_sent += messages_sent
                entry.total_message_chars += total_message_chars
                if outcome == "win":
                    entry.wins += 1
                elif outcome == "loss":
                    entry.losses += 1
                else:
                    entry.draws += 1

            # ---- team aggregation ----
            for team_name, score_for, score_against, outcome in [
                (r.team1_name, r.team1_score, r.team2_score, t1_outcome),
                (r.team2_name, r.team2_score, r.team1_score, t2_outcome),
            ]:
                if team_name not in team_map:
                    team_map[team_name] = TeamLeaderboardEntry(team_name=team_name)
                entry = team_map[team_name]
                entry.games += 1
                entry.goals_for += score_for
                entry.goals_against += score_against
                entry.score_diff += score_for - score_against
                if outcome == "win":
                    entry.wins += 1
                elif outcome == "loss":
                    entry.losses += 1
                else:
                    entry.draws += 1

        # Sort by wins desc, score_diff desc
        by_model = sorted(model_map.values(), key=lambda e: (-e.wins, -e.score_diff))
        by_team = sorted(team_map.values(), key=lambda e: (-e.wins, -e.score_diff))

        return LeaderboardResponse(
            total_games=len(results),
            by_model=by_model,
            by_team=by_team,
        )
