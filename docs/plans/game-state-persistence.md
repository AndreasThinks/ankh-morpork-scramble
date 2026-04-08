# Game State Persistence — Implementation Plan

**Goal:** Survive Railway container restarts without losing in-progress games.
Any game in KICKOFF, PLAYING, or HALF_TIME phase must resume transparently after
a server restart, picking up from the exact turn it was on.

---

## 0. Quick orientation

The pain point is a startup race built into `app/main.py`:

```
module import → GameManager() created (empty)
             → bootstrap_interactive_game() runs → creates fresh SETUP game
             → app_lifespan() fires → init_db() called
```

The bootstrap is already idempotent — it checks `manager.get_game(game_id)` first
and bails out if the game exists. So if we restore games *before* the bootstrap
runs, everything just works. To do that, we must move the bootstrap call from
module-level into `app_lifespan`, after `init_db()` + restore.

---

## 1. Schema — new table in `versus.db`

**File:** `app/state/agent_registry.py`, inside `init_db()`.

Add this `CREATE TABLE IF NOT EXISTS` block immediately after the existing
`notifications` table creation:

```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS game_snapshots (
        game_id    TEXT PRIMARY KEY,
        phase      TEXT    NOT NULL,
        state_json TEXT    NOT NULL,
        saved_at   TEXT    NOT NULL
    )
""")
```

**Column guide:**

| Column     | Why                                                            |
|------------|----------------------------------------------------------------|
| `game_id`  | PK, matches `GameState.game_id` — e.g. `"the-match"`         |
| `phase`    | Canonical string from `GamePhase` enum — for cheap filtering  |
| `state_json` | Full `GameState.model_dump_json()` blob (~50–500 KB per game) |
| `saved_at` | ISO UTC string, useful for debugging stale snapshots          |

No foreign-key constraints — game_snapshots is intentionally stand-alone.
The existing `ALTER TABLE` migration pattern (try/except) is not needed here
because `CREATE TABLE IF NOT EXISTS` is safe on existing databases.

---

## 2. Save strategy

### What to save

Save the complete `GameState.model_dump_json()` blob. GameState is a Pydantic
model and already round-trips cleanly. This is ~50 KB for a fresh game and
~200–500 KB for a game near the end (large `events` list). SQLite handles this
fine; Railway volumes are persistent so no I/O concerns.

### When to save

Save on every state-mutating call that can cross a restart boundary. There are
four natural hook points, all in `game_manager.py`:

1. **`start_game()`** — captures KICKOFF phase. Without this, a restart between
   "setup completed" and "first turn taken" loses the game entirely.

2. **`end_turn()`** — this is the primary save point. Already fires `_save_game_logs()`
   at the end. Add `_persist_game()` at the same location (line ~245):
   ```python
   if self.auto_save_logs:
       self._save_game_logs(game_state)
   self._persist_game(game_state)   # <-- add this
   ```

3. **`record_forfeit()`** — saves CONCLUDED phase so the row is cleaned up.

4. **`_record_result_if_concluded()`** — after the leaderboard write succeeds,
   delete the snapshot row (see §4 below).

Do **not** save during SETUP phase on buy_player / buy_reroll / place_players.
SETUP is intentionally excluded from restore (see §3). Saving without restoring
just wastes writes.

### Avoiding amplification

The `events` list grows by ~5–20 entries per turn, so by turn 30 a game has
~300 events. Each `end_turn()` rewrites the whole JSON. At 300 events × ~200
bytes each that's ~60 KB per write, every 30–60 seconds. This is negligible —
don't optimise it. A differential event log would add significant complexity
for no practical gain.

---

## 3. `_persist_game()` and `_delete_game_snapshot()` helpers

**File:** `app/state/game_manager.py`

Add these two methods to `GameManager`:

```python
def _persist_game(self, game_state: GameState) -> None:
    """Write the current game state to versus.db. Overwrites any existing row."""
    from app.state.agent_registry import _get_conn
    from datetime import datetime, timezone
    try:
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO game_snapshots
                    (game_id, phase, state_json, saved_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    game_state.game_id,
                    game_state.phase,           # str value of GamePhase enum
                    game_state.model_dump_json(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        logger.debug("Persisted game %s (phase=%s)", game_state.game_id, game_state.phase)
    except Exception as exc:
        logger.error("Failed to persist game %s: %s", game_state.game_id, exc)


def _delete_game_snapshot(self, game_id: str) -> None:
    """Remove a concluded game from the snapshots table."""
    from app.state.agent_registry import _get_conn
    try:
        with _get_conn() as conn:
            conn.execute("DELETE FROM game_snapshots WHERE game_id = ?", (game_id,))
            conn.commit()
        logger.debug("Deleted snapshot for concluded game %s", game_id)
    except Exception as exc:
        logger.error("Failed to delete snapshot for game %s: %s", game_id, exc)
```

Both methods swallow exceptions and log them — a persistence failure must never
crash the game loop. The `INSERT OR REPLACE` ensures save is idempotent.

---

## 4. `restore_active_games()` helper

**File:** `app/state/game_manager.py`

```python
def restore_active_games(self) -> int:
    """Load in-progress game snapshots from versus.db into self.games.

    Only restores games in KICKOFF, PLAYING, or HALF_TIME phase.
    SETUP games are skipped — the runner re-creates them via bootstrap.
    CONCLUDED games are skipped — they are done.

    Resets turn_started_at on each restored game so the timeout watcher
    doesn't immediately forfeit the game for a stale clock.

    Returns the number of games restored.
    """
    from app.state.agent_registry import _get_conn
    from datetime import datetime, timezone

    RESTORABLE_PHASES = ("kickoff", "playing", "half_time")

    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT game_id, state_json FROM game_snapshots WHERE phase IN (?, ?, ?)",
                RESTORABLE_PHASES,
            ).fetchall()
    except Exception as exc:
        logger.error("restore_active_games: DB error: %s", exc)
        return 0

    count = 0
    for row in rows:
        try:
            state = GameState.model_validate_json(row["state_json"])
            # Reset turn clock so timeout watcher doesn't fire immediately
            if state.turn:
                state.turn.turn_started_at = datetime.now(timezone.utc)
            self.games[state.game_id] = state
            logger.info(
                "Restored game %s (phase=%s, turn=%s)",
                state.game_id,
                state.phase,
                state.turn.team_turn if state.turn else "N/A",
            )
            count += 1
        except Exception as exc:
            logger.error("Failed to restore game %s: %s", row["game_id"], exc)

    if count:
        logger.info("Restored %d active game(s) from versus.db", count)
    return count
```

---

## 5. `GameManager` method changes — exact hooks

### `start_game()` — save at KICKOFF

After the final `return game_state` line, just before it, add:

```python
self._persist_game(game_state)
return game_state
```

(line ~197 in the current file, after the `logger.info` call)

### `end_turn()` — save after every turn

Current code at line ~244:
```python
# Auto-save logs after each turn
if self.auto_save_logs:
    self._save_game_logs(game_state)

return game_state
```

Change to:
```python
# Auto-save logs and persist state after each turn
if self.auto_save_logs:
    self._save_game_logs(game_state)
self._persist_game(game_state)

return game_state
```

Note: `_save_game_logs()` calls `_record_result_if_concluded()` when the game
ends. `_record_result_if_concluded()` is where we add snapshot cleanup (below).

### `record_forfeit()` — save after forfeit

At the end of `record_forfeit()`, after the existing `_save_game_logs` / 
`_record_result_if_concluded` calls:

```python
self._persist_game(game_state)   # update phase to 'finished' in snapshot
```

### `_record_result_if_concluded()` — delete snapshot on conclusion

At the end of the method, after the successful `self.leaderboard.record(result)`
and `self._recorded_games.add(...)` block:

```python
self._delete_game_snapshot(game_state.game_id)
```

Wrap in the same try/except pattern already used in that method. Deleting after
a successful leaderboard write means the snapshot lifecycle is:
```
start_game → [INSERT/REPLACE] → end_turn × N → ... → CONCLUDED → [DELETE]
```

If the delete fails (e.g. DB unavailable), the snapshot remains with phase
`finished`. The next restore skips it (phase not in restorable set), so it's
harmless. A periodic cleanup cron is fine-to-have but not required.

---

## 6. `app_lifespan` and `app/main.py` changes

### Move bootstrap calls into lifespan

**This is the most important structural change.**

Currently `app/main.py` bootstraps the game at module level (lines ~59–88),
*before* `init_db()` is called in lifespan. This means restore can't happen
first. Fix: remove the module-level bootstrap calls and re-add them inside
`app_lifespan`, after `init_db()` and `restore_active_games()`.

**Remove** lines ~59–88 (the entire `if demo_mode: ... else: ...` block) from
module level. Move the logic into `app_lifespan`:

```python
@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """FastAPI application lifespan."""
    logger.info("FastAPI application starting up...")

    # 1. Initialise DB schema / run migrations
    init_db()
    logger.info("versus.db initialised")

    # 2. Restore any in-progress games from the last run
    restored = game_manager.restore_active_games()
    logger.info("Restored %d active game(s) from previous run", restored)

    # 3. Bootstrap default/interactive game — idempotent, no-ops if already restored
    if demo_mode:
        bootstrap_default_game(
            game_manager,
            game_id=os.getenv("DEFAULT_GAME_ID", DEFAULT_GAME_ID),
            logger=logger,
        )
    else:
        bootstrap_interactive_game(
            game_manager,
            game_id=os.getenv("INTERACTIVE_GAME_ID", INTERACTIVE_GAME_ID),
            team1_name=os.getenv("TEAM1_NAME", "City Watch Constables"),
            team2_name=os.getenv("TEAM2_NAME", "Unseen University Adepts"),
            logger=logger,
        )

    logger.info("Game manager has %d active game(s)", len(game_manager.games))

    # 4. Start turn timeout watcher
    _timeout_task = asyncio.create_task(_turn_timeout_watcher())
    logger.info("Turn timeout watcher started")

    yield

    _timeout_task.cancel()
    logger.info("FastAPI application shutting down...")
```

The bootstrap functions are already idempotent — both check `manager.get_game()`
first. If restore loaded the game, bootstrap sees it and returns immediately.
If restore found nothing (first boot, or all games concluded), bootstrap creates
a fresh SETUP game as before.

**Remove the module-level variables** `demo_game_state` and `default_demo_game_id`
(they are not referenced elsewhere — confirm with `grep -r demo_game_state app/`).

The module-level `demo_mode` variable (line ~57) can stay where it is — it's just
an env-var read with no side-effects.

---

## 7. `run_simple_game.py` changes — detecting and resuming a restored game

The game runner's main loop assumes it must always run `run_setup()` first.
After a restart with a restored PLAYING game, `run_setup()` would call `buy-player`
endpoints that return 422 (wrong phase), crashing the setup phase.

**Add a resume-detection helper:**

```python
def _detect_resumed_game() -> bool:
    """Return True if the game is already in a restorable phase."""
    RESUMABLE = {"kickoff", "playing", "half_time"}
    try:
        resp = requests.get(f"{SERVER_URL}/game/{GAME_ID}", timeout=5)
        if resp.status_code == 200:
            st = resp.json()
            phase = (st.get("phase") or "").lower()
            if phase in RESUMABLE:
                logger.info(
                    "Detected restored game '%s' in phase '%s' — skipping setup",
                    GAME_ID,
                    phase,
                )
                # Sync model identities back from restored state
                if st.get("team1_model"):
                    TEAM_CONFIGS["team1"]["model"] = st["team1_model"]
                    tried_models_init["team1"] = {st["team1_model"]}
                if st.get("team2_model"):
                    TEAM_CONFIGS["team2"]["model"] = st["team2_model"]
                    tried_models_init["team2"] = {st["team2_model"]}
                return True
    except Exception as exc:
        logger.warning("Could not check for resumed game: %s", exc)
    return False
```

Move `tried_models` initialisation out of `run_game()` into a module-level dict
`tried_models_init` that `_detect_resumed_game` can write to, or just re-sync
inside `run_game()` from `TEAM_CONFIGS` at start (simpler).

**Update the main loop in `main()`:**

```python
# After wait_for_server() and model validation:

is_resumed = _detect_resumed_game()

while True:
    if not is_resumed:
        if not _MANUAL_MODEL_OVERRIDE:
            m1, m2 = pick_models(SERVER_URL)
            TEAM_CONFIGS["team1"]["model"] = m1
            TEAM_CONFIGS["team2"]["model"] = m2
            logger.info("Tournament pick: team1=%s  team2=%s", m1, m2)
        run_setup()

    is_resumed = False   # Only skip setup on the first (resumed) iteration

    run_game()
    trigger_rematch()
    wait_for_rematch()
```

This is a minimal diff. The only change to normal (non-resumed) flow is the
`is_resumed` flag wrapping. Every loop iteration after the first runs normally.

Note: `trigger_rematch()` calls `POST /game/{GAME_ID}/rematch` which resets to
SETUP and clears the in-memory state. The next `_persist_game()` call (on the
first `end_turn()` of the new game) will overwrite the snapshot with the fresh
SETUP state, then KICKOFF once setup completes, and so on.

---

## 8. Migration — existing `versus.db` without the new table

No ALTER TABLE migration is needed. `CREATE TABLE IF NOT EXISTS game_snapshots`
is a no-op if the table already exists, and creates it if it doesn't. This is
identical to how the `agents` and `lobby` tables are created.

The only edge case: a Railway instance that has been running for months may have
a `versus.db` at `/data/versus.db` without the new table. The first time the
new code deploys, `init_db()` runs and creates the table. No data loss.

---

## 9. Testing approach

No Railway volume required. The `DATA_DIR` env var makes the DB location
configurable. All existing tests already use this pattern (see `agent_registry.py`
line 21: `Path(os.getenv("DATA_DIR", ...))` — defaults to `data/` locally).

### Unit test: round-trip serialisation

```python
# tests/test_persistence.py
import os, tempfile
os.environ["DATA_DIR"] = tempfile.mkdtemp()   # must set before any import

from app.state.agent_registry import init_db
from app.state.game_manager import GameManager

def test_save_and_restore_kickoff():
    init_db()
    mgr = GameManager(auto_save_logs=False)

    # Create and advance to KICKOFF
    game = mgr.create_game("test-game-1")
    # ... buy players, place them, then:
    mgr.start_game("test-game-1")   # persists at KICKOFF

    # New manager instance simulates a restart
    mgr2 = GameManager(auto_save_logs=False)
    restored = mgr2.restore_active_games()
    assert restored == 1
    state = mgr2.get_game("test-game-1")
    assert state is not None
    assert state.phase == "kickoff"
    assert len(state.players) == len(game.players)

def test_concluded_game_not_restored():
    init_db()
    mgr = GameManager(auto_save_logs=False)
    # ... run a full game to CONCLUDED
    # Snapshot should be deleted after conclusion
    mgr2 = GameManager(auto_save_logs=False)
    assert mgr2.restore_active_games() == 0
```

### Integration / smoke test

Run the server locally, start a game, kill the server mid-game (Ctrl+C), restart,
check that `GET /game/the-match` returns the same game state in the same phase:

```bash
DATA_DIR=/tmp/scramble-test GAME_ID=the-match uv run python run_simple_game.py &
# Wait for game to reach PLAYING phase, then:
curl http://localhost:8000/game/the-match | python -m json.tool | grep '"phase"'
kill %1
DATA_DIR=/tmp/scramble-test uv run uvicorn app.main:app &
sleep 3
curl http://localhost:8000/game/the-match | python -m json.tool | grep '"phase"'
# Should still show "playing", not "setup"
```

---

## 10. Pitfalls and deliberate omissions

### Pitfall 1 — stale turn clock causes immediate forfeit

`TurnState.turn_started_at` is persisted with the snapshot. If the server was
down for 10 minutes and the turn clock says "started 10 minutes ago", the turn
timeout watcher fires within 60 seconds of startup and forfeits the active team.

**Fix:** `restore_active_games()` resets `turn_started_at` to `now()` on every
restored game (included in the implementation above). This gives each team a
fresh 5-minute window on restart.

### Pitfall 2 — module-level bootstrap creates a fresh game before lifespan

This is the ordering issue described in §0. **Fix:** move bootstrap into lifespan.
Do not skip this step — if you add `_persist_game` hooks without moving the
bootstrap, restores will be overwritten immediately by a fresh SETUP game.

### Pitfall 3 — `_recorded_games` set is lost on restart

`GameManager._recorded_games` is an in-memory deduplication guard. After
restore, a game that was previously recorded to the leaderboard won't have its
game_id in this set, so if it concludes again (impossible for a live game, but
possible if the snapshot is stale), `_record_result_if_concluded` might write
a duplicate leaderboard entry.

**Mitigation:** The leaderboard table uses `game_id` as part of its primary key
(confirm in `leaderboard_store.py`). If it does, the second INSERT is a no-op or
raises a handled IntegrityError. If it doesn't, add `INSERT OR IGNORE` there.
This is a belt-and-suspenders concern — in practice a game can only conclude once.

### Pitfall 4 — `GameState.model_validate_json` fails on schema changes

If a future code change adds a required field to GameState without a default,
deserialising an old snapshot will raise a ValidationError. The restore will log
the error and skip that game, falling back to a fresh SETUP — acceptable.

**Recommendation:** give every new GameState field a default value (use
`Optional[X] = None` or `Field(default=...)`). The existing model already does
this consistently.

### Pitfall 5 — large blob writes on every turn

For a 30-turn game with rich event history, each persist is ~200–400 KB. At one
write every 30–60 seconds, that's well within SQLite's capacity. If game logs
grow much larger (e.g. 5000+ events for a marathon game), consider a cutoff:
persist only the last N events in the snapshot and rely on the `game_log_saver`
for full history. Not needed now.

### Deliberate omission: SETUP phase persistence

SETUP phase is not restored. The game runner (`run_simple_game.py`) drives setup
via HTTP calls and has no "resume mid-setup" logic. Rather than add complex
checkpoint state to the runner, a restarted SETUP game just re-runs setup from
scratch. The cost is small (a few API calls and ~30 seconds of setup time).

If you want to restore SETUP in the future, the runner would need to detect which
players were already purchased and skip those buy calls — doable but out of scope.

### Deliberate omission: concurrent write safety

This plan assumes a single-process server (the current Railway deployment). If
multiple uvicorn workers are ever used (e.g. with `--workers 4`), concurrent
`_persist_game()` calls to the same `game_id` row could race. SQLite WAL mode
handles concurrent readers but not concurrent writers well. For multi-worker
deployments, switch to PostgreSQL and use `ON CONFLICT DO UPDATE`. Not needed now.

---

## 11. Summary of changes

| File | Change |
|---|---|
| `app/state/agent_registry.py` | Add `game_snapshots` table to `init_db()` |
| `app/state/game_manager.py` | Add `_persist_game()`, `_delete_game_snapshot()`, `restore_active_games()`; hook `_persist_game()` into `start_game()`, `end_turn()`, `record_forfeit()`; hook `_delete_game_snapshot()` into `_record_result_if_concluded()` |
| `app/main.py` | Move bootstrap calls from module-level into `app_lifespan`, after `init_db()` and `game_manager.restore_active_games()` |
| `run_simple_game.py` | Add `_detect_resumed_game()` helper; update `main()` loop to skip `run_setup()` when resumed |
| `tests/test_persistence.py` | New test file: round-trip and no-restore-after-conclude tests |

Total new code: ~80 lines across 4 files. No new dependencies.
