# Implementation Plan: Versus Mode Phase 4 — Game Manager Updates

## Overview

Two changes:
1. `app/models/leaderboard.py` — add nullable agent identity fields to `GameResult`
2. `app/state/game_manager.py` — update `_record_result_if_concluded` to query
   the `game_agents` SQLite table and populate those fields when present

No new files. No changes to game engine. Arena games are unaffected (fields are nullable).

---

## File 1: `app/models/leaderboard.py` — add nullable agent fields to GameResult

The `GameResult` class currently ends at `team2_total_message_chars`. Add these
fields at the end of the class, after `team2_total_message_chars`:

```python
    # Agent identity — populated for versus games, None for arena games
    team1_agent_id:   Optional[str] = None
    team1_agent_name: Optional[str] = None
    team2_agent_id:   Optional[str] = None
    team2_agent_name: Optional[str] = None
```

No other changes to this file.

---

## File 2: `app/state/game_manager.py` — update `_record_result_if_concluded`

### 2a. Add import at the top of the file

After the existing imports, add:
```python
from app.state.agent_registry import _get_conn, AgentRegistry
```

### 2b. Update `_record_result_if_concluded` to look up agent assignments

Find the block that builds the `GameResult(...)` call (around line 575).
Before the `GameResult(...)` constructor call, add this block to look up
agent assignments from the SQLite game_agents table:

```python
        # Look up agent assignments for versus games (None for arena games)
        team1_agent_id = team1_agent_name = None
        team2_agent_id = team2_agent_name = None
        try:
            with _get_conn() as conn:
                rows = conn.execute(
                    "SELECT ga.team_id, ga.agent_id, a.name "
                    "FROM game_agents ga "
                    "JOIN agents a ON ga.agent_id = a.agent_id "
                    "WHERE ga.game_id = ?",
                    (game_state.game_id,)
                ).fetchall()
            for row in rows:
                if row["team_id"] == "team1":
                    team1_agent_id = row["agent_id"]
                    team1_agent_name = row["name"]
                elif row["team_id"] == "team2":
                    team2_agent_id = row["agent_id"]
                    team2_agent_name = row["name"]
        except Exception as exc:
            logger.warning("Could not look up agent assignments for game %s: %s",
                           game_state.game_id, exc)
```

### 2c. Add the four new fields to the `GameResult(...)` constructor call

The existing constructor call ends with:
```python
            team1_total_message_chars=t1_total_message_chars,
            team2_total_message_chars=t2_total_message_chars,
        )
```

Change it to:
```python
            team1_total_message_chars=t1_total_message_chars,
            team2_total_message_chars=t2_total_message_chars,
            team1_agent_id=team1_agent_id,
            team1_agent_name=team1_agent_name,
            team2_agent_id=team2_agent_id,
            team2_agent_name=team2_agent_name,
        )
```

---

## Integration notes

- `_get_conn` is already defined in `app/state/agent_registry.py` and points to
  the same `versus.db` file used by the lobby. Importing it here is safe.
- The `game_agents` table is only populated for versus games. For arena games,
  the query returns zero rows and all four agent fields stay None. No change
  to arena behaviour.
- The `game_id` used in the query is `game_state.game_id`, which is the same ID
  used when the lobby called `game_manager.create_game(game_id)`.
- The `AgentRegistry` import is included in case it's needed but the lookup is
  done directly via `_get_conn` to avoid double token hashing overhead.

---

## Verification steps

1. Syntax checks:
   ```
   python3 -c "import ast; ast.parse(open('app/models/leaderboard.py').read()); print('leaderboard.py OK')"
   python3 -c "import ast; ast.parse(open('app/state/game_manager.py').read()); print('game_manager.py OK')"
   ```

2. Import check:
   ```
   source .venv/bin/activate
   python3 -c "from app.models.leaderboard import GameResult; r = GameResult(game_id='test', team1_name='A', team1_score=0, team2_name='B', team2_score=0); print('team1_agent_id:', r.team1_agent_id); print('OK')"
   ```

3. Full test suite:
   ```
   uv run pytest tests/ -q 2>&1 | tail -20
   ```

4. Quick end-to-end: start server, register two agents, pair them into a game,
   manually mark it concluded via the game state and verify the leaderboard
   picks up agent names. (This is complex to fully automate — confirming the
   GameResult fields are populated correctly via a unit test is sufficient.)

5. If all passes:
   ```
   git add -A && git commit -m "feat: versus phase 4 - agent identity in game results" && git push origin feature/versus
   ```
