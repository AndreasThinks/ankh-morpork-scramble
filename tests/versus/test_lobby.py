import pytest, os
from unittest.mock import patch, MagicMock

@pytest.fixture
def lobby(tmp_path):
    with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
        from app.state.agent_registry import AgentRegistry, init_db
        from app.state.lobby import LobbyManager
        init_db()
        reg = AgentRegistry()
        gm = MagicMock()
        gm.create_game = MagicMock()
        gm.get_game = MagicMock(return_value=MagicMock(team1=MagicMock(name="t1"), team2=MagicMock(name="t2")))
        mgr = LobbyManager(gm)
        yield reg, mgr

def test_first_agent_waits(lobby):
    reg, mgr = lobby
    a1, _ = reg.register("AgentA")
    result = mgr.join(a1.agent_id)
    assert result["status"] == "waiting"
    assert result["poll_interval_seconds"] == 300

def test_second_agent_matches_deferred(lobby):
    """Match is deferred — no game_id until both agents ack."""
    reg, mgr = lobby
    a1, _ = reg.register("AgentA")
    a2, _ = reg.register("AgentB")
    mgr.join(a1.agent_id)
    result = mgr.join(a2.agent_id)
    assert result["status"] == "matched"
    assert result.get("game_id") is None  # deferred — no game yet
    assert result["scheduled_start"] is not None
    assert result["poll_interval_seconds"] == 30

def test_rejoin_while_matched_returns_existing(lobby):
    reg, mgr = lobby
    a1, _ = reg.register("AgentC")
    a2, _ = reg.register("AgentD")
    mgr.join(a1.agent_id)
    mgr.join(a2.agent_id)
    # A1 calls join again — should get existing matched state
    result = mgr.join(a1.agent_id)
    assert result["status"] == "matched"
    assert result["scheduled_start"] is not None

def test_leave_removes_waiting_agent(lobby):
    reg, mgr = lobby
    a1, _ = reg.register("AgentE")
    mgr.join(a1.agent_id)
    removed = mgr.leave(a1.agent_id)
    assert removed is True
    status = mgr.get_status(a1.agent_id)
    assert status["status"] == "not_in_lobby"

def test_leave_matched_agent_does_nothing(lobby):
    reg, mgr = lobby
    a1, _ = reg.register("AgentF")
    a2, _ = reg.register("AgentG")
    mgr.join(a1.agent_id)
    mgr.join(a2.agent_id)
    removed = mgr.leave(a1.agent_id)
    assert removed is False  # can't leave once matched

def test_ack_both_creates_game(lobby):
    """When both agents ack, the game is created."""
    reg, mgr = lobby
    a1, _ = reg.register("AgentH")
    a2, _ = reg.register("AgentI")
    mgr.join(a1.agent_id)
    mgr.join(a2.agent_id)
    # First ack — waiting for opponent
    r1 = mgr.ack(a1.agent_id)
    assert r1["status"] == "waiting_for_opponent"
    # Second ack — game created
    r2 = mgr.ack(a2.agent_id)
    assert r2["status"] == "playing"
    assert r2["game_id"] is not None

def test_ack_not_matched(lobby):
    """Acking when not matched returns not_matched."""
    reg, mgr = lobby
    a1, _ = reg.register("AgentJ")
    mgr.join(a1.agent_id)
    result = mgr.ack(a1.agent_id)
    assert result["status"] == "not_matched"

def test_cancel_match(lobby):
    """Cancel removes both agents from lobby."""
    reg, mgr = lobby
    a1, _ = reg.register("AgentK")
    a2, _ = reg.register("AgentL")
    mgr.join(a1.agent_id)
    mgr.join(a2.agent_id)
    mgr.cancel_match(a1.agent_id, a2.agent_id)
    assert mgr.get_status(a1.agent_id)["status"] == "not_in_lobby"
    assert mgr.get_status(a2.agent_id)["status"] == "not_in_lobby"

def test_forfeit_unacked(lobby):
    """Forfeit re-queues the acked agent."""
    reg, mgr = lobby
    a1, _ = reg.register("AgentM")
    a2, _ = reg.register("AgentN")
    mgr.join(a1.agent_id)
    mgr.join(a2.agent_id)
    mgr.ack(a1.agent_id)
    mgr.forfeit_unacked(a2.agent_id, a1.agent_id)
    assert mgr.get_status(a2.agent_id)["status"] == "not_in_lobby"
    assert mgr.get_status(a1.agent_id)["status"] == "waiting"

def test_status_includes_poll_interval(lobby):
    """Status responses include poll_interval_seconds."""
    reg, mgr = lobby
    a1, _ = reg.register("AgentO")
    a2, _ = reg.register("AgentP")
    mgr.join(a1.agent_id)
    s1 = mgr.get_status(a1.agent_id)
    assert s1["poll_interval_seconds"] == 300
    mgr.join(a2.agent_id)
    s2 = mgr.get_status(a1.agent_id)
    assert s2["poll_interval_seconds"] == 30
    assert s2["scheduled_start"] is not None
