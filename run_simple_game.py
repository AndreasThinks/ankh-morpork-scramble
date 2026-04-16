#!/usr/bin/env python3
"""
Ankh-Morpork Scramble — simple agent runner.

Starts the game server then drives two LLM player agents and a commentator
through a full match via direct OpenRouter API calls. No Hermes agents.

Configuration via environment variables (all optional):
  TEAM1_MODEL, TEAM2_MODEL, COMMENTATOR_MODEL  — model IDs (default: qwen/qwen3-8b:free)
  TEAM1_PROMPT, TEAM2_PROMPT                   — custom system prompts
  SERVER_PORT                                  — default 8000
  GAME_ID                                      — default "the-match"

Usage:
  cd ~/projects/ankh-morpork-scramble
  uv run run_simple_game.py

Watch at: http://192.168.4.57:8000/ui
"""
import concurrent.futures
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
        "model": os.getenv("TEAM1_MODEL", "google/gemma-3-12b-it:free"),
        "system_prompt": os.getenv("TEAM1_PROMPT"),  # None → default in player.py
    },
    "team2": {
        "team_id": "team2",
        "team_name": "Unseen University Adepts",
        "model": os.getenv("TEAM2_MODEL", "google/gemma-3-12b-it:free"),
        "system_prompt": os.getenv("TEAM2_PROMPT"),
    },
}
COMMENTATOR_MODEL = os.getenv("COMMENTATOR_MODEL", "google/gemma-3-12b-it:free")

# Use the tournament model picker unless TEAM1_MODEL / TEAM2_MODEL are set AND
# OPENROUTER_MODELS is NOT set.  If OPENROUTER_MODELS is present it always wins —
# that's the explicit tournament pool and it should override per-team defaults.
_MANUAL_MODEL_OVERRIDE = bool(
    (os.getenv("TEAM1_MODEL") or os.getenv("TEAM2_MODEL"))
    and not os.getenv("OPENROUTER_MODELS")
)

# ── service status helper ─────────────────────────────────────────────────

_last_published_status: str | None = None


def _publish_service_status(status: str, reason: str | None = None) -> None:
    """Push the current service status to the API so the UI can react.

    Admin key is read from ADMIN_API_KEY env var; if unset, we log and skip.
    """
    global _last_published_status
    if status == _last_published_status:
        return
    admin_key = os.getenv("ADMIN_API_KEY")
    if not admin_key:
        logger.warning(
            "_publish_service_status(%s): ADMIN_API_KEY unset — cannot notify server.", status,
        )
        _last_published_status = status
        return
    try:
        r = requests.post(
            f"{SERVER_URL}/admin/service-status",
            params={"status": status, "reason": reason or ""},
            headers={"X-Admin-Key": admin_key},
            timeout=5,
        )
        if r.status_code < 400:
            logger.info("_publish_service_status: %s → server OK", status)
            _last_published_status = status
        else:
            logger.warning("_publish_service_status: server returned %d: %s", r.status_code, r.text[:200])
    except Exception as exc:
        logger.warning("_publish_service_status: failed to notify server: %s", exc)


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

# Maximum time allowed for the entire setup phase (buy + place + ready + start).
# If setup stalls beyond this — e.g. call_llm burning retries while rate-limited —
# the outer loop catches the TimeoutError and restarts cleanly.
SETUP_TIMEOUT_SECONDS = 8 * 60  # 8 minutes


# ── setup phase ─────────────────────────────────────────────────────────────

def _run_setup_inner() -> None:
    """Core setup logic — buy rosters, place players, start game."""
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
            # Pass model names to /start endpoint
            r = requests.post(
                f"{SERVER_URL}/game/{GAME_ID}/start",
                params={
                    "team1_model": TEAM_CONFIGS["team1"]["model"],
                    "team2_model": TEAM_CONFIGS["team2"]["model"],
                }
            )
            if r.status_code == 200:
                logger.info("Game started!")
                return
        time.sleep(2)
    raise RuntimeError("Teams never became ready — check server logs.")


def run_setup() -> None:
    """Run setup with a hard wall-clock timeout.

    Wraps _run_setup_inner() in a thread so that if setup stalls — e.g. because
    call_llm is burning retry backoff while the rate limit is saturated — we
    surface a TimeoutError after SETUP_TIMEOUT_SECONDS instead of hanging
    indefinitely and going silent.  Models still get their full retry budget;
    the timeout only fires if the *entire* setup phase can't complete in time.
    """
    logger.info(
        "Starting setup (timeout=%ds / %.0fmin).",
        SETUP_TIMEOUT_SECONDS, SETUP_TIMEOUT_SECONDS / 60,
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_setup_inner)
        try:
            future.result(timeout=SETUP_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(
                f"run_setup() exceeded {SETUP_TIMEOUT_SECONDS}s — "
                "likely stalled on LLM retries during roster build. "
                "Outer loop will restart."
            )

# ── main game loop ──────────────────────────────────────────────────────────

def run_game() -> None:
    from simple_agents.player import play_turn
    from simple_agents.commentator import comment, final_comment, set_commentator_model
    from simple_agents.model_picker import get_fallback_model, mark_model_dead, get_service_status, validate_pool

    # Initialise the commentator's live model for this match so it can swap internally.
    set_commentator_model(COMMENTATOR_MODEL)

    logger.info("=== GAME LOOP ===")

    last_event_count = 0
    # Track consecutive LLM-failed turns per team, plus models already tried,
    # so we can hot-swap a team's model when it keeps erroring out.
    consecutive_llm_failures: dict[str, int] = {"team1": 0, "team2": 0}
    tried_models: dict[str, set[str]] = {
        "team1": {TEAM_CONFIGS["team1"]["model"]},
        "team2": {TEAM_CONFIGS["team2"]["model"]},
    }
    SWAP_AFTER_FAILURES = 2

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

        # If credits ran out mid-game, periodically re-probe instead of dying permanently.
        if get_service_status() == "out_of_credits":
            logger.info("Game loop: out_of_credits — re-validating pool in 60s...")
            time.sleep(60)
            validate_pool(force=True)
            new_status = get_service_status()
            _publish_service_status(new_status)
            if new_status != "ok":
                continue  # Still dead, keep waiting
            logger.info("Game loop: credits restored — resuming play.")

        turn = state.get("turn") or {}
        active_team_id = turn.get("active_team_id")
        cfg = TEAM_CONFIGS.get(active_team_id)
        if not cfg:
            time.sleep(1)
            continue

        result = play_turn(
            game_id=GAME_ID,
            team_id=cfg["team_id"],
            team_name=cfg["team_name"],
            state=state,
            model=cfg["model"],
            system_prompt=cfg.get("system_prompt"),
            base_url=SERVER_URL,
        ) or {}

        # Hot-swap the team's model if it keeps producing nothing usable.
        # Skipped when TEAM1_MODEL/TEAM2_MODEL were set manually without a
        # pool override — the user picked that model deliberately.
        permanent = result.get("permanent_failure")
        failure_reason = result.get("failure_reason") or "unavailable"
        if result.get("llm_failed"):
            consecutive_llm_failures[active_team_id] += 1
            logger.warning(
                "[%s] LLM turn failed (%d/%d) with model=%s%s",
                cfg["team_name"],
                consecutive_llm_failures[active_team_id],
                SWAP_AFTER_FAILURES,
                cfg["model"],
                " [permanent]" if permanent else "",
            )
            # Permanent error → ban the model globally *now*; transient errors
            # still need to accumulate before we swap.
            if permanent:
                mark_model_dead(cfg["model"], failure_reason)
                # If this flipped the service status, notify the UI immediately.
                current_status = get_service_status()
                if current_status != "ok":
                    _publish_service_status(current_status, failure_reason)
            threshold = 1 if permanent else SWAP_AFTER_FAILURES
            if (
                consecutive_llm_failures[active_team_id] >= threshold
                and not _MANUAL_MODEL_OVERRIDE
            ):
                new_model = get_fallback_model(tried_models[active_team_id])
                if new_model:
                    logger.warning(
                        "[%s] Swapping model %s → %s after %d failure(s)%s",
                        cfg["team_name"], cfg["model"], new_model,
                        consecutive_llm_failures[active_team_id],
                        " [permanent]" if permanent else "",
                    )
                    cfg["model"] = new_model
                    tried_models[active_team_id].add(new_model)
                    consecutive_llm_failures[active_team_id] = 0
                else:
                    logger.error(
                        "[%s] No untried models left in pool; sticking with %s",
                        cfg["team_name"], cfg["model"],
                    )
        else:
            consecutive_llm_failures[active_team_id] = 0

        # Commentator fires after every team turn (not just once per round)
        fresh_state = requests.get(f"{SERVER_URL}/game/{GAME_ID}").json()
        all_events = fresh_state.get("events") or []
        new_events = all_events[last_event_count:]
        last_event_count = len(all_events)

        if new_events:
            had_turnover = any(
                isinstance(e, dict) and e.get("event_type") == "turnover"
                for e in new_events
            )
            comment(
                GAME_ID, fresh_state, new_events,
                COMMENTATOR_MODEL, SERVER_URL,
                had_turnover=had_turnover,
            )

        time.sleep(0.3)

def trigger_rematch() -> None:
    """Call the /rematch endpoint to reset the game to setup phase."""
    try:
        r = requests.post(f"{SERVER_URL}/game/{GAME_ID}/rematch", timeout=10)
        logger.info(f"Rematch triggered (status {r.status_code})")
    except Exception as e:
        logger.warning(f"Failed to trigger rematch: {e}")


def wait_for_rematch() -> None:
    """Poll until the game returns to setup phase after rematch."""
    logger.info("Waiting for rematch to reset to setup phase...")
    timeout_minutes = int(os.getenv("REMATCH_TIMEOUT_MINUTES", "5"))
    max_iterations = (timeout_minutes * 60 // 5) if timeout_minutes > 0 else None
    iterations = 0

    while True:
        try:
            state = requests.get(f"{SERVER_URL}/game/{GAME_ID}").json()
            if state.get("phase") in ("setup", "SETUP"):
                logger.info("Game reset to setup — ready for next match.")
                return
        except Exception as e:
            logger.warning(f"Error polling for rematch: {e}")

        if max_iterations and iterations >= max_iterations:
            raise RuntimeError(f"Timed out waiting for Play Again after {timeout_minutes} minutes")

        iterations += 1
        time.sleep(5)

# ── resume detection ─────────────────────────────────────────────────────────

def _detect_resumed_game() -> bool:
    """Return True if the game is already in a restorable phase (restored from DB).

    When True, the caller should skip run_setup() and go straight to run_game(),
    syncing model configs from the restored state first.
    """
    RESUMABLE = {"kickoff", "playing", "half_time"}
    try:
        resp = requests.get(f"{SERVER_URL}/game/{GAME_ID}", timeout=5)
        if resp.status_code == 200:
            st = resp.json()
            phase = (st.get("phase") or "").lower()
            if phase in RESUMABLE:
                logger.info(
                    "Detected restored game '%s' in phase '%s' — skipping setup",
                    GAME_ID, phase,
                )
                # Sync model identities from restored state so the runner
                # uses the right models for commentary and swap logic
                if st.get("team1_model"):
                    TEAM_CONFIGS["team1"]["model"] = st["team1_model"]
                if st.get("team2_model"):
                    TEAM_CONFIGS["team2"]["model"] = st["team2_model"]
                return True
    except Exception as exc:
        logger.warning("Could not check for resumed game: %s", exc)
    return False


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

    # Probe every pool model once — drop dead ones and detect out-of-credits.
    from simple_agents.model_picker import validate_pool, get_service_status
    validate_pool()
    status = get_service_status()
    _publish_service_status(status)

    # Cool down after probing so the RPM window resets before the game loop
    # starts making real LLM calls. Without this, validate_pool and play_turn
    # race against the same free-tier rate limit.
    logger.info("Startup probe complete — cooling down 5s before game loop.")
    time.sleep(5)

    if status != "ok":
        logger.error(
            "Startup model validation failed (status=%s) — entering maintenance mode.", status,
        )
        # Keep the API up so the UI shows the maintenance screen, but don't launch matches.
        # Periodically re-probe so we recover when credits are added.
        while True:
            time.sleep(60)
            logger.info("Maintenance mode: re-validating pool...")
            validate_pool(force=True)
            status = get_service_status()
            _publish_service_status(status)
            if status == "ok":
                logger.info("Pool restored after maintenance — resuming normal startup.")
                break

    # DEV_MODE: start the server but don't run any games. No model validation,
    # no token spend. Useful when developing new features against a live server.
    if os.getenv("DEV_MODE", "false").lower() in ("true", "1", "yes"):
        logger.info("DEV_MODE active — server is up, game loop disabled. No tokens will be spent.")
        while True:
            time.sleep(60)

    if _MANUAL_MODEL_OVERRIDE:
        logger.info(
            "Manual model override active — team1=%s  team2=%s",
            TEAM_CONFIGS["team1"]["model"], TEAM_CONFIGS["team2"]["model"],
        )
    else:
        logger.info(
            "Tournament mode active — will pick from pool each game "
            "(OPENROUTER_MODELS=%s)", os.getenv("OPENROUTER_MODELS", "<default pool>")
        )

    is_resumed = _detect_resumed_game()
    game_iteration = 0

    while True:
        game_iteration += 1
        try:
            if not is_resumed:
                if not _MANUAL_MODEL_OVERRIDE:
                    from simple_agents.model_picker import pick_models
                    m1, m2 = pick_models(SERVER_URL)
                    TEAM_CONFIGS["team1"]["model"] = m1
                    TEAM_CONFIGS["team2"]["model"] = m2
                    logger.info("Tournament pick: team1=%s  team2=%s", m1, m2)
                logger.info("=== GAME ITERATION %d: entering setup ===", game_iteration)
                run_setup()
                logger.info("=== GAME ITERATION %d: setup complete, starting game ===", game_iteration)
            else:
                logger.info("=== GAME ITERATION %d: resuming in-progress game ===", game_iteration)

            is_resumed = False  # Only skip setup on first (restored) iteration
            run_game()
            logger.info("=== GAME ITERATION %d: game complete, triggering rematch ===", game_iteration)
            trigger_rematch()
            wait_for_rematch()
            # Re-probe the model pool after every match so newly available free
            # models are picked up without requiring a redeploy.
            from simple_agents.model_picker import validate_pool
            logger.info("Re-validating model pool after match completion...")
            validate_pool(force=True)
        except Exception as exc:
            # If the game loop crashes (e.g. LLM 429 storm, network blip),
            # log it and re-enter the loop.  _detect_resumed_game() will
            # check the server state: if the game is still resumable it
            # picks up where we left off, otherwise run_setup() starts fresh.
            logger.error(
                "=== GAME ITERATION %d FAILED: %s — restarting in 3s ===",
                game_iteration, exc, exc_info=True,
            )
            is_resumed = _detect_resumed_game()
            if not is_resumed:
                logger.info("Game not resumable after crash — will start fresh setup.")
            time.sleep(3)


if __name__ == "__main__":
    main()
