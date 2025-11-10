#!/usr/bin/env python3
"""Run Ankh-Morpork Scramble with two Cline agents and a referee commentator.

This script:
1. Starts the FastAPI game server in the background
2. Launches two Cline instances (one per team) concurrently
3. Starts a referee agent that provides live commentary
4. Monitors tasks and auto-restarts them when complete
5. Logs each team's output to separate files (team1.log, team2.log, referee.log)

Usage:
    python run_game.py

Environment variables:
    OPENROUTER_API_KEY: Required - Your OpenRouter API key
    OPENROUTER_MODEL: Optional - Model for teams (default: google/gemini-2.5-flash)
    REFEREE_MODEL: Optional - Model for referee (default: anthropic/claude-3.5-haiku)
    REFEREE_COMMENTARY_INTERVAL: Optional - Seconds between commentary (default: 30)
    REFEREE_PROMPT: Optional - Custom referee prompt
    INTERACTIVE_GAME_ID: Optional - Game ID (default: interactive-game)
    DEMO_MODE: Optional - Use demo game (default: false)
    AGENT_LOG_LEVEL: Optional - Logging level (default: INFO)
    ENABLE_REFEREE: Optional - Enable referee commentary (default: true)
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()  # 

import httpx

from app.agents.config import AgentConfig
from app.agents.run_agent import ClineAgentRunner
from app.agents.referee import RefereeAgent, RefereeConfig


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


async def run_referee(config: RefereeConfig, log_file: Path) -> None:
    """Run the referee commentator agent.

    Args:
        config: Referee configuration
        log_file: Path to log file for referee output
    """
    global shutdown_requested

    # Set up logging for referee
    referee_logger = logging.getLogger("app.agents.referee")
    referee_logger.setLevel(getattr(logging, os.getenv("REFEREE_LOG_LEVEL", "INFO")))

    # Add file handler
    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    referee_logger.addHandler(file_handler)

    # Also log to console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("[referee] %(levelname)s: %(message)s")
    )
    referee_logger.addHandler(console_handler)

    referee_logger.info("Referee agent starting")
    referee_logger.info("Commentary interval: %.1fs", config.commentary_interval)
    referee_logger.info("Model: %s", config.model)

    referee = RefereeAgent(config, referee_logger)

    try:
        await referee.run()
    except asyncio.CancelledError:
        referee_logger.info("Referee agent cancelled, shutting down")
    except Exception as e:
        referee_logger.error("Referee error: %s", e, exc_info=True)

    referee_logger.info("Referee agent shut down")


def cleanup_previous_services(logger: logging.Logger) -> None:
    """Kill any previous game server, referee, or Cline instances and clean up directories.
    
    This ensures a clean start by:
    1. Killing processes on port 8000 (game server)
    2. Killing referee processes
    3. Killing Cline instances using team directories
    4. Removing old Cline data directories
    """
    logger.info("Cleaning up previous services...")
    
    # 1. Kill process on port 8000 (game server)
    try:
        result = subprocess.run(
            ["lsof", "-ti", ":8000"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                logger.info("Killing process on port 8000 (PID: %s)", pid)
                try:
                    subprocess.run(["kill", "-TERM", pid], timeout=2)
                    time.sleep(1)
                    # Force kill if still running
                    subprocess.run(["kill", "-9", pid], stderr=subprocess.DEVNULL, timeout=2)
                except subprocess.TimeoutExpired:
                    logger.warning("Timeout killing PID %s", pid)
    except FileNotFoundError:
        # lsof not available, try alternative method
        logger.debug("lsof not available, skipping port cleanup")
    except Exception as e:
        logger.warning("Error cleaning port 8000: %s", e)
    
    # 2. Kill referee processes
    try:
        result = subprocess.run(
            ["pgrep", "-f", "referee.py"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                logger.info("Killing referee process (PID: %s)", pid)
                try:
                    subprocess.run(["kill", "-TERM", pid], timeout=2)
                except subprocess.TimeoutExpired:
                    logger.warning("Timeout killing referee PID %s", pid)
    except FileNotFoundError:
        logger.debug("pgrep not available, skipping referee process cleanup")
    except Exception as e:
        logger.warning("Error killing referee processes: %s", e)
    
    # 3. Kill Cline instances using team directories
    for team_dir in ["/tmp/cline-team1", "/tmp/cline-team2"]:
        try:
            result = subprocess.run(
                ["pgrep", "-f", team_dir],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    logger.info("Killing Cline process %s using %s", pid, team_dir)
                    try:
                        subprocess.run(["kill", "-TERM", pid], timeout=2)
                    except subprocess.TimeoutExpired:
                        logger.warning("Timeout killing Cline PID %s", pid)
        except FileNotFoundError:
            logger.debug("pgrep not available, skipping Cline process cleanup")
        except Exception as e:
            logger.warning("Error killing Cline instances for %s: %s", team_dir, e)
    
    # Give processes time to die gracefully
    time.sleep(2)
    
    # 4. Clean up Cline directories
    for team_dir in ["/tmp/cline-team1", "/tmp/cline-team2"]:
        team_path = Path(team_dir)
        if team_path.exists():
            try:
                logger.info("Removing directory: %s", team_dir)
                shutil.rmtree(team_path)
            except Exception as e:
                logger.warning("Error removing %s: %s", team_dir, e)
    
    logger.info("Cleanup complete")


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

    # Clean up any previous services before starting
    cleanup_previous_services(logger)

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

        # Configure referee if enabled
        enable_referee = os.getenv("ENABLE_REFEREE", "true").lower() == "true"

        tasks = [
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
        ]

        if enable_referee:
            referee_config = RefereeConfig(
                game_id=game_id,
                api_base_url="http://localhost:8000",
                commentary_interval=float(os.getenv("REFEREE_COMMENTARY_INTERVAL", "30")),
                model=os.getenv("REFEREE_MODEL", "anthropic/claude-3.5-haiku"),
                api_key=api_key,
                custom_prompt=os.getenv("REFEREE_PROMPT"),
            )
            tasks.append(run_referee(referee_config, log_dir / "referee.log"))
            logger.info("Starting agents with referee commentary...")
        else:
            logger.info("Starting agents (referee disabled)...")

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

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
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Ankh-Morpork Scramble with AI agents")
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Only cleanup previous services and exit (don't start game)"
    )
    args = parser.parse_args()
    
    if args.cleanup_only:
        # Set up basic logging for cleanup
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        logger = logging.getLogger(__name__)
        
        logger.info("Running cleanup only...")
        cleanup_previous_services(logger)
        logger.info("Cleanup complete. Exiting.")
        sys.exit(0)
    
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
