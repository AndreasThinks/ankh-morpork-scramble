#!/usr/bin/env python3
"""Launch an Ankh-Morpork Scramble match with three Hermes agents.

Starts the FastAPI game server, then dispatches:
  - Two player agents (City Watch vs Unseen University)
  - One referee/commentator agent

Commentary appears in the web UI at http://192.168.4.57:8000/ui

Usage:
    cd ~/projects/ankh-morpork-scramble
    source .venv/bin/activate
    python run_hermes_game.py

The server runs in the background. Ctrl+C to stop everything.
"""
from __future__ import annotations

import subprocess
import sys
import time
import signal
import os
from pathlib import Path

import httpx

PROJECT_DIR = Path(__file__).parent
SERVER_URL = "http://localhost:8000"
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000


def start_server() -> subprocess.Popen:
    """Start the FastAPI game server in the background."""
    env = os.environ.copy()
    env["DEMO_MODE"] = "false"
    env["INTERACTIVE_GAME_ID"] = "the-match"
    env["TEAM1_NAME"] = "City Watch Constables"
    env["TEAM2_NAME"] = "Unseen University Adepts"
    env["CORS_ORIGINS"] = "*"

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", SERVER_HOST,
            "--port", str(SERVER_PORT),
        ],
        cwd=PROJECT_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(f"[server] Started (pid {proc.pid})")
    return proc


def wait_for_server(timeout: float = 60.0) -> None:
    """Block until the server responds or timeout."""
    print("[server] Waiting for server to be ready...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{SERVER_URL}/current-game", timeout=3)
            if r.status_code < 500:
                print("[server] Ready.")
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(f"Server did not become ready within {timeout}s")


PLAYER_CONTEXT = """You are playing a match of Ankh-Morpork Scramble.

YOUR TEAM:
  Team ID:   {team_id}
  Team Name: {team_name}

OPPONENT:
  Team ID:   {opp_id}
  Team Name: {opp_name}

Load the skill 'ankh-morpork-player' and follow it exactly to play the full match,
from SETUP (buying players and placing them) through PLAYING until the game concludes.

Set MY_TEAM_ID = "{team_id}" and MY_TEAM_NAME = "{team_name}" in your code.

The game server is at http://localhost:8000. The game ID is "the-match".
Use execute_code for all HTTP calls (requests library is available).

Stay in character. Post brief in-character messages after each turn.
When the game ends, post a final comment and stop.
"""

COMMENTATOR_CONTEXT = """You are the referee commentator for an Ankh-Morpork Scramble match.

Load the skill 'ankh-morpork-commentator' and follow it exactly.

The game server is at http://localhost:8000. The game ID is "the-match".
Use execute_code for all HTTP calls (requests library is available).

Wait for the game to move past SETUP before posting commentary.
Run until the game concludes, then post a final summary and stop.
"""


def dispatch_hermes_agents() -> None:
    """Dispatch the three Hermes subagents using hermes CLI."""
    # Team info
    teams = [
        {
            "team_id": "team1",
            "team_name": "City Watch Constables",
            "opp_id": "team2",
            "opp_name": "Unseen University Adepts",
        },
        {
            "team_id": "team2",
            "team_name": "Unseen University Adepts",
            "opp_id": "team1",
            "opp_name": "City Watch Constables",
        },
    ]

    procs = []

    for team in teams:
        context = PLAYER_CONTEXT.format(**team)
        label = f"[{team['team_name']}]"
        log_path = PROJECT_DIR / "logs" / f"{team['team_id']}_hermes.log"
        log_path.parent.mkdir(exist_ok=True)

        proc = subprocess.Popen(
            [
                "hermes", "chat",
                "-q", context,
                "-m", "qwen/qwen3-8b:free",
                "--provider", "openrouter",
                "-s", "ankh-morpork-player",
                "-Q",
            ],
            stdout=open(log_path, "w"),
            stderr=subprocess.STDOUT,
        )
        procs.append((label, proc, log_path))
        print(f"{label} dispatched (pid {proc.pid}) → {log_path}")
        time.sleep(2)  # Stagger starts slightly

    # Commentator
    log_path = PROJECT_DIR / "logs" / "referee_hermes.log"
    proc = subprocess.Popen(
        [
            "hermes", "chat",
            "-q", COMMENTATOR_CONTEXT,
            "-m", "qwen/qwen3-8b:free",
            "--provider", "openrouter",
            "-s", "ankh-morpork-commentator",
            "-Q",
        ],
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
    )
    procs.append(("[Referee]", proc, log_path))
    print(f"[Referee]  dispatched (pid {proc.pid}) → {log_path}")

    return procs


def main() -> None:
    server_proc = None
    agent_procs = []
    shutdown = [False]

    def handle_signal(sig, frame):
        print("\n[launcher] Shutting down...")
        shutdown[0] = True
        for label, proc, _ in agent_procs:
            try:
                proc.terminate()
                print(f"{label} terminated")
            except Exception:
                pass
        if server_proc:
            server_proc.terminate()
            print("[server] terminated")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Start server
    server_proc = start_server()
    wait_for_server()

    print(f"\nWeb UI: http://192.168.4.57:{SERVER_PORT}/ui")
    print(f"API docs: http://192.168.4.57:{SERVER_PORT}/docs\n")

    # Dispatch agents
    agent_procs = dispatch_hermes_agents()

    print("\nAll agents dispatched. Watching for completion...\n")
    print("Tail logs with:")
    for label, proc, log_path in agent_procs:
        print(f"  tail -f {log_path}")
    print()

    # Monitor until all agents finish or server dies
    while not shutdown[0]:
        if server_proc.poll() is not None:
            print("[server] Server died unexpectedly.")
            break

        all_done = all(p.poll() is not None for _, p, _ in agent_procs)
        if all_done:
            print("All agents have finished.")
            break

        time.sleep(5)

    handle_signal(None, None)


if __name__ == "__main__":
    main()
