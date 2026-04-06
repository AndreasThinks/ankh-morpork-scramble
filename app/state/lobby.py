"""Lobby queue and pairing logic for versus mode."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from app.state.agent_registry import _get_conn
from app.state.game_manager import GameManager

logger = logging.getLogger("app.state.lobby")

# Alternating team assignment: track total completed pairings
# team1 = City Watch (TeamType.CITY_WATCH), team2 = Unseen University (TeamType.UNSEEN_UNIVERSITY)
# Alternate so neither faction is always team1


class LobbyManager:
    """Manages the waiting queue and pairs agents into games."""

    def __init__(self, game_manager: GameManager):
        self.game_manager = game_manager

    def join(self, agent_id: str) -> dict:
        """
        Add agent to lobby. If another agent is waiting, pair them into a game.
        Returns dict with keys: status, game_id (optional), team_id (optional), opponent_agent_id (optional)
        """
        now = datetime.now(timezone.utc).isoformat()

        with _get_conn() as conn:
            # Remove any stale entry for this agent first
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
                return {"status": "waiting"}

            # Found an opponent — pair them
            opponent_id = opponent["agent_id"]

            # Determine team assignment: count past pairings to alternate
            pairing_count = conn.execute("SELECT COUNT(*) FROM game_agents").fetchone()[0] // 2
            if pairing_count % 2 == 0:
                team1_agent_id = opponent_id   # waiting agent gets team1
                team2_agent_id = agent_id      # joining agent gets team2
            else:
                team1_agent_id = agent_id
                team2_agent_id = opponent_id

            # Get agent names for team names
            t1_name_row = conn.execute("SELECT name FROM agents WHERE agent_id=?", (team1_agent_id,)).fetchone()
            t2_name_row = conn.execute("SELECT name FROM agents WHERE agent_id=?", (team2_agent_id,)).fetchone()
            team1_name = t1_name_row["name"] if t1_name_row else "City Watch"
            team2_name = t2_name_row["name"] if t2_name_row else "Unseen University"

        # Create game outside the connection context to avoid nesting issues
        import uuid
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
                "UPDATE lobby SET status='matched', game_id=? WHERE agent_id=?",
                (game_id, opponent_id)
            )
            conn.execute(
                "INSERT INTO lobby (agent_id, joined_at, status, game_id) VALUES (?,?,?,?)",
                (agent_id, now, "matched", game_id)
            )
            conn.commit()

        # Determine which team this joining agent is on
        joining_team_id = "team2" if team2_agent_id == agent_id else "team1"

        logger.info("Paired agents %s (team1) vs %s (team2) in game %s",
                    team1_agent_id, team2_agent_id, game_id)
        return {
            "status": "matched",
            "game_id": game_id,
            "team_id": joining_team_id,
            "opponent_agent_id": opponent_id,
        }

    def get_status(self, agent_id: str) -> dict:
        """Get current lobby status for an agent."""
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM lobby WHERE agent_id=?", (agent_id,)
            ).fetchone()

            if not row:
                return {"status": "not_in_lobby"}

            result = {"status": row["status"], "game_id": row["game_id"]}

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

    def get_waiting_count(self) -> int:
        with _get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM lobby WHERE status='waiting'").fetchone()
        return row[0] if row else 0
