import os
import pytest

from app.agents.config import AgentConfig, _get_env


def test_get_env_returns_first_set():
    """Test _get_env returns first environment variable that is set"""
    os.environ["TEST_VAR_1"] = "value1"
    os.environ["TEST_VAR_2"] = "value2"

    result = _get_env("TEST_VAR_MISSING", "TEST_VAR_1", "TEST_VAR_2")
    assert result == "value1"

    # Cleanup
    del os.environ["TEST_VAR_1"]
    del os.environ["TEST_VAR_2"]


def test_get_env_returns_default_when_none_set():
    """Test _get_env returns default when no env vars are set"""
    result = _get_env("MISSING_VAR_1", "MISSING_VAR_2", default="default_value")
    assert result == "default_value"


def test_get_env_returns_none_when_no_default():
    """Test _get_env returns None when no vars set and no default"""
    result = _get_env("MISSING_VAR_1", "MISSING_VAR_2")
    assert result is None


def test_agent_config_from_env_missing_team_id():
    """Test AgentConfig.from_env raises error when TEAM_ID is missing"""
    # Clear relevant env vars
    old_team_id = os.environ.pop("TEAM_ID", None)
    old_api_key = os.environ.pop("openrouter_api_key", None)
    old_api_key_upper = os.environ.pop("OPENROUTER_API_KEY", None)

    with pytest.raises(RuntimeError, match="TEAM_ID environment variable is required"):
        AgentConfig.from_env()

    # Restore
    if old_team_id:
        os.environ["TEAM_ID"] = old_team_id
    if old_api_key:
        os.environ["openrouter_api_key"] = old_api_key
    if old_api_key_upper:
        os.environ["OPENROUTER_API_KEY"] = old_api_key_upper


def test_agent_config_from_env_missing_api_key():
    """Test AgentConfig.from_env raises error when API key is missing"""
    # Set required TEAM_ID but clear API keys
    os.environ["TEAM_ID"] = "test_team"
    old_api_key = os.environ.pop("openrouter_api_key", None)
    old_api_key_upper = os.environ.pop("OPENROUTER_API_KEY", None)

    with pytest.raises(RuntimeError, match="openrouter_api_key.*environment variable is required"):
        AgentConfig.from_env()

    # Restore
    del os.environ["TEAM_ID"]
    if old_api_key:
        os.environ["openrouter_api_key"] = old_api_key
    if old_api_key_upper:
        os.environ["OPENROUTER_API_KEY"] = old_api_key_upper


def test_agent_config_from_env_with_all_vars():
    """Test AgentConfig.from_env loads all environment variables correctly"""
    # Set all env vars
    os.environ["TEAM_ID"] = "test_team"
    os.environ["TEAM_NAME"] = "Test Team"
    os.environ["GAME_ID"] = "test_game"
    os.environ["MCP_SERVER_URL"] = "http://test:8000/mcp"
    os.environ["OPENROUTER_MODEL"] = "test/model"
    os.environ["openrouter_api_key"] = "test_key"
    os.environ["OPENROUTER_BASE_URL"] = "https://test.example.com/api"
    os.environ["OPENROUTER_REFERER"] = "https://test.example.com"
    os.environ["OPENROUTER_APP_TITLE"] = "Test App"
    os.environ["JOIN_RETRY_DELAY"] = "2.5"
    os.environ["POLL_INTERVAL"] = "3.5"
    os.environ["POST_TURN_DELAY"] = "4.5"
    os.environ["SERVER_STARTUP_TIMEOUT"] = "30"
    os.environ["MAX_AGENT_STEPS"] = "20"
    os.environ["AGENT_MEMORY_WINDOW"] = "10"

    config = AgentConfig.from_env()

    assert config.team_id == "test_team"
    assert config.team_name == "Test Team"
    assert config.game_id == "test_game"
    assert config.mcp_server_url == "http://test:8000/mcp"
    assert config.model == "test/model"
    assert config.api_key == "test_key"
    assert config.base_url == "https://test.example.com/api"
    assert config.http_referer == "https://test.example.com"
    assert config.app_title == "Test App"
    assert config.join_retry_delay == 2.5
    assert config.poll_interval == 3.5
    assert config.post_turn_delay == 4.5
    assert config.startup_timeout == 30.0
    assert config.max_steps == 20
    assert config.memory_window == 10

    # Cleanup
    for key in ["TEAM_ID", "TEAM_NAME", "GAME_ID", "MCP_SERVER_URL", "OPENROUTER_MODEL",
                "openrouter_api_key", "OPENROUTER_BASE_URL", "OPENROUTER_REFERER",
                "OPENROUTER_APP_TITLE", "JOIN_RETRY_DELAY", "POLL_INTERVAL",
                "POST_TURN_DELAY", "SERVER_STARTUP_TIMEOUT", "MAX_AGENT_STEPS",
                "AGENT_MEMORY_WINDOW"]:
        os.environ.pop(key, None)


def test_agent_config_from_env_with_defaults():
    """Test AgentConfig.from_env uses default values when vars not set"""
    os.environ["TEAM_ID"] = "test_team"
    os.environ["openrouter_api_key"] = "test_key"

    # Clear optional vars
    for key in ["TEAM_NAME", "GAME_ID", "MCP_SERVER_URL", "OPENROUTER_MODEL"]:
        os.environ.pop(key, None)

    config = AgentConfig.from_env()

    assert config.team_id == "test_team"
    assert config.team_name == "test_team"  # Defaults to team_id
    assert config.game_id == "demo-game"  # Default
    assert config.mcp_server_url == "http://game-server:8000/mcp"  # Default
    assert config.model == "openrouter/auto"  # Default

    # Cleanup
    del os.environ["TEAM_ID"]
    del os.environ["openrouter_api_key"]


def test_agent_config_team_direction_team1():
    """Test team_direction returns +1 for team1"""
    config = AgentConfig(
        team_id="team1",
        team_name="Team 1",
        game_id="test",
        mcp_server_url="http://test:8000/mcp",
        model="test/model",
        api_key="key"
    )

    assert config.team_direction == 1


def test_agent_config_team_direction_team2():
    """Test team_direction returns -1 for team2"""
    config = AgentConfig(
        team_id="team2",
        team_name="Team 2",
        game_id="test",
        mcp_server_url="http://test:8000/mcp",
        model="test/model",
        api_key="key"
    )

    assert config.team_direction == -1


def test_agent_config_http_base_url_with_mcp():
    """Test http_base_url strips /mcp suffix"""
    config = AgentConfig(
        team_id="team1",
        team_name="Team 1",
        game_id="test",
        mcp_server_url="http://test:8000/mcp",
        model="test/model",
        api_key="key"
    )

    assert config.http_base_url == "http://test:8000"


def test_agent_config_http_base_url_without_mcp():
    """Test http_base_url returns URL as-is without /mcp suffix"""
    config = AgentConfig(
        team_id="team1",
        team_name="Team 1",
        game_id="test",
        mcp_server_url="http://test:8000",
        model="test/model",
        api_key="key"
    )

    assert config.http_base_url == "http://test:8000"
