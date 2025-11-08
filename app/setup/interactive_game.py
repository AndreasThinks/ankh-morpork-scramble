"""Utilities to create an interactive setup game where agents build their teams."""
from __future__ import annotations

import logging
import os
from typing import Optional

from app.models.enums import TeamType, GamePhase
from app.state.game_manager import GameManager, GameState


# Default identifiers are configurable
INTERACTIVE_GAME_ID = os.getenv("INTERACTIVE_GAME_ID", "interactive-game")


def bootstrap_interactive_game(
    manager: GameManager,
    *,
    game_id: Optional[str] = None,
    team1_type: TeamType = TeamType.CITY_WATCH,
    team2_type: TeamType = TeamType.UNSEEN_UNIVERSITY,
    team1_name: str = "Team 1",
    team2_name: str = "Team 2",
    logger: Optional[logging.Logger] = None,
) -> GameState:
    """Create an interactive game where agents must buy and place their own players.

    This creates a game in DEPLOYMENT phase with empty rosters. Agents must:
    1. Join the game using join_game()
    2. Purchase players using buy_player() (at least 3)
    3. Optionally purchase rerolls using buy_reroll()
    4. Place players on the pitch using place_players()
    5. Mark ready using ready_to_play()

    Once both teams are ready, the game automatically starts.

    This configuration is idempotent – repeated calls simply return the existing game.

    Args:
        manager: Shared :class:`GameManager` instance.
        game_id: Optional override for the interactive game identifier.
        team1_type: Team type for team 1 (default: CITY_WATCH)
        team2_type: Team type for team 2 (default: UNSEEN_UNIVERSITY)
        team1_name: Display name for team 1
        team2_name: Display name for team 2
        logger: Optional logger used to emit informative startup messages.

    Returns:
        The prepared :class:`GameState` instance in DEPLOYMENT phase.
    """
    interactive_game_id = game_id or INTERACTIVE_GAME_ID
    existing = manager.get_game(interactive_game_id)
    if existing:
        if logger:
            logger.debug("Interactive game %s already exists", interactive_game_id)
        return existing

    # Create empty game in DEPLOYMENT phase
    state = manager.create_game(interactive_game_id)

    # Set team types and names
    state.team1.team_type = team1_type
    state.team1.name = team1_name
    state.team2.team_type = team2_type
    state.team2.name = team2_name

    # Game starts in DEPLOYMENT phase by default
    assert state.phase == GamePhase.DEPLOYMENT

    state.add_event(
        "Interactive game created. Teams must purchase and place players before starting."
    )

    if logger:
        logger.info(
            "Created interactive game %s: %s (%s) vs %s (%s)",
            interactive_game_id,
            team1_name,
            team1_type.value,
            team2_name,
            team2_type.value,
        )

    return state


__all__ = [
    "bootstrap_interactive_game",
    "INTERACTIVE_GAME_ID",
]
