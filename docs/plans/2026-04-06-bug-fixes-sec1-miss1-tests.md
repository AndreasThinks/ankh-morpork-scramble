# Implementation Plan: SEC-1, MISS-1, Tests

## Overview

Three remaining issues from code review:

1. **SEC-1**: O(N) bcrypt token scan — add `token_prefix` column for O(1) lookup
2. **MISS-1**: Turn timeout — 5-minute background task that forfeits stalled versus games
3. **Tests**: Basic test coverage for versus mode (registry, lobby, auth, leaderboard)

---

## Part 1: SEC-1 — O(1) Token Lookup

### Problem
`resolve_token()` in `app/state/agent_registry.py` fetches ALL agents and runs
bcrypt on each until it finds a match. O(N) bcrypt calls per request.

### Fix
Add a `token_prefix` column (first 12 chars of raw token — not secret, just
a fast discriminator). On lookup: `SELECT WHERE token_prefix=?` first, then
bcrypt only the matching row(s). Typically O(1).

### Changes

**`app/state/agent_registry.py`:**

1. In `init_db()`, add the column to the CREATE TABLE and add an index:
```python
CREATE TABLE IF NOT EXISTS agents (
    agent_id      TEXT PRIMARY KEY,
    name          TEXT UNIQUE NOT NULL,
    model         TEXT,
    token_hash    TEXT NOT NULL,
    token_prefix  TEXT NOT NULL DEFAULT '',
    registered_at TEXT NOT NULL
)
```
And add after the CREATE TABLE:
```python
conn.execute("CREATE INDEX IF NOT EXISTS idx_agents_token_prefix ON agents(token_prefix)")
```

2. Also run a migration for existing rows (token_prefix column may not exist):
```python
try:
    conn.execute("ALTER TABLE agents ADD COLUMN token_prefix TEXT NOT NULL DEFAULT ''")
    conn.commit()
except Exception:
    pass  # column already exists
```

3. In `register()`, after generating `raw_token`, set:
```python
token_prefix = raw_token[:12]
```
And include `token_prefix` in the INSERT:
```python
conn.execute(
    "INSERT INTO agents (agent_id, name, model, token_hash, token_prefix, registered_at) VALUES (?,?,?,?,?,?)",
    (agent_id, name, model, token_hash, token_prefix, now)
)
```

4. Replace `resolve_token()` body:
```python
def resolve_token(self, raw_token: str) -> Optional[AgentIdentity]:
    """Resolve a raw token to an AgentIdentity. Returns None if invalid."""
    if not raw_token or len(raw_token) < 12:
        return None
    prefix = raw_token[:12]
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM agents WHERE token_prefix=?", (prefix,)
        ).fetchall()
    for row in rows:
        if _verify_token(raw_token, row["token_hash"]):
            return AgentIdentity(
                agent_id=row["agent_id"],
                name=row["name"],
                model=row["model"],
                token_hash=row["token_hash"],
                registered_at=datetime.fromisoformat(row["registered_at"])
            )
    return None
```

---

## Part 2: MISS-1 — Turn Timeout Background Task

### Problem
The agent-skill.md promises a 5-minute turn timeout, but nothing enforces it.

### Fix
Add a FastAPI background task (asyncio) that:
- Runs every 60 seconds
- Finds active versus games where the current turn started > 5 minutes ago
- Calls `record_forfeit()` on the game manager to conclude the game

### Changes

**`app/state/game_manager.py`:** Add `record_forfeit()` method:

```python
def record_forfeit(self, game_id: str, forfeiting_team_id: str) -> None:
    """Conclude a versus game as a forfeit loss for the specified team."""
    game_state = self.get_game(game_id)
    if not game_state:
        return
    if game_state.phase == GamePhase.CONCLUDED:
        return  # already concluded

    # Set the winning team's score to 1 if it's 0-0 (forfeit = loss)
    if forfeiting_team_id == game_state.team1.id:
        if game_state.team2.score == 0:
            game_state.team2.score = 1
    else:
        if game_state.team1.score == 0:
            game_state.team1.score = 1

    # Conclude the game
    game_state.phase = GamePhase.CONCLUDED

    logger.warning(
        "Game %s: %s forfeited (turn timeout). Concluding.",
        game_id, forfeiting_team_id
    )

    # Save logs and record result
    if self.auto_save_logs:
        self._save_game_logs(game_state)
    else:
        self._record_result_if_concluded(game_state)
```

**`app/state/game_state.py` or `app/models/game_state.py`:** The GameState needs
a `turn_started_at` timestamp. Add to `TurnState`:
```python
turn_started_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
```
Import `datetime` and `timezone` from `datetime` module if not already present.

**`app/state/game_manager.py`:** In `end_turn()`, when a new turn begins, reset
`turn_started_at`. Find where `game_state.turn.active_team_id` is updated and add:
```python
game_state.turn.turn_started_at = datetime.now(timezone.utc)
```

**`app/main.py`:** Add the background task in the lifespan:

After `init_db()`:
```python
import asyncio as _asyncio
from datetime import datetime, timezone, timedelta

async def _turn_timeout_watcher():
    """Background task: forfeit versus games where a turn has exceeded 5 minutes."""
    TIMEOUT_MINUTES = 5
    CHECK_INTERVAL = 60  # seconds

    while True:
        await _asyncio.sleep(CHECK_INTERVAL)
        try:
            now = datetime.now(timezone.utc)
            for game_id, game_state in list(game_manager.games.items()):
                # Only check versus games (have agent assignments) that are active
                if game_state.phase not in ("PLAYING", "KICKOFF"):
                    continue
                if not game_state.turn:
                    continue
                turn_started = game_state.turn.turn_started_at
                if not turn_started:
                    continue
                # Make timezone-aware if naive
                if turn_started.tzinfo is None:
                    turn_started = turn_started.replace(tzinfo=timezone.utc)
                elapsed = now - turn_started
                if elapsed > timedelta(minutes=TIMEOUT_MINUTES):
                    # Check this is a versus game
                    with _versus_get_conn() as conn:
                        row = conn.execute(
                            "SELECT agent_id FROM game_agents WHERE game_id=? LIMIT 1",
                            (game_id,)
                        ).fetchone()
                    if row:
                        active_team = game_state.turn.active_team_id
                        logger.warning(
                            "Turn timeout: game %s team %s exceeded %d minutes",
                            game_id, active_team, TIMEOUT_MINUTES
                        )
                        game_manager.record_forfeit(game_id, active_team)
        except Exception as exc:
            logger.error("Turn timeout watcher error: %s", exc)
```

In the lifespan `async` function, start the task:
```python
_timeout_task = _asyncio.create_task(_turn_timeout_watcher())
yield
_timeout_task.cancel()
```

Note: the lifespan function must be `async def` for `asyncio.create_task` to work.
Check if it already is; if not, change `def app_lifespan` to `async def app_lifespan`.

---

## Part 3: Tests

Create `tests/versus/` directory with `__init__.py` and these test files:

### `tests/versus/test_agent_registry.py`

```python
import pytest, os, tempfile
from unittest.mock import patch
from pathlib import Path

@pytest.fixture
def registry(tmp_path):
    with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
        from app.state.agent_registry import AgentRegistry, init_db
        init_db()
        yield AgentRegistry()

def test_register_new_agent(registry):
    identity, token = registry.register("TestBot", "gpt-4o")
    assert identity.name == "TestBot"
    assert token.startswith("ams_")
    assert len(token) == 36

def test_register_duplicate_name_raises(registry):
    registry.register("DupeBot")
    with pytest.raises(ValueError, match="already taken"):
        registry.register("DupeBot")

def test_resolve_token_valid(registry):
    identity, token = registry.register("TokenBot")
    resolved = registry.resolve_token(token)
    assert resolved is not None
    assert resolved.agent_id == identity.agent_id

def test_resolve_token_invalid(registry):
    assert registry.resolve_token("ams_notreal00000000000000000000000") is None

def test_resolve_token_prefix_fast_path(registry):
    """Token lookup uses prefix index — invalid prefix returns None immediately."""
    identity, token = registry.register("PrefixBot")
    bad_token = "ams_" + "x" * 32
    assert registry.resolve_token(bad_token) is None

def test_name_taken(registry):
    registry.register("TakenBot")
    assert registry.name_taken("TakenBot") is True
    assert registry.name_taken("FreeBot") is False

def test_name_too_short_raises(registry):
    with pytest.raises(ValueError):
        registry.register("X")

def test_name_too_long_raises(registry):
    with pytest.raises(ValueError):
        registry.register("A" * 33)
```

### `tests/versus/test_lobby.py`

```python
import pytest, os
from unittest.mock import patch, MagicMock

@pytest.fixture
def lobby(tmp_path):
    with patch.dict(os.environ, {"DATA_DIR": str(tmp_path)}):
        from app.state.agent_registry import AgentRegistry, init_db
        from app.state.lobby import LobbyManager
        init_db()
        reg = AgentRegistry()
        gm = MagicMock()
        gm.create_game = MagicMock()
        gm.get_game = MagicMock(return_value=MagicMock(team1=MagicMock(name="t1"), team2=MagicMock(name="t2")))
        mgr = LobbyManager(gm)
        yield reg, mgr

def test_first_agent_waits(lobby):
    reg, mgr = lobby
    a1, _ = reg.register("AgentA")
    result = mgr.join(a1.agent_id)
    assert result["status"] == "waiting"

def test_second_agent_matches(lobby):
    reg, mgr = lobby
    a1, _ = reg.register("AgentA")
    a2, _ = reg.register("AgentB")
    mgr.join(a1.agent_id)
    result = mgr.join(a2.agent_id)
    assert result["status"] == "matched"
    assert result["game_id"] is not None
    assert result["team_id"] in ("team1", "team2")

def test_rejoin_while_matched_returns_existing(lobby):
    reg, mgr = lobby
    a1, _ = reg.register("AgentC")
    a2, _ = reg.register("AgentD")
    mgr.join(a1.agent_id)
    mgr.join(a2.agent_id)
    # A1 calls join again — should get existing state, not re-queue
    result = mgr.join(a1.agent_id)
    assert result["status"] == "matched"
    assert result["game_id"] is not None

def test_leave_removes_waiting_agent(lobby):
    reg, mgr = lobby
    a1, _ = reg.register("AgentE")
    mgr.join(a1.agent_id)
    removed = mgr.leave(a1.agent_id)
    assert removed is True
    status = mgr.get_status(a1.agent_id)
    assert status["status"] == "not_in_lobby"

def test_leave_matched_agent_does_nothing(lobby):
    reg, mgr = lobby
    a1, _ = reg.register("AgentF")
    a2, _ = reg.register("AgentG")
    mgr.join(a1.agent_id)
    mgr.join(a2.agent_id)
    removed = mgr.leave(a1.agent_id)
    assert removed is False  # can't leave once matched
```

### `tests/versus/test_leaderboard_agents.py`

```python
import pytest
from app.models.leaderboard import GameResult, AgentLeaderboardEntry
from app.state.leaderboard_store import LeaderboardStore
from pathlib import Path

def make_versus_result(game_id, a1_id, a1_name, a2_id, a2_name, score1, score2):
    return GameResult(
        game_id=game_id,
        team1_name=a1_name, team1_model="gpt-4o", team1_score=score1,
        team2_name=a2_name, team2_model="claude-3", team2_score=score2,
        team1_agent_id=a1_id, team1_agent_name=a1_name,
        team2_agent_id=a2_id, team2_agent_name=a2_name,
    )

def test_agent_leaderboard_populated(tmp_path):
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    store.record(make_versus_result("g1", "a1", "BotA", "a2", "BotB", 3, 1))
    store.record(make_versus_result("g2", "a1", "BotA", "a2", "BotB", 1, 2))

    lb = store.get_leaderboard()
    assert len(lb.by_agent) == 2

    bota = next(e for e in lb.by_agent if e.agent_name == "BotA")
    assert bota.wins == 1
    assert bota.losses == 1
    assert bota.goals_for == 4
    assert bota.goals_against == 3

def test_arena_games_not_in_agent_leaderboard(tmp_path):
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    # Arena game — no agent_id fields
    store.record(GameResult(
        game_id="arena1",
        team1_name="CW", team1_model="gpt-4o", team1_score=2,
        team2_name="UU", team2_model="claude-3", team2_score=1,
    ))
    lb = store.get_leaderboard()
    assert lb.by_agent == []
    assert len(lb.by_model) == 2  # arena models still appear

def test_game_id_matches_state(tmp_path):
    """BUG-1 regression: GameResult game_id must match the actual game_id."""
    store = LeaderboardStore(path=tmp_path / "results.jsonl")
    result = make_versus_result("real-game-id", "a1", "BotA", "a2", "BotB", 1, 0)
    store.record(result)
    loaded = store.load_all()
    assert loaded[0].game_id == "real-game-id"
```

---

## Verification steps

1. Syntax checks on all modified files
2. Run full test suite including new tests:
   ```
   source .venv/bin/activate
   uv run pytest tests/ -q 2>&1 | tail -20
   uv run pytest tests/versus/ -v 2>&1 | tail -30
   ```
3. Confirm token prefix migration runs cleanly on a fresh DB
4. If all passes:
   ```
   git add -A && git commit -m "fix: SEC-1 token prefix lookup, MISS-1 turn timeout, versus test coverage" && git push origin feature/versus
   ```
