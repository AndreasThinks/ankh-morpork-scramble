"""Tests for the autonomous Cline agent runner helpers."""
from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace

import pytest

from app.agents.config import AgentConfig
from app.agents import run_agent


def _make_config(**overrides) -> AgentConfig:
    """Return a minimal :class:`AgentConfig` for test scenarios."""

    base = {
        "team_id": "team1",
        "team_name": "City Watch",
        "game_id": "demo",
        "mcp_server_url": "http://example.com/mcp",
        "model": "test-model",
        "api_key": "super-secret",
    }
    base.update(overrides)
    return AgentConfig(**base)


@pytest.mark.asyncio
async def test_wait_for_server_success(monkeypatch):
    """A healthy response should return immediately without sleeping."""

    calls: list[tuple[str, float]] = []

    class DummyClient:
        async def __aenter__(self):  # pragma: no cover - exercised via context manager
            return self

        async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - exercised via context manager
            return False

        async def get(self, url: str, timeout: float):
            calls.append((url, timeout))
            return SimpleNamespace(status_code=200)

    async def no_sleep(_seconds: float) -> None:
        await asyncio.sleep(0)

    monkeypatch.setattr(run_agent.httpx, "AsyncClient", lambda: DummyClient())
    monkeypatch.setattr(run_agent.asyncio, "sleep", no_sleep)

    await run_agent._wait_for_server("http://example.com", timeout=5)

    assert calls == [("http://example.com", 5)]


@pytest.mark.asyncio
async def test_wait_for_server_timeout(monkeypatch):
    """If the server never responds, a RuntimeError should be raised once the deadline passes."""

    class DummyLoop:
        def __init__(self):
            self.current = 0.0

        def time(self) -> float:
            return self.current

    loop = DummyLoop()

    async def fast_sleep(seconds: float):
        loop.current += seconds

    class FailingClient:
        async def __aenter__(self):  # pragma: no cover - exercised via context manager
            return self

        async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover - exercised via context manager
            return False

        async def get(self, *_args, **_kwargs):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(run_agent.httpx, "AsyncClient", lambda: FailingClient())
    monkeypatch.setattr(run_agent.asyncio, "sleep", fast_sleep)
    monkeypatch.setattr(run_agent.asyncio, "get_event_loop", lambda: loop)

    with pytest.raises(RuntimeError):
        await run_agent._wait_for_server("http://never-up", timeout=3)


@pytest.mark.asyncio
async def test_start_instance_error_includes_output(tmp_path, monkeypatch, caplog):
    """When instance creation fails, the error should surface the CLI output."""

    config = _make_config(api_key="top-secret")
    runner = run_agent.ClineAgentRunner(
        config,
        env={},
        cline_dir=tmp_path,
        agent_logger=logging.getLogger("test.agent"),
    )

    class FailingProcess:
        returncode = 1

        async def communicate(self):
            return (b"Error: token top-secret invalid", None)

    async def fake_subprocess_exec(*_args, **_kwargs):
        return FailingProcess()

    monkeypatch.setattr(run_agent.asyncio, "create_subprocess_exec", fake_subprocess_exec)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError) as exc:
            await runner._start_instance()

    message = str(exc.value)
    assert "Output" in message
    assert "[REDACTED]" in message  # API key should be masked
    assert "Failed to start instance" in caplog.text


def test_ensure_prerequisites_creates_directories(tmp_path, monkeypatch):
    """The runner should validate the CLI and create the data directory structure."""

    config = _make_config()
    env: dict[str, str] = {}
    cline_dir = tmp_path / "cline"
    logger = logging.getLogger("test.agent")

    monkeypatch.setattr(run_agent.shutil, "which", lambda name: "/usr/bin/cline" if name == "cline" else None)

    runner = run_agent.ClineAgentRunner(config, env=env, cline_dir=cline_dir, agent_logger=logger)
    runner._ensure_prerequisites()

    assert cline_dir.exists()
    assert (cline_dir / "data" / "settings").exists()


def test_ensure_prerequisites_requires_cline(tmp_path, monkeypatch):
    """A helpful error is raised when the cline executable cannot be found."""

    config = _make_config()
    runner = run_agent.ClineAgentRunner(
        config,
        env={},
        cline_dir=tmp_path / "cline",
        agent_logger=logging.getLogger("test.agent"),
    )

    monkeypatch.setattr(run_agent.shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError):
        runner._ensure_prerequisites()


def test_write_mcp_settings(tmp_path, monkeypatch):
    """The MCP configuration file should contain the expected server configuration."""

    config = _make_config(mcp_server_url="http://localhost:8000/mcp")
    runner = run_agent.ClineAgentRunner(
        config,
        env={},
        cline_dir=tmp_path,
        agent_logger=logging.getLogger("test.agent"),
    )

    monkeypatch.setattr(run_agent.shutil, "which", lambda _name: "/usr/bin/cline")
    runner._ensure_prerequisites()
    runner._write_mcp_settings()

    settings_path = tmp_path / "data" / "settings" / "cline_mcp_settings.json"
    settings = json.loads(settings_path.read_text())

    assert run_agent.MCP_SERVER_NAME in settings["mcpServers"]
    entry = settings["mcpServers"][run_agent.MCP_SERVER_NAME]
    assert entry["url"] == "http://localhost:8000/mcp"
    assert "join_game" in entry["alwaysAllow"]
    assert "buy_player" in entry["alwaysAllow"]
    assert "place_players" in entry["alwaysAllow"]


def test_prompt_includes_team_details():
    """Ensure the generated prompt contains identifying details and direction guidance."""

    config = _make_config(team_name="Seamstresses", team_id="team2")
    runner = run_agent.ClineAgentRunner(
        config,
        env={},
        cline_dir=run_agent.Path("/tmp"),
        agent_logger=logging.getLogger("test.agent"),
    )

    prompt = runner._build_prompt()

    assert "Seamstresses" in prompt
    assert "team2" in prompt
    assert "decrease the x coordinate" in prompt
    assert "buy_player" in prompt
    assert "ready_to_play" in prompt


def test_secret_masking():
    """Both argument and log masking should redact API keys."""

    config = _make_config()
    runner = run_agent.ClineAgentRunner(
        config,
        env={},
        cline_dir=run_agent.Path("/tmp"),
        agent_logger=logging.getLogger("test.agent"),
    )

    masked_arg = runner._mask_argument("--apikey=" + config.api_key, mask_args=[config.api_key])
    masked_text = runner._mask_text(f"token={config.api_key}")

    assert "[REDACTED]" in masked_arg
    assert "[REDACTED]" in masked_text
