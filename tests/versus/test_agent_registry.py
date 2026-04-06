import pytest, os, tempfile
from unittest.mock import patch
from pathlib import Path

@pytest.fixture
def registry(tmp_path):
    with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
        from app.state.agent_registry import AgentRegistry, init_db
        init_db()
        yield AgentRegistry()

def test_register_new_agent(registry):
    identity, token = registry.register("TestBot", "gpt-4o")
    assert identity.name == "TestBot"
    assert token.startswith("ams_")
    assert len(token) == 36

def test_register_duplicate_name_raises(registry):
    registry.register("DupeBot")
    with pytest.raises(ValueError, match="already taken"):
        registry.register("DupeBot")

def test_resolve_token_valid(registry):
    identity, token = registry.register("TokenBot")
    resolved = registry.resolve_token(token)
    assert resolved is not None
    assert resolved.agent_id == identity.agent_id

def test_resolve_token_invalid(registry):
    assert registry.resolve_token("ams_notreal00000000000000000000000") is None

def test_resolve_token_prefix_fast_path(registry):
    """Token lookup uses prefix index — invalid prefix returns None immediately."""
    identity, token = registry.register("PrefixBot")
    bad_token = "ams_" + "x" * 32
    assert registry.resolve_token(bad_token) is None

def test_name_taken(registry):
    registry.register("TakenBot")
    assert registry.name_taken("TakenBot") is True
    assert registry.name_taken("FreeBot") is False

def test_name_too_short_raises(registry):
    with pytest.raises(ValueError):
        registry.register("X")

def test_name_too_long_raises(registry):
    with pytest.raises(ValueError):
        registry.register("A" * 33)
