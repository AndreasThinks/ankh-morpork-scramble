# Reachable Squares Plan

> **For Cline or Hermes:** Implement in order. Each task is a self-contained commit.

**Goal:** Eliminate illegal move attempts by the LLM agent. Instead of asking the LLM to
construct arbitrary paths, give it a pre-computed list of reachable destination squares per
player. The LLM picks a destination from the menu; path construction errors become impossible.

**Root cause:** The LLM knows a player's MA remaining but still constructs paths that exceed
it, pass through occupied squares, or go out of bounds. Pre-computing reachability on the
server removes these failure modes entirely.

**Architecture:** Four-file change.
1. `app/game/movement.py` — add `get_reachable_squares()` method to `MovementHandler`
2. `app/models/actions.py` — add `reachable_squares` field to `ValidActionsResponse`
3. `app/main.py` — populate `reachable_squares` in `/valid-actions` endpoint
4. `simple_agents/player.py` — use reachable squares in `_describe_valid_actions()`

**No frontend changes. No database changes. No new dependencies.**

---

## Task 1: Add `get_reachable_squares()` to MovementHandler

**File:** `app/game/movement.py`

**Objective:** BFS flood-fill from a player's current position to find all squares they can
legally reach this turn, respecting MA remaining, rush limit (2 extra squares), pitch bounds,
and occupied squares.

**Insert after the `can_move_to()` method (after line 99):**

```python
def get_reachable_squares(
    self,
    game_state: "GameState",
    player_id: str,
) -> list[dict]:
    """BFS flood-fill to find all squares reachable by this player this turn.

    Returns a list of dicts: {"x": int, "y": int, "rush": bool}
    "rush" is True when the square requires one or two rush rolls to reach.
    Occupied squares and out-of-bounds squares are excluded.
    """
    from collections import deque
    from app.models.pitch import Position

    player = game_state.get_player(player_id)
    if not player or not player.is_standing:
        return []

    start = game_state.pitch.player_positions.get(player_id)
    if not start:
        return []

    ma_remaining = player.movement_remaining  # squares before rush needed
    max_steps = ma_remaining + 2              # +2 for rush

    # BFS: track minimum steps to reach each square
    visited: dict[tuple[int, int], int] = {(start.x, start.y): 0}
    queue: deque[tuple[int, int, int]] = deque([(start.x, start.y, 0)])
    reachable: list[dict] = []

    while queue:
        x, y, steps = queue.popleft()

        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy

                # Pitch bounds: 26 wide (x 0-25), 15 tall (y 0-14)
                if not (0 <= nx < 26 and 0 <= ny < 15):
                    continue

                new_steps = steps + 1
                if new_steps > max_steps:
                    continue

                key = (nx, ny)
                if key in visited and visited[key] <= new_steps:
                    continue

                next_pos = Position(x=nx, y=ny)

                # Skip occupied squares (can't move through or into)
                if game_state.pitch.is_occupied(next_pos):
                    continue

                visited[key] = new_steps
                reachable.append({
                    "x": nx,
                    "y": ny,
                    "rush": new_steps > ma_remaining,
                })
                if new_steps < max_steps:
                    queue.append((nx, ny, new_steps))

    return reachable
```

**Verification:** Add a quick sanity check in a Python shell:
```python
# In the project root with the venv active:
# A player with MA=6, movement_used=0, at (10,7) on an empty pitch
# should have many reachable squares; a player with MA=0 should have none.
```

**Commit:** `feat: MovementHandler.get_reachable_squares() — BFS flood-fill for valid destinations`

---

## Task 2: Add `reachable_squares` to `ValidActionsResponse`

**File:** `app/models/actions.py`

**Objective:** Add the new field so the endpoint can return it.

**Find the `ValidActionsResponse` class. After the `ball_position` field, add:**

```python
    # Per-player reachable squares (pre-computed for the LLM agent)
    # Maps player_id -> list of {"x": int, "y": int, "rush": bool}
    reachable_squares: dict[str, list[dict]] = Field(
        default_factory=dict,
        description="Per-player reachable destination squares this turn"
    )
```

**Commit:** `feat: ValidActionsResponse.reachable_squares field`

---

## Task 3: Populate `reachable_squares` in the `/valid-actions` endpoint

**File:** `app/main.py`

**Objective:** Call `get_reachable_squares()` for each movable player and include the result.

**Find `get_valid_actions()` (around line 626). It already imports nothing new — the
`MovementHandler` is accessed via `game_manager` or needs to be instantiated. Check whether
`game_manager` exposes a movement handler, or instantiate one directly:**

```python
from app.game.movement import MovementHandler
from app.game.dice import DiceRoller
```

Add these imports at the top of `app/main.py` if not already present.

**Inside `get_valid_actions()`, after the `movable_players` / `blockable_targets` loops,
add:**

```python
    # Pre-compute reachable squares for each movable player
    movement_handler = MovementHandler(DiceRoller())
    reachable_squares: dict[str, list[dict]] = {}
    for player_id in movable_players:
        reachable_squares[player_id] = movement_handler.get_reachable_squares(
            game_state, player_id
        )
```

**Update the `return ValidActionsResponse(...)` call to include:**

```python
        reachable_squares=reachable_squares,
```

**Verification:**
```bash
# Start the server locally and call the endpoint:
uv run uvicorn app.main:app --port 8001 &
curl -s http://localhost:8001/game/the-match/valid-actions | python3 -m json.tool | grep -A5 reachable
# Should see per-player lists of {x, y, rush} dicts
```

**Commit:** `feat: /valid-actions populates reachable_squares per movable player`

---

## Task 4: Use reachable squares in `_describe_valid_actions()`

**File:** `simple_agents/player.py`

**Objective:** Replace the prose "X squares remaining" description with a concrete list of
valid destination squares. The LLM picks one and uses it as the final element of `path`.

**Find `_describe_valid_actions()`. In the movable-players loop, after the `ma_note` line,
replace the `lines.append(f"  - [{pid}] {role}...")` call with:**

```python
            reachable = (valid_actions.get("reachable_squares") or {}).get(pid, [])
            safe_squares = [(s["x"], s["y"]) for s in reachable if not s.get("rush")]
            rush_squares = [(s["x"], s["y"]) for s in reachable if s.get("rush")]

            if safe_squares:
                # Show up to 12 safe destinations to keep prompt size reasonable
                safe_sample = safe_squares[:12]
                safe_str = ", ".join(f"({x},{y})" for x, y in safe_sample)
                more = f" (+{len(safe_squares)-12} more)" if len(safe_squares) > 12 else ""
                lines.append(
                    f"  - [{pid}] {role} at ({x},{y}): "
                    f"{ma_remaining} squares free — safe destinations: {safe_str}{more}"
                )
            else:
                lines.append(
                    f"  - [{pid}] {role} at ({x},{y}): {ma_note} (no safe moves)"
                )

            if rush_squares:
                rush_sample = rush_squares[:6]
                rush_str = ", ".join(f"({rx},{ry})" for rx, ry in rush_sample)
                lines.append(
                    f"    Rush options (dice roll required, max 2 extra squares): {rush_str}"
                )
```

**Also update the system prompt hint in `_BASE_RULES` to tell the LLM to use the provided
destinations:**

Find the Move action format line and add a note:
```
  Move:     {"action_type":"move","player_id":"...","path":[{"x":N,"y":N},...]}
            IMPORTANT: the final element of path must be a square listed under
            "safe destinations" or "Rush options" in VALID ACTIONS below.
            Intermediate squares must form a connected path — each step adjacent
            to the previous.
```

**Commit:** `feat: _describe_valid_actions uses pre-computed reachable squares`

---

## Execution notes

- Tasks 1–3 can be done sequentially in one session (they build on each other).
- Task 4 is independent of 1–3 at the code level but only useful once 1–3 are deployed.
- The BFS in Task 1 runs in <1ms for typical board states (26x15 grid, max MA+2=10 steps).
  No caching needed.
- The `reachable_squares` field is additive — old clients that don't read it are unaffected.
- If `reachable_squares` is empty for a player (e.g. completely surrounded), the existing
  prose fallback in `_describe_valid_actions` still works.

## What this fixes

After these changes the LLM cannot generate an out-of-bounds move, a too-long path, or a
path that ends on an occupied square. The only remaining failure mode is an invalid
intermediate step (path goes through an occupied square on the way to a valid destination).
That can be addressed later by either:
  a) Having the server compute the full path given just the destination (cleanest)
  b) Having the agent use a straight-line path heuristic
Option (a) is a natural follow-up task: add a `/game/{id}/path` endpoint that takes
`player_id` + `destination` and returns the optimal path.
