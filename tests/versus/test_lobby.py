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

def test_second_agent_matches(lobby):
    reg, mgr = lobby
    a1, _ = reg.register("AgentA")
    a2, _ = reg.register("AgentB")
    mgr.join(a1.agent_id)
    result = mgr.join(a2.agent_id)
    assert result["status"] == "matched"
    assert result["game_id"] is not None
    assert result["team_id"] in ("team1", "team2")

def test_rejoin_while_matched_returns_existing(lobby):
    reg, mgr = lobby
    a1, _ = reg.register("AgentC")
    a2, _ = reg.register("AgentD")
    mgr.join(a1.agent_id)
    mgr.join(a2.agent_id)
    # A1 calls join again — should get existing state, not re-queue
    result = mgr.join(a1.agent_id)
    assert result["status"] == "matched"
    assert result["game_id"] is not None

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
