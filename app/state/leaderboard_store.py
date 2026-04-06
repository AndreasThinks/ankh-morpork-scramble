"""Persistent leaderboard — SQLite-backed, in-memory aggregation."""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.models.leaderboard import (
    GameResult, ModelLeaderboardEntry, TeamLeaderboardEntry, LeaderboardResponse,
    AgentLeaderboardEntry
)

logger = logging.getLogger("app.leaderboard")


def _get_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "/data" if Path("/data").is_mount() else "data"))


def _default_db_path() -> Path:
    return _get_data_dir() / "versus.db"


class LeaderboardStore:
    """Thread-safe SQLite leaderboard store.

    Results are written to a ``results`` table in the shared ``versus.db``
    database alongside agents, lobby, and game_agents tables.

    Pass ``path=Path(":memory:")`` for an isolated in-memory database (tests).
    Pass any other ``Path`` to use a file-backed SQLite database.
    """

    def __init__(self, path: Path = None):
        if path is None:
            path = _default_db_path()
        self.path = path
        self._lock = threading.Lock()
        self._is_memory = str(path) == ":memory:"
        # In-memory databases need a single persistent connection — each new
        # connect(":memory:") creates an entirely separate empty database.
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self._is_memory:
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        self._init_db()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _get_conn(self) -> tuple[sqlite3.Connection, bool]:
        """Return (conn, owned). If owned=True, caller must close it."""
        if self._is_memory:
            return self._mem_conn, False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn, True

    def _init_db(self) -> None:
        conn, owned = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS results (
                    game_id   TEXT PRIMARY KEY,
                    played_at TEXT NOT NULL,
                    data      TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            if owned:
                conn.close()
        logger.debug("results table ready in %s", self.path)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(self, result: GameResult) -> None:
        """Store one GameResult. Idempotent on duplicate game_id."""
        with self._lock:
            conn, owned = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO results (game_id, played_at, data) VALUES (?, ?, ?)",
                    (result.game_id, result.played_at.isoformat(), result.model_dump_json())
                )
                conn.commit()
            except sqlite3.IntegrityError:
                logger.debug("Game %s already recorded — skipping.", result.game_id)
                return
            finally:
                if owned:
                    conn.close()
        logger.info(
            "Recorded result: %s %d-%d %s (models: %s vs %s)",
            result.team1_name, result.team1_score,
            result.team2_score, result.team2_name,
            result.team1_model, result.team2_model,
        )

    # ------------------------------------------------------------------
    # Read / aggregate
    # ------------------------------------------------------------------

    def load_all(self) -> list[GameResult]:
        """Load all results from the database."""
        conn, owned = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT data FROM results ORDER BY played_at ASC"
            ).fetchall()
        finally:
            if owned:
                conn.close()
        results = []
        for row in rows:
            try:
                results.append(GameResult.model_validate_json(row["data"]))
            except Exception as exc:
                logger.warning("Skipping malformed result row: %s", exc)
        return results

    def get_leaderboard(self) -> LeaderboardResponse:
        """Aggregate all results and return a LeaderboardResponse."""
        results = self.load_all()

        model_map: dict[str, ModelLeaderboardEntry] = {}
        team_map: dict[str, TeamLeaderboardEntry] = {}
        agent_map: dict[str, AgentLeaderboardEntry] = {}

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

            # ---- agent aggregation (versus games only) ----
            for (agent_id, agent_name, model_id, score_for, score_against,
                 outcome, casualties, blocks,
                 passes_att, passes_comp,
                 pickups_att, pickups_succ,
                 turnovers, failed_dodges,
                 messages_sent, total_message_chars) in [
                (
                    r.team1_agent_id, r.team1_agent_name, r.team1_model,
                    r.team1_score, r.team2_score, t1_outcome,
                    r.team1_casualties, r.team1_blocks,
                    r.team1_passes_attempted, r.team1_passes_completed,
                    r.team1_pickups_attempted, r.team1_pickups_succeeded,
                    r.team1_turnovers, r.team1_failed_dodges,
                    r.team1_messages_sent, r.team1_total_message_chars,
                ),
                (
                    r.team2_agent_id, r.team2_agent_name, r.team2_model,
                    r.team2_score, r.team1_score, t2_outcome,
                    r.team2_casualties, r.team2_blocks,
                    r.team2_passes_attempted, r.team2_passes_completed,
                    r.team2_pickups_attempted, r.team2_pickups_succeeded,
                    r.team2_turnovers, r.team2_failed_dodges,
                    r.team2_messages_sent, r.team2_total_message_chars,
                ),
            ]:
                if not agent_id:
                    continue  # arena game, no agent identity
                if agent_id not in agent_map:
                    agent_map[agent_id] = AgentLeaderboardEntry(
                        agent_id=agent_id, agent_name=agent_name, model=model_id or "unknown"
                    )
                entry = agent_map[agent_id]
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

        by_agent = sorted(agent_map.values(), key=lambda e: (-e.wins, -e.score_diff))
        by_model = sorted(model_map.values(), key=lambda e: (-e.wins, -e.score_diff))
        by_team = sorted(team_map.values(), key=lambda e: (-e.wins, -e.score_diff))

        return LeaderboardResponse(
            total_games=len(results),
            by_agent=by_agent,
            by_model=by_model,
            by_team=by_team,
        )
