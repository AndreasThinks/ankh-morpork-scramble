# Implementation Plan: Versus Mode Phase 5 — Leaderboard Extension

## Overview

Add `AgentLeaderboardEntry` model and wire it into the aggregation loop in
`app/state/leaderboard_store.py`. The `/versus/leaderboard` endpoint returns
both agent and model leaderboards. Arena games (no agent identity) contribute
only to the model leaderboard. Versus games contribute to both.

One file modified: `app/state/leaderboard_store.py`
One file added: `app/models/leaderboard.py` gets the new model class

---

## File 1: `app/models/leaderboard.py` — add `AgentLeaderboardEntry`

Add this new class after `TeamLeaderboardEntry` and before `LeaderboardResponse`:

```python
class AgentLeaderboardEntry(BaseModel):
    """Aggregated stats for one named agent across all games."""
    agent_id: str
    agent_name: str
    model: str = "unknown"

    # Results
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    forfeits: int = 0
    goals_for: int = 0
    goals_against: int = 0
    score_diff: int = 0

    # Raw accumulated counts
    casualties_caused: int = 0
    blocks_thrown: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    pickups_attempted: int = 0
    pickups_succeeded: int = 0
    turnovers: int = 0
    failed_dodges: int = 0
    messages_sent: int = 0
    total_message_chars: int = 0

    # ── Computed per-game rates ────────────────────────────────────────────

    @computed_field
    @property
    def win_pct(self) -> float:
        return round(self.wins / self.games, 3) if self.games else 0.0

    @computed_field
    @property
    def aggression(self) -> float:
        """Blocks thrown per game."""
        return round(self.blocks_thrown / self.games, 2) if self.games else 0.0

    @computed_field
    @property
    def recklessness(self) -> float:
        """Turnovers per game."""
        return round(self.turnovers / self.games, 2) if self.games else 0.0

    @computed_field
    @property
    def ball_craft(self) -> float:
        """Successful passes + pickups per game."""
        return round(
            (self.passes_completed + self.pickups_succeeded) / self.games, 2
        ) if self.games else 0.0

    @computed_field
    @property
    def lethality(self) -> float:
        """Casualties caused per game."""
        return round(self.casualties_caused / self.games, 2) if self.games else 0.0

    @computed_field
    @property
    def verbosity(self) -> float:
        """Average strategy message length in characters."""
        return round(self.total_message_chars / self.messages_sent, 1) if self.messages_sent else 0.0

    @computed_field
    @property
    def efficiency(self) -> float:
        """Goals per game divided by turnover rate."""
        if not self.games:
            return 0.0
        gf_per_game = self.goals_for / self.games
        to_per_game = self.turnovers / self.games
        return round(gf_per_game / max(to_per_game, 0.5), 2)

    @computed_field
    @property
    def pass_completion_pct(self) -> float:
        """Pass completion percentage (0–100)."""
        return round(
            100 * self.passes_completed / self.passes_attempted, 1
        ) if self.passes_attempted else 0.0
```

Also update `LeaderboardResponse` to include the agent leaderboard:

```python
class LeaderboardResponse(BaseModel):
    """Response shape for GET /leaderboard and GET /versus/leaderboard."""
    total_games: int
    by_agent: list[AgentLeaderboardEntry] = []
    by_model: list[ModelLeaderboardEntry]
    by_team: list[TeamLeaderboardEntry]
```

---

## File 2: `app/state/leaderboard_store.py` — update `get_leaderboard()`

### 2a. Add import at the top

After the existing imports from `app.models.leaderboard`, add:
```python
from app.models.leaderboard import AgentLeaderboardEntry
```

### 2b. Add agent aggregation to the `get_leaderboard()` method

Inside the `for r in results:` loop, after the team aggregation block and before
the sort statement, add:

```python
            # ---- agent aggregation (versus games only) ----
            for (agent_id, agent_name, model_id, score_for, score_against,
                 outcome, casualties, blocks,
                 passes_att, passes_comp,
                 pickups_att, pickups_succ,
                 turnovers, failed_dodges,
                 messages_sent, total_message_chars) in [
                (
                    r.team1_agent_id, r.team1_agent_name, r.team1_model,
                    r.team1_score, r.team2_score, t1_outcome,
                    r.team1_casualties, r.team1_blocks,
                    r.team1_passes_attempted, r.team1_passes_completed,
                    r.team1_pickups_attempted, r.team1_pickups_succeeded,
                    r.team1_turnovers, r.team1_failed_dodges,
                    r.team1_messages_sent, r.team1_total_message_chars,
                ),
                (
                    r.team2_agent_id, r.team2_agent_name, r.team2_model,
                    r.team2_score, r.team1_score, t2_outcome,
                    r.team2_casualties, r.team2_blocks,
                    r.team2_passes_attempted, r.team2_passes_completed,
                    r.team2_pickups_attempted, r.team2_pickups_succeeded,
                    r.team2_turnovers, r.team2_failed_dodges,
                    r.team2_messages_sent, r.team2_total_message_chars,
                ),
            ]:
                if not agent_id:
                    continue  # arena game, no agent identity
                if agent_id not in agent_map:
                    agent_map[agent_id] = AgentLeaderboardEntry(
                        agent_id=agent_id, agent_name=agent_name, model=model_id or "unknown"
                    )
                entry = agent_map[agent_id]
                entry.games += 1
                entry.goals_for += score_for
                entry.goals_against += score_against
                entry.score_diff += score_for - score_against
                entry.casualties_caused += casualties
                entry.blocks_thrown += blocks
                entry.passes_attempted += passes_att
                entry.passes_completed += passes_comp
                entry.pickups_attempted += pickups_att
                entry.pickups_succeeded += pickups_succ
                entry.turnovers += turnovers
                entry.failed_dodges += failed_dodges
                entry.messages_sent += messages_sent
                entry.total_message_chars += total_message_chars
                if outcome == "win":
                    entry.wins += 1
                elif outcome == "loss":
                    entry.losses += 1
                else:
                    entry.draws += 1
```

### 2c. Update the return statement

Before the `return LeaderboardResponse(...)` line, add:
```python
        # Sort agents by wins desc, score_diff desc
        by_agent = sorted(agent_map.values(), key=lambda e: (-e.wins, -e.score_diff))
```

Then update the return call to include `by_agent`:
```python
        return LeaderboardResponse(
            total_games=len(results),
            by_agent=by_agent,
            by_model=by_model,
            by_team=by_team,
        )
```

### 2d. Initialize `agent_map` at the top of the function

Right after `model_map: dict[str, ModelLeaderboardEntry] = {}` and `team_map`, add:
```python
        agent_map: dict[str, AgentLeaderboardEntry] = {}
```

---

## File 3: `app/main.py` — add `/versus/leaderboard` endpoint

Add this endpoint near the other versus endpoints (after `/versus/lobby/leave`):

```python
@app.get("/versus/leaderboard", response_model=LeaderboardResponse)
def versus_leaderboard():
    """
    Return aggregated standings by agent, model, and team.
    Includes both arena and versus games. Agent fields populated for versus games.
    """
    return game_manager.leaderboard.get_leaderboard()
```

The existing `/leaderboard` endpoint stays untouched — it returns the same data
but without the `by_agent` field populated (legacy behaviour).

---

## Integration notes

- `computed_field` is already imported in `app/models/leaderboard.py` (used by
  `ModelLeaderboardEntry`). No new import needed.
- The agent aggregation only runs when `agent_id` is present (versus games).
  Arena games skip it naturally.
- The `by_agent` list in `LeaderboardResponse` defaults to `[]` so existing
  code that doesn't expect agents won't break.
- Forfeit tracking: the `forfeits` field is in the model but not populated yet.
  That comes with the turn timeout feature (not in this phase).

---

## Verification steps

1. Syntax checks:
   ```
   python3 -c "import ast; ast.parse(open('app/models/leaderboard.py').read()); print('leaderboard.py OK')"
   python3 -c "import ast; ast.parse(open('app/state/leaderboard_store.py').read()); print('leaderboard_store.py OK')"
   python3 -c "import ast; ast.parse(open('app/main.py').read()); print('main.py OK')"
   ```

2. Import check:
   ```
   source .venv/bin/activate
   python3 -c "from app.models.leaderboard import AgentLeaderboardEntry; e = AgentLeaderboardEntry(agent_id='test', agent_name='TestBot'); print('win_pct:', e.win_pct); print('OK')"
   ```

3. Full test suite:
   ```
   uv run pytest tests/ -q 2>&1 | tail -20
   ```

4. Quick smoke test:
   ```bash
   uv run uvicorn app.main:app --port 8001 &
   sleep 4
   # Hit the leaderboard endpoint
   curl -s http://localhost:8001/versus/leaderboard | python3 -m json.tool | head -30
   pkill -f "uvicorn app.main:app --port 8001"
   ```

5. If all passes:
   ```
   git add -A && git commit -m "feat: versus phase 5 - agent leaderboard" && git push origin feature/versus
   ```
