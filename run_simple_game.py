#!/usr/bin/env python3
"""
Ankh-Morpork Scramble — simple agent runner.

Starts the game server then drives two LLM player agents and a commentator
through a full match via direct OpenRouter API calls. No Hermes agents.

Configuration via environment variables (all optional):
  TEAM1_MODEL, TEAM2_MODEL, COMMENTATOR_MODEL  — model IDs (default: qwen/qwen3.6-plus:free)
  TEAM1_PROMPT, TEAM2_PROMPT                   — custom system prompts
  SERVER_PORT                                  — default 8000
  GAME_ID                                      — default "the-match"

Usage:
  cd ~/projects/ankh-morpork-scramble
  uv run run_simple_game.py

Watch at: http://192.168.4.57:8000/ui
"""
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests

# ── logging ────────────────────────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/simple_game.log"),
    ],
)
logger = logging.getLogger("launcher")

# ── config ─────────────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent
PORT = os.getenv("PORT") or os.getenv("SERVER_PORT", "8000")
SERVER_URL = f"http://localhost:{PORT}"
GAME_ID = os.getenv("GAME_ID", "the-match")

TEAM_CONFIGS = {
    "team1": {
        "team_id": "team1",
        "team_name": "City Watch Constables",
        "model": os.getenv("TEAM1_MODEL", "qwen/qwen3.6-plus:free"),
        "system_prompt": os.getenv("TEAM1_PROMPT"),  # None → default in player.py
    },
    "team2": {
        "team_id": "team2",
        "team_name": "Unseen University Adepts",
        "model": os.getenv("TEAM2_MODEL", "qwen/qwen3.6-plus:free"),
        "system_prompt": os.getenv("TEAM2_PROMPT"),
    },
}
COMMENTATOR_MODEL = os.getenv("COMMENTATOR_MODEL", "qwen/qwen3.6-plus:free")

# ── server ─────────────────────────────────────────────────────────────────

def start_server() -> subprocess.Popen:
    env = os.environ.copy()
    env.update({"DEMO_MODE": "false", "INTERACTIVE_GAME_ID": GAME_ID, "CORS_ORIGINS": "*"})
    proc = subprocess.Popen(
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", PORT],
        cwd=PROJECT_DIR, env=env,
        stdout=open("logs/server.log", "w"),
        stderr=subprocess.STDOUT,
    )
    logger.info(f"Server started (pid {proc.pid})")
    return proc


def wait_for_server(timeout: float = 60.0) -> None:
    logger.info("Waiting for server...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(f"{SERVER_URL}/current-game", timeout=3).status_code < 500:
                logger.info("Server ready.")
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Server did not become ready in time.")

# ── setup phase ─────────────────────────────────────────────────────────────

def run_setup() -> None:
    from simple_agents.player import setup_team

    logger.info("=== SETUP PHASE ===")
    for cfg in TEAM_CONFIGS.values():
        setup_team(
            game_id=GAME_ID,
            team_id=cfg["team_id"],
            team_name=cfg["team_name"],
            model=cfg["model"],
            base_url=SERVER_URL,
        )

    # Wait for both teams ready, then kick off
    logger.info("Waiting for both teams to be ready...")
    for _ in range(30):
        state = requests.get(f"{SERVER_URL}/game/{GAME_ID}").json()
        if state.get("team1_ready") and state.get("team2_ready"):
            r = requests.post(f"{SERVER_URL}/game/{GAME_ID}/start")
            if r.status_code == 200:
                logger.info("Game started!")
                return
        time.sleep(2)
    raise RuntimeError("Teams never became ready — check server logs.")

# ── main game loop ──────────────────────────────────────────────────────────

def run_game() -> None:
    from simple_agents.player import play_turn
    from simple_agents.commentator import comment, final_comment

    logger.info("=== GAME LOOP ===")

    last_event_count = 0
    team1_played = False
    team2_played = False

    while True:
        state = requests.get(f"{SERVER_URL}/game/{GAME_ID}").json()
        phase = state["phase"]

        if phase in ("concluded", "finished"):
            logger.info("Game concluded.")
            final_comment(GAME_ID, state, COMMENTATOR_MODEL, SERVER_URL)
            break

        if phase in ("setup",):
            time.sleep(1)
            continue

        turn = state.get("turn") or {}
        active_team_id = turn.get("active_team_id")
        cfg = TEAM_CONFIGS.get(active_team_id)
        if not cfg:
            time.sleep(1)
            continue

        play_turn(
            game_id=GAME_ID,
            team_id=cfg["team_id"],
            team_name=cfg["team_name"],
            state=state,
            model=cfg["model"],
            system_prompt=cfg.get("system_prompt"),
            base_url=SERVER_URL,
        )

        if active_team_id == "team1":
            team1_played = True
        elif active_team_id == "team2":
            team2_played = True

        # Commentator fires once per round, after both teams have played
        if team1_played and team2_played:
            fresh_state = requests.get(f"{SERVER_URL}/game/{GAME_ID}").json()
            all_events = fresh_state.get("events") or []
            new_events = all_events[last_event_count:]
            last_event_count = len(all_events)
            comment(GAME_ID, fresh_state, new_events, COMMENTATOR_MODEL, SERVER_URL)
            team1_played = team2_played = False

        time.sleep(0.3)

# ── entrypoint ──────────────────────────────────────────────────────────────

def main() -> None:
    server_proc = None

    def shutdown(sig=None, frame=None):
        logger.info("Shutting down...")
        if server_proc:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    server_proc = start_server()
    wait_for_server()
    logger.info(f"Web UI:   http://192.168.4.57:{PORT}/ui")
    logger.info(f"API docs: http://192.168.4.57:{PORT}/docs")

    run_setup()
    run_game()
    shutdown()


if __name__ == "__main__":
    main()
