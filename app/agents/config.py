"""Configuration helpers for containerised Cline CLI agents."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


def _get_env(*keys: str, default: Optional[str] = None) -> Optional[str]:
    """Return the first environment variable that is set."""

    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return default


@dataclass(slots=True)
class AgentConfig:
    """Runtime configuration for a single MCP agent container."""

    team_id: str
    team_name: str
    game_id: str
    mcp_server_url: str
    model: str
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    http_referer: str = "https://github.com/AndreasThinks/ankh-morpork-scramble"
    app_title: str = "Ankh-Morpork Scramble Agent"
    join_retry_delay: float = 3.0
    poll_interval: float = 5.0
    post_turn_delay: float = 8.0
    startup_timeout: float = 60.0
    max_steps: int = 12
    memory_window: int = 6

    @property
    def team_direction(self) -> int:
        """Return +1 for team1 (moves right) or -1 for everyone else."""

        return 1 if self.team_id.lower() == "team1" else -1

    @property
    def http_base_url(self) -> str:
        """Derive the HTTP base URL from the MCP endpoint."""

        endpoint = self.mcp_server_url.rstrip("/")
        if endpoint.endswith("/mcp"):
            return endpoint[: -len("/mcp")]
        return endpoint

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables."""

        team_id = _get_env("TEAM_ID")
        if not team_id:
            raise RuntimeError("TEAM_ID environment variable is required")

        team_name = _get_env("TEAM_NAME", default=team_id)
        game_id = _get_env("GAME_ID", default="demo-game")
        mcp_server_url = _get_env("MCP_SERVER_URL", default="http://game-server:8000/mcp")
        model = _get_env("OPENROUTER_MODEL", default="openrouter/auto")
        api_key = _get_env("openrouter_api_key", "OPENROUTER_API_KEY")

        if not api_key:
            raise RuntimeError(
                "openrouter_api_key (or OPENROUTER_API_KEY) environment variable is required"
            )

        base_url = _get_env("OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1")
        http_referer = _get_env("OPENROUTER_REFERER", default="https://example.com")
        app_title = _get_env("OPENROUTER_APP_TITLE", default="Ankh-Morpork Scramble Agents")

        join_retry_delay = float(_get_env("JOIN_RETRY_DELAY", default="3"))
        poll_interval = float(_get_env("POLL_INTERVAL", default="5"))
        post_turn_delay = float(_get_env("POST_TURN_DELAY", default="8"))
        startup_timeout = float(_get_env("SERVER_STARTUP_TIMEOUT", default="60"))
        max_steps = int(_get_env("MAX_AGENT_STEPS", default="12"))
        memory_window = int(_get_env("AGENT_MEMORY_WINDOW", default="6"))

        return cls(
            team_id=team_id,
            team_name=team_name,
            game_id=game_id,
            mcp_server_url=mcp_server_url,
            model=model,
            api_key=api_key,
            base_url=base_url,
            http_referer=http_referer,
            app_title=app_title,
            join_retry_delay=join_retry_delay,
            poll_interval=poll_interval,
            post_turn_delay=post_turn_delay,
            startup_timeout=startup_timeout,
            max_steps=max_steps,
            memory_window=memory_window,
        )
