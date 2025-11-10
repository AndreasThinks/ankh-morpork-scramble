#!/usr/bin/env python3
"""Run Ankh-Morpork Scramble with two Cline agents in a single Python process.

This script:
1. Starts the FastAPI game server in the background
2. Launches two Cline instances (one per team) concurrently
3. Monitors tasks and auto-restarts them when complete
4. Logs each team's output to separate files (team1.log, team2.log)

Usage:
    python run_game.py

Environment variables:
    OPENROUTER_API_KEY: Required - Your OpenRouter API key
    OPENROUTER_MODEL: Optional - Model to use (default: google/gemini-2.5-flash)
    INTERACTIVE_GAME_ID: Optional - Game ID (default: interactive-game)
    DEMO_MODE: Optional - Use demo game (default: false)
    AGENT_LOG_LEVEL: Optional - Logging level (default: INFO)
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

import httpx

from app.agents.config import AgentConfig
from app.agents.run_agent import ClineAgentRunner


# Global flag for graceful shutdown
shutdown_requested = False


async def wait_for_server(base_url: str, timeout: float = 60.0) -> None:
    """Wait for the game server to become available.

    Args:
        base_url: The HTTP base URL of the server
        timeout: Maximum time to wait in seconds

    Raises:
        RuntimeError: If the server doesn't become ready within timeout
    """
    logger = logging.getLogger(__name__)
    logger.info("Waiting for game server at %s...", base_url)

    deadline = asyncio.get_event_loop().time() + timeout
    async with httpx.AsyncClient() as client:
        while True:
            try:
                response = await client.get(base_url, timeout=5)
                if response.status_code < 500:
                    logger.info("Game server is ready!")
                    return
            except Exception:
                pass

            if asyncio.get_event_loop().time() > deadline:
                raise RuntimeError(f"Server at {base_url} did not become ready in {timeout}s")

            await asyncio.sleep(1)


async def run_agent_with_restart(
    config: AgentConfig,
    env: dict[str, str],
    cline_dir: Path,
    log_file: Path,
) -> None:
    """Run a Cline agent in a loop, restarting when tasks complete.

    Args:
        config: Agent configuration
        env: Environment variables for the agent
        cline_dir: Cline data directory
        log_file: Path to log file for this agent
    """
    global shutdown_requested

    # Set up logging for this agent
    agent_logger = logging.getLogger(f"app.agents.{config.team_id}")
    agent_logger.setLevel(getattr(logging, os.getenv("AGENT_LOG_LEVEL", "INFO")))

    # Add file handler
    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    agent_logger.addHandler(file_handler)

    # Also log to console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(f"[{config.team_id}] %(levelname)s: %(message)s")
    )
    agent_logger.addHandler(console_handler)

    agent_logger.info("Starting agent for %s (%s)", config.team_name, config.team_id)
    agent_logger.info("Logging to: %s", log_file)

    iteration = 0
    while not shutdown_requested:
        iteration += 1
        agent_logger.info("=" * 80)
        agent_logger.info("Starting iteration %d for %s", iteration, config.team_name)
        agent_logger.info("=" * 80)

        try:
            runner = ClineAgentRunner(
                config,
                env=env,
                cline_dir=cline_dir,
                agent_logger=agent_logger,
            )
            await runner.run()

            if shutdown_requested:
                break

            agent_logger.info("Task completed. Restarting in 5 seconds...")
            await asyncio.sleep(5)

        except asyncio.CancelledError:
            agent_logger.info("Agent cancelled, shutting down")
            break
        except Exception as e:
            agent_logger.error("Agent error: %s", e, exc_info=True)
            if shutdown_requested:
                break
            agent_logger.info("Restarting in 10 seconds...")
            await asyncio.sleep(10)

    agent_logger.info("Agent %s shutting down", config.team_id)


def start_game_server(game_id: str, demo_mode: bool = False, log_dir: Path = Path("logs")) -> subprocess.Popen:
    """Start the FastAPI game server as a subprocess.

    Args:
        game_id: The game ID to use
        demo_mode: Whether to use demo mode
        log_dir: Directory for log files

    Returns:
        The subprocess handle
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting game server (DEMO_MODE=%s, GAME_ID=%s)", demo_mode, game_id)

    env = os.environ.copy()
    env["DEMO_MODE"] = "true" if demo_mode else "false"
    env["INTERACTIVE_GAME_ID"] = game_id

    # Create log directory if it doesn't exist
    log_dir.mkdir(exist_ok=True)
    server_log_path = log_dir / "server.log"

    # Open log file for server output
    # This prevents pipe buffer deadlock that would occur if we used PIPE without reading
    server_log_file = open(server_log_path, "w")

    # Start uvicorn with output redirected to file
    process = subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        env=env,
        stdout=server_log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )

    logger.info("Game server started (PID: %d)", process.pid)
    logger.info("Server logs: %s", server_log_path)
    return process


async def main() -> int:
    """Main entry point."""
    global shutdown_requested

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Check required environment variables
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("openrouter_api_key")
    if not api_key:
        logger.error("OPENROUTER_API_KEY environment variable is required")
        return 1

    # Configuration
    game_id = os.getenv("INTERACTIVE_GAME_ID", "interactive-game")
    demo_mode = os.getenv("DEMO_MODE", "false").lower() == "true"
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")

    logger.info("=" * 80)
    logger.info("Ankh-Morpork Scramble - Dual Agent Runner")
    logger.info("=" * 80)
    logger.info("Game ID: %s", game_id)
    logger.info("Demo Mode: %s", demo_mode)
    logger.info("Model: %s", model)
    logger.info("=" * 80)

    # Create log directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Start game server (redirects output to logs/server.log)
    server_process = start_game_server(game_id, demo_mode, log_dir)

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        global shutdown_requested
        logger.info("Shutdown signal received, cleaning up...")
        shutdown_requested = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Wait for server to be ready
        await wait_for_server("http://localhost:8000", timeout=60.0)

        # Create configurations for both teams
        base_env = os.environ.copy()
        base_env["POSTHOG_TELEMETRY_ENABLED"] = "false"
        base_env["CLINE_DISABLE_AUTO_UPDATE"] = "1"
        base_env["CLINE_CLI_DISABLE_AUTO_UPDATE"] = "1"

        import json
        default_headers = json.dumps({
            "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "https://localhost"),
            "X-Title": os.getenv("OPENROUTER_APP_TITLE", "Ankh-Morpork Scramble Agents"),
        })
        base_env["OPENAI_DEFAULT_HEADERS"] = default_headers

        # Team 1 configuration
        team1_env = base_env.copy()
        team1_env["TEAM_ID"] = "team1"
        team1_env["TEAM_NAME"] = "City Watch Constables"
        team1_env["GAME_ID"] = game_id
        team1_env["MCP_SERVER_URL"] = "http://localhost:8000/mcp"
        team1_env["OPENROUTER_MODEL"] = model
        team1_env["OPENROUTER_API_KEY"] = api_key
        team1_env["openrouter_api_key"] = api_key
        team1_env["CLINE_DIR"] = "/tmp/cline-team1"

        config1 = AgentConfig(
            team_id="team1",
            team_name="City Watch Constables",
            game_id=game_id,
            mcp_server_url="http://localhost:8000/mcp",
            model=model,
            api_key=api_key,
        )

        # Team 2 configuration
        team2_env = base_env.copy()
        team2_env["TEAM_ID"] = "team2"
        team2_env["TEAM_NAME"] = "Unseen University Adepts"
        team2_env["GAME_ID"] = game_id
        team2_env["MCP_SERVER_URL"] = "http://localhost:8000/mcp"
        team2_env["OPENROUTER_MODEL"] = model
        team2_env["OPENROUTER_API_KEY"] = api_key
        team2_env["openrouter_api_key"] = api_key
        team2_env["CLINE_DIR"] = "/tmp/cline-team2"

        config2 = AgentConfig(
            team_id="team2",
            team_name="Unseen University Adepts",
            game_id=game_id,
            mcp_server_url="http://localhost:8000/mcp",
            model=model,
            api_key=api_key,
        )

        # Run both agents concurrently
        logger.info("Starting both agents...")
        await asyncio.gather(
            run_agent_with_restart(
                config1,
                team1_env,
                Path("/tmp/cline-team1"),
                log_dir / "team1.log",
            ),
            run_agent_with_restart(
                config2,
                team2_env,
                Path("/tmp/cline-team2"),
                log_dir / "team2.log",
            ),
        )

    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        return 1
    finally:
        # Clean up server process
        logger.info("Shutting down game server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Server didn't terminate, killing...")
            server_process.kill()
        logger.info("Cleanup complete")

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
