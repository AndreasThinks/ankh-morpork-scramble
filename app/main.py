"""FastAPI application for Ankh-Morpork Scramble"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
import asyncio
from app.logging_utils import configure_root_logger
from app.web import router as ui_router

from app.models.game_state import GameState
from app.models.team import TeamType
from app.models.actions import (
    ActionRequest,
    ActionResult,
    SetupRequest,
    ValidActionsResponse,
    BudgetStatus,
    PurchaseResult,
    AvailablePositionsResponse
)
from app.models.pitch import Position
from app.setup.default_game import DEFAULT_GAME_ID, bootstrap_default_game
from app.setup.interactive_game import INTERACTIVE_GAME_ID, bootstrap_interactive_game
from app.state.game_manager import GameManager
from app.game.statistics import StatisticsAggregator
from app.models.events import GameStatistics

# Global game manager instance
game_manager = GameManager()

# Configure logging early so startup hooks can log useful information
_LOG_FILE = configure_root_logger(service_name="api", env_prefix="APP_")
logger = logging.getLogger("app.main")
if _LOG_FILE:
    logger.info("API log file initialised at %s", _LOG_FILE)

# Import FastMCP for auto-generating MCP server from FastAPI endpoints
from fastmcp import FastMCP

# Configure MCP-specific logging
_MCP_LOG_FILE = configure_root_logger(
    service_name="mcp",
    env_prefix="MCP_",
    default_level=os.getenv("MCP_LOG_LEVEL", "INFO")
)
mcp_logger = logging.getLogger("fastmcp")
if _MCP_LOG_FILE:
    mcp_logger.info("MCP logging initialized at %s", _MCP_LOG_FILE)

# Initialize game based on DEMO_MODE setting
# DEMO_MODE=true (default): Pre-configured demo game ready to play
# DEMO_MODE=false: Interactive setup where agents must buy and place players
demo_mode = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")

if demo_mode:
    # Demo mode: Create pre-configured game ready to play
    default_demo_game_id = os.getenv("DEFAULT_GAME_ID", DEFAULT_GAME_ID)
    demo_game_state = bootstrap_default_game(
        game_manager,
        game_id=default_demo_game_id,
        logger=logger
    )
    logger.info(
        "Demo game '%s' is ready with %d players",
        default_demo_game_id,
        len(demo_game_state.players)
    )
else:
    # Interactive mode: Create empty game requiring setup
    default_demo_game_id = None
    interactive_game_id = os.getenv("INTERACTIVE_GAME_ID", INTERACTIVE_GAME_ID)
    demo_game_state = bootstrap_interactive_game(
        game_manager,
        game_id=interactive_game_id,
        logger=logger
    )
    logger.info(
        "Interactive game '%s' created in DEPLOYMENT phase. Agents must purchase and place players.",
        interactive_game_id
    )

# Simple lifespan for FastAPI
@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """FastAPI application lifespan."""
    # Startup
    logger.info("FastAPI application starting up...")
    logger.info("Game manager initialized with %d active games", len(game_manager.games))
    yield
    # Shutdown
    logger.info("FastAPI application shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Ankh-Morpork Scramble API",
    description="Turn-based sports game server based on Blood Bowl mechanics",
    version="0.1.0",
    lifespan=app_lifespan
)

# Expose the lightweight monitoring dashboard
app.include_router(ui_router)


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "name": "Ankh-Morpork Scramble API",
        "version": "0.1.0",
        "status": "running",
        "disclaimer": "This is an unofficial, non-commercial fan project inspired by Blood Bowl and Discworld. Not affiliated with Games Workshop or Terry Pratchett's estate."
    }


@app.post("/game", response_model=GameState)
def create_game(game_id: Optional[str] = None):
    """Create a new game"""
    try:
        game_state = game_manager.create_game(game_id)
        return game_state
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/game/{game_id}", response_model=GameState)
def get_game(game_id: str):
    """Get current game state"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    return game_state


@app.get("/game/{game_id}/statistics", response_model=GameStatistics)
def get_game_statistics(game_id: str):
    """Return aggregated statistics for a completed or in-progress game."""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    aggregator = StatisticsAggregator(game_state)
    return aggregator.aggregate()


@app.post("/game/{game_id}/setup-team", response_model=GameState)
def setup_team(
    game_id: str,
    team_id: str,
    team_type: TeamType,
    player_positions: dict[str, str]
):
    """
    Set up a team with player roster
    
    Example player_positions:
    {
        "constable": "5",
        "clerk_runner": "1",
        "fleet_recruit": "2",
        "watch_sergeant": "3"
    }
    """
    try:
        game_state = game_manager.setup_team(
            game_id,
            team_id,
            team_type,
            player_positions
        )
        return game_state
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/game/{game_id}/team/{team_id}/budget", response_model=BudgetStatus)
def get_team_budget(game_id: str, team_id: str):
    """Get budget information for a team"""
    try:
        budget_status = game_manager.get_budget_status(game_id, team_id)
        return budget_status
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/game/{game_id}/team/{team_id}/available-positions", response_model=AvailablePositionsResponse)
def get_available_positions(game_id: str, team_id: str):
    """Get available player positions and rerolls for purchase"""
    try:
        available = game_manager.get_available_positions(game_id, team_id)
        return available
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/team/{team_id}/buy-player", response_model=PurchaseResult)
def buy_player(game_id: str, team_id: str, position_key: str):
    """
    Purchase a player for a team during setup phase

    Args:
        game_id: Game identifier
        team_id: Team identifier (e.g., "team1")
        position_key: Position to purchase (e.g., "constable", "apprentice_wizard")

    Returns:
        PurchaseResult with updated budget status
    """
    try:
        result = game_manager.buy_player(game_id, team_id, position_key)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/team/{team_id}/buy-reroll", response_model=PurchaseResult)
def buy_reroll(game_id: str, team_id: str):
    """
    Purchase a team reroll during setup phase

    Args:
        game_id: Game identifier
        team_id: Team identifier (e.g., "team1")

    Returns:
        PurchaseResult with updated budget status
    """
    try:
        result = game_manager.buy_reroll(game_id, team_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/place-players", response_model=GameState)
def place_players(game_id: str, request: SetupRequest):
    """Place players on the pitch during setup"""
    try:
        game_state = game_manager.place_players(
            game_id,
            request.team_id,
            request.positions
        )
        return game_state
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/start", response_model=GameState)
def start_game(game_id: str):
    """Start the game"""
    try:
        game_state = game_manager.start_game(game_id)
        return game_state
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/action", response_model=ActionResult)
def execute_action(game_id: str, action: ActionRequest):
    """Execute a game action"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    # Verify player belongs to active team
    if game_state.turn and not game_state.is_player_on_active_team(action.player_id):
        raise HTTPException(
            status_code=400,
            detail="Not this team's turn"
        )
    
    try:
        result = game_manager.executor.execute_action(game_state, action)
        
        # Check for scoring after action
        if result.success:
            scored_team = game_manager.check_scoring(game_id)
            if scored_team:
                result.details["scored"] = scored_team
        
        # If turnover, automatically end turn
        if result.turnover:
            game_manager.end_turn(game_id)
            result.details["turn_ended"] = True
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/end-turn", response_model=GameState)
def end_turn(game_id: str):
    """Manually end the current turn.

    Raises HTTP 400 if the game has already concluded or if no turn is active.
    """
    try:
        game_state = game_manager.end_turn(game_id)
        return game_state
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/reroll")
def use_reroll(game_id: str, team_id: str):
    """Use a team re-roll"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    try:
        team = game_state.get_team_by_id(team_id)
        team.use_reroll()
        return {"success": True, "rerolls_remaining": team.rerolls_remaining}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/game/{game_id}/valid-actions", response_model=ValidActionsResponse)
def get_valid_actions(game_id: str):
    """Get all valid actions for current game state"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    if not game_state.turn:
        raise HTTPException(status_code=400, detail="Game not started")
    
    active_team = game_state.get_active_team()
    
    # Get movable players (standing, has movement)
    movable_players = []
    blockable_targets = {}
    
    for player_id in active_team.player_ids:
        player = game_state.get_player(player_id)
        
        if player.is_standing and player.movement_remaining > 0:
            movable_players.append(player_id)
        
        # Find blockable targets for this player
        if player.is_standing:
            player_pos = game_state.pitch.player_positions.get(player_id)
            if player_pos:
                targets = []
                for adj_player_id in game_state.pitch.get_adjacent_players(player_pos):
                    adj_player = game_state.get_player(adj_player_id)
                    if adj_player.team_id != player.team_id and adj_player.is_active:
                        targets.append(adj_player_id)
                
                if targets:
                    blockable_targets[player_id] = targets
    
    return ValidActionsResponse(
        current_team=active_team.id,
        phase=game_state.phase.value,
        can_charge=not game_state.turn.charge_used,
        can_hurl=not game_state.turn.hurl_used,
        can_quick_pass=not game_state.turn.quick_pass_used,
        can_boot=not game_state.turn.boot_used,
        movable_players=movable_players,
        blockable_targets=blockable_targets,
        ball_carrier=game_state.pitch.ball_carrier,
        ball_on_ground=game_state.pitch.ball_position is not None and game_state.pitch.ball_carrier is None,
        ball_position=game_state.pitch.ball_position
    )


@app.get("/game/{game_id}/history")
def get_history(game_id: str, limit: int = 50):
    """Get game event history"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    return {
        "game_id": game_id,
        "events": game_state.event_log[-limit:]
    }


@app.get("/game/{game_id}/log")
def export_game_log(game_id: str, format: str = "markdown"):
    """
    Export complete game log with events, dice rolls, and statistics.

    Formats:
    - markdown: Human-readable narrative with full details
    - json: Structured event data

    The log includes:
    - All game events chronologically
    - Dice rolls and outcomes
    - Turn-by-turn breakdown
    - Game statistics
    """
    if format not in ["markdown", "json"]:
        raise HTTPException(
            status_code=400,
            detail="Format must be 'markdown' or 'json'"
        )

    log_content = game_manager.export_game_log(game_id, format=format)

    if not log_content:
        raise HTTPException(
            status_code=404,
            detail=f"Game {game_id} not found or has no events"
        )

    # Return as appropriate content type
    if format == "markdown":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=log_content, media_type="text/markdown")
    else:
        from fastapi.responses import JSONResponse
        import json
        return JSONResponse(content=json.loads(log_content))


@app.get("/game/{game_id}/suggest-path")
def suggest_path(game_id: str, player_id: str, target_x: int, target_y: int):
    """
    Suggest a path for a player to reach a target position with risk assessment.
    
    Returns path with detailed risk information including:
    - Dodge requirements
    - Rush square identification
    - Success probabilities
    - Total risk score
    """
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    try:
        from app.game.pathfinding import PathFinder
        from app.game.movement import MovementHandler
        from app.game.dice import DiceRoller
        
        # Create pathfinder
        dice_roller = DiceRoller()
        movement_handler = MovementHandler(dice_roller)
        pathfinder = PathFinder(movement_handler)
        
        # Generate suggestion
        target_pos = Position(x=target_x, y=target_y)
        suggestion = pathfinder.suggest_path(game_state, player_id, target_pos)
        
        return suggestion
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/join")
def join_game(game_id: str, team_id: str):
    """Mark a team as joined"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    try:
        if team_id == game_state.team1.id:
            game_state.team1_joined = True
            game_state.add_event(f"Team {team_id} joined")
        elif team_id == game_state.team2.id:
            game_state.team2_joined = True
            game_state.add_event(f"Team {team_id} joined")
        else:
            raise HTTPException(status_code=400, detail=f"Invalid team_id: {team_id}")
        
        return {
            "success": True,
            "team_id": team_id,
            "players_ready": game_state.players_ready
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/message")
def send_message(game_id: str, sender_id: str, sender_name: str, content: str):
    """Send a message in the game"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    try:
        message = game_state.add_message(sender_id, sender_name, content)
        return {
            "success": True,
            "message": message
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/game/{game_id}/messages")
def get_messages(game_id: str, turn_number: Optional[int] = None, limit: Optional[int] = None):
    """Get messages from the game"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    messages = game_state.messages
    
    # Filter by turn if specified
    if turn_number is not None:
        messages = [m for m in messages if m.turn_number == turn_number]
    
    # Apply limit if specified
    if limit is not None:
        messages = messages[-limit:]
    
    return {
        "game_id": game_id,
        "count": len(messages),
        "messages": messages
    }


@app.post("/game/{game_id}/reset", response_model=GameState)
def reset_game(game_id: str):
    """Reset game to setup phase, preserving join status and message history"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    try:
        game_state.reset_to_setup()
        return game_state
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/rematch", response_model=GameState)
def rematch_game(game_id: str):
    """Prepare and start a fresh match after the current game concludes."""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    try:
        if demo_mode and default_demo_game_id and game_id == default_demo_game_id:
            # Remove the existing entry so ``bootstrap_default_game`` creates a new instance
            game_manager.games.pop(game_id, None)
            fresh_state = bootstrap_default_game(
                game_manager,
                game_id=game_id,
                logger=logger
            )
            # Mark teams as joined so the kickoff can start immediately
            fresh_state.team1_joined = True
            fresh_state.team2_joined = True
            fresh_state.team1_ready = True
            fresh_state.team2_ready = True
            return game_manager.start_game(game_id)

        # Fallback for interactive/custom games: reset to setup and let clients configure
        game_state.reset_to_setup()
        return game_state

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Generate MCP server from FastAPI endpoints
# This must come after all endpoints are defined
logger.info("Generating MCP server from FastAPI endpoints...")
mcp = FastMCP.from_fastapi(
    app=app,
    name="Ankh-Morpork Scramble MCP"
)
logger.info("MCP server generated with tools for all FastAPI endpoints")

# Create MCP ASGI app and mount it
mcp_app = mcp.http_app(path='/mcp')

# Update FastAPI lifespan to include MCP
@asynccontextmanager
async def combined_lifespan(app: FastAPI):
    """Combined lifespan for FastAPI and MCP."""
    # FastAPI startup
    logger.info("FastAPI application starting up...")
    logger.info("Game manager initialized with %d active games", len(game_manager.games))
    
    # MCP startup (nested)
    async with mcp_app.lifespan(app):
        logger.info("MCP server ready at /mcp")
        yield
    
    # Shutdown
    logger.info("FastAPI application shutting down...")

# Replace the lifespan
app.router.lifespan_context = combined_lifespan

# Mount MCP server
app.mount("/mcp", mcp_app)
logger.info("MCP server mounted at /mcp")


async def main():
    # Use run_async() in async contexts
    await mcp.run_async(transport="http", port=8000)

if __name__ == "__main__":
    asyncio.run(main())
