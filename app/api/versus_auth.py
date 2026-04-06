"""
Optional token auth dependency for versus mode game endpoints.

Arena games (no agent assignments in game_agents table) pass through without
any auth check. Versus games require X-Agent-Token to match an assigned agent.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Header, HTTPException

from app.models.agent import AgentContext
from app.state.agent_registry import AgentRegistry, _get_conn

logger = logging.getLogger("app.api.versus_auth")

# Module-level registry instance — shares the same DB as the one in main.py
_registry = AgentRegistry()


async def optional_agent_auth(
    game_id: str,
    x_agent_token: Optional[str] = Header(None),
) -> Optional[AgentContext]:
    """
    FastAPI dependency for game write endpoints.

    - If game has no agent assignments (arena game): returns None, no auth required.
    - If game has agent assignments (versus game):
        - Token missing → 401
        - Token invalid → 401
        - Token valid but agent not in this game → 403
        - Token valid and agent assigned → returns AgentContext with team_id set
    """
    # Check if this game has agent assignments
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT team_id, agent_id FROM game_agents WHERE game_id=?",
            (game_id,)
        ).fetchall()

    if not rows:
        # No assignments = arena game, pass through
        return None

    # Versus game — token required
    if not x_agent_token:
        raise HTTPException(
            status_code=401,
            detail="X-Agent-Token header required for versus games"
        )

    identity = _registry.resolve_token(x_agent_token)
    if not identity:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Find this agent's team assignment for this game
    assignments = {row["team_id"]: row["agent_id"] for row in rows}
    my_team_id = next(
        (tid for tid, aid in assignments.items() if aid == identity.agent_id),
        None
    )
    if not my_team_id:
        raise HTTPException(
            status_code=403,
            detail="You are not a participant in this game"
        )

    return AgentContext(
        agent_id=identity.agent_id,
        name=identity.name,
        team_id=my_team_id,
    )
