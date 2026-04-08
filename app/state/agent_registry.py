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

# Resolve data directory at call time so DATA_DIR env patches work in tests
def _get_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "/data" if Path("/data").is_mount() else "data"))


def _get_db_path() -> Path:
    return _get_data_dir() / "versus.db"


def _get_conn() -> sqlite3.Connection:
    data_dir = _get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_get_db_path()))
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
                token_prefix  TEXT NOT NULL DEFAULT '',
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
        # Migration: add token_prefix column to existing databases
        try:
            conn.execute("ALTER TABLE agents ADD COLUMN token_prefix TEXT NOT NULL DEFAULT ''")
            conn.commit()
        except Exception:
            pass  # column already exists

        # Migration: add lobby columns for async match flow
        for col in ("scheduled_start TEXT", "acked_at TEXT", "paired_with TEXT"):
            try:
                conn.execute(f"ALTER TABLE lobby ADD COLUMN {col}")
                conn.commit()
            except Exception:
                pass  # column already exists
        
        # Create index after ensuring column exists
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agents_token_prefix ON agents(token_prefix)")
        conn.commit()
    logger.info("versus.db initialised at %s", _get_db_path())


_WORDLIST = [
    "amber", "anchor", "anvil", "arrow", "ashes", "axle", "badge", "barrel",
    "beacon", "blade", "blaze", "bloom", "bolt", "bone", "book", "boot",
    "brace", "brass", "brick", "bridge", "brine", "bronze", "brook", "brush",
    "candle", "cargo", "chalk", "chain", "chase", "chest", "chip", "cinder",
    "cipher", "cloak", "clock", "cloud", "clover", "coal", "cobble", "coin",
    "comet", "copper", "cord", "cork", "crane", "crest", "cross", "crown",
    "dale", "dart", "dawn", "deck", "delta", "ditch", "dome", "draft",
    "drake", "draw", "drift", "drum", "dusk", "dust", "echo", "edge",
    "ember", "epoch", "fable", "fang", "fern", "field", "flare", "flask",
    "flint", "flood", "flora", "flute", "foam", "forge", "fork", "fossil",
    "frame", "frost", "gale", "gate", "gauge", "gavel", "gear", "gem",
    "ghost", "glade", "glass", "gleam", "gloom", "glyph", "grain", "gravel",
    "grove", "guard", "guild", "hatch", "haven", "hawk", "haze", "helm",
    "hinge", "hive", "hollow", "hook", "horn", "hull", "husk", "iron",
    "jade", "jewel", "keel", "kelp", "knot", "latch", "lava", "ledge",
    "lens", "link", "loom", "lute", "mace", "marsh", "mask", "mast",
    "maul", "maze", "mead", "mesh", "mill", "mist", "mote", "mound",
    "mount", "murk", "nail", "nest", "notch", "oak", "oar", "ore",
    "peak", "peat", "petal", "pike", "pillar", "pine", "pitch", "pivot",
    "plank", "plate", "plume", "pod", "pool", "post", "prism", "pump",
    "quill", "rack", "rail", "ramp", "raven", "reef", "ridge", "rivet",
    "robe", "rock", "rook", "rope", "ruin", "rune", "rust", "sable",
    "sage", "salt", "shard", "shelf", "shell", "shield", "shoal", "signal",
    "silver", "slate", "sluice", "smoke", "snare", "spark", "spear", "spike",
    "spine", "spire", "spool", "spore", "staff", "stave", "steel", "stem",
    "stone", "storm", "strap", "straw", "stream", "stride", "strut", "sump",
    "surge", "sway", "thorn", "tide", "tile", "timber", "token", "torch",
    "tower", "track", "trap", "trench", "trill", "trunk", "tusk", "vale",
    "valve", "vault", "veil", "vine", "visor", "wake", "ward", "warden",
    "wave", "weld", "wheel", "whirl", "wick", "wisp", "wren", "zinc",
]


def _generate_token() -> str:
    """Generate a human-readable agent token: three random words joined by dashes.

    Uses secrets.choice for cryptographic randomness. A 256-word list gives
    256^3 = 16.7 million combinations — ample for a game context. The format
    avoids the ams_ prefix which clashes with AgentMail token masking.
    """
    return "-".join(secrets.choice(_WORDLIST) for _ in range(3))


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
        token_prefix = raw_token[:12]
        now = datetime.now(timezone.utc).isoformat()

        try:
            with _get_conn() as conn:
                conn.execute(
                    "INSERT INTO agents (agent_id, name, model, token_hash, token_prefix, registered_at) VALUES (?,?,?,?,?,?)",
                    (agent_id, name, model, token_hash, token_prefix, now)
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
