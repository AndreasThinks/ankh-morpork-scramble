# Leaderboard Implementation Plan
**Date:** 2026-04-04  
**Scope:** Track per-team and per-model win/loss/draw records across games, persist to disk,
surface in the UI after each game, and gate new games behind an explicit "Play Again" click.

---

## Background / What Was Found in the Codebase

| Area | Finding |
|------|---------|
| Model identity | **Not tracked anywhere in GameState.** `run_simple_game.py` reads `TEAM1_MODEL`/`TEAM2_MODEL` env vars but never stores them on the server. `run_hermes_game.py` hard-codes `"qwen/qwen3.6-plus:free"`. |
| Game lifecycle | `GamePhase.CONCLUDED` (alias `FINISHED`) is set in `GameState.end_half()` when half 2 ends. `GameManager._save_game_logs()` is called after every turn and every touchdown. |
| Persistence | Entirely in-memory (`game_manager.games` dict) plus `logs/games/{game_id}/` files. No database. |
| "Play Again" gate (UI) | **Already exists.** The scoreboard overlay fires when `phase === 'finished'` and has a "Start New Game" button wired to `POST /game/{id}/rematch`. Polling stops when scoreboard shows. |
| "Play Again" gate (runner) | **Does not exist.** `run_simple_game.py::main()` calls `run_setup()` then `run_game()` then `shutdown()`. It never loops. Once the game ends the process exits. |
| `/rematch` endpoint | `app/main.py:862` — resets the game for interactive mode, re-bootstraps for demo mode. Does NOT record the result before resetting. |
| Statistics | `StatisticsAggregator` (already in `app/game/statistics.py`) provides team-level casualties, turnovers, etc. Used by the scoreboard. |
| Existing scoreboard overlay | DOM IDs at lines 1320–1347 of `dashboard.html`. JS in `showScoreboard()` (~line 2320). |

---

## Design Decisions

1. **Persistence format:** Append-only JSONL at `data/results.jsonl` (one JSON object per
   completed game). No new dependencies. In-memory aggregation on every read.
   _Gotcha:_ If uvicorn is ever run with `--workers N > 1`, concurrent appends can interleave.
   Single-worker deployments (current Railway setup) are safe. Document this constraint.

2. **Model identity:** Add `team1_model: Optional[str]` and `team2_model: Optional[str]`
   to `GameState`. Stamp them via two new optional query-string params on
   `POST /game/{id}/start`. The runner script already calls that endpoint; it just needs
   to pass the model names. Default to `"unknown"` if not provided.

3. **Recording trigger:** Record the result inside `rematch_game()` (the `/rematch`
   endpoint in `app/main.py`), immediately before the reset. Guard against double-recording
   with a `set[str]` in `GameManager` (`_recorded_games`). As a belt-and-suspenders
   measure also record inside `_save_game_logs()` when `phase == CONCLUDED`, so a crash
   between game-end and rematch-click doesn't lose the data.

4. **Granularity:** One full match per row.

5. **UI surface:** Embed a "Season Standings" section inside the existing scoreboard overlay
   (no new page required). Fetch `/leaderboard` when the overlay opens, render two tables
   (by team, by model) below the player highlights. Also add a `GET /leaderboard/ui` page
   for standalone access.

6. **Runner loop:** `run_simple_game.py` gets a `wait_for_rematch()` helper that polls
   `/game/{id}` until `phase == "setup"` (meaning the user clicked "Play Again" and
   `/rematch` ran). The main function becomes a `while True` loop.
   `run_hermes_game.py` is left as-is (it is the manually-invoked runner; AGENTS.md lists
   `run_simple_game.py` as the canonical orchestrator).

---

## Step-by-Step Implementation

---

### Step 1 — Add model fields to `GameState`
**File:** `app/models/game_state.py`

After the `game_started: bool = False` line (~line 57), add:

```python
# Model identity — which LLM is playing each team (stamped at /start time)
team1_model: Optional[str] = None
team2_model: Optional[str] = None

# Guard against recording the same result twice (transient, not serialised)
# Handled via GameManager._recorded_games instead — see Step 3.
```

Only `team1_model` and `team2_model` are added to the Pydantic model.
They are Optional[str] so existing games and tests continue to work without changes.

**Why:** Every downstream piece (leaderboard, statistics) needs to know which model played
which side. Storing it on `GameState` keeps it in one place and means it's included in the
existing `game_manager.get_game()` and log-save calls automatically.

---

### Step 2 — Expose model identity on the `/start` endpoint
**File:** `app/main.py`

Change the `start_game` endpoint signature from:

```python
@app.post("/game/{game_id}/start", response_model=GameState)
def start_game(game_id: str):
```

to:

```python
@app.post("/game/{game_id}/start", response_model=GameState)
def start_game(
    game_id: str,
    team1_model: Optional[str] = None,
    team2_model: Optional[str] = None,
):
```

Inside the function body, after `game_state = game_manager.start_game(game_id)`, add:

```python
if team1_model:
    game_state.team1_model = team1_model
if team2_model:
    game_state.team2_model = team2_model
```

**Why:** The runner script already calls this endpoint. Adding optional query params is
backwards-compatible. No signature change to `GameManager.start_game()` is needed.

**Gotcha:** The `/game/{id}/start` endpoint is also called in `run_setup()` inside
`run_simple_game.py`. That call will be updated in Step 9 to pass the model names.
For the Hermes runner (`run_hermes_game.py`), models are hard-coded there; it can be
updated separately or left with `team1_model=None` (defaults to `"unknown"`).

---

### Step 3 — Create `app/models/leaderboard.py`
**File:** `app/models/leaderboard.py` *(new file)*

```python
"""Leaderboard data models."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class GameResult(BaseModel):
    """One completed match result written to data/results.jsonl."""
    game_id: str
    played_at: datetime = Field(default_factory=datetime.utcnow)
    team1_name: str
    team1_model: str = "unknown"
    team1_score: int
    team2_name: str
    team2_model: str = "unknown"
    team2_score: int
    team1_casualties: int = 0
    team2_casualties: int = 0
    team1_turnovers: int = 0
    team2_turnovers: int = 0
    winner_model: Optional[str] = None   # None = draw
    winner_team: Optional[str] = None    # None = draw


class ModelLeaderboardEntry(BaseModel):
    """Aggregated stats for one model across all games."""
    model_id: str
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    goals_for: int = 0
    goals_against: int = 0
    score_diff: int = 0
    casualties_caused: int = 0
    turnovers: int = 0

    @property
    def win_pct(self) -> float:
        return round(self.wins / self.games, 3) if self.games else 0.0


class TeamLeaderboardEntry(BaseModel):
    """Aggregated stats for one team name across all games."""
    team_name: str
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    goals_for: int = 0
    goals_against: int = 0
    score_diff: int = 0


class LeaderboardResponse(BaseModel):
    """Response shape for GET /leaderboard."""
    total_games: int
    by_model: list[ModelLeaderboardEntry]
    by_team: list[TeamLeaderboardEntry]
```

**Why:** Separating the data model into its own file follows the existing conventions
(one file per domain in `app/models/`). Pydantic ensures the JSONL is always valid JSON
and allows clean serialisation.

---

### Step 4 — Create `app/state/leaderboard_store.py`
**File:** `app/state/leaderboard_store.py` *(new file)*

```python
"""Persistent leaderboard — append-only JSONL + in-memory aggregation."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.leaderboard import (
    GameResult, ModelLeaderboardEntry, TeamLeaderboardEntry, LeaderboardResponse
)

logger = logging.getLogger("app.leaderboard")

_DEFAULT_PATH = Path("data/results.jsonl")


class LeaderboardStore:
    """
    Thread-safe append-only JSONL store.

    Gotcha: safe for single-process uvicorn only. Multi-worker deployments
    would need an external lock (e.g. a file lock via fcntl or portalocker).
    """

    def __init__(self, path: Path = _DEFAULT_PATH):
        self.path = path
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(self, result: GameResult) -> None:
        """Append one GameResult to the JSONL file. Idempotent on duplicate game_id."""
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Idempotency guard: skip if this game_id is already present
            if self._is_recorded(result.game_id):
                logger.debug("Game %s already recorded — skipping.", result.game_id)
                return
            line = result.model_dump_json() + "\n"
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line)
            logger.info(
                "Recorded result: %s %d-%d %s (models: %s vs %s)",
                result.team1_name, result.team1_score,
                result.team2_score, result.team2_name,
                result.team1_model, result.team2_model,
            )

    def _is_recorded(self, game_id: str) -> bool:
        """Check if a game_id already exists in the file (called while holding lock)."""
        if not self.path.exists():
            return False
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("game_id") == game_id:
                        return True
                except json.JSONDecodeError:
                    continue
        return False

    # ------------------------------------------------------------------
    # Read / aggregate
    # ------------------------------------------------------------------

    def load_all(self) -> list[GameResult]:
        """Load all results from disk."""
        if not self.path.exists():
            return []
        results = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(GameResult.model_validate_json(line))
                except Exception as exc:
                    logger.warning("Skipping malformed leaderboard line: %s", exc)
        return results

    def get_leaderboard(self) -> LeaderboardResponse:
        """Aggregate all results and return a LeaderboardResponse."""
        results = self.load_all()

        model_map: dict[str, ModelLeaderboardEntry] = {}
        team_map: dict[str, TeamLeaderboardEntry] = {}

        for r in results:
            # ---- determine outcomes ----
            if r.team1_score > r.team2_score:
                t1_outcome, t2_outcome = "win", "loss"
            elif r.team2_score > r.team1_score:
                t1_outcome, t2_outcome = "loss", "win"
            else:
                t1_outcome = t2_outcome = "draw"

            # ---- model aggregation ----
            for model_id, score_for, score_against, casualties, turnovers, outcome in [
                (r.team1_model, r.team1_score, r.team2_score, r.team1_casualties, r.team1_turnovers, t1_outcome),
                (r.team2_model, r.team2_score, r.team1_score, r.team2_casualties, r.team2_turnovers, t2_outcome),
            ]:
                if model_id not in model_map:
                    model_map[model_id] = ModelLeaderboardEntry(model_id=model_id)
                entry = model_map[model_id]
                entry.games += 1
                entry.goals_for += score_for
                entry.goals_against += score_against
                entry.score_diff += score_for - score_against
                entry.casualties_caused += casualties
                entry.turnovers += turnovers
                if outcome == "win":
                    entry.wins += 1
                elif outcome == "loss":
                    entry.losses += 1
                else:
                    entry.draws += 1

            # ---- team aggregation ----
            for team_name, score_for, score_against, outcome in [
                (r.team1_name, r.team1_score, r.team2_score, t1_outcome),
                (r.team2_name, r.team2_score, r.team1_score, t2_outcome),
            ]:
                if team_name not in team_map:
                    team_map[team_name] = TeamLeaderboardEntry(team_name=team_name)
                entry = team_map[team_name]
                entry.games += 1
                entry.goals_for += score_for
                entry.goals_against += score_against
                entry.score_diff += score_for - score_against
                if outcome == "win":
                    entry.wins += 1
                elif outcome == "loss":
                    entry.losses += 1
                else:
                    entry.draws += 1

        # Sort by wins desc, score_diff desc
        by_model = sorted(model_map.values(), key=lambda e: (-e.wins, -e.score_diff))
        by_team = sorted(team_map.values(), key=lambda e: (-e.wins, -e.score_diff))

        return LeaderboardResponse(
            total_games=len(results),
            by_model=by_model,
            by_team=by_team,
        )
```

**Why:** A `threading.Lock` guards the append so it's safe even if FastAPI's async
threadpool fires concurrent requests. The idempotency guard means the belt-and-suspenders
recording from `_save_game_logs` and the recording from `/rematch` don't create duplicates.

---

### Step 5 — Wire result recording into `GameManager`
**File:** `app/state/game_manager.py`

**5a. Import and store the leaderboard store:**

At the top of the file, add:
```python
from app.state.leaderboard_store import LeaderboardStore
```

In `GameManager.__init__`, add:
```python
self.leaderboard = LeaderboardStore()
self._recorded_games: set[str] = set()   # in-memory guard against double-recording
```

**5b. Add a helper method `_record_result_if_concluded()`:**

```python
def _record_result_if_concluded(self, game_state: GameState) -> None:
    """Record a completed game to the leaderboard (idempotent)."""
    if game_state.phase != GamePhase.CONCLUDED:
        return
    if game_state.game_id in self._recorded_games:
        return
    self._recorded_games.add(game_state.game_id)

    # Pull casualties + turnovers from StatisticsAggregator
    from app.game.statistics import StatisticsAggregator
    try:
        stats = StatisticsAggregator(game_state).aggregate()
        t1_stats = (stats.team_stats or {}).get(game_state.team1.id, {})
        t2_stats = (stats.team_stats or {}).get(game_state.team2.id, {})
        t1_casualties = getattr(t1_stats, "casualties_caused", 0) if hasattr(t1_stats, "casualties_caused") else t1_stats.get("casualties_caused", 0) if isinstance(t1_stats, dict) else 0
        t2_casualties = getattr(t2_stats, "casualties_caused", 0) if hasattr(t2_stats, "casualties_caused") else t2_stats.get("casualties_caused", 0) if isinstance(t2_stats, dict) else 0
        t1_turnovers = getattr(t1_stats, "turnovers", 0) if hasattr(t1_stats, "turnovers") else t1_stats.get("turnovers", 0) if isinstance(t1_stats, dict) else 0
        t2_turnovers = getattr(t2_stats, "turnovers", 0) if hasattr(t2_stats, "turnovers") else t2_stats.get("turnovers", 0) if isinstance(t2_stats, dict) else 0
    except Exception:
        t1_casualties = t2_casualties = t1_turnovers = t2_turnovers = 0

    t1_score = game_state.team1.score
    t2_score = game_state.team2.score
    winner_model = None
    winner_team = None
    if t1_score > t2_score:
        winner_model = game_state.team1_model
        winner_team = game_state.team1.name
    elif t2_score > t1_score:
        winner_model = game_state.team2_model
        winner_team = game_state.team2.name

    from app.models.leaderboard import GameResult
    result = GameResult(
        game_id=game_state.game_id,
        team1_name=game_state.team1.name,
        team1_model=game_state.team1_model or "unknown",
        team1_score=t1_score,
        team2_name=game_state.team2.name,
        team2_model=game_state.team2_model or "unknown",
        team2_score=t2_score,
        team1_casualties=t1_casualties,
        team2_casualties=t2_casualties,
        team1_turnovers=t1_turnovers,
        team2_turnovers=t2_turnovers,
        winner_model=winner_model,
        winner_team=winner_team,
    )
    self.leaderboard.record(result)
    logger.info("Leaderboard updated for game %s", game_state.game_id)
```

**5c. Call it from `_save_game_logs()`:**

At the end of `_save_game_logs()`, after the log-save call, add:
```python
self._record_result_if_concluded(game_state)
```

**Why:** `_save_game_logs` is already called after every turn and after every touchdown.
When the phase transitions to CONCLUDED (at end of half 2), the next call to
`_save_game_logs` from `end_turn()` will catch it. This gives crash-safety: if the
server dies before `/rematch` is called, the result is still persisted on disk.

**Gotcha about StatisticsAggregator:** The `stats.team_stats` field shape depends on
`app/game/statistics.py`. Verify whether it returns a `dict[str, TeamStats]` or a
Pydantic model. The helper above handles both via `hasattr`/`isinstance` checks; adjust
to match the actual type if cleaner access is available.

---

### Step 6 — Update `rematch_game()` in `app/main.py`
**File:** `app/main.py`

Inside `rematch_game()` (currently at line 862), add a recording call at the very
beginning of the `try` block, before any reset logic:

```python
@app.post("/game/{game_id}/rematch", response_model=GameState)
def rematch_game(game_id: str):
    """Prepare and start a fresh match after the current game concludes.
    
    Records the completed game result to the leaderboard before resetting.
    The 'Play Again' button in the UI calls this endpoint.
    """
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    try:
        # ── NEW: record result before we wipe the state ──────────────
        game_manager._record_result_if_concluded(game_state)
        # ─────────────────────────────────────────────────────────────

        if demo_mode and ...:   # existing demo branch unchanged
            ...
        
        # Fallback: reset to setup
        game_state.reset_to_setup()
        return game_state
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Why:** Belt-and-suspenders. The `_save_game_logs` path already persisted it, so this
call is a no-op in normal flow (idempotency guard). But if the server was restarted or
the save path was skipped, this guarantees recording happens exactly at the moment the
user clicks "Play Again".

---

### Step 7 — Add leaderboard API endpoints to `app/main.py`
**File:** `app/main.py`

Add after the existing `/game/{game_id}/statistics` route:

```python
from app.models.leaderboard import LeaderboardResponse


@app.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard():
    """Return aggregated season standings — wins/losses/draws per team and per AI model.
    
    Reads from data/results.jsonl. Returns empty standings if no games have been played.
    """
    return game_manager.leaderboard.get_leaderboard()
```

**Why:** Keeping the JSON API endpoint decoupled from the UI page makes it easy for
external scripts, monitoring, or future dashboards to consume the leaderboard.

---

### Step 8 — Add leaderboard HTML route to `app/web/ui.py`
**File:** `app/web/ui.py`

Add a second route below the existing `/ui` route:

```python
@router.get("/leaderboard/ui", response_class=HTMLResponse)
def render_leaderboard(request: Request) -> HTMLResponse:
    """Render the standalone season leaderboard page."""
    return _templates.TemplateResponse(
        request,
        "leaderboard.html",
        {}
    )
```

**Why:** Consistent with the existing pattern — routes in `ui.py`, templates in
`app/web/templates/`.

---

### Step 9 — Create `app/web/templates/leaderboard.html`
**File:** `app/web/templates/leaderboard.html` *(new file)*

Minimal standalone page that fetches `/leaderboard` on load and renders two tables:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Ankh-Morpork Scramble — Season Standings</title>
  <!-- reuse same fonts and CSS variables as dashboard -->
  <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Spectral:ital,wght@0,400;0,500;1,400&display=swap" rel="stylesheet">
  <style>
    /* Copy the :root CSS variables block and base body/panel/table styles
       verbatim from dashboard.html lines 10-60 and 264-460 so the pages
       share the same dark Ankh-Morpork look. */
    ...
  </style>
</head>
<body>
  <header>
    <h1>Ankh-Morpork Scramble — Season Standings</h1>
    <nav><a href="/ui">← Back to Match</a></nav>
  </header>
  <main>
    <section id="by-model">
      <h2>By AI Model</h2>
      <table id="model-table">
        <thead>
          <tr>
            <th>Model</th><th>GP</th><th>W</th><th>L</th><th>D</th>
            <th>GF</th><th>GA</th><th>+/-</th><th>Cas</th>
          </tr>
        </thead>
        <tbody id="model-rows"></tbody>
      </table>
    </section>
    <section id="by-team">
      <h2>By Team</h2>
      <table id="team-table">
        <thead>
          <tr>
            <th>Team</th><th>GP</th><th>W</th><th>L</th><th>D</th>
            <th>GF</th><th>GA</th><th>+/-</th>
          </tr>
        </thead>
        <tbody id="team-rows"></tbody>
      </table>
    </section>
    <p id="total-games"></p>
  </main>
  <script>
    async function load() {
      const r = await fetch('/leaderboard');
      const data = await r.json();
      document.getElementById('total-games').textContent =
        `Total games played: ${data.total_games}`;

      document.getElementById('model-rows').innerHTML =
        data.by_model.map(m => `
          <tr>
            <td>${m.model_id}</td>
            <td>${m.games}</td><td>${m.wins}</td>
            <td>${m.losses}</td><td>${m.draws}</td>
            <td>${m.goals_for}</td><td>${m.goals_against}</td>
            <td>${m.score_diff >= 0 ? '+' : ''}${m.score_diff}</td>
            <td>${m.casualties_caused}</td>
          </tr>`).join('');

      document.getElementById('team-rows').innerHTML =
        data.by_team.map(t => `
          <tr>
            <td>${t.team_name}</td>
            <td>${t.games}</td><td>${t.wins}</td>
            <td>${t.losses}</td><td>${t.draws}</td>
            <td>${t.goals_for}</td><td>${t.goals_against}</td>
            <td>${t.score_diff >= 0 ? '+' : ''}${t.score_diff}</td>
          </tr>`).join('');
    }
    load();
  </script>
</body>
</html>
```

**Implementation note:** Copy the `:root` CSS variable block and the `body`, `header`,
`table`, `thead th`, `tbody tr td`, `.panel`, and `h2` styles verbatim from
`dashboard.html` (lines 10–460) so it matches the existing visual theme without
duplicating maintenance work. Keep the file focused — no JS polling needed, just one
`fetch` on load.

---

### Step 10 — Embed mini-leaderboard in the scoreboard overlay (`dashboard.html`)
**File:** `app/web/templates/dashboard.html`

**10a. Add HTML section inside `.scoreboard-panel`:**

After the closing `</div>` of `.scoreboard-highlights` (currently line ~1341) and before
`.scoreboard-actions`, insert:

```html
<div class="scoreboard-season" id="scoreboard-season">
    <h3>Season Standings</h3>
    <div id="scoreboard-leaderboard-content">
        <p class="scoreboard-note">Loading standings…</p>
    </div>
    <p><a href="/leaderboard/ui" target="_blank" style="color: var(--accent-gold);">
      View full standings →
    </a></p>
</div>
```

**10b. Add CSS (in the `<style>` block near the other `.scoreboard-*` rules):**

```css
.scoreboard-season {
    margin-top: 1.5rem;
    border-top: 1px solid rgba(217, 180, 91, 0.2);
    padding-top: 1rem;
}
.scoreboard-season h3 {
    font-family: "Cinzel", serif;
    font-size: 0.9rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--accent-gold);
    margin: 0 0 0.75rem;
}
.lb-mini-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    margin-bottom: 0.5rem;
}
.lb-mini-table th {
    color: var(--accent-gold);
    font-family: "Cinzel", serif;
    font-size: 0.7rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 0.3rem 0.2rem;
    border-bottom: 1px solid rgba(217,180,91,0.2);
    text-align: left;
}
.lb-mini-table td {
    padding: 0.3rem 0.2rem;
    border-top: 1px solid rgba(217,180,91,0.1);
    color: rgba(242,227,198,0.88);
}
```

**10c. Add JS function `renderLeaderboardInScoreboard()` in the `<script>` block:**

Place this near the other `render*` functions (after `renderPlayerHighlights`):

```javascript
async function renderLeaderboardInScoreboard() {
    const container = document.getElementById('scoreboard-leaderboard-content');
    if (!container) return;
    try {
        const r = await fetch('/leaderboard');
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        if (data.total_games === 0) {
            container.innerHTML = '<p class="scoreboard-note">No completed games yet.</p>';
            return;
        }
        const modelRows = data.by_model.slice(0, 5).map(m =>
            `<tr>
              <td title="${escapeHtml(m.model_id)}">${escapeHtml(m.model_id.split('/').pop())}</td>
              <td>${m.games}</td><td>${m.wins}</td><td>${m.losses}</td><td>${m.draws}</td>
              <td>${m.score_diff >= 0 ? '+' : ''}${m.score_diff}</td>
            </tr>`
        ).join('');
        container.innerHTML = `
            <p style="font-size:0.75rem;color:var(--muted);margin:0 0 0.5rem;">
              ${data.total_games} game${data.total_games === 1 ? '' : 's'} on record
            </p>
            <table class="lb-mini-table">
              <thead>
                <tr><th>Model</th><th>GP</th><th>W</th><th>L</th><th>D</th><th>+/-</th></tr>
              </thead>
              <tbody>${modelRows}</tbody>
            </table>`;
    } catch (e) {
        container.innerHTML = `<p class="scoreboard-note">Standings unavailable: ${e.message}</p>`;
    }
}
```

**10d. Call `renderLeaderboardInScoreboard()` from `showScoreboard()`:**

In `showScoreboard()`, after the `scoreboardOverlay.removeAttribute('hidden')` line, add:

```javascript
renderLeaderboardInScoreboard();
```

**Why:** The user sees the standings right after the game ends, before deciding whether to
play again. The "View full standings" link gives a persistent URL for deeper inspection.
Loading is async so it doesn't block the scoreboard from appearing.

---

### Step 11 — Update `run_simple_game.py` to loop on user-gated rematch
**File:** `run_simple_game.py`

**11a. Add `wait_for_rematch()` helper:**

```python
def wait_for_rematch(poll_interval: float = 5.0, timeout: float = 3600.0) -> None:
    """Block until the user has clicked 'Play Again' (game phase returns to 'setup').
    
    The /rematch endpoint — called by the 'Start New Game' button — resets the
    game to SETUP phase.  We poll until that transition is detected.
    """
    logger.info("Game over. Waiting for 'Play Again' click in the UI...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            state = requests.get(f"{SERVER_URL}/game/{GAME_ID}", timeout=5).json()
            if state.get("phase") in ("setup", "SETUP"):
                logger.info("Rematch detected — phase is now 'setup'. Starting next game.")
                return
        except Exception as e:
            logger.warning(f"Poll error waiting for rematch: {e}")
        time.sleep(poll_interval)
    raise RuntimeError(f"Timed out waiting for Play Again after {timeout}s")
```

**11b. Change `main()` to loop:**

```python
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

    game_number = 0
    while True:
        game_number += 1
        logger.info(f"=== Starting game #{game_number} ===")
        run_setup()
        run_game()
        # run_game() returns when phase == 'finished'.
        # Now block until the user clicks "Play Again" in the UI.
        # /rematch resets the phase to 'setup', which unblocks the next iteration.
        wait_for_rematch()
```

**11c. Pass model names when calling `/start`:**

Inside `run_setup()`, change the `/start` call from:

```python
r = requests.post(f"{SERVER_URL}/game/{GAME_ID}/start")
```

to:

```python
r = requests.post(
    f"{SERVER_URL}/game/{GAME_ID}/start",
    params={
        "team1_model": TEAM_CONFIGS["team1"]["model"],
        "team2_model": TEAM_CONFIGS["team2"]["model"],
    },
)
```

**Why:** Now the event loop is:
1. Agents play → game ends → scoreboard appears in UI (already implemented)
2. User reviews → clicks "Start New Game" → `/rematch` called → resets phase to SETUP
3. `wait_for_rematch()` unblocks → runner loops back to `run_setup()`
4. Agents buy/place players → `/start` called with model names → game plays

The runner process stays alive between games (server process also stays alive), so
Railway's persistent deployment works naturally.

---

### Step 12 — Add `data/` to `.gitignore` or create `data/.gitkeep`
**File:** `.gitignore` (or create `data/.gitkeep`)

The `data/results.jsonl` file should not be committed to git (it's runtime data).
Add to `.gitignore`:

```
data/results.jsonl
```

But create `data/.gitkeep` so the directory is version-controlled and Railway's
filesystem has it ready:

```
data/.gitkeep
```

**Why:** Avoids accidentally committing match history. The `LeaderboardStore` already
calls `self.path.parent.mkdir(parents=True, exist_ok=True)` before writing, so the
directory is created at runtime if missing.

---

### Step 13 — Write tests
**File:** `tests/test_leaderboard.py` *(new file)*

Minimum test surface:

```python
"""Tests for the leaderboard system."""
import json
from pathlib import Path
import pytest
from app.models.leaderboard import GameResult
from app.state.leaderboard_store import LeaderboardStore


def test_record_and_aggregate(tmp_path):
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    r1 = GameResult(
        game_id="g1", team1_name="City Watch", team1_model="model-a",
        team1_score=2, team2_name="UU Adepts", team2_model="model-b",
        team2_score=1, winner_model="model-a", winner_team="City Watch",
    )
    store.record(r1)
    store.record(r1)   # idempotency: should not duplicate
    lb = store.get_leaderboard()
    assert lb.total_games == 1
    assert lb.by_model[0].model_id == "model-a"
    assert lb.by_model[0].wins == 1
    assert lb.by_model[1].losses == 1


def test_empty_leaderboard(tmp_path):
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    lb = store.get_leaderboard()
    assert lb.total_games == 0
    assert lb.by_model == []
    assert lb.by_team == []


def test_api_leaderboard_endpoint(tmp_path, monkeypatch):
    """GET /leaderboard returns 200 with empty standings when no games played."""
    from fastapi.testclient import TestClient
    # Point the store at a temp path so tests don't touch real data
    from app.state import game_manager as gm_module
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    # Monkeypatch game_manager's leaderboard instance
    # (exact monkeypatch depends on how game_manager is imported in main.py)
    ...
```

**Why:** Cover the idempotency guard, the empty-state edge case, and the API endpoint.
The monkeypatching pattern for the API test depends on whether `game_manager` is a
module-level singleton in `main.py` (it is — `game_manager = GameManager()` at line 37).

---

## Open Gotchas and Design Calls

| # | Issue | Recommended call |
|---|-------|-----------------|
| 1 | **Multi-worker safety.** `data/results.jsonl` uses `threading.Lock` only. If Railway ever uses `--workers 2+`, appends can corrupt the file. | Add a note to AGENTS.md. Use `portalocker` (file-level lock) if multi-worker is needed. No action required now. |
| 2 | **`StatisticsAggregator` return type.** The helper in Step 5 uses `getattr`/`isinstance` defensively because the shape of `stats.team_stats` values wasn't confirmed. | Open `app/game/statistics.py` and check whether `team_stats` values are dicts or Pydantic models, then tighten the accessor. |
| 3 | **`run_hermes_game.py` loop.** The Hermes runner is not updated in this plan. It will exit after each game as before. If that runner is used on Railway it won't loop. | Either apply the same loop pattern from Step 11, or rely on `run_simple_game.py` only. |
| 4 | **Server restart between game-end and rematch click.** If the server restarts after the game ends but before the user clicks "Play Again", the in-memory `_recorded_games` set is wiped. The JSONL idempotency check (`_is_recorded`) will catch the duplicate on the next recording attempt, but only if `game_id` is stable across restarts. `game_id = "the-match"` is stable; auto-UUID game IDs are not. | For the single-game-ID interactive mode, this is safe. Note it for UUID-based games. |
| 5 | **Model ID display.** The mini-leaderboard in Step 10 trims the model ID to `id.split('/').pop()` (e.g. `"qwen3.6-plus:free"` instead of `"qwen/qwen3.6-plus:free"`) to fit the panel. Full ID is in the `title` attribute. | Adjust truncation logic if model names need a different display format. |
| 6 | **`wait_for_rematch` timeout.** Default is 3600 s (1 hour). If nobody clicks "Play Again" the runner exits. | Adjust `timeout` to whatever makes sense for the deployment (e.g. `float("inf")` for a truly persistent loop). |
| 7 | **`reset_to_setup()` clears join status?** Looking at `game_state.py:246`, `reset_to_setup()` does NOT reset `team1_joined`/`team2_joined` or team names. So after `/rematch` the new game retains the team names, which is correct for the leaderboard (same team name across rematches). The model field (`team1_model`) IS also preserved across resets — add `self.team1_model = None; self.team2_model = None` to `reset_to_setup()` so stale model names don't bleed into the next game's record. | Add the two clear lines to `reset_to_setup()` in `app/models/game_state.py`. |

---

## File Change Summary

| File | Action | Purpose |
|------|--------|---------|
| `app/models/game_state.py` | Modify | Add `team1_model`, `team2_model` fields; clear them in `reset_to_setup()` |
| `app/models/leaderboard.py` | **Create** | `GameResult`, `ModelLeaderboardEntry`, `TeamLeaderboardEntry`, `LeaderboardResponse` models |
| `app/state/leaderboard_store.py` | **Create** | JSONL read/write, idempotency guard, aggregation |
| `app/state/game_manager.py` | Modify | Import store, add `_recorded_games`, add `_record_result_if_concluded()`, call it from `_save_game_logs()` |
| `app/main.py` | Modify | Add `team1_model`/`team2_model` params to `/start`; record result in `/rematch`; add `GET /leaderboard` endpoint |
| `app/web/ui.py` | Modify | Add `GET /leaderboard/ui` route |
| `app/web/templates/leaderboard.html` | **Create** | Standalone leaderboard page |
| `app/web/templates/dashboard.html` | Modify | Add `#scoreboard-season` HTML section, CSS, `renderLeaderboardInScoreboard()` JS, call from `showScoreboard()` |
| `run_simple_game.py` | Modify | Pass model names to `/start`; add `wait_for_rematch()`; wrap `main()` in `while True` loop |
| `data/.gitkeep` | **Create** | Ensure `data/` directory exists in repo |
| `.gitignore` | Modify | Exclude `data/results.jsonl` |
| `tests/test_leaderboard.py` | **Create** | Unit tests for store + API endpoint |

---

## Suggested Commit Sequence

```
feat(leaderboard): add GameResult and leaderboard models
feat(leaderboard): add LeaderboardStore with JSONL persistence
feat(leaderboard): stamp model identity on GameState at /start
feat(leaderboard): wire recording into GameManager on game end
feat(leaderboard): add GET /leaderboard API endpoint
feat(leaderboard): add /leaderboard/ui page and template
feat(leaderboard): embed season standings in post-match scoreboard
feat(runner): loop run_simple_game.py with wait_for_rematch gate
test(leaderboard): add unit tests for store and API
```
