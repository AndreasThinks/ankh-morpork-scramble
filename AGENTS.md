# Ankh-Morpork Scramble — Agent Orientation

This file is the first thing a coding agent should read before touching this project.
It contains current state, active work, upcoming tasks, and open questions.

---

## Project in one paragraph

A turn-based sports game server (FastAPI + Python) inspired by Blood Bowl, set in Terry
Pratchett's Discworld. Two AI agent teams (City Watch vs. Unseen University Adepts) play
matches autonomously via LLM agents in `simple_agents/`. The game is deployed on Railway.
A live dashboard at `app/web/templates/dashboard.html` polls the server and renders the
pitch, team thoughts, and a structured event log.

**Repo:** https://github.com/AndreasThinks/ankh-morpork-scramble
**Live:** https://ankh-morpork-scramble-production.up.railway.app
**Railway project:** f7d18fb1-066d-446c-a95a-7a657a5d39ca
**Railway service:** 043548be-1186-4ad7-8955-4e7ce4368722
**Deploy:** `git push` then `railway up` (or push triggers Railway auto-deploy)

---

## Environment

- Python package manager: `uv` — use `uv run` for all commands
- Server: `uv run uvicorn app.main:app --reload`
- Game runner: `uv run python run_simple_game.py`
- Tests: `uv run pytest`
- Railway env vars: `DEMO_MODE=false`, `GAME_ID=the-match`, `ADMIN_API_KEY=Adm1nk4y`

---

## Current state (as of 2026-04-04)

### Recently completed
- **Game log overhaul** (commit `f1ecb92`) — replaced fragile markdown-based log with
  structured event-typed log rendered directly from `state.events`. Adds visual tiers
  (landmark/dramatic/action/quiet), inline die-face display, filter bar, count badge.
  Plan: `docs/plans/2026-04-04-game-log-improvements.md`

- **Post-fix review** — automated review pass correcting bugs introduced during the above.
  Specifically: `escapeHtml` entity bug, hoisting Set constants, placeholder restore on
  rematch, dead `gameLogEntries` reference.

### Known outstanding issues
- `docs/plans/2026-04-04-reachable-squares.md` — plan written, not yet implemented.
  Adds BFS reachable-squares pre-computation to `/valid-actions` so LLM agents cannot
  construct illegal move paths. Four-file change, no dependencies.

---

## Next major task: Tournament Leaderboard

**Goal:** Track and display which LLM models perform best as team agents across multiple
games, using wins, losses, score differential, and key in-game stats.

### Open design questions (resolve with Andreas before writing the plan)

1. **Model identity tagging**
   The game currently does NOT record which LLM model played as which team. This is the
   load-bearing question. We need to stamp model identity somewhere at game start.
   Options:
   - Add `model_id: Optional[str]` to the `Team` model in `app/models/team.py`
   - Add it to `GameState` as `team1_model` / `team2_model`
   - Pass it at game-start via env vars or a new API parameter on `/game/{id}/start`

2. **Granularity of a "result"**
   - One full match = one data point (simplest)
   - Per-half results (two data points per game)
   - Per-drive (too granular, harder to define)
   Recommendation: one full match per row.

3. **Metrics to track per model**
   Confirmed useful:
   - Wins / losses / draws
   - Score (touchdowns for / against)
   - Score differential (cumulative)
   Candidates:
   - Casualties caused / suffered
   - Turnovers caused / conceded
   - Pass completion rate
   - An Elo-style rating (needs initial rating + K-factor decision)

4. **Persistence**
   `GameState` is in-memory and resets on rematch. Leaderboard data must survive resets.
   Options:
   - Simple JSON file on disk (`data/leaderboard.json`) — no new dependencies
   - SQLite via the stdlib `sqlite3` module — queryable, no new dependencies
   - Append-only JSONL event log (`data/results.jsonl`) — simplest, git-friendly
   Recommendation: JSONL results file + in-memory aggregation on read. No new deps.

5. **Where it surfaces**
   - New `/leaderboard` page (separate HTML template)
   - Panel or tab on the existing dashboard
   - JSON API endpoint only (for external display / future use)
   Recommendation: JSON API at `/leaderboard` + a minimal dedicated page.

6. **How games get tagged to the leaderboard**
   - Automatically on `GAME_END` event if model identity was stamped at start
   - Manually via an admin POST endpoint

### Suggested architecture (pending Andreas confirmation)

```
app/models/leaderboard.py       — GameResult, ModelStats pydantic models
app/state/leaderboard_store.py  — JSONL read/write, aggregation
app/main.py                     — GET /leaderboard, POST /game/{id}/record-result
app/web/templates/leaderboard.html — simple leaderboard page
app/models/game_state.py        — add team1_model / team2_model fields to GameState
app/models/team.py              — add model_id field to Team
```

The `GameResult` model would contain:
```python
class GameResult(BaseModel):
    game_id: str
    played_at: datetime
    team1_name: str
    team1_model: str        # e.g. "anthropic/claude-sonnet-4-6"
    team1_score: int
    team2_name: str
    team2_model: str
    team2_score: int
    # Key stats from StatisticsAggregator
    team1_casualties: int
    team2_casualties: int
    team1_turnovers: int
    team2_turnovers: int
    winner_model: Optional[str]   # None = draw
```

---

## Key files quick-reference

| What | Where |
|---|---|
| FastAPI app + all endpoints | `app/main.py` |
| Game state model | `app/models/game_state.py` |
| Structured events | `app/models/events.py` + `app/game/event_logger.py` |
| Statistics aggregation | `app/game/statistics.py` |
| LLM agent runner | `simple_agents/player.py` |
| Game orchestrator | `run_simple_game.py` |
| Dashboard (single HTML file) | `app/web/templates/dashboard.html` |
| Plans directory | `docs/plans/` |
| Game rules | `rules.md` |
| Skills (for LLM agents) | `skills/` |

---

## Coding conventions

- All new endpoints go in `app/main.py` with a docstring and `response_model`
- Pydantic models in `app/models/` — one file per domain
- No new Python packages without checking `pyproject.toml` first (Railway build)
- No new npm/JS dependencies — vanilla JS only in the dashboard
- Commits: `type(scope): description` — e.g. `feat(leaderboard): add GameResult model`
- Always `git push` after committing so Railway can auto-deploy
