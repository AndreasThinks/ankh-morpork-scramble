# LLM Move Quality Improvements

> **For Cline:** Implement each task in order. Each task is a self-contained commit. Read the exact file/line references before editing — line numbers are approximate and may shift after prior tasks.

**Goal:** Dramatically reduce the number of failed/rejected action attempts by the LLM agent by giving it richer, more actionable information at every decision point.

**Root cause:** The LLM repeatedly tries moves that fail validation because (a) it cannot see remaining MA per player, (b) the valid-actions JSON is opaque machine data, (c) failure messages are bare server strings without context, and (d) it cannot tell how many players are still eligible to act this turn.

**Architecture:** Changes are split between:
- `simple_agents/state_summary.py` — what the LLM sees as game context
- `simple_agents/player.py` — how failures are fed back and how valid-actions are presented
- No backend changes required. All improvements are on the agent/client side.

**Tech stack:** Pure Python. No new dependencies.

---

## Phase 1: Core Information Gaps

### Task 1: Add per-player movement budget to state summary

**Objective:** The LLM currently sees `MA6` for every player but has no idea how much of that is already spent. It also cannot tell which players have already acted this turn. This causes it to plan moves for exhausted or already-acted players.

**File:** `simple_agents/state_summary.py`

**Current code (lines 42–62):**
```python
    # My squad
    lines.append("YOUR SQUAD:")
    for pid in my_team.get("player_ids") or []:
        p = players.get(pid) or {}
        pos = player_positions.get(pid) or {}
        x, y = pos.get("x", "?"), pos.get("y", "?")
        flags = []
        if not p.get("is_active", True):
            flags.append("OFF PITCH")
        elif p.get("is_prone", False):
            flags.append("PRONE")
        if pid == ball_carrier_id:
            flags.append("BALL")
        skills = p.get("skills") or []
        skill_str = f" [{','.join(skills[:3])}]" if skills else ""
        flag_str = f" | {', '.join(flags)}" if flags else ""
        lines.append(
            f"  [{pid}] {str(p.get('position',{}).get('role','?')):<22} ({x:>2},{y:>2})"
            f"  MA{p.get('ma', p.get('position',{}).get('ma','?'))} ST{p.get('st', p.get('position',{}).get('st','?'))} AG{p.get('ag', p.get('position',{}).get('ag','?'))}"
            f"{skill_str}{flag_str}"
        )
```

**Note:** The game state serialises `Player` model instances. The `Player` model (app/models/player.py) has `movement_used: int`, `has_acted: bool`, and a computed property `movement_remaining`. After JSON serialisation these come through as `movement_used` and `has_acted` keys in the player dict. The `state` field is a `PlayerState` enum that serialises to a string like `"standing"`, `"prone"`, `"stunned"`, `"knocked_out"`, `"casualty"`.

**Replacement (replace the entire YOUR SQUAD block):**
```python
    # My squad
    my_players_unacted = 0
    lines.append("YOUR SQUAD:")
    for pid in my_team.get("player_ids") or []:
        p = players.get(pid) or {}
        pos = player_positions.get(pid) or {}
        x, y = pos.get("x", "?"), pos.get("y", "?")

        state_val = p.get("state", "standing")
        has_acted = p.get("has_acted", False)
        movement_used = p.get("movement_used", 0)

        # Compute MA values
        position_data = p.get("position") or {}
        ma_total = p.get("ma") or position_data.get("ma") or "?"
        if isinstance(ma_total, int):
            ma_remaining = max(0, ma_total - movement_used)
            ma_str = f"MA{ma_remaining}/{ma_total}"
        else:
            ma_str = f"MA{ma_total}"

        flags = []
        if state_val in ("knocked_out", "casualty"):
            flags.append("OFF PITCH")
        elif state_val == "stunned":
            flags.append("STUNNED")
        elif state_val == "prone":
            flags.append("PRONE")
        if has_acted:
            flags.append("ACTED")
        else:
            # Only count on-pitch, not-yet-acted players
            if state_val not in ("knocked_out", "casualty"):
                my_players_unacted += 1
        if pid == ball_carrier_id:
            flags.append("BALL")

        skills = p.get("skills") or []
        skill_str = f" [{','.join(skills[:3])}]" if skills else ""
        flag_str = f" | {', '.join(flags)}" if flags else ""
        lines.append(
            f"  [{pid}] {str(position_data.get('role','?')):<22} ({x:>2},{y:>2})"
            f"  {ma_str} ST{p.get('st') or position_data.get('st','?')} AG{p.get('ag') or position_data.get('ag','?')}"
            f"{skill_str}{flag_str}"
        )
```

Also update the opponent squad block (lines 65–81) to show `ACTED` flag so the LLM knows which opponents have already spent their turn:
```python
    lines.append("")
    lines.append("OPPONENT SQUAD:")
    for pid in opp_team.get("player_ids") or []:
        p = players.get(pid) or {}
        pos = player_positions.get(pid) or {}
        x, y = pos.get("x", "?"), pos.get("y", "?")
        state_val = p.get("state", "standing")
        flags = []
        if state_val in ("knocked_out", "casualty"):
            flags.append("OFF PITCH")
        elif state_val == "stunned":
            flags.append("STUNNED")
        elif state_val == "prone":
            flags.append("PRONE")
        if pid == ball_carrier_id:
            flags.append("BALL")
        flag_str = f" | {', '.join(flags)}" if flags else ""
        position_data = p.get("position") or {}
        lines.append(
            f"  [{pid}] {str(position_data.get('role','?')):<22} ({x:>2},{y:>2})"
            f"  ST{p.get('st') or position_data.get('st','?')}{flag_str}"
        )
```

And return `my_players_unacted` from the function for use in Task 4. Change the function signature and return statement:

Current (line 4): `def summarize_for_player(state: dict, my_team_id: str) -> str:`
New: `def summarize_for_player(state: dict, my_team_id: str) -> tuple[str, int]:`

Current (line 92): `return "\n".join(lines)`
New: `return "\n".join(lines), my_players_unacted`

**Important:** After changing the return type, update the call site in `simple_agents/player.py` line 214:
```python
        summary, players_unacted = summarize_for_player(state, team_id)
```

**Commit:** `feat: per-player MA remaining and ACTED flag in state summary`

---

### Task 2: Transform valid-actions JSON into plain-language descriptions

**Objective:** The raw `ValidActionsResponse` JSON is machine-readable but hard for an LLM to reason about. The `movable_players` list is just a list of opaque IDs with no context. The `blockable_targets` dict needs to be expanded into sentences.

**File:** `simple_agents/player.py`

**Add a new helper function** after line 183 (after `_parse_step`), before `play_turn`:

```python
def _describe_valid_actions(valid_actions: dict, state: dict, team_id: str) -> str:
    """Convert the /valid-actions JSON into human-readable sentences the LLM can reason about."""
    players = state.get("players") or {}
    pitch = state.get("pitch") or {}
    player_positions = pitch.get("player_positions") or {}

    lines = ["WHAT YOU CAN DO THIS ACTION:"]

    # Per-player move opportunities
    movable = valid_actions.get("movable_players") or []
    if movable:
        lines.append("")
        lines.append("Players who can still MOVE (have MA remaining, not yet acted):")
        for pid in movable:
            p = players.get(pid) or {}
            pos = player_positions.get(pid) or {}
            position_data = p.get("position") or {}
            role = position_data.get("role", pid)
            ma_total = position_data.get("ma", "?")
            movement_used = p.get("movement_used", 0)
            if isinstance(ma_total, int):
                ma_remaining = max(0, ma_total - movement_used)
                ma_note = f"{ma_remaining} squares remaining (used {movement_used}/{ma_total})"
            else:
                ma_note = f"MA{ma_total}"
            x, y = pos.get("x", "?"), pos.get("y", "?")
            lines.append(f"  - [{pid}] {role} at ({x},{y}): {ma_note}")
    else:
        lines.append("  No players can move (all have acted or exhausted MA).")

    # Block/scuffle opportunities
    blockable = valid_actions.get("blockable_targets") or {}
    if blockable:
        lines.append("")
        lines.append("Players who can BLOCK (scuffle) — already adjacent to an opponent:")
        for attacker_pid, target_pids in blockable.items():
            p = players.get(attacker_pid) or {}
            pos = player_positions.get(attacker_pid) or {}
            position_data = p.get("position") or {}
            role = position_data.get("role", attacker_pid)
            x, y = pos.get("x", "?"), pos.get("y", "?")
            target_descs = []
            for tpid in target_pids:
                tp = players.get(tpid) or {}
                tpos = player_positions.get(tpid) or {}
                trole = (tp.get("position") or {}).get("role", tpid)
                tx, ty = tpos.get("x", "?"), tpos.get("y", "?")
                target_descs.append(f"[{tpid}] {trole} at ({tx},{ty})")
            lines.append(f"  - [{attacker_pid}] {role} at ({x},{y}) can scuffle: {'; '.join(target_descs)}")

    # One-per-turn special actions
    specials = []
    if valid_actions.get("can_charge"):
        specials.append("CHARGE (move + block in one action) — not yet used this turn")
    else:
        specials.append("CHARGE — already used this turn (only once allowed)")
    if valid_actions.get("can_hurl"):
        specials.append("HURL (pass the ball) — not yet used this turn")
    else:
        specials.append("HURL — already used this turn")
    if valid_actions.get("can_quick_pass"):
        specials.append("QUICK PASS (hand-off to adjacent teammate) — not yet used this turn")
    else:
        specials.append("QUICK PASS — already used this turn")

    lines.append("")
    lines.append("One-per-turn special actions:")
    for s in specials:
        lines.append(f"  - {s}")

    # Ball state
    ball_carrier = valid_actions.get("ball_carrier")
    ball_on_ground = valid_actions.get("ball_on_ground", False)
    ball_pos = valid_actions.get("ball_position")
    lines.append("")
    if ball_carrier:
        bc = players.get(ball_carrier) or {}
        bc_team = bc.get("team_id", "?")
        bc_role = (bc.get("position") or {}).get("role", ball_carrier)
        ownership = "YOUR player" if bc_team == team_id else "OPPONENT'S player"
        bpos = player_positions.get(ball_carrier) or {}
        bx, by = bpos.get("x", "?"), bpos.get("y", "?")
        lines.append(f"Ball: carried by {ownership} [{ball_carrier}] {bc_role} at ({bx},{by})")
    elif ball_on_ground and ball_pos:
        lines.append(f"Ball: loose on ground at ({ball_pos.get('x','?')},{ball_pos.get('y','?')}) — move a player there to pick it up")
    else:
        lines.append("Ball: not yet in play")

    lines.append("")
    lines.append("You may also return action=null to end your turn voluntarily.")

    return "\n".join(lines)
```

**Update the user_msg construction in `play_turn` (lines 219–224):**

Replace:
```python
        user_msg = (
            f"{summary}\n\n"
            f"VALID ACTIONS:\n{json.dumps(valid_actions, indent=2)}\n"
            f"{failure_note}\n"
            "What is your next single action? Return one JSON object with 'thought' and 'action'."
        )
```

With:
```python
        valid_actions_prose = _describe_valid_actions(valid_actions, state, team_id)
        user_msg = (
            f"{summary}\n\n"
            f"{valid_actions_prose}\n"
            f"{failure_note}\n"
            "What is your next single action? Return one JSON object with 'thought' and 'action'."
        )
```

**Commit:** `feat: plain-language valid-actions description for LLM`

---

## Phase 2: Feedback Quality

### Task 3: Richer failure feedback messages

**Objective:** When an action fails, the LLM currently sees only the raw server error string (e.g. `"Player has already acted this turn"`). It has no context about which player it tried to move, what that player's current stats are, or what alternatives exist. This causes it to retry the same broken move.

**File:** `simple_agents/player.py`

**Add a new helper function** after `_describe_valid_actions` (before `play_turn`):

```python
def _build_failure_note(last_failure: str, last_action: dict | None, state: dict, team_id: str) -> str:
    """Build a rich, contextual failure message for the LLM retry prompt."""
    if not last_failure:
        return ""

    lines = ["PREVIOUS ACTION FAILED — choose a different valid action."]
    lines.append(f"  Error: {last_failure}")

    if last_action:
        action_type = last_action.get("action_type", "unknown")
        player_id = last_action.get("player_id")
        lines.append(f"  Failed action: {action_type}" + (f" by player [{player_id}]" if player_id else ""))

        if player_id:
            players = state.get("players") or {}
            pitch = state.get("pitch") or {}
            player_positions = pitch.get("player_positions") or {}
            p = players.get(player_id) or {}
            pos = player_positions.get(player_id) or {}
            position_data = p.get("position") or {}
            role = position_data.get("role", player_id)
            ma_total = position_data.get("ma", "?")
            movement_used = p.get("movement_used", 0)
            has_acted = p.get("has_acted", False)
            state_val = p.get("state", "standing")
            x, y = pos.get("x", "?"), pos.get("y", "?")

            if isinstance(ma_total, int):
                ma_remaining = max(0, ma_total - movement_used)
                ma_note = f"{ma_remaining}/{ma_total} remaining"
            else:
                ma_note = f"MA{ma_total}"

            lines.append(f"  Player [{player_id}] {role} stats:")
            lines.append(f"    Position: ({x},{y})  State: {state_val}  MA: {ma_note}  Already acted: {has_acted}")

            if has_acted:
                lines.append("    -> This player has already acted this turn. Pick a different player.")
            if isinstance(ma_total, int) and ma_total - movement_used <= 0:
                lines.append("    -> This player has no MA remaining. Pick a different player or end turn.")
            if state_val in ("knocked_out", "casualty"):
                lines.append("    -> This player is off the pitch and cannot act.")
            if state_val == "stunned":
                lines.append("    -> This player is stunned and cannot act.")

        # If it was a move, note path length constraint
        if action_type == "move":
            path = last_action.get("path") or []
            lines.append(f"  Path you tried had {len(path)} steps.")
            if player_id:
                players = state.get("players") or {}
                p = players.get(player_id) or {}
                position_data = p.get("position") or {}
                ma_total = position_data.get("ma", "?")
                movement_used = p.get("movement_used", 0)
                if isinstance(ma_total, int):
                    ma_remaining = max(0, ma_total - movement_used)
                    lines.append(f"  Player can move at most {ma_remaining} squares (+ up to 2 rush squares with dice).")
                    lines.append(f"  Path must be exactly the squares you want to traverse — don't include starting square.")

    lines.append("")
    return "\n".join(lines)
```

**Update `play_turn` to track `last_action` and use the new helper.**

In `play_turn`, add `last_action: dict | None = None` after `last_failure: str | None = None` (line 199):
```python
    actions_taken = 0
    last_failure: str | None = None
    last_action: dict | None = None
```

Replace the failure_note construction (line 218):
```python
        failure_note = f"\nPREVIOUS ACTION FAILED: {last_failure}\nChoose a different valid action.\n" if last_failure else ""
```

With:
```python
        failure_note = _build_failure_note(last_failure, last_action, state, team_id)
```

After successful action (where `last_failure = None` is set, around line 257):
```python
                if ok:
                    last_failure = None
                    last_action = None
                    actions_taken += 1
                    break
                else:
                    last_failure = msg
                    last_action = action
                    if attempt < MAX_RETRIES_PER_ACTION - 1:
                        break
```

Also update the exception handler (around line 265–267):
```python
            except Exception as e:
                last_failure = str(e)
                last_action = action
                logger.warning(f"[{team_name}] Action error: {e}")
                break
```

**Commit:** `feat: richer failure feedback with per-player context for LLM retry`

---

### Task 4: Explicit unacted-player count so LLM knows when to end turn

**Objective:** The LLM often wastes actions trying to move players that have already acted, rather than ending the turn cleanly. An explicit "N players still haven't acted" count helps it decide when ending the turn is the right call.

**File:** `simple_agents/player.py` (and the return type change from Task 1 is a prerequisite)

**In `play_turn`, update the summary call (Task 1 changed it already) and add an unacted count line to user_msg.**

After the Task 1 change, `summary` and `players_unacted` come from:
```python
        summary, players_unacted = summarize_for_player(state, team_id)
```

Update the `user_msg` construction to include this count (extend the Task 2 version):

```python
        valid_actions_prose = _describe_valid_actions(valid_actions, state, team_id)

        if players_unacted == 0:
            turn_status = "TURN STATUS: All your players have acted — consider ending your turn (return action=null)."
        elif players_unacted == 1:
            turn_status = "TURN STATUS: 1 player has not yet acted this turn."
        else:
            turn_status = f"TURN STATUS: {players_unacted} players have not yet acted this turn."

        user_msg = (
            f"{summary}\n\n"
            f"{turn_status}\n\n"
            f"{valid_actions_prose}\n"
            f"{failure_note}\n"
            "What is your next single action? Return one JSON object with 'thought' and 'action'."
        )
```

**Also update `simple_agents/state_summary.py`** to initialise `my_players_unacted = 0` at the top of `summarize_for_player` (before the first `for` loop), since Task 1 adds the counting logic inside the loop. The variable must exist even if the loop body is never entered (empty squad edge case).

After the line:
```python
    lines.append("")
```
(which is line 40, just before `lines.append("YOUR SQUAD:")`), add:
```python
    my_players_unacted = 0
```

Wait — Task 1 already adds this inside the loop correctly. The initialisation goes just before the `YOUR SQUAD:` loop, not inside it. Make sure Task 1 places `my_players_unacted = 0` before the `for pid in my_team...` loop, not inside it.

**Commit:** `feat: unacted player count in LLM turn status prompt`

---

## Execution Order

Tasks must be done in order because Task 4 depends on Task 1's return-value change, and Task 3 depends on Task 2's placement of helpers before `play_turn`.

1. **Task 1** — state_summary.py: per-player MA + ACTED flags + tuple return
2. **Task 2** — player.py: `_describe_valid_actions` helper + update user_msg
3. **Task 3** — player.py: `_build_failure_note` helper + track last_action
4. **Task 4** — player.py: wire `players_unacted` into user_msg turn status line

After all tasks, run the agent against a live game and check logs for reduced FAIL lines.

---

## Final state of affected files

### simple_agents/state_summary.py — full rewrite of `summarize_for_player`

The function signature becomes:
```python
def summarize_for_player(state: dict, my_team_id: str) -> tuple[str, int]:
```

Returns `(summary_text, players_unacted_count)`.

Key changes:
- Each player line now shows `MA{remaining}/{total}` instead of just `MA{total}`
- Players with `has_acted=True` show `| ACTED` flag
- `state` field drives OFF PITCH / PRONE / STUNNED flags (replaces `is_active`/`is_prone` lookups which may not be top-level keys in the serialised dict)
- `my_players_unacted` counter is incremented for every on-pitch player without `has_acted`

### simple_agents/player.py — additions and modifications

New helpers added (in order) between `_parse_step` and `play_turn`:
1. `_describe_valid_actions(valid_actions, state, team_id) -> str`
2. `_build_failure_note(last_failure, last_action, state, team_id) -> str`

Changes in `play_turn`:
- Line ~199: add `last_action: dict | None = None`
- Line ~214: `summary, players_unacted = summarize_for_player(state, team_id)`
- Lines ~219–224: replace `user_msg` construction with version using prose valid-actions + turn status
- Lines ~257–264: set `last_action = action` on failure, clear it on success
- Lines ~265–268: set `last_action = action` in exception handler

---

## Example output after changes

### State summary (YOUR SQUAD section):
```
YOUR SQUAD:
  [team1_p0] Constable              ( 5, 7)  MA4/6 ST3 AG3+  | ACTED
  [team1_p1] Fleet Recruit          ( 6, 6)  MA6/6 ST2 AG4+
  [team1_p2] Watch Sergeant         ( 7, 7)  MA2/5 ST4 AG4+  | BALL
```

### Valid actions prose:
```
WHAT YOU CAN DO THIS ACTION:

Players who can still MOVE (have MA remaining, not yet acted):
  - [team1_p1] Fleet Recruit at (6,6): 6 squares remaining (used 0/6)

One-per-turn special actions:
  - CHARGE (move + block in one action) — not yet used this turn
  - HURL — already used this turn
  - QUICK PASS — already used this turn

Ball: carried by YOUR player [team1_p2] Watch Sergeant at (7,7)

You may also return action=null to end your turn voluntarily.
```

### Turn status line:
```
TURN STATUS: 1 player has not yet acted this turn.
```

### Failure feedback:
```
PREVIOUS ACTION FAILED — choose a different valid action.
  Error: Player has already acted this turn
  Failed action: move by player [team1_p0]
  Player [team1_p0] Constable stats:
    Position: (5,7)  State: standing  MA: 0/6 remaining  Already acted: True
    -> This player has already acted this turn. Pick a different player.
```
