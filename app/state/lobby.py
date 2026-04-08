"""Lobby queue and pairing logic for versus mode."""
from __future__ import annotations

import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.state.agent_registry import _get_conn
from app.state.game_manager import GameManager

logger = logging.getLogger("app.state.lobby")

# Alternating team assignment: track total completed pairings
# team1 = City Watch (TeamType.CITY_WATCH), team2 = Unseen University (TeamType.UNSEEN_UNIVERSITY)
# Alternate so neither faction is always team1

# Module-level lock — prevents concurrent joins from double-pairing the same waiting agent
_JOIN_LOCK = threading.Lock()

# Ack window: agents have this many minutes to call /versus/ready after being matched
ACK_DEADLINE_MINUTES = 10


class LobbyManager:
    """Manages the waiting queue and pairs agents into games."""

    def __init__(self, game_manager: GameManager):
        self.game_manager = game_manager

    def join(self, agent_id: str) -> dict:
        """
        Add agent to lobby. If another agent is waiting, pair them (deferred game).
        Returns dict with keys: status, game_id (optional), team_id (optional),
        opponent_agent_id (optional), scheduled_start (optional), poll_interval_seconds.
        """
        now = datetime.now(timezone.utc).isoformat()

        with _JOIN_LOCK:
            return self._join_locked(agent_id, now)

    def _join_locked(self, agent_id: str, now: str) -> dict:
        """Inner join logic — must be called with _JOIN_LOCK held."""
        with _get_conn() as conn:
            # If already matched or playing, return current state instead of re-queuing
            existing = conn.execute(
                "SELECT status, game_id, scheduled_start, paired_with FROM lobby WHERE agent_id=?",
                (agent_id,)
            ).fetchone()
            if existing and existing["status"] == "playing":
                # Find opponent and team
                opp = conn.execute(
                    "SELECT ga.agent_id, a.name FROM game_agents ga "
                    "JOIN agents a ON ga.agent_id = a.agent_id "
                    "WHERE ga.game_id=? AND ga.agent_id != ?",
                    (existing["game_id"], agent_id)
                ).fetchone()
                my_team = conn.execute(
                    "SELECT team_id FROM game_agents WHERE game_id=? AND agent_id=?",
                    (existing["game_id"], agent_id)
                ).fetchone()
                return {
                    "status": "playing",
                    "game_id": existing["game_id"],
                    "team_id": my_team["team_id"] if my_team else None,
                    "opponent_agent_id": opp["agent_id"] if opp else None,
                }
            if existing and existing["status"] == "matched":
                return {
                    "status": "matched",
                    "game_id": existing["game_id"],
                    "opponent_agent_id": existing["paired_with"],
                    "scheduled_start": existing["scheduled_start"],
                    "poll_interval_seconds": 30,
                }

            # Remove any stale waiting entry for this agent
            conn.execute("DELETE FROM lobby WHERE agent_id=?", (agent_id,))

            # Check for a waiting opponent
            opponent = conn.execute(
                "SELECT agent_id FROM lobby WHERE status='waiting' AND agent_id != ? ORDER BY joined_at ASC LIMIT 1",
                (agent_id,)
            ).fetchone()

            if not opponent:
                # No opponent yet — queue this agent
                conn.execute(
                    "INSERT INTO lobby (agent_id, joined_at, status, game_id) VALUES (?,?,?,?)",
                    (agent_id, now, "waiting", None)
                )
                conn.commit()
                logger.info("Agent %s queued, waiting for opponent", agent_id)
                return {"status": "waiting", "poll_interval_seconds": 300}

            # Found an opponent — pair them (deferred: no game created yet)
            opponent_id = opponent["agent_id"]
            scheduled_start = (datetime.now(timezone.utc) + timedelta(minutes=ACK_DEADLINE_MINUTES)).isoformat()

            # Update opponent row to matched
            conn.execute(
                "UPDATE lobby SET status='matched', scheduled_start=?, paired_with=? WHERE agent_id=?",
                (scheduled_start, agent_id, opponent_id)
            )
            # Insert joining agent as matched
            conn.execute(
                "INSERT INTO lobby (agent_id, joined_at, status, game_id, scheduled_start, paired_with) VALUES (?,?,?,?,?,?)",
                (agent_id, now, "matched", None, scheduled_start, opponent_id)
            )
            conn.commit()

        logger.info("Matched agents %s vs %s, ack deadline %s", agent_id, opponent_id, scheduled_start)
        return {
            "status": "matched",
            "opponent_agent_id": opponent_id,
            "scheduled_start": scheduled_start,
            "poll_interval_seconds": 30,
        }

    def _create_game_for_pair(self, agent1_id: str, agent2_id: str) -> str:
        """Create a game for a matched pair. Returns game_id."""
        with _get_conn() as conn:
            # Determine team assignment: count past pairings to alternate
            pairing_count = conn.execute("SELECT COUNT(*) FROM game_agents").fetchone()[0] // 2
            if pairing_count % 2 == 0:
                team1_agent_id = agent1_id
                team2_agent_id = agent2_id
            else:
                team1_agent_id = agent2_id
                team2_agent_id = agent1_id

            # Get agent names for team names
            t1_name_row = conn.execute("SELECT name FROM agents WHERE agent_id=?", (team1_agent_id,)).fetchone()
            t2_name_row = conn.execute("SELECT name FROM agents WHERE agent_id=?", (team2_agent_id,)).fetchone()
            team1_name = t1_name_row["name"] if t1_name_row else "City Watch"
            team2_name = t2_name_row["name"] if t2_name_row else "Unseen University"

        # Create game outside the connection context to avoid nesting issues
        game_id = f"versus-{uuid.uuid4().hex[:8]}"
        self.game_manager.create_game(game_id)

        # Update team names on the created game
        game_state = self.game_manager.get_game(game_id)
        game_state.team1.name = team1_name
        game_state.team2.name = team2_name

        # Record game_agents and update lobby
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO game_agents (game_id, team_id, agent_id) VALUES (?,?,?)",
                (game_id, "team1", team1_agent_id)
            )
            conn.execute(
                "INSERT INTO game_agents (game_id, team_id, agent_id) VALUES (?,?,?)",
                (game_id, "team2", team2_agent_id)
            )
            conn.execute(
                "UPDATE lobby SET status='playing', game_id=? WHERE agent_id IN (?,?)",
                (game_id, agent1_id, agent2_id)
            )
            conn.commit()

        logger.info("Created game %s: %s (team1) vs %s (team2)",
                     game_id, team1_agent_id, team2_agent_id)
        return game_id

    def ack(self, agent_id: str) -> dict:
        """Mark agent as ready. If both agents acked, create the game immediately."""
        now = datetime.now(timezone.utc).isoformat()
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT status, paired_with, scheduled_start FROM lobby WHERE agent_id=?",
                (agent_id,)
            ).fetchone()
            if not row or row["status"] != "matched":
                return {"status": "not_matched"}

            conn.execute(
                "UPDATE lobby SET acked_at=? WHERE agent_id=?",
                (now, agent_id)
            )
            conn.commit()

            # Check if opponent has also acked
            opponent_id = row["paired_with"]
            opp_row = conn.execute(
                "SELECT acked_at FROM lobby WHERE agent_id=?",
                (opponent_id,)
            ).fetchone()

        if opp_row and opp_row["acked_at"]:
            # Both acked — create game immediately
            game_id = self._create_game_for_pair(agent_id, opponent_id)
            return {"status": "playing", "game_id": game_id}

        return {"status": "waiting_for_opponent"}

    def cancel_match(self, agent1_id: str, agent2_id: str) -> None:
        """Neither agent responded — remove both from lobby."""
        with _get_conn() as conn:
            conn.execute(
                "DELETE FROM lobby WHERE agent_id IN (?,?)",
                (agent1_id, agent2_id)
            )
            conn.commit()
        logger.info("Match cancelled (no acks): %s vs %s", agent1_id, agent2_id)

    def forfeit_unacked(self, unacked_id: str, acked_id: str) -> None:
        """One agent didn't ack — remove both, re-queue the acked agent."""
        now = datetime.now(timezone.utc).isoformat()
        with _get_conn() as conn:
            conn.execute(
                "DELETE FROM lobby WHERE agent_id IN (?,?)",
                (unacked_id, acked_id)
            )
            # Re-queue the acked agent as waiting
            conn.execute(
                "INSERT INTO lobby (agent_id, joined_at, status, game_id) VALUES (?,?,?,?)",
                (acked_id, now, "waiting", None)
            )
            conn.commit()
        logger.info("Forfeit: %s didn't ack, re-queued %s", unacked_id, acked_id)

    def get_status(self, agent_id: str) -> dict:
        """Get current lobby status for an agent."""
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM lobby WHERE agent_id=?", (agent_id,)
            ).fetchone()

            if not row:
                return {"status": "not_in_lobby"}

            result = {"status": row["status"], "game_id": row["game_id"]}

            if row["status"] == "matched":
                result["scheduled_start"] = row["scheduled_start"]
                result["poll_interval_seconds"] = 30
            elif row["status"] == "waiting":
                result["poll_interval_seconds"] = 300

            if row["game_id"]:
                # Find opponent
                opp = conn.execute(
                    "SELECT ga.agent_id, a.name FROM game_agents ga "
                    "JOIN agents a ON ga.agent_id = a.agent_id "
                    "WHERE ga.game_id=? AND ga.agent_id != ?",
                    (row["game_id"], agent_id)
                ).fetchone()
                if opp:
                    result["opponent_name"] = opp["name"]

                # Find this agent's team_id
                my_team = conn.execute(
                    "SELECT team_id FROM game_agents WHERE game_id=? AND agent_id=?",
                    (row["game_id"], agent_id)
                ).fetchone()
                if my_team:
                    result["team_id"] = my_team["team_id"]
            elif row["status"] == "matched" and row["paired_with"]:
                # Matched but game not yet created — look up opponent name directly
                opp = conn.execute(
                    "SELECT name FROM agents WHERE agent_id=?",
                    (row["paired_with"],)
                ).fetchone()
                if opp:
                    result["opponent_name"] = opp["name"]

        return result

    def leave(self, agent_id: str) -> bool:
        """Remove agent from lobby if waiting. Returns True if removed."""
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT status FROM lobby WHERE agent_id=?", (agent_id,)
            ).fetchone()
            if not row or row["status"] != "waiting":
                return False
            conn.execute("DELETE FROM lobby WHERE agent_id=?", (agent_id,))
            conn.commit()
        logger.info("Agent %s left the lobby", agent_id)
        return True

    def mark_game_playing(self, game_id: str) -> None:
        """Transition lobby rows for both agents in a game from 'matched' to 'playing'."""
        try:
            with _get_conn() as conn:
                conn.execute(
                    "UPDATE lobby SET status='playing' WHERE game_id=? AND status='matched'",
                    (game_id,)
                )
                conn.commit()
        except sqlite3.OperationalError:
            pass  # lobby table not initialised — no rows to update

    def get_waiting_count(self) -> int:
        with _get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM lobby WHERE status='waiting'").fetchone()
        return row[0] if row else 0
