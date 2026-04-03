# Code Review: Ankh-Morpork Scramble

**Reviewer:** Claude (AI Code Review)  
**Date:** March 4, 2026  
**Scope:** Full codebase review focusing on game mechanics, API correctness, launcher script, and interactive setup flow

---

## Executive Summary

The codebase is generally well-structured with good separation of concerns. However, I've identified several bugs, edge cases, and potential issues that should be addressed. The most critical issues relate to game phase handling, scoring logic, and the launcher script.

---

## 1. Critical Bugs

### 1.1 GamePhase Enum Aliasing Issue
**File:** `app/models/enums.py` (lines 145-165)  
**Severity:** HIGH

The `GamePhase` enum uses value aliasing which can cause unexpected behavior:

```python
class GamePhase(str, Enum):
    SETUP = "setup"
    KICKOFF = "kickoff"
    PLAYING = "playing"
    HALF_TIME = "half_time"
    FINISHED = "finished"

    # Aliases preserved for backwards compatibility with themed code
    DEPLOYMENT = "setup"
    OPENING_SCRAMBLE = "kickoff"
    ACTIVE_PLAY = "playing"
    INTERMISSION = "half_time"
    CONCLUDED = "finished"
```

**Problem:** In Python enums, when two members have the same value, the second becomes an alias to the first. This means `GamePhase.DEPLOYMENT is GamePhase.SETUP` returns `True`, but comparisons like `phase == GamePhase.DEPLOYMENT` may behave unexpectedly in serialization contexts.

**Impact:** The code mixes usage of both names (e.g., `GamePhase.DEPLOYMENT` in `interactive_game.py:68` and `GamePhase.SETUP` in `game_manager.py:163`), which works but is confusing and error-prone.

**Recommendation:** Choose one naming convention and deprecate the other, or use a proper alias pattern.

---

### 1.2 Scoring End Zone Logic Inconsistency
**File:** `app/state/game_manager.py` (lines 451-457)  
**Severity:** MEDIUM

```python
# Check if in end zone
# Team 1 scores in x >= 23 (endzone depth: 3 squares), Team 2 scores in x <= 2 (endzone depth: 3 squares)
if carrier.team_id == game_state.team1.id and carrier_pos.x >= 23:
    scored_team = game_state.team1
elif carrier.team_id == game_state.team2.id and carrier_pos.x <= 2:
    scored_team = game_state.team2
```

**Problem:** The comment says "endzone depth: 3 squares" but:
- Team 1 end zone: x >= 23 means squares 23, 24, 25 (3 squares) ✓
- Team 2 end zone: x <= 2 means squares 0, 1, 2 (3 squares) ✓

However, the pitch is 26 squares wide (0-25), and the center is at x=13. This creates asymmetric distances:
- Team 1 must travel from x=0-12 to x>=23 (minimum 11 squares from center)
- Team 2 must travel from x=13-25 to x<=2 (minimum 11 squares from center)

This is actually symmetric, but the placement validation in `game_manager.py:136-145` allows Team 1 to place at x=12 and Team 2 at x=13, meaning the line of scrimmage is between 12 and 13.

**Recommendation:** Add constants for end zone boundaries and document the pitch layout clearly.

---

### 1.3 Ball Scatter Direction Bug
**File:** `app/game/dice.py` (lines 111-136)  
**Severity:** MEDIUM

```python
def scatter(self) -> tuple[int, int]:
    """Roll scatter direction (returns x, y offset)"""
    roll = self.roll_d6()
    
    # Scatter directions (clockwise from top)
    directions = [
        (0, -1),   # 1: North
        (1, -1),   # 2: NE
        (1, 0),    # 3: East
        (1, 1),    # 4: SE
        (0, 1),    # 5: South
        (-1, 1),   # 6: SW
    ]
    
    # Handle wrap (6 options, but d6 gives 1-6)
    if roll == 6:
        # Continue with next roll for SW, West, NW
        roll2 = self.roll_d6()
        if roll2 <= 2:
            return (-1, 1)   # SW
        elif roll2 <= 4:
            return (-1, 0)   # West
        else:
            return (-1, -1)  # NW
    
    return directions[roll - 1]
```

**Problem:** The scatter logic is broken:
1. The `directions` list has 6 elements but only covers 6 of 8 possible directions (missing West and NW)
2. When roll == 6, it returns SW (which is already in the list at index 5)
3. The second roll for directions 6+ is non-standard Blood Bowl behavior

**Blood Bowl Standard:** Scatter uses a d8 for direction (8 directions) and a d6 for distance. This implementation conflates the two.

**Recommendation:** Implement proper 8-direction scatter:
```python
directions = [
    (0, -1),   # N
    (1, -1),   # NE
    (1, 0),    # E
    (1, 1),    # SE
    (0, 1),    # S
    (-1, 1),   # SW
    (-1, 0),   # W
    (-1, -1),  # NW
]
roll = self.rng.randint(0, 7)
return directions[roll]
```

---

### 1.4 Turn Counter Logic Issue
**File:** `app/models/game_state.py` (lines 173-178)  
**Severity:** MEDIUM

```python
# Switch to other team
if self.turn.active_team_id == self.team1.id:
    self.turn.active_team_id = self.team2.id
else:
    self.turn.active_team_id = self.team1.id
    # Increment turn counter when returning to team 1
    self.turn.team_turn += 1
```

**Problem:** The turn counter only increments when switching back to team1. This means:
- Turn 0: Team1 plays, Team2 plays
- Turn 1: Team1 plays, Team2 plays
- etc.

This is correct for Blood Bowl (each "turn" is both teams), but the `team_turn` field description says "Turn number for active team" which is misleading.

**Recommendation:** Clarify the field description or rename to `round_number`.

---

## 2. API Issues

### 2.1 Missing Validation in `/game/{game_id}/start`
**File:** `app/state/game_manager.py` (lines 157-186)  
**Severity:** MEDIUM

```python
def start_game(self, game_id: str) -> GameState:
    """Start the game"""
    game_state = self.get_game(game_id)
    if not game_state:
        raise ValueError(f"Game {game_id} not found")

    if game_state.phase != GamePhase.SETUP:
        raise ValueError("Game must be in setup phase to start")

    game_state.start_game()
```

**Problem:** The `start_game` method doesn't validate:
1. That both teams have at least 3 players (minimum for a valid game)
2. That players are actually placed on the pitch
3. That both teams have joined

The `start_game()` method on `GameState` (line 263) checks `players_ready` but this only checks if teams have joined, not if they have players.

**Recommendation:** Add validation:
```python
if len(game_state.team1.player_ids) < 3:
    raise ValueError("Team 1 must have at least 3 players")
if len(game_state.team2.player_ids) < 3:
    raise ValueError("Team 2 must have at least 3 players")
if len(game_state.pitch.player_positions) == 0:
    raise ValueError("Players must be placed on the pitch before starting")
```

---

### 2.2 Race Condition in Turnover Handling
**File:** `app/main.py` (lines 564-567)  
**Severity:** LOW

```python
# If turnover, automatically end turn
if result.turnover:
    # Set flag before calling end_turn to prevent double calls
    game_state.turn.turnover_ended_turn = True
    game_manager.end_turn(game_id)
    result.details["turn_ended"] = True
```

**Problem:** The `turnover_ended_turn` flag is set on `game_state.turn`, but if `end_turn` creates a new turn state, this flag might be lost. The guard in `end_turn` (line 201) checks this flag, but there's a potential race condition if multiple requests come in simultaneously.

**Recommendation:** Use a more robust locking mechanism or ensure the flag persists across turn transitions.

---

### 2.3 Inconsistent Error Handling
**File:** `app/main.py` (various lines)  
**Severity:** LOW

Some endpoints return 400 for "game not found" while others return 404:
- `get_game` (line 406): Returns 404 ✓
- `execute_action` (line 539): Returns 404 ✓
- `end_turn` (line 589): Returns 404 ✓
- `setup_team` (line 448): Returns 400 ✗
- `place_players` (line 521): Returns 400 ✗
- `start_game` (line 530): Returns 400 ✗

**Recommendation:** Standardize on 404 for "not found" errors.

---

### 2.4 Missing Input Sanitization
**File:** `app/main.py` (line 372)  
**Severity:** LOW

```python
@app.post("/game", response_model=GameState)
def create_game(game_id: Optional[str] = None):
    """Create a new game"""
    try:
        game_state = game_manager.create_game(game_id)
        return game_state
```

**Problem:** The `game_id` parameter is not sanitized. While `sanitize_id` exists in `app/api/middleware.py`, it's not used here. Malicious game IDs could potentially cause issues.

**Recommendation:** Apply `sanitize_id` to user-provided game IDs.

---

## 3. run_hermes_game.py Launcher Script Issues

### 3.1 Hardcoded IP Address
**File:** `run_hermes_game.py` (lines 8, 191-192)  
**Severity:** HIGH

```python
# Line 8
# Commentary appears in the web UI at http://192.168.4.57:8000/ui

# Lines 191-192
print(f"\nWeb UI: http://192.168.4.57:{SERVER_PORT}/ui")
print(f"API docs: http://192.168.4.57:{SERVER_PORT}/docs\n")
```

**Problem:** The IP address `192.168.4.57` is hardcoded, which is a local network address specific to the developer's machine. This will not work for other users.

**Recommendation:** Use `localhost` or detect the local IP dynamically:
```python
import socket
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"
```

---

### 3.2 Non-existent Skill References
**File:** `run_hermes_game.py` (lines 84, 97)  
**Severity:** HIGH

```python
# Line 84
# Load the skill 'ankh-morpork-player' and follow it exactly to play the full match,

# Line 97
# Load the skill 'ankh-morpork-commentator' and follow it exactly.
```

**Problem:** The skills referenced (`ankh-morpork-player`, `ankh-morpork-commentator`) don't exist in the `skills/` directory. The available skills are:
- `ankh-morpork-scramble`
- `scramble-combat`
- `scramble-movement`
- `scramble-setup`
- `scramble-ball-handling`

**Recommendation:** Update to use existing skills or create the missing skills.

---

### 3.3 Missing Error Handling for Hermes CLI
**File:** `run_hermes_game.py` (lines 133-143)  
**Severity:** MEDIUM

```python
proc = subprocess.Popen(
    [
        "hermes",
        "--task", context,
        "--model", "openrouter/google/gemini-2.5-flash",
        "--quiet",
    ],
    stdout=open(log_path, "w"),
    stderr=subprocess.STDOUT,
)
```

**Problem:** 
1. No check if `hermes` CLI is installed
2. File handles are not properly closed (should use context manager)
3. No error handling if the subprocess fails to start

**Recommendation:**
```python
import shutil
if not shutil.which("hermes"):
    print("Error: 'hermes' CLI not found. Please install it first.")
    sys.exit(1)

with open(log_path, "w") as log_file:
    proc = subprocess.Popen(
        [...],
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
```

---

### 3.4 Resource Leak on Shutdown
**File:** `run_hermes_game.py` (lines 170-182)  
**Severity:** LOW

```python
def handle_signal(sig, frame):
    print("\n[launcher] Shutting down...")
    shutdown[0] = True
    for label, proc, _ in agent_procs:
        try:
            proc.terminate()
            print(f"{label} terminated")
        except Exception:
            pass
    if server_proc:
        server_proc.terminate()
        print("[server] terminated")
    sys.exit(0)
```

**Problem:** The signal handler calls `sys.exit(0)` which may not properly clean up resources. Also, `proc.terminate()` sends SIGTERM but doesn't wait for processes to actually terminate.

**Recommendation:**
```python
def handle_signal(sig, frame):
    print("\n[launcher] Shutting down...")
    shutdown[0] = True
    for label, proc, _ in agent_procs:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception:
            pass
    if server_proc:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()
```

---

## 4. Interactive Setup Flow Issues

### 4.1 Phase Mismatch Between create_game and bootstrap_interactive_game
**File:** `app/state/game_manager.py` (line 52) vs `app/setup/interactive_game.py` (line 68)  
**Severity:** MEDIUM

```python
# game_manager.py:52
game_state = GameState(
    game_id=game_id,
    phase=GamePhase.SETUP,  # Uses SETUP
    ...
)

# interactive_game.py:68
assert state.phase == GamePhase.DEPLOYMENT  # Expects DEPLOYMENT
```

**Problem:** Due to the enum aliasing, this assertion passes (DEPLOYMENT == SETUP), but it's confusing and could break if the aliasing is removed.

**Recommendation:** Use consistent phase names throughout.

---

### 4.2 No Minimum Player Validation Before Start
**File:** `app/state/game_manager.py` (lines 157-186)  
**Severity:** MEDIUM

As mentioned in 2.1, there's no validation that teams have enough players before starting. The interactive setup flow allows teams to buy 0 players and still attempt to start the game.

---

### 4.3 Team Names Not Set in Interactive Mode
**File:** `app/setup/interactive_game.py` (lines 62-65)  
**Severity:** LOW

```python
state.team1.team_type = team1_type
state.team1.name = team1_name  # Default: "Team 1"
state.team2.team_type = team2_type
state.team2.name = team2_name  # Default: "Team 2"
```

**Problem:** The default team names are generic ("Team 1", "Team 2"). In the `run_hermes_game.py` script, the context mentions "City Watch Constables" and "Unseen University Adepts" but these names are never actually set on the team objects.

**Recommendation:** Either:
1. Update `bootstrap_interactive_game` to accept and use meaningful team names
2. Or update `run_hermes_game.py` to call an API to set team names

---

### 4.4 Missing "Ready" Endpoint
**File:** `app/main.py`  
**Severity:** LOW

The interactive setup documentation mentions teams should "Mark ready using ready_to_play()" but there's no such endpoint. The `team1_ready` and `team2_ready` flags exist but are only set via the `/join` endpoint.

**Recommendation:** Either:
1. Add a `/game/{game_id}/team/{team_id}/ready` endpoint
2. Or document that joining automatically marks the team as ready

---

## 5. Game Mechanics Issues

### 5.1 Block Dice Result Selection Logic
**File:** `app/game/combat.py` (lines 99-137)  
**Severity:** LOW

```python
def choose_block_result(
    self,
    results: list[BlockResult],
    attacker_chooses: bool,
    attacker: Player,
    defender: Player
) -> BlockResult:
    """Choose the best block result from available dice"""
    if len(results) == 1:
        return results[0]
    
    if attacker_chooses:
        # Prefer results that knock down or stumble defender
        if BlockResult.DEFENDER_DOWN in results:
            return BlockResult.DEFENDER_DOWN
        elif BlockResult.DEFENDER_STUMBLES in results:
            return BlockResult.DEFENDER_STUMBLES
        elif BlockResult.PUSH in results:
            return BlockResult.PUSH
        elif BlockResult.BOTH_DOWN in results:
            # Choose both down if attacker has Block skill
            if attacker.has_skill(SkillType.DRILL_HARDENED):
                return BlockResult.BOTH_DOWN
            return BlockResult.PUSH if BlockResult.PUSH in results else results[0]
```

**Problem:** The logic for choosing BOTH_DOWN when attacker has Block skill is backwards. If the attacker has Block, they should AVOID BOTH_DOWN (since they won't go down but the defender will). The current logic makes them prefer it.

**Recommendation:** Fix the logic:
```python
elif BlockResult.BOTH_DOWN in results:
    # Choose both down only if attacker has Block skill (they won't go down)
    if attacker.has_skill(SkillType.DRILL_HARDENED):
        return BlockResult.BOTH_DOWN
    # Otherwise, prefer push to avoid going down
    return BlockResult.PUSH if BlockResult.PUSH in results else results[0]
```

Wait, re-reading the code, this is actually correct - if attacker has Block, BOTH_DOWN is good because only defender goes down. The issue is the comment is misleading.

---

### 5.2 Assist Counting Not Implemented
**File:** `app/game/combat.py` (lines 49-76)  
**Severity:** MEDIUM

```python
def get_block_dice_count(
    self,
    attacker: Player,
    defender: Player,
    assist_count_attacker: int = 0,
    assist_count_defender: int = 0
) -> tuple[int, bool]:
```

**Problem:** The method accepts assist counts but they're never calculated or passed in. In `execute_block` (line 152), the method is called without assists:

```python
dice_count, attacker_chooses = self.get_block_dice_count(attacker, defender)
```

**Recommendation:** Implement assist calculation in `execute_block`:
```python
# Calculate assists
attacker_assists = self._count_assists(game_state, attacker, defender)
defender_assists = self._count_assists(game_state, defender, attacker)
dice_count, attacker_chooses = self.get_block_dice_count(
    attacker, defender, attacker_assists, defender_assists
)
```

---

### 5.3 Push Not Implemented
**File:** `app/game/combat.py` (line 209)  
**Severity:** MEDIUM

```python
# PUSH result requires no further action (handled by caller)
```

**Problem:** Push is not actually handled anywhere. When a PUSH result occurs, the defender should be moved one square away from the attacker, but this never happens.

**Recommendation:** Implement push handling in `execute_block` or `_execute_scuffle`.

---

### 5.4 Stunned Player Recovery Timing
**File:** `app/models/player.py` (lines 92-94)  
**Severity:** LOW

```python
# Remove stunned state if turn has passed
if self.state == PlayerState.STUNNED:
    self.state = PlayerState.PRONE
```

**Problem:** In Blood Bowl, stunned players recover at the END of their next turn, not the start. The current implementation recovers them at the start of their team's turn.

**Recommendation:** Track when the player was stunned and recover at the appropriate time.

---

### 5.5 Pathfinding Uses Diagonal Movement Incorrectly
**File:** `app/game/pathfinding.py` (lines 48-78)  
**Severity:** LOW

```python
def calculate_straight_line_path(
    self,
    from_pos: Position,
    to_pos: Position
) -> list[Position]:
    ...
    while current_x != target_x or current_y != target_y:
        # Move towards target (one step at a time)
        if current_x != target_x:
            current_x += dx
        if current_y != target_y:
            current_y += dy
        
        path.append(Position(x=current_x, y=current_y))
```

**Problem:** This creates diagonal paths where both x and y change in a single step. While diagonal movement is allowed, this "straight line" approach may not be optimal and doesn't account for obstacles.

**Recommendation:** Implement proper A* pathfinding or at least document the limitations.

---

## 6. Code Quality Issues

### 6.1 Unused Imports
**File:** `app/main.py` (line 13)  
**Severity:** TRIVIAL

```python
import asyncio
```

This import is never used.

---

### 6.2 Inconsistent Logging
**File:** Various  
**Severity:** LOW

Some modules use `logging.getLogger(__name__)` while others use specific names like `logging.getLogger("app.game.manager")`. This inconsistency makes log filtering harder.

---

### 6.3 Magic Numbers
**File:** Various  
**Severity:** LOW

Several magic numbers appear throughout the code:
- Pitch dimensions (26x15) - should be constants
- End zone boundaries (x >= 23, x <= 2) - should be constants
- Budget (1,000,000) - should be a constant
- Max rerolls (8) - already a constant in roster, good

**Recommendation:** Create a `constants.py` file:
```python
PITCH_WIDTH = 26
PITCH_HEIGHT = 15
TEAM1_ENDZONE_START = 23
TEAM2_ENDZONE_END = 2
DEFAULT_TEAM_BUDGET = 1_000_000
```

---

## 7. Test Coverage Gaps

### 7.1 Missing Tests for Scoring
No tests verify that scoring works correctly when a player enters the end zone.

### 7.2 Missing Tests for Ball Scatter
No tests verify the scatter direction logic.

### 7.3 Missing Tests for Push Mechanic
No tests for push results (because it's not implemented).

### 7.4 Missing Tests for Stunned Recovery
No tests verify stunned players recover correctly.

---

## 8. Security Considerations

### 8.1 Admin API Key in Environment
**File:** `app/main.py` (lines 136-146)  
**Severity:** LOW

The admin API key is read from environment variables, which is good. However, there's no rate limiting on admin endpoints specifically.

### 8.2 Log File Path Traversal
**File:** `app/main.py` (lines 327-328)  
**Severity:** LOW

```python
# Sanitize log name to prevent directory traversal
if "/" in log_name or ".." in log_name:
    raise HTTPException(status_code=400, detail="Invalid log file name")
```

Good sanitization, but could also check for backslashes on Windows.

---

## Summary of Recommendations

### High Priority
1. Fix hardcoded IP in `run_hermes_game.py`
2. Fix non-existent skill references in `run_hermes_game.py`
3. Fix ball scatter direction logic in `dice.py`
4. Add minimum player validation before game start

### Medium Priority
1. Implement assist counting for blocks
2. Implement push mechanic
3. Standardize error codes (404 vs 400)
4. Add proper error handling in launcher script

### Low Priority
1. Clean up GamePhase enum aliasing
2. Add constants for magic numbers
3. Fix stunned recovery timing
4. Improve pathfinding algorithm
5. Add missing test coverage

---

## Conclusion

The codebase demonstrates solid architecture and good separation of concerns. The main issues are:
1. The launcher script has several problems that would prevent it from working out of the box
2. Some game mechanics (push, assists) are incomplete
3. The ball scatter logic has a bug
4. Input validation could be stronger

With the fixes outlined above, the game should be fully functional and robust.
