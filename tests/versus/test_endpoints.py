"""Tests for versus-mode FastAPI endpoints and forfeit integration."""
import os
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.models.leaderboard import GameResult
from app.state.leaderboard_store import LeaderboardStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def versus_client(tmp_path):
    """TestClient with an isolated DATA_DIR so SQLite files go to tmp_path."""
    with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
        from app.state.agent_registry import init_db
        init_db()
        from app.main import app
        # Use raise_server_exceptions=True (default) to surface app errors clearly
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client


# ---------------------------------------------------------------------------
# POST /versus/join — new agent registration
# ---------------------------------------------------------------------------

def test_join_new_agent(versus_client):
    resp = versus_client.post("/versus/join", json={"name": "Rincewind"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Rincewind"
    assert data["token"].startswith("ams_")
    assert data["status"] == "waiting"
    assert data["game_id"] is None


def test_join_duplicate_name_returns_409(versus_client):
    versus_client.post("/versus/join", json={"name": "Granny"})
    resp = versus_client.post("/versus/join", json={"name": "Granny"})
    assert resp.status_code == 409


def test_join_returns_no_token_on_duplicate_attempt(versus_client):
    """First join gives a token; second same-name attempt is rejected, not silently replayed."""
    r1 = versus_client.post("/versus/join", json={"name": "Nanny"})
    assert r1.status_code == 200
    r2 = versus_client.post("/versus/join", json={"name": "Nanny"})
    assert r2.status_code == 409


def test_join_missing_name_and_token_returns_400(versus_client):
    resp = versus_client.post("/versus/join", json={})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /versus/join — returning agent via token
# ---------------------------------------------------------------------------

def test_join_returning_agent_with_token(versus_client):
    r1 = versus_client.post("/versus/join", json={"name": "Carrot"})
    token = r1.json()["token"]

    r2 = versus_client.post("/versus/join", json={"token": token})
    assert r2.status_code == 200
    assert r2.json()["name"] == "Carrot"
    assert r2.json()["token"] is None  # token NOT re-issued on return


def test_join_invalid_token_returns_401(versus_client):
    resp = versus_client.post("/versus/join", json={"token": "ams_" + "x" * 32})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /versus/lobby/status
# ---------------------------------------------------------------------------

def test_lobby_status_waiting(versus_client):
    r = versus_client.post("/versus/join", json={"name": "Vetinari"})
    token = r.json()["token"]

    resp = versus_client.get("/versus/lobby/status", headers={"X-Agent-Token": token})
    assert resp.status_code == 200
    assert resp.json()["status"] == "waiting"


def test_lobby_status_no_token_returns_401(versus_client):
    resp = versus_client.get("/versus/lobby/status")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /versus/lobby/leave
# ---------------------------------------------------------------------------

def test_leave_waiting_agent(versus_client):
    r = versus_client.post("/versus/join", json={"name": "Moist"})
    token = r.json()["token"]

    resp = versus_client.delete("/versus/lobby/leave", headers={"X-Agent-Token": token})
    assert resp.status_code == 200
    assert resp.json()["removed"] is True

    status_resp = versus_client.get("/versus/lobby/status", headers={"X-Agent-Token": token})
    assert status_resp.json()["status"] == "not_in_lobby"


def test_leave_not_in_lobby(versus_client):
    r = versus_client.post("/versus/join", json={"name": "Reaper"})
    token = r.json()["token"]
    versus_client.delete("/versus/lobby/leave", headers={"X-Agent-Token": token})

    # Second leave should report not removed
    resp = versus_client.delete("/versus/lobby/leave", headers={"X-Agent-Token": token})
    assert resp.status_code == 200
    assert resp.json()["removed"] is False


# ---------------------------------------------------------------------------
# Forfeit integration
# ---------------------------------------------------------------------------

def test_forfeit_recorded_as_loss_with_forfeit_flag(tmp_path):
    """record_forfeit() stores is_forfeit=True in the leaderboard entry."""
    store = LeaderboardStore(path=tmp_path / "results.jsonl")

    # Simulate a forfeit by hand — record a GameResult with is_forfeit=True
    result = GameResult(
        game_id="g-forfeit-1",
        team1_name="BotA", team1_model="gpt-4o", team1_score=0,
        team2_name="BotB", team2_model="claude-3", team2_score=1,
        team1_agent_id="a1", team1_agent_name="BotA",
        team2_agent_id="a2", team2_agent_name="BotB",
        is_forfeit=True,
    )
    store.record(result)

    lb = store.get_leaderboard()
    bota = next(e for e in lb.by_agent if e.agent_name == "BotA")
    botb = next(e for e in lb.by_agent if e.agent_name == "BotB")

    assert bota.losses == 1
    assert bota.forfeits == 1  # forfeiting team gets forfeit counter incremented
    assert botb.wins == 1
    assert botb.forfeits == 0  # winning team is not penalised


def test_non_forfeit_loss_does_not_increment_forfeits(tmp_path):
    """Normal loss keeps forfeits == 0."""
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    result = GameResult(
        game_id="g-normal-loss",
        team1_name="BotC", team1_model="gpt-4o", team1_score=0,
        team2_name="BotD", team2_model="claude-3", team2_score=2,
        team1_agent_id="a3", team1_agent_name="BotC",
        team2_agent_id="a4", team2_agent_name="BotD",
        is_forfeit=False,
    )
    store.record(result)

    lb = store.get_leaderboard()
    botc = next(e for e in lb.by_agent if e.agent_name == "BotC")
    assert botc.losses == 1
    assert botc.forfeits == 0


def test_forfeit_result_round_trips_through_jsonl(tmp_path):
    """is_forfeit survives serialise → persist → reload."""
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    result = GameResult(
        game_id="g-roundtrip",
        team1_name="BotE", team1_model="gpt-4o", team1_score=0,
        team2_name="BotF", team2_model="claude-3", team2_score=1,
        team1_agent_id="a5", team1_agent_name="BotE",
        team2_agent_id="a6", team2_agent_name="BotF",
        is_forfeit=True,
    )
    store.record(result)

    loaded = store.load_all()
    assert loaded[0].is_forfeit is True


# ---------------------------------------------------------------------------
# M-2 regression: LeaderboardStore DATA_DIR resolved lazily
# ---------------------------------------------------------------------------

def test_leaderboard_store_respects_data_dir_at_construction(tmp_path):
    """LeaderboardStore.__init__ evaluates DATA_DIR at call time, not import time."""
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    with patch.dict(os.environ, {"DATA_DIR": str(custom_dir)}):
        store = LeaderboardStore()
    assert store.path == custom_dir / "results.jsonl"
