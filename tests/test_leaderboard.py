"""Tests for the leaderboard system — store, models, and API endpoint."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.models.leaderboard import GameResult, ModelLeaderboardEntry, LeaderboardResponse
from app.state.leaderboard_store import LeaderboardStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_result(
    game_id="g1",
    team1_name="City Watch",
    team1_model="model-a",
    team1_score=2,
    team2_name="UU Adepts",
    team2_model="model-b",
    team2_score=1,
    team1_casualties=1,
    team2_casualties=0,
    team1_turnovers=2,
    team2_turnovers=3,
    winner_model="model-a",
    winner_team="City Watch",
) -> GameResult:
    return GameResult(
        game_id=game_id,
        team1_name=team1_name,
        team1_model=team1_model,
        team1_score=team1_score,
        team2_name=team2_name,
        team2_model=team2_model,
        team2_score=team2_score,
        team1_casualties=team1_casualties,
        team2_casualties=team2_casualties,
        team1_turnovers=team1_turnovers,
        team2_turnovers=team2_turnovers,
        winner_model=winner_model,
        winner_team=winner_team,
    )


# ---------------------------------------------------------------------------
# LeaderboardStore — basic record and aggregate
# ---------------------------------------------------------------------------

def test_empty_leaderboard(tmp_path):
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    lb = store.get_leaderboard()
    assert lb.total_games == 0
    assert lb.by_model == []
    assert lb.by_team == []


def test_record_single_win(tmp_path):
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    store.record(make_result())
    lb = store.get_leaderboard()

    assert lb.total_games == 1

    # Winner model
    winner = next(e for e in lb.by_model if e.model_id == "model-a")
    assert winner.wins == 1
    assert winner.losses == 0
    assert winner.draws == 0
    assert winner.games == 1
    assert winner.goals_for == 2
    assert winner.goals_against == 1
    assert winner.score_diff == 1
    assert winner.casualties_caused == 1
    assert winner.turnovers == 2

    # Loser model
    loser = next(e for e in lb.by_model if e.model_id == "model-b")
    assert loser.wins == 0
    assert loser.losses == 1
    assert loser.goals_for == 1
    assert loser.goals_against == 2
    assert loser.score_diff == -1

    # Team aggregation
    team_cw = next(e for e in lb.by_team if e.team_name == "City Watch")
    assert team_cw.wins == 1
    team_uu = next(e for e in lb.by_team if e.team_name == "UU Adepts")
    assert team_uu.losses == 1


def test_record_draw(tmp_path):
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    store.record(make_result(
        game_id="draw1",
        team1_score=1,
        team2_score=1,
        winner_model=None,
        winner_team=None,
    ))
    lb = store.get_leaderboard()
    for entry in lb.by_model:
        assert entry.draws == 1
        assert entry.wins == 0
        assert entry.losses == 0


def test_idempotency(tmp_path):
    """Recording the same game_id twice must not create a duplicate entry."""
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    r = make_result()
    store.record(r)
    store.record(r)  # second call should be silently ignored
    lb = store.get_leaderboard()
    assert lb.total_games == 1
    winner = next(e for e in lb.by_model if e.model_id == "model-a")
    assert winner.wins == 1


def test_idempotency_survives_reinit(tmp_path):
    """Idempotency guard must work across store restarts (loaded from disk)."""
    path = tmp_path / "results.jsonl"
    store1 = LeaderboardStore(path=path)
    store1.record(make_result())

    # New store instance re-reads same file
    store2 = LeaderboardStore(path=path)
    store2.record(make_result())  # same game_id — should be skipped

    lb = store2.get_leaderboard()
    assert lb.total_games == 1


def test_multiple_games_accumulate(tmp_path):
    """Two games by the same model should accumulate wins and goals correctly."""
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    store.record(make_result(game_id="g1", team1_score=2, team2_score=0))
    store.record(make_result(game_id="g2", team1_score=3, team2_score=1))

    lb = store.get_leaderboard()
    assert lb.total_games == 2

    model_a = next(e for e in lb.by_model if e.model_id == "model-a")
    assert model_a.wins == 2
    assert model_a.goals_for == 5
    assert model_a.goals_against == 1
    assert model_a.score_diff == 4


def test_leaderboard_sorted_by_wins_then_score_diff(tmp_path):
    """by_model should be sorted: wins desc, score_diff desc."""
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    # model-a wins 2 games; model-b and model-c each win 1
    store.record(make_result(game_id="g1", team1_model="model-a", team2_model="model-b", team1_score=2, team2_score=0, winner_model="model-a", winner_team="City Watch"))
    store.record(make_result(game_id="g2", team1_model="model-a", team2_model="model-c", team1_score=1, team2_score=0, winner_model="model-a", winner_team="City Watch"))
    store.record(make_result(game_id="g3", team1_model="model-b", team2_model="model-c", team1_score=3, team2_score=0, winner_model="model-b", winner_team="City Watch"))

    lb = store.get_leaderboard()
    ids = [e.model_id for e in lb.by_model]
    assert ids[0] == "model-a"  # 2 wins


def test_malformed_jsonl_line_skipped(tmp_path):
    """A corrupt line in the JSONL file should be skipped, not crash."""
    path = tmp_path / "results.jsonl"
    path.write_text(
        '{"game_id": "g1", "not": "a valid GameResult"}\n'
        + make_result(game_id="g2").model_dump_json() + "\n"
    )
    store = LeaderboardStore(path=path)
    lb = store.get_leaderboard()
    # g1 is malformed and skipped; g2 is valid
    assert lb.total_games == 1


# ---------------------------------------------------------------------------
# Model serialization
# ---------------------------------------------------------------------------

def test_win_pct_serialized(tmp_path):
    """ModelLeaderboardEntry.win_pct must appear in model_dump() output (computed_field)."""
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    store.record(make_result())
    lb = store.get_leaderboard()
    winner = next(e for e in lb.by_model if e.model_id == "model-a")
    dumped = winner.model_dump()
    assert "win_pct" in dumped
    assert dumped["win_pct"] == 1.0


def test_win_pct_zero_games():
    """win_pct should be 0.0 when games == 0, not raise ZeroDivisionError."""
    entry = ModelLeaderboardEntry(model_id="x")
    assert entry.win_pct == 0.0


def test_game_result_timezone_aware():
    """played_at should be timezone-aware (not naive UTC)."""
    r = make_result()
    assert r.played_at.tzinfo is not None


# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------

def test_api_leaderboard_empty(tmp_path):
    """GET /leaderboard returns 200 with empty standings when no games played."""
    from app.main import app, game_manager

    # Point the store at a temp path so this test doesn't touch real data
    original_store = game_manager.leaderboard
    game_manager.leaderboard = LeaderboardStore(path=tmp_path / "results.jsonl")

    try:
        client = TestClient(app)
        response = client.get("/leaderboard")
        assert response.status_code == 200
        data = response.json()
        assert data["total_games"] == 0
        assert data["by_model"] == []
        assert data["by_team"] == []
    finally:
        game_manager.leaderboard = original_store


def test_api_leaderboard_with_results(tmp_path):
    """GET /leaderboard returns aggregated standings after recording a game."""
    from app.main import app, game_manager

    original_store = game_manager.leaderboard
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    store.record(make_result())
    game_manager.leaderboard = store

    try:
        client = TestClient(app)
        response = client.get("/leaderboard")
        assert response.status_code == 200
        data = response.json()
        assert data["total_games"] == 1
        assert len(data["by_model"]) == 2
        assert len(data["by_team"]) == 2
        # win_pct must be present in serialized response
        winner = next(e for e in data["by_model"] if e["model_id"] == "model-a")
        assert "win_pct" in winner
        assert winner["wins"] == 1
    finally:
        game_manager.leaderboard = original_store
