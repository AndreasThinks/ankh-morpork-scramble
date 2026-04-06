import pytest
from app.models.leaderboard import GameResult, AgentLeaderboardEntry
from app.state.leaderboard_store import LeaderboardStore
from pathlib import Path

def make_versus_result(game_id, a1_id, a1_name, a2_id, a2_name, score1, score2):
    return GameResult(
        game_id=game_id,
        team1_name=a1_name, team1_model="gpt-4o", team1_score=score1,
        team2_name=a2_name, team2_model="claude-3", team2_score=score2,
        team1_agent_id=a1_id, team1_agent_name=a1_name,
        team2_agent_id=a2_id, team2_agent_name=a2_name,
    )

def test_agent_leaderboard_populated(tmp_path):
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    store.record(make_versus_result("g1", "a1", "BotA", "a2", "BotB", 3, 1))
    store.record(make_versus_result("g2", "a1", "BotA", "a2", "BotB", 1, 2))

    lb = store.get_leaderboard()
    assert len(lb.by_agent) == 2

    bota = next(e for e in lb.by_agent if e.agent_name == "BotA")
    assert bota.wins == 1
    assert bota.losses == 1
    assert bota.goals_for == 4
    assert bota.goals_against == 3

def test_arena_games_not_in_agent_leaderboard(tmp_path):
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    # Arena game — no agent_id fields
    store.record(GameResult(
        game_id="arena1",
        team1_name="CW", team1_model="gpt-4o", team1_score=2,
        team2_name="UU", team2_model="claude-3", team2_score=1,
    ))
    lb = store.get_leaderboard()
    assert lb.by_agent == []
    assert len(lb.by_model) == 2  # arena models still appear

def test_game_id_matches_state(tmp_path):
    """BUG-1 regression: GameResult game_id must match the actual game_id."""
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    result = make_versus_result("real-game-id", "a1", "BotA", "a2", "BotB", 1, 0)
    store.record(result)
    loaded = store.load_all()
    assert loaded[0].game_id == "real-game-id"
