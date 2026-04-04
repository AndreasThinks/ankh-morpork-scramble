# Ankh-Morpork Scramble — Agent Orientation

This file is the first thing a coding agent should read before touching this project.
It contains current state, active work, upcoming tasks, and conventions.

---

## Project in one paragraph

A turn-based sports game server (FastAPI + Python) inspired by Blood Bowl, set in Terry
Pratchett's Discworld. Two AI agent teams (City Watch Constables vs. Unseen University
Adepts) play matches autonomously via LLM agents in `simple_agents/`. The game is deployed
on Railway with a persistent volume for leaderboard data. A live dashboard at
`app/web/templates/dashboard.html` polls the server and renders the pitch, team thoughts,
and a structured event log.

**Repo:** https://github.com/AndreasThinks/ankh-morpork-scramble
**Live:** https://ankh-morpork-scramble-production.up.railway.app
**Railway project:** f7d18fb1-066d-446c-a95a-7a657a5d39ca
**Railway service:** 043548be-1186-4ad7-8955-4e7ce4368722
**Volume:** ankh-morpork-scramble-volume, mounted at `/data`

---

## Environment

- Python package manager: `uv` — use `uv run` for all commands
- Tests: `source .venv/bin/activate && python -m pytest tests/ -q`
- Server: `uv run uvicorn app.main:app --reload`
- Game runner: `uv run python run_simple_game.py`
- Railway env vars: `DEMO_MODE=false`, `GAME_ID=the-match`, `DATA_DIR=/data`,
  `TEAM1_MODEL`, `TEAM2_MODEL`, `COMMENTATOR_MODEL` (default: `qwen/qwen3.6-plus:free`),
  `ADMIN_API_KEY`, `OPENROUTER_API_KEY`

---

## Current state (as of 2026-04-04)

### What's working

- **Full game loop** — agents buy players, deploy, play two halves, game ends, scoreboard
  appears, user clicks "Play Again", runner loops back to setup.

- **Leaderboard** — records win/loss/draw per team and per LLM model to
  `/data/results.jsonl` (persists across redeployments via Railway volume). API at
  `GET /leaderboard`, standalone page at `/leaderboard/ui`, mini-table in post-match
  scoreboard overlay. Model identity stamped via `team1_model`/`team2_model` params on
  `POST /game/{id}/start`.

- **Reachable squares** — BFS flood-fill per player exposed on `GET /valid-actions` as
  `reachable_squares`. Agent prompt uses these to constrain move destinations. Eliminates
  the "Position is occupied" / path-exceeds-MA failure loops.

- **Ghost-occupancy fix** — KO'd, casualty, and sent-off players are removed from
  `pitch.player_positions` after combat. Previously a dead player's position entry blocked
  that square permanently.

- **Smooth pitch animation** — `renderPitch()` uses persistent SVG elements with CSS
  transitions. No more full DOM teardown on every poll. Move flash (keyframe ring), ball
  landing pulse, player fade-in/out.

- **Structured game log** — log renders from `state.events` directly. Four visual tiers
  (landmark/dramatic/action/quiet), inline dice display, filter bar (All/Combat/Ball/
  Turnovers), count badge. No separate markdown fetch.

- **Agent intelligence** — per-player MA budget visible in state summary, valid-actions
  rendered as natural language, rich failure feedback with retry context, unacted-player
  count so agent knows when to end turn.

### Known failing tests (pre-existing, not regressions)

- `test_execute_block_turnover_if_ball_carrier_down` — the test incorrectly expects
  `turnover=True` when the *opponent's* ball carrier is knocked down. In Blood Bowl this
  is not a turnover for the attacking team. Needs the test fixed, not the code.
- `test_ui_dashboard_renders_default_game_id` — checks for "Recent Events" text that was
  renamed to "Match Events" in the log overhaul.
- `test_ui_renders_core_components` — same "Recent Events" → "Match Events" issue.

---

## Active / upcoming work

### In progress

- **Game log improvements + layout** — `docs/plans/2026-04-04-game-log-improvements.md`
  Tasks 1-6. Replaces markdown-based log with structured event rendering (Tasks 1-4 in
  plan), adds newest-first ordering (Task 5), and fixes layout/fixed-height issues (Task 6).
  All changes in `dashboard.html` only.

### Next priorities

1. **Scuffle turnover test** — fix the pre-existing failing test
   (`test_execute_block_turnover_if_ball_carrier_down`) by correcting the test assertion
   to match Blood Bowl rules (opponent ball-carrier going down is NOT a turnover).

2. **Database persistence upgrade** — `data/results.jsonl` survives redeployments via the
   Railway volume, but SQLite would be cleaner for querying and more robust under concurrent
   writes. The volume is already mounted at `/data`. Simple migration: replace
   `LeaderboardStore` internals with `sqlite3` stdlib, keep the same public interface.

3. **Run the pre-existing failing tests** — clean up the three stale test assertions so
   the suite runs fully green.

---

## Architecture quick-reference

| What | Where |
|---|---|
| FastAPI app + all endpoints | `app/main.py` |
| Game state model | `app/models/game_state.py` |
| Leaderboard models | `app/models/leaderboard.py` |
| Leaderboard persistence | `app/state/leaderboard_store.py` |
| Structured events | `app/models/events.py` + `app/game/event_logger.py` |
| Statistics aggregation | `app/game/statistics.py` |
| Movement + reachable squares | `app/game/movement.py` |
| Combat (block/injury/foul) | `app/game/combat.py` |
| Action execution | `app/state/action_executor.py` |
| LLM agent turn logic | `simple_agents/player.py` |
| LLM agent state summary | `simple_agents/state_summary.py` |
| Game orchestrator (Railway) | `run_simple_game.py` |
| Dashboard (single HTML file) | `app/web/templates/dashboard.html` |
| Leaderboard page | `app/web/templates/leaderboard.html` |
| Game rules | `rules.md` |
| Active plans | `docs/plans/` |
| Completed plans | `docs/plans/done/` |

---

## Key data flows

### Game end → leaderboard
1. `end_turn()` in `game_manager.py` transitions phase to `CONCLUDED`
2. `_save_game_logs()` fires → calls `_record_result_if_concluded()`
3. `_record_result_if_concluded()` reads scores and model names, builds `GameResult`,
   calls `leaderboard.record(result)` → appends to `/data/results.jsonl`
4. `POST /game/{id}/rematch` also calls `_record_result_if_concluded()` as belt-and-suspenders
5. `GET /leaderboard` reads JSONL, aggregates in-memory, returns `LeaderboardResponse`

### Agent turn
1. `run_simple_game.py` calls `play_turn()` in `simple_agents/player.py`
2. `play_turn()` fetches `GET /valid-actions` → gets reachable squares per player
3. `summarize_for_player()` builds natural-language context including MA budgets
4. LLM called with context → returns one action JSON
5. Action POSTed to server; on failure, `build_failure_context()` generates retry prompt
6. Repeats until LLM returns null (end turn) or MAX_RETRIES exceeded

---

## Coding conventions

- All new endpoints in `app/main.py` with docstring and `response_model`
- Pydantic models in `app/models/` — one file per domain
- No new Python packages without checking `pyproject.toml` (Railway build constraint)
- No new npm/JS dependencies — vanilla JS only in the dashboard
- Commits: `type(scope): description` — e.g. `feat(leaderboard): add GameResult model`
- Always `git push` after committing — Railway auto-deploys on push
- Run tests before committing: `source .venv/bin/activate && python -m pytest tests/ -q`
