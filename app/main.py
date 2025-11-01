"""FastAPI application for Ankh-Morpork Scramble"""
from fastapi import FastAPI, HTTPException
from typing import Optional
from app.models.game_state import GameState
from app.models.team import TeamType
from app.models.actions import ActionRequest, ActionResult, SetupRequest, ValidActionsResponse
from app.models.pitch import Position
from app.state.game_manager import GameManager

app = FastAPI(
    title="Ankh-Morpork Scramble API",
    description="Turn-based sports game server based on Blood Bowl mechanics",
    version="0.1.0"
)

# Global game manager instance
game_manager = GameManager()


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
