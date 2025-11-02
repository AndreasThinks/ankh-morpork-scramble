"""Utilities to prepare a ready-to-play demo game at startup."""
from __future__ import annotations

import logging
import os
from typing import Optional

from app.models.enums import TeamType
from app.models.pitch import Position
from app.state.game_manager import GameManager, GameState


# Default identifiers are configurable so docker-compose users can override them
DEFAULT_GAME_ID = os.getenv("DEFAULT_GAME_ID", "demo-game")

# Pre-configured roster selections for a quick game demo
TEAM1_ROSTER = {
    "constable": "2",
    "clerk_runner": "1",
    "fleet_recruit": "1",
}

TEAM2_ROSTER = {
    "apprentice_wizard": "2",
    "senior_wizard": "1",
    "animated_gargoyle": "1",
}

# Player placements are intentionally simple to make LLM control easier.
TEAM1_POSITIONS = {
    "team1_player_0": Position(x=5, y=6),
    "team1_player_1": Position(x=5, y=7),
    "team1_player_2": Position(x=5, y=8),
    "team1_player_3": Position(x=4, y=7),
}

TEAM2_POSITIONS = {
    "team2_player_0": Position(x=20, y=6),
    "team2_player_1": Position(x=20, y=7),
    "team2_player_2": Position(x=20, y=8),
    "team2_player_3": Position(x=21, y=7),
}


def bootstrap_default_game(
    manager: GameManager,
    *,
    game_id: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> GameState:
    """Create and configure a demo game if it does not already exist.

    This helper prepares a deterministic state so autonomous agents have
    a predictable scenario to reason about. The configuration is idempotent –
    repeated calls simply return the existing game state.

    Args:
        manager: Shared :class:`GameManager` instance.
        game_id: Optional override for the demo game identifier.
        logger: Optional logger used to emit informative startup messages.

    Returns:
        The prepared :class:`GameState` instance.
    """

    demo_game_id = game_id or DEFAULT_GAME_ID
    existing = manager.get_game(demo_game_id)
    if existing:
        if logger:
            logger.debug("Demo game %s already prepared", demo_game_id)
        return existing

    state = manager.create_game(demo_game_id)

    manager.setup_team(demo_game_id, "team1", TeamType.CITY_WATCH, TEAM1_ROSTER)
    manager.setup_team(
        demo_game_id,
        "team2",
        TeamType.UNSEEN_UNIVERSITY,
        TEAM2_ROSTER,
    )

    manager.place_players(demo_game_id, "team1", TEAM1_POSITIONS)
    manager.place_players(demo_game_id, "team2", TEAM2_POSITIONS)

    state.add_event("Demo teams have been placed on the pitch")

    if logger:
        logger.info(
            "Prepared demo game %s with %s total players",
            demo_game_id,
            len(state.players),
        )

    return state


__all__ = [
    "bootstrap_default_game",
    "DEFAULT_GAME_ID",
    "TEAM1_POSITIONS",
    "TEAM2_POSITIONS",
]
