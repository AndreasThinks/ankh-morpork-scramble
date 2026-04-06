# Versus Mode — Project Plan

## What We're Building

A persistent versus mode for Ankh-Morpork Scramble. External AI agents register
with a named identity, join a lobby, get matched against an opponent, and play
authenticated games. Results accumulate into an agent leaderboard over time.
Both versus mode and the existing arena auto-play run simultaneously on the same
deployment at different route prefixes.

---

## Decisions

All design decisions are resolved. No open questions.

| Decision | Choice | Reason |
|---|---|---|
| Deployment | One Railway service, two prefixes | Simpler ops, shared DB |
| Development | `feature/versus` branch, new Railway service | Arena stays untouched during dev |
| Storage | SQLite (`data/versus.db`) | Uniqueness constraints, lobby transactions, leaderboard queries |
| Results | Keep `results.jsonl` + nullable agent fields | Arena and versus share it cleanly |
| Agent identity | Chosen name + persistent token | Named leaderboard, long-term identity |
| Token | `ams_` + 32-char hex, shown once, bcrypt hash stored | Unguessable, never re-issued |
| Join endpoint | Single `/versus/join` for new and returning agents | No client-side branching |
| Team assignment | Server alternates City Watch / UU | Fairer leaderboard, no lobby negotiation |
| Concurrent games | One active game per agent at a time | Lobby simplicity |
| Turn timeout | 5 minutes, forfeit = loss, logged | Simple, unambiguous |
| Notifications | Email via AgentMail, fired on lobby open | Lightweight, already wired in |

---

## Development Strategy

```
main branch          →  existing Railway service (wwg82zfb)  →  arena, untouched
feature/versus       →  new Railway service (auto-deploy)    →  versus dev
```

The `feature/versus` branch carries its own `railway.json` with a different
start command. It never touches the arena service config.

When versus is stable: merge to main, arena service updated to serve both
`/arena/*` and `/versus/*`. Single deployment, single DB, two modes.

---

## Route Structure

```
/arena/*           Current game endpoints (prefixed on merge, unchanged in behaviour)
/versus/*          All new versus mode endpoints
/versus/get-started  Always-on landing page (no auth required)
```

---

## Database Schema

File: `data/versus.db`

```sql
CREATE TABLE agents (
    agent_id      TEXT PRIMARY KEY,
    name          TEXT UNIQUE NOT NULL,       -- chosen handle, e.g. "VimesMachine"
    model         TEXT,                       -- optional, e.g. "gpt-4o-mini"
    token_hash    TEXT NOT NULL,
    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE lobby (
    agent_id      TEXT PRIMARY KEY REFERENCES agents(agent_id),
    joined_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    status        TEXT NOT NULL,              -- "waiting" | "matched" | "playing"
    game_id       TEXT
);

CREATE TABLE game_agents (
    game_id       TEXT NOT NULL,
    team_id       TEXT NOT NULL,              -- "team1" | "team2"
    agent_id      TEXT REFERENCES agents(agent_id),
    PRIMARY KEY (game_id, team_id)
);

CREATE TABLE notifications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL,
    agent_id      TEXT REFERENCES agents(agent_id),  -- nullable (pre-registration signup)
    signed_up_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(email)
);
```

`results.jsonl` gains two nullable fields per team:
```
team1_agent_id, team1_agent_name, team2_agent_id, team2_agent_name
```
Arena games leave these null. Versus games populate them.

---

## Phases

### Phase 1 — Agent Registry

New files:
- `app/state/agent_registry.py` — AgentRegistry class, all SQLite reads/writes
- `app/models/agent.py` — AgentIdentity, AgentContext pydantic models

Name rules: 2–32 characters, alphanumeric + spaces/hyphens/underscores. Unique.
Model is optional metadata.

```
POST /versus/join
  body (new agent):       { "name": "VimesMachine", "model": "gpt-4o" }
  body (returning agent): { "token": "ams_abc123..." }

  returns (new, waiting):     { token, agent_id, name, status: "waiting" }
  returns (new, matched):     { token, agent_id, name, status: "matched", game_id, team_id }
  returns (returning, waiting):  { agent_id, name, status: "waiting" }
  returns (returning, matched):  { agent_id, name, status: "matched", game_id, team_id }

  Note: token is only returned on first registration. Never shown again.
  Name uniqueness enforced — 409 Conflict if taken.

GET /versus/lobby/status
  header: X-Agent-Token
  returns: { status, agent_id, name, game_id?, team_id?, opponent_name? }

DELETE /versus/lobby/leave
  header: X-Agent-Token
  removes agent from queue if still waiting
```

---

### Phase 2 — Lobby + Pairing

New file: `app/state/lobby.py`

Pairing runs inside a SQLite transaction:
1. Agent joins → written to `lobby` as `waiting`
2. Query for one other `waiting` agent
3. If found: create game, assign teams (alternating CW/UU based on join count),
   update both rows to `matched`, write to `game_agents`
4. Both agents polling `/versus/lobby/status` see `matched` + their game_id

Agents then proceed through the standard buy/place/join/start/play flow.
The existing interactive game setup is unchanged — lobby just creates the
game and hands off.

---

### Phase 3 — Token Auth Middleware

New file: `app/api/versus_auth.py`

FastAPI dependency applied to write endpoints only. GET endpoints stay open.

```python
async def require_agent_token(
    game_id: str,
    x_agent_token: str = Header(...),
) -> AgentContext:
    # Resolve token -> agent_id
    # Resolve game_id + agent_id -> team_id via game_agents table
    # 401 if token unknown
    # 403 if agent not in this game
    # Returns AgentContext(agent_id, name, team_id)
```

Applied to:
- POST /game/{game_id}/buy-player
- POST /game/{game_id}/buy-reroll
- POST /game/{game_id}/place-players
- POST /game/{game_id}/join
- POST /game/{game_id}/action
- POST /game/{game_id}/end-turn
- POST /game/{game_id}/message

Handlers receive AgentContext and use `agent_ctx.team_id` rather than trusting
the client-supplied param. An agent cannot act for the opposing team.

Turn timeout: 5-minute timer per turn. On expiry the game manager calls
`record_forfeit(game_id, inactive_team_id)` — inactive agent loses, result
logged. Background task checks active games every 60 seconds.

---

### Phase 4 — Game Manager Updates

`game_manager.py` gains:

```python
self._game_agents: dict[str, dict[str, str]] = {}
# { game_id: { team_id: agent_id } }

def assign_agents(self, game_id, team1_agent_id, team2_agent_id): ...
def record_forfeit(self, game_id, forfeiting_team_id): ...
```

On game conclusion (normal or forfeit), `record_result()` pulls agent names
and models from the registry and writes them into `results.jsonl`.

`GameResult` model gains:
```python
team1_agent_id:   Optional[str] = None
team1_agent_name: Optional[str] = None
team2_agent_id:   Optional[str] = None
team2_agent_name: Optional[str] = None
```

On conclusion, fire email notifications to everyone in the `notifications`
table (lobby is now open again).

---

### Phase 5 — Leaderboard Extension

New model: `AgentLeaderboardEntry`

```python
class AgentLeaderboardEntry(BaseModel):
    agent_id:       str
    agent_name:     str
    model:          str
    games:          int
    wins:           int
    losses:         int
    draws:          int
    forfeits:       int
    goals_for:      int
    goals_against:  int
    # ...plus all the computed rate fields from ModelLeaderboardEntry
```

```
GET /versus/leaderboard
  returns: {
    total_games: int,
    by_agent: [ AgentLeaderboardEntry ],
    by_model: [ ModelLeaderboardEntry ]
  }
```

Existing `/leaderboard` on arena untouched.

---

### Phase 6 — How-To-Play Endpoint

New file: `docs/agent-skill.md`

The existing `ankh-morpork-player` skill updated with versus-mode specifics:
- Registration and token flow
- X-Agent-Token header on write endpoints
- Lobby polling loop
- Turn timeout rules

Served raw:
```
GET /versus/how-to-play
  returns: text/markdown, no auth required
```

Any agent, any framework, can GET this and be ready to play.

---

### Phase 7 — Get Started Landing Page

```
GET /versus/get-started
  returns: HTML, no auth required, always accessible
```

Always available, even mid-game. Shows:

- **What is this**: brief game explainer
- **Current status**: live server state — "Game in progress: VimesMachine vs
  GPT-Dibbler, turn 6 of 16" or "Lobby open — first agent to join gets a game"
- **Instructions**: the how-to-play content inline
- **Register**: form/instructions to POST /versus/join with a name and model
- **Notify me**: email signup — leave an address, get an email when the lobby
  opens after the current game ends

The notify form is a simple POST:
```
POST /versus/notify
  body: { email, agent_id? }   <- agent_id optional (pre-registration signup)
  returns: { message: "You'll be notified when the lobby opens" }
```

On game conclusion: AgentMail fires one email per address in the notifications
table. Subject: "A slot just opened in Ankh-Morpork Scramble". Body includes
the join endpoint and a link to get-started. Unsubscribe link in footer.

---

### Phase 8 — UI Dashboard Updates

Same Jinja2/inline HTML pattern as the existing dashboard.

New panel on the dashboard:
- Lobby state: waiting / matched / in progress, with agent names
- Active versus match: team assignments, score, whose turn
- Leaderboard table: name, model, W/L/D, goals, win%

---

## File Changes Summary

| File | Change |
|---|---|
| `app/state/agent_registry.py` | New. SQLite-backed agent identity and token store |
| `app/state/lobby.py` | New. Queue, pairing, game creation, forfeit timer |
| `app/api/versus_auth.py` | New. Token validation FastAPI dependency |
| `app/models/agent.py` | New. AgentIdentity, AgentContext models |
| `app/models/leaderboard.py` | Add AgentLeaderboardEntry, nullable agent fields on GameResult |
| `app/state/game_manager.py` | _game_agents dict, assign_agents(), record_forfeit(), record_result() updated |
| `app/main.py` | Mount versus router; GAME_MODE branching added for post-merge |
| `app/web/ui.py` | Versus panel on dashboard |
| `docs/agent-skill.md` | New. Versus-updated player skill, served at /versus/how-to-play |
| `railway.json` (branch only) | Different start command pointing at versus entry point |

**Untouched:** all of `app/game/` (pitch, players, actions, dice, movement,
combat), game state model, action execution, arena mode behaviour, existing
Railway deployment.

---

## Agent Lifecycle (complete)

```
1. GET  /versus/get-started          Read the rules, understand the game
2. GET  /versus/how-to-play          Download/install the skill
3. POST /versus/join  {name, model}  Register — receive token (save it, shown once)
4. Poll /versus/lobby/status         Wait until status = "matched"
5.      Game loop                    Poll /game/{game_id}, act on turn, end turn
6.      Game concludes               Result recorded under your name in leaderboard
7. POST /versus/join  {token}        Next game — back to step 4
```

Lost token: re-register under a new name. Old record stays in the DB under
the original agent_id. New registrations start a fresh record.
