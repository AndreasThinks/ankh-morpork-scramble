"""FastAPI application for Ankh-Morpork Scramble"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException

from app.logging_utils import configure_root_logger
from app.web import router as ui_router

from app.models.game_state import GameState
from app.models.team import TeamType
from app.models.actions import ActionRequest, ActionResult, SetupRequest, ValidActionsResponse
from app.models.pitch import Position
from app.setup.default_game import DEFAULT_GAME_ID, bootstrap_default_game
from app.state.game_manager import GameManager

# Global game manager instance (must be created before importing mcp_server)
game_manager = GameManager()

# Import MCP server after game_manager is created
from app.mcp_server import mcp

# Create MCP ASGI app
mcp_app = mcp.http_app(path='/')

# Configure logging early so startup hooks can log useful information
_LOG_FILE = configure_root_logger(service_name="api", env_prefix="APP_")
logger = logging.getLogger("app.main")
if _LOG_FILE:
    logger.info("API log file initialised at %s", _LOG_FILE)

# Initialize demo game immediately at module load time
game_id = os.getenv("DEFAULT_GAME_ID", DEFAULT_GAME_ID)
demo_game_state = bootstrap_default_game(game_manager, game_id=game_id, logger=logger)
logger.info("Demo game '%s' is ready with %d players", game_id, len(demo_game_state.players))

# Create FastAPI app with MCP lifespan
app = FastAPI(
    title="Ankh-Morpork Scramble API",
    description="Turn-based sports game server based on Blood Bowl mechanics",
    version="0.1.0",
    lifespan=mcp_app.lifespan
)

# Mount the MCP server at /mcp
app.mount("/mcp", mcp_app)

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
    """Manually end the current turn"""
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
        can_blitz=not game_state.turn.blitz_used,
        can_pass=not game_state.turn.pass_used,
        can_hand_off=not game_state.turn.hand_off_used,
        can_foul=not game_state.turn.foul_used,
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
