# Implementation Plan: Versus Mode Phases 1 & 2

## Overview

Implement agent registration, token auth, and lobby pairing for versus mode.
No changes to the game engine. All new code in new files, plus endpoint additions
to `app/main.py`.

---

## Dependencies to add

Add `bcrypt` to `pyproject.toml` dependencies section. Check existing deps first
and only add if not already present.

---

## File 1: `app/models/agent.py` (NEW)

```python
"""Agent identity models for versus mode."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class AgentIdentity(BaseModel):
    """Persistent agent record stored in SQLite."""
    agent_id: str
    name: str
    model: Optional[str] = None
    token_hash: str  # bcrypt hash — never returned to clients
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentContext(BaseModel):
    """Resolved agent context injected by auth dependency."""
    agent_id: str
    name: str
    team_id: Optional[str] = None  # set once matched to a game


class JoinRequest(BaseModel):
    """POST /versus/join body."""
    # New agent: provide name (and optional model)
    name: Optional[str] = None
    model: Optional[str] = None
    # Returning agent: provide token
    token: Optional[str] = None


class JoinResponse(BaseModel):
    """Response from POST /versus/join."""
    agent_id: str
    name: str
    status: str  # "waiting" or "matched"
    token: Optional[str] = None  # ONLY on first registration, never again
    game_id: Optional[str] = None
    team_id: Optional[str] = None
    opponent_name: Optional[str] = None


class LobbyStatusResponse(BaseModel):
    """Response from GET /versus/lobby/status."""
    agent_id: str
    name: str
    status: str  # "waiting", "matched", "playing", "not_in_lobby"
    game_id: Optional[str] = None
    team_id: Optional[str] = None
    opponent_name: Optional[str] = None
```

---

## File 2: `app/state/agent_registry.py` (NEW)

```python
"""SQLite-backed agent identity and token store."""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import bcrypt

from app.models.agent import AgentIdentity

logger = logging.getLogger("app.state.agent_registry")

# Resolve data directory (matches Railway volume mount pattern)
_DATA_DIR = Path(os.getenv("DATA_DIR", "/data" if Path("/data").is_mount() else "data"))
_DB_PATH = _DATA_DIR / "versus.db"


def _get_conn() -> sqlite3.Connection:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id      TEXT PRIMARY KEY,
                name          TEXT UNIQUE NOT NULL,
                model         TEXT,
                token_hash    TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lobby (
                agent_id  TEXT PRIMARY KEY REFERENCES agents(agent_id),
                joined_at TEXT NOT NULL,
                status    TEXT NOT NULL,
                game_id   TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_agents (
                game_id  TEXT NOT NULL,
                team_id  TEXT NOT NULL,
                agent_id TEXT REFERENCES agents(agent_id),
                PRIMARY KEY (game_id, team_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                email        TEXT NOT NULL UNIQUE,
                agent_id     TEXT REFERENCES agents(agent_id),
                signed_up_at TEXT NOT NULL
            )
        """)
        conn.commit()
    logger.info("versus.db initialised at %s", _DB_PATH)


def _generate_token() -> str:
    """Generate a new agent token: ams_ + 32 hex chars."""
    return "ams_" + secrets.token_hex(16)


def _hash_token(token: str) -> str:
    return bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()


def _verify_token(token: str, token_hash: str) -> bool:
    try:
        return bcrypt.checkpw(token.encode(), token_hash.encode())
    except Exception:
        return False


class AgentRegistry:
    """Read/write agent identity records."""

    def register(self, name: str, model: Optional[str] = None) -> tuple[AgentIdentity, str]:
        """
        Register a new agent. Returns (AgentIdentity, raw_token).
        Raises ValueError if name already taken.
        Name rules: 2-32 chars, alphanumeric + spaces/hyphens/underscores.
        """
        name = name.strip()
        if not (2 <= len(name) <= 32):
            raise ValueError("Name must be 2-32 characters")
        import re
        if not re.match(r'^[\w\s\-]+$', name):
            raise ValueError("Name may only contain letters, numbers, spaces, hyphens, underscores")

        import uuid
        agent_id = str(uuid.uuid4())
        raw_token = _generate_token()
        token_hash = _hash_token(raw_token)
        now = datetime.now(timezone.utc).isoformat()

        try:
            with _get_conn() as conn:
                conn.execute(
                    "INSERT INTO agents (agent_id, name, model, token_hash, registered_at) VALUES (?,?,?,?,?)",
                    (agent_id, name, model, token_hash, now)
                )
                conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Name '{name}' is already taken")

        identity = AgentIdentity(
            agent_id=agent_id, name=name, model=model,
            token_hash=token_hash,
            registered_at=datetime.fromisoformat(now)
        )
        logger.info("Registered agent %s (%s)", name, agent_id)
        return identity, raw_token

    def resolve_token(self, raw_token: str) -> Optional[AgentIdentity]:
        """Resolve a raw token to an AgentIdentity. Returns None if invalid."""
        with _get_conn() as conn:
            # Fetch all agents and check bcrypt — no shortcut, but agent count is small
            rows = conn.execute("SELECT * FROM agents").fetchall()
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

    def get_by_id(self, agent_id: str) -> Optional[AgentIdentity]:
        with _get_conn() as conn:
            row = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
        if not row:
            return None
        return AgentIdentity(
            agent_id=row["agent_id"], name=row["name"], model=row["model"],
            token_hash=row["token_hash"],
            registered_at=datetime.fromisoformat(row["registered_at"])
        )

    def name_taken(self, name: str) -> bool:
        with _get_conn() as conn:
            row = conn.execute("SELECT 1 FROM agents WHERE name=?", (name.strip(),)).fetchone()
        return row is not None
```

---

## File 3: `app/state/lobby.py` (NEW)

```python
"""Lobby queue and pairing logic for versus mode."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from app.state.agent_registry import _get_conn
from app.state.game_manager import GameManager

logger = logging.getLogger("app.state.lobby")

# Alternating team assignment: track total completed pairings
# team1 = City Watch (TeamType.CITY_WATCH), team2 = Unseen University (TeamType.UNSEEN_UNIVERSITY)
# Alternate so neither faction is always team1


class LobbyManager:
    """Manages the waiting queue and pairs agents into games."""

    def __init__(self, game_manager: GameManager):
        self.game_manager = game_manager

    def join(self, agent_id: str) -> dict:
        """
        Add agent to lobby. If another agent is waiting, pair them into a game.
        Returns dict with keys: status, game_id (optional), team_id (optional), opponent_agent_id (optional)
        """
        now = datetime.now(timezone.utc).isoformat()

        with _get_conn() as conn:
            # Remove any stale entry for this agent first
            conn.execute("DELETE FROM lobby WHERE agent_id=?", (agent_id,))

            # Check for a waiting opponent
            opponent = conn.execute(
                "SELECT agent_id FROM lobby WHERE status='waiting' AND agent_id != ? ORDER BY joined_at ASC LIMIT 1",
                (agent_id,)
            ).fetchone()

            if not opponent:
                # No opponent yet — queue this agent
                conn.execute(
                    "INSERT INTO lobby (agent_id, joined_at, status, game_id) VALUES (?,?,?,?)",
                    (agent_id, now, "waiting", None)
                )
                conn.commit()
                logger.info("Agent %s queued, waiting for opponent", agent_id)
                return {"status": "waiting"}

            # Found an opponent — pair them
            opponent_id = opponent["agent_id"]

            # Determine team assignment: count past pairings to alternate
            pairing_count = conn.execute("SELECT COUNT(*) FROM game_agents").fetchone()[0] // 2
            if pairing_count % 2 == 0:
                team1_agent_id = opponent_id   # waiting agent gets team1
                team2_agent_id = agent_id      # joining agent gets team2
            else:
                team1_agent_id = agent_id
                team2_agent_id = opponent_id

            # Get agent names for team names
            t1_name_row = conn.execute("SELECT name FROM agents WHERE agent_id=?", (team1_agent_id,)).fetchone()
            t2_name_row = conn.execute("SELECT name FROM agents WHERE agent_id=?", (team2_agent_id,)).fetchone()
            team1_name = t1_name_row["name"] if t1_name_row else "City Watch"
            team2_name = t2_name_row["name"] if t2_name_row else "Unseen University"

        # Create game outside the connection context to avoid nesting issues
        import uuid
        game_id = f"versus-{uuid.uuid4().hex[:8]}"
        self.game_manager.create_game(game_id)

        # Update team names on the created game
        game_state = self.game_manager.get_game(game_id)
        game_state.team1.name = team1_name
        game_state.team2.name = team2_name

        # Record game_agents and update lobby
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO game_agents (game_id, team_id, agent_id) VALUES (?,?,?)",
                (game_id, "team1", team1_agent_id)
            )
            conn.execute(
                "INSERT INTO game_agents (game_id, team_id, agent_id) VALUES (?,?,?)",
                (game_id, "team2", team2_agent_id)
            )
            conn.execute(
                "UPDATE lobby SET status='matched', game_id=? WHERE agent_id=?",
                (game_id, opponent_id)
            )
            conn.execute(
                "INSERT INTO lobby (agent_id, joined_at, status, game_id) VALUES (?,?,?,?)",
                (agent_id, now, "matched", game_id)
            )
            conn.commit()

        # Determine which team this joining agent is on
        joining_team_id = "team2" if team2_agent_id == agent_id else "team1"

        logger.info("Paired agents %s (team1) vs %s (team2) in game %s",
                    team1_agent_id, team2_agent_id, game_id)
        return {
            "status": "matched",
            "game_id": game_id,
            "team_id": joining_team_id,
            "opponent_agent_id": opponent_id,
        }

    def get_status(self, agent_id: str) -> dict:
        """Get current lobby status for an agent."""
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM lobby WHERE agent_id=?", (agent_id,)
            ).fetchone()

            if not row:
                return {"status": "not_in_lobby"}

            result = {"status": row["status"], "game_id": row["game_id"]}

            if row["game_id"]:
                # Find opponent
                opp = conn.execute(
                    "SELECT ga.agent_id, a.name FROM game_agents ga "
                    "JOIN agents a ON ga.agent_id = a.agent_id "
                    "WHERE ga.game_id=? AND ga.agent_id != ?",
                    (row["game_id"], agent_id)
                ).fetchone()
                if opp:
                    result["opponent_name"] = opp["name"]

                # Find this agent's team_id
                my_team = conn.execute(
                    "SELECT team_id FROM game_agents WHERE game_id=? AND agent_id=?",
                    (row["game_id"], agent_id)
                ).fetchone()
                if my_team:
                    result["team_id"] = my_team["team_id"]

        return result

    def leave(self, agent_id: str) -> bool:
        """Remove agent from lobby if waiting. Returns True if removed."""
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT status FROM lobby WHERE agent_id=?", (agent_id,)
            ).fetchone()
            if not row or row["status"] != "waiting":
                return False
            conn.execute("DELETE FROM lobby WHERE agent_id=?", (agent_id,))
            conn.commit()
        logger.info("Agent %s left the lobby", agent_id)
        return True

    def get_waiting_count(self) -> int:
        with _get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM lobby WHERE status='waiting'").fetchone()
        return row[0] if row else 0
```

---

## File 4: `app/main.py` — additions (MODIFY EXISTING)

### 4a. Add imports near the top (after existing imports)

Add after the line `from app.models.leaderboard import LeaderboardResponse`:

```python
from app.models.agent import AgentIdentity, AgentContext, JoinRequest, JoinResponse, LobbyStatusResponse
from app.state.agent_registry import AgentRegistry, init_db
from app.state.lobby import LobbyManager
```

### 4b. Initialise registry and lobby after `game_manager = GameManager()`

Add these two lines immediately after `game_manager = GameManager()`:

```python
agent_registry = AgentRegistry()
lobby_manager = LobbyManager(game_manager)
```

### 4c. Call init_db() in the lifespan startup block

Inside `app_lifespan`, after `logger.info("Game manager initialized...")`, add:

```python
    init_db()
    logger.info("versus.db initialised")
```

### 4d. Add the versus endpoints at the END of main.py (before the last line if any)

```python
# ── versus mode endpoints ────────────────────────────────────────────────────

@app.post("/versus/join", response_model=JoinResponse)
def versus_join(request: JoinRequest):
    """
    Register a new agent or authenticate a returning one, then join the lobby.

    New agent: provide { name, model (optional) }
    Returning agent: provide { token }

    Token is returned ONLY on first registration. Save it — it is never shown again.
    """
    if request.token:
        # Returning agent
        identity = agent_registry.resolve_token(request.token)
        if not identity:
            raise HTTPException(status_code=401, detail="Invalid token")
        raw_token = None
    elif request.name:
        # New agent — register
        if agent_registry.name_taken(request.name):
            raise HTTPException(
                status_code=409,
                detail=f"Name '{request.name}' is already taken. Choose another."
            )
        try:
            identity, raw_token = agent_registry.register(request.name, request.model)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'token' (returning agent) or 'name' (new agent)"
        )

    # Join the lobby
    result = lobby_manager.join(identity.agent_id)

    # Resolve opponent name if matched
    opponent_name = None
    if result.get("opponent_agent_id"):
        opp = agent_registry.get_by_id(result["opponent_agent_id"])
        if opp:
            opponent_name = opp.name

    return JoinResponse(
        agent_id=identity.agent_id,
        name=identity.name,
        token=raw_token,
        status=result["status"],
        game_id=result.get("game_id"),
        team_id=result.get("team_id"),
        opponent_name=opponent_name,
    )


@app.get("/versus/lobby/status", response_model=LobbyStatusResponse)
def versus_lobby_status(x_agent_token: Optional[str] = Header(None)):
    """
    Poll lobby status for the authenticated agent.
    Returns waiting / matched / playing / not_in_lobby.
    """
    if not x_agent_token:
        raise HTTPException(status_code=401, detail="X-Agent-Token header required")
    identity = agent_registry.resolve_token(x_agent_token)
    if not identity:
        raise HTTPException(status_code=401, detail="Invalid token")

    status = lobby_manager.get_status(identity.agent_id)

    return LobbyStatusResponse(
        agent_id=identity.agent_id,
        name=identity.name,
        status=status["status"],
        game_id=status.get("game_id"),
        team_id=status.get("team_id"),
        opponent_name=status.get("opponent_name"),
    )


@app.delete("/versus/lobby/leave")
def versus_lobby_leave(x_agent_token: Optional[str] = Header(None)):
    """Remove the authenticated agent from the lobby if waiting."""
    if not x_agent_token:
        raise HTTPException(status_code=401, detail="X-Agent-Token header required")
    identity = agent_registry.resolve_token(x_agent_token)
    if not identity:
        raise HTTPException(status_code=401, detail="Invalid token")

    removed = lobby_manager.leave(identity.agent_id)
    return {"removed": removed, "agent_id": identity.agent_id}


@app.get("/versus/agents/{agent_id}")
def versus_get_agent(agent_id: str):
    """Get public profile for an agent (no token, no token_hash returned)."""
    identity = agent_registry.get_by_id(agent_id)
    if not identity:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "agent_id": identity.agent_id,
        "name": identity.name,
        "model": identity.model,
        "registered_at": identity.registered_at,
    }
```

---

## Integration notes

- `bcrypt` must be in `pyproject.toml` — if it's not there, add it.
- The `_get_conn()` function is in `agent_registry.py` and imported by `lobby.py`.
  This is intentional — both share the same DB file and connection helper.
- `init_db()` is idempotent (CREATE TABLE IF NOT EXISTS) — safe to call on every startup.
- The `Header` import is already in `app/main.py` (`from fastapi import FastAPI, HTTPException, Header, Query`).
- `Optional` is already imported in `app/main.py`.
- Do NOT modify any existing endpoints.

---

## Verification steps after implementation

1. `cd /home/andreasclaw/projects/ankh-morpork-scramble && source .venv/bin/activate`
2. `python3 -c "import app.models.agent; import app.state.agent_registry; import app.state.lobby; print('imports OK')"` 
3. `python3 -c "import ast; ast.parse(open('app/main.py').read()); print('main.py syntax OK')"`
4. `uv run pytest tests/ -q 2>&1 | tail -20`
5. Start the server locally and test:
   ```
   uv run uvicorn app.main:app --port 8001 &
   curl -s -X POST http://localhost:8001/versus/join -H "Content-Type: application/json" -d '{"name":"TestAgent","model":"test"}' | python3 -m json.tool
   ```
   Should return agent_id, token, status: "waiting"
6. Register a second agent:
   ```
   curl -s -X POST http://localhost:8001/versus/join -H "Content-Type: application/json" -d '{"name":"TestAgent2","model":"test"}' | python3 -m json.tool
   ```
   Should return status: "matched", game_id, team_id
7. Kill the test server: `pkill -f "uvicorn app.main:app --port 8001"`
8. If all passes: `git add -A && git commit -m "feat: versus phase 1+2 - agent registry and lobby pairing"`
