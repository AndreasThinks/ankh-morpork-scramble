# Versus Mode: Async Join Implementation Plan

## Problem

Agent A joins the lobby and waits. Hours pass. Agent B joins, triggering a match.
The game is created immediately and the 5-minute turn clock starts. Agent A hasn't
polled recently, doesn't know it's been matched, and forfeits before it ever plays.

## Solution: Two-Phase Match Flow

Split the current single-phase join into two distinct states:

```
waiting → matched (game scheduled, ack window open) → playing
```

Game creation is deferred until both agents have acknowledged the match, OR the
ack deadline passes and the non-responder is forfeited.

---

## New States

| Lobby status | Meaning                                              |
|--------------|------------------------------------------------------|
| `waiting`    | In queue, no opponent yet (unchanged)                |
| `matched`    | Opponent found, ack window open, game not yet live   |
| `playing`    | Game created, turn timer running (unchanged)         |

---

## Polling Cadences (documented in skill + API response)

| Phase          | Poll interval | Rationale                                       |
|----------------|---------------|-------------------------------------------------|
| waiting        | 5 min         | No urgency, opponent may never come             |
| matched        | 30-60 sec     | Ack window is 10 min, want to respond promptly  |
| playing        | 10-15 sec     | 5-min turn timer, need timely action            |

The matched response includes `poll_interval_seconds: 30` so agents can adapt
without hardcoding. Game start time is also included so agents know their deadline.

---

## Detailed Changes

### 1. DB schema — `agent_registry.py`

Add two columns to the `lobby` table:

```sql
ALTER TABLE lobby ADD COLUMN scheduled_start TEXT;   -- ISO UTC, set on match
ALTER TABLE lobby ADD COLUMN acked_at TEXT;          -- ISO UTC, set on POST /versus/ready
```

Add migration block in `init_db()` (same try/except pattern as `token_prefix`):

```python
for col in ("scheduled_start TEXT", "acked_at TEXT"):
    try:
        conn.execute(f"ALTER TABLE lobby ADD COLUMN {col}")
        conn.commit()
    except Exception:
        pass
```

---

### 2. `lobby.py` — defer game creation

In `_join_locked()`, when an opponent is found:

- **Remove** the `game_manager.create_game()` call and all the team name/game_agents
  setup that follows it.
- Instead, write both agents to lobby with `status='matched'` and
  `scheduled_start = now + 10 minutes`.
- Return `status: "matched"` with `scheduled_start` and `poll_interval_seconds: 30`
  in the dict. No `game_id` yet.

New helper `_create_game_for_pair(agent1_id, agent2_id)` — extracts the current
game creation logic (team assignment, name lookup, `create_game()`, `game_agents`
insert, lobby status update to `"playing"`). Called from two places: the ready
endpoint and the timeout watcher.

Add `ack(agent_id, game_pair_key)` method — marks `acked_at` for this agent,
then checks if both agents in the pair have acked. If yes, calls
`_create_game_for_pair()` immediately.

How to identify the pair: when matched, write the opponent's `agent_id` into a
`opponent_agent_id` column (or look it up from the shared `game_id`-to-be). Simplest:
add a `paired_with TEXT` column to lobby, set on match. Used by `ack()` to find
the other row.

---

### 3. New endpoint — `POST /versus/ready/{agent_id}`

Authenticated with `X-Agent-Token`. Marks this agent as ready.

```python
@app.post("/versus/ready/{agent_id}")
def versus_ready(agent_id: str, x_agent_token: str = Header(...)):
    identity = agent_registry.resolve_token(x_agent_token)
    if not identity or identity.agent_id != agent_id:
        raise HTTPException(status_code=401)
    result = lobby_manager.ack(agent_id)
    # result: {"status": "waiting_for_opponent"} or {"status": "matched", "game_id": ...}
    return result
```

---

### 4. `JoinResponse` and `LobbyStatusResponse` — `models/agent.py`

Add fields to both models:

```python
scheduled_start: Optional[datetime] = None   # when the game will be created
poll_interval_seconds: Optional[int] = None  # hint to agent: how often to poll
```

`poll_interval_seconds` is `300` when waiting, `30` when matched, `None` once playing
(agent should already know to poll fast).

---

### 5. Background watcher — `main.py`

Extend `_turn_timeout_watcher()` to handle two additional cases (check every 60 sec
same as now):

**Case A: ack deadline expired**

```python
matched_rows = conn.execute(
    "SELECT agent_id, paired_with, scheduled_start FROM lobby WHERE status='matched'"
).fetchall()
for row in matched_rows:
    deadline = datetime.fromisoformat(row["scheduled_start"]).replace(tzinfo=timezone.utc)
    if now > deadline:
        # Check who hasn't acked
        both = conn.execute(
            "SELECT agent_id, acked_at FROM lobby WHERE agent_id IN (?,?)",
            (row["agent_id"], row["paired_with"])
        ).fetchall()
        unacked = [r["agent_id"] for r in both if not r["acked_at"]]
        acked   = [r["agent_id"] for r in both if r["acked_at"]]
        if len(unacked) == 2:
            # Neither responded — remove both, re-queue neither (they can rejoin)
            lobby_manager.cancel_match(row["agent_id"], row["paired_with"])
        elif len(unacked) == 1:
            # One acked, one didn't — forfeit the non-responder, re-queue the other
            lobby_manager.forfeit_unacked(unacked[0], acked[0])
        # If both acked, game should already be live — skip
```

**Case B: both acked but game not created yet** (belt-and-braces, shouldn't happen
if `ack()` works correctly, but guards against race conditions):

Check for matched rows where both have `acked_at` set but no game exists yet and
call `_create_game_for_pair()`.

---

### 6. Lobby status endpoint

Update `GET /versus/agents/{agent_id}` (or equivalent status endpoint) to include
`scheduled_start` and `poll_interval_seconds` in matched responses. Agents polling
the status route get the same hint even if they missed it in the join response.

---

### 7. Skill update — `ankh-morpork-player`

Update the "Joining a versus game" section:

- Document the three polling phases and their intervals
- Show the `POST /versus/ready/{agent_id}` call immediately after seeing `matched`
- Note that `scheduled_start` is in the matched response and is the deadline to ack
- Note `poll_interval_seconds` field and how to use it
- Add example polling loop that adapts cadence based on status

---

## Summary of file changes

| File                            | Change                                                  |
|---------------------------------|---------------------------------------------------------|
| `app/state/agent_registry.py`   | Add `scheduled_start`, `acked_at`, `paired_with` cols  |
| `app/state/lobby.py`            | Defer game creation; add `ack()`, `_create_game_for_pair()`, `cancel_match()`, `forfeit_unacked()` |
| `app/models/agent.py`           | Add `scheduled_start`, `poll_interval_seconds` to response models |
| `app/main.py`                   | Add `POST /versus/ready/{agent_id}`; extend watcher     |
| `skills/gaming/ankh-morpork-player/SKILL.md` | Document new flow and polling cadences     |

No changes to `game_manager.py`, `versus_auth.py`, or any arena-mode code.
All arena games continue to pass through without auth or lobby involvement.

---

## Edge cases covered

- Both agents ack fast: game live in under 60 seconds from match
- One agent is slow: game starts as soon as slow agent acks (within 10-min window)
- Neither agent responds: both removed from lobby after 10 min, no game created
- One ghost, one active: ghost forfeited at deadline, active agent re-queued
- Agent re-joins after being forfeited: hits the normal join flow, treated as new
- Returning agent (token re-used): already handled by existing `JoinRequest.token` path
