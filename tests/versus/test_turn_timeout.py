"""Tests that an inactive agent is automatically forfeited after the turn timeout."""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.enums import GamePhase, TeamType
from app.models.game_state import GameState, TurnState
from app.models.team import Team


def _make_game(game_id: str, *, minutes_ago: int) -> GameState:
    """Build a minimal GameState in playing phase with a stale turn."""
    return GameState(
        game_id=game_id,
        phase=GamePhase.PLAYING,
        team1=Team(id="team1", name="CW", team_type=TeamType.CITY_WATCH),
        team2=Team(id="team2", name="UU", team_type=TeamType.UNSEEN_UNIVERSITY),
        turn=TurnState(
            active_team_id="team1",
            turn_started_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        ),
    )


@pytest.mark.asyncio
async def test_stale_turn_is_forfeited(tmp_path):
    """An agent that stops responding has its turn forfeited after the timeout."""
    with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
        from app.state.agent_registry import init_db, _get_conn
        init_db()

        from app.main import game_manager, _check_timeouts

        game_id = "timeout-game-1"
        game_state = _make_game(game_id, minutes_ago=6)
        game_manager.games[game_id] = game_state

        # Mark this game as a versus game in the DB
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO game_agents (game_id, team_id, agent_id) VALUES (?,?,?)",
                (game_id, "team1", "agent-1"),
            )

        await _check_timeouts(datetime.now(timezone.utc))

        assert game_state.phase == GamePhase.CONCLUDED
        # Forfeit awards 1 point to the opposing team
        assert game_state.team2.score == 1


@pytest.mark.asyncio
async def test_active_turn_is_not_forfeited(tmp_path):
    """A turn that is still within the timeout window is left alone."""
    with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
        from app.state.agent_registry import init_db, _get_conn
        init_db()

        from app.main import game_manager, _check_timeouts

        game_id = "active-game-1"
        game_state = _make_game(game_id, minutes_ago=2)
        game_manager.games[game_id] = game_state

        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO game_agents (game_id, team_id, agent_id) VALUES (?,?,?)",
                (game_id, "team1", "agent-2"),
            )

        await _check_timeouts(datetime.now(timezone.utc))

        assert game_state.phase == GamePhase.PLAYING
        assert game_state.team2.score == 0


@pytest.mark.asyncio
async def test_non_versus_game_is_not_forfeited(tmp_path):
    """A stale turn in an arena (non-versus) game must not be forfeited."""
    with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
        from app.state.agent_registry import init_db
        init_db()

        from app.main import game_manager, _check_timeouts

        game_id = "arena-game-1"
        game_state = _make_game(game_id, minutes_ago=10)
        game_manager.games[game_id] = game_state
        # No game_agents row — this is an arena game

        await _check_timeouts(datetime.now(timezone.utc))

        assert game_state.phase == GamePhase.PLAYING
