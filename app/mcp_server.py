"""MCP server for LLM agents to play Ankh-Morpork Scramble"""
from typing import Annotated, Optional
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from app.models.game_state import GameState
from app.models.actions import ActionRequest, ActionResult, ValidActionsResponse
from app.models.enums import ActionType
from app.models.pitch import Position
from app.state.game_manager import GameManager


# Create MCP server
mcp = FastMCP("Ankh-Morpork Scramble")


def get_manager() -> GameManager:
    """Get the shared game manager instance"""
    # Import here to access the app's game_manager
    from app.main import game_manager
    return game_manager


@mcp.tool
def join_game(
    game_id: Annotated[str, "The unique identifier of the game to join"],
    team_id: Annotated[str, "Your team's unique identifier (usually 'team1' or 'team2')"]
) -> dict:
    """
    Join a game and mark your team as ready to play.
    
    Use this tool when you first connect to a game that has been set up for you.
    Once both teams have joined and are ready, the game can begin.
    
    Returns:
        Dictionary with success status, your team_id, and whether all players are ready
    
    Example:
        join_game(game_id="game123", team_id="team1")
    """
    manager = get_manager()
    game_state = manager.get_game(game_id)
    
    if not game_state:
        raise ToolError(f"Game '{game_id}' not found. Check the game ID and try again.")
    
    # Mark team as joined
    if team_id == game_state.team1.id:
        game_state.team1_joined = True
        game_state.add_event(f"Team {team_id} joined the game")
    elif team_id == game_state.team2.id:
        game_state.team2_joined = True
        game_state.add_event(f"Team {team_id} joined the game")
    else:
        raise ToolError(
            f"Invalid team_id '{team_id}'. This game has teams: "
            f"'{game_state.team1.id}' and '{game_state.team2.id}'"
        )
    
    # Automatically start the match once both teams are ready.
    game_started = False
    if game_state.players_ready and not game_state.game_started:
        manager.start_game(game_id)
        game_state.add_event("Both teams joined via MCP; kickoff initiated automatically")
        game_started = True

    return {
        "success": True,
        "team_id": team_id,
        "players_ready": game_state.players_ready,
        "game_started": game_state.game_started,
        "message": (
            "Game started after both teams joined"
            if game_started
            else f"Successfully joined as {team_id}"
        )
    }


@mcp.tool
def get_game_state(
    game_id: Annotated[str, "The unique identifier of the game"]
) -> dict:
    """
    Get the complete current state of the game.
    
    This returns all game information including:
    - Both teams' rosters and player positions
    - Current phase (SETUP, PLAYING, KICKOFF, etc.)
    - Active team and turn number
    - Ball location and carrier
    - Player states (standing, prone, stunned, KO'd)
    - Available rerolls
    - Score
    
    Use this regularly to understand the current game situation before making decisions.
    
    Returns:
        Complete GameState object with all current game information
    
    Example:
        state = get_game_state(game_id="game123")
        print(f"Current turn: {state.turn.number if state.turn else 'Not started'}")
        print(f"Active team: {state.turn.active_team if state.turn else 'None'}")
    """
    manager = get_manager()
    game_state = manager.get_game(game_id)
    
    if not game_state:
        raise ToolError(f"Game '{game_id}' not found. Check the game ID and try again.")
    
    return game_state.model_dump()


@mcp.tool
def get_valid_actions(
    game_id: Annotated[str, "The unique identifier of the game"]
) -> ValidActionsResponse:
    """
    Get all valid actions available for the current active team.
    
    This tool tells you:
    - Which team can act right now
    - Which special actions are still available (blitz, pass, hand-off, foul)
    - Which players can move
    - Which players can block which opponents
    - Ball location and carrier
    
    Use this before deciding what action to take. It helps you understand your options.
    
    Returns:
        ValidActionsResponse with detailed information about available actions
    
    Example:
        actions = get_valid_actions(game_id="game123")
        if "player1" in actions.movable_players:
            # This player can move
        if "player1" in actions.blockable_targets:
            # This player has adjacent opponents to block
    """
    manager = get_manager()
    game_state = manager.get_game(game_id)
    
    if not game_state:
        raise ToolError(f"Game '{game_id}' not found. Check the game ID and try again.")
    
    if not game_state.turn:
        raise ToolError("Game has not started yet. Wait for the game to begin.")
    
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


@mcp.tool
def execute_action(
    game_id: Annotated[str, "The unique identifier of the game"],
    action_type: Annotated[ActionType, "Type of action: MOVE, BLOCK, BLITZ, PASS, HAND_OFF, PICKUP, or FOUL"],
    player_id: Annotated[str, "ID of your player who will perform this action"],
    target_position: Annotated[Optional[Position], "Target square coordinates (x, y) for movement"] = None,
    target_player_id: Annotated[Optional[str], "ID of opponent player for blocks/fouls or teammate for passes"] = None,
    path: Annotated[Optional[list[Position]], "Sequence of positions for movement (rarely needed, auto-calculated)"] = None,
    target_receiver_id: Annotated[Optional[str], "ID of teammate to receive pass or hand-off"] = None,
    use_reroll: Annotated[bool, "Whether to use a team reroll on a failed action"] = False
) -> ActionResult:
    """
    Execute a game action with one of your players.
    
    ACTION TYPES:
    
    MOVE: Move a player to an adjacent unoccupied square
        - Requires: target_position
        - Costs movement points based on square type
        - May require dodge roll if leaving opponent's tackle zones
    
    BLOCK: Attack an adjacent opponent
        - Requires: target_player_id (must be adjacent)
        - Rolls block dice based on strength comparison
        - Can knock down, push back, or bounce off opponent
    
    BLITZ: Move and then block (once per turn)
        - Requires: target_player_id and optionally target_position
        - Combines movement and a block action
        - Only available once per team per turn
    
    PASS: Throw the ball to a teammate
        - Requires: target_receiver_id or target_position
        - Ball carrier only
        - Requires passing roll, defender may intercept
        - Only one pass attempt per team per turn
    
    HAND_OFF: Give ball to adjacent teammate
        - Requires: target_receiver_id (must be adjacent)
        - Ball carrier only, safer than passing
        - Only one hand-off per team per turn
    
    PICKUP: Pick up the ball from the ground
        - Requires: player at ball location
        - Requires agility roll
    
    FOUL: Kick a prone opponent (dirty play!)
        - Requires: target_player_id (prone adjacent opponent)
        - Can injure opponent but risks penalty
        - Only one foul per team per turn
    
    Returns:
        ActionResult with success status, dice rolls, and state changes
    
    Example:
        # Move a player
        execute_action(
            game_id="game123",
            action_type=ActionType.MOVE,
            player_id="team1_player1",
            target_position=Position(x=5, y=5)
        )
        
        # Block an opponent
        execute_action(
            game_id="game123",
            action_type=ActionType.BLOCK,
            player_id="team1_player1",
            target_player_id="team2_player3"
        )
    """
    manager = get_manager()
    game_state = manager.get_game(game_id)
    
    if not game_state:
        raise ToolError(f"Game '{game_id}' not found. Check the game ID and try again.")
    
    if not game_state.turn:
        raise ToolError("Game has not started yet. Wait for the game to begin.")
    
    # Verify player belongs to active team
    if not game_state.is_player_on_active_team(player_id):
        active_team = game_state.get_active_team()
        raise ToolError(
            f"Not your turn! It's {active_team.id}'s turn. "
            f"Player '{player_id}' cannot act right now."
        )
    
    # Create action request
    action = ActionRequest(
        action_type=action_type,
        player_id=player_id,
        target_position=target_position,
        path=path,
        target_player_id=target_player_id,
        target_receiver_id=target_receiver_id,
        use_reroll=use_reroll
    )
    
    try:
        result = manager.executor.execute_action(game_state, action)
        
        # Check for scoring after action
        if result.success:
            scored_team = manager.check_scoring(game_id)
            if scored_team:
                result.details["scored"] = scored_team
        
        # If turnover, automatically end turn
        if result.turnover:
            manager.end_turn(game_id)
            result.details["turn_ended"] = True
        
        return result
        
    except Exception as e:
        raise ToolError(f"Action failed: {str(e)}")


@mcp.tool
def end_turn(
    game_id: Annotated[str, "The unique identifier of the game"],
    team_id: Annotated[str, "Your team's identifier to confirm you're ending your own turn"]
) -> dict:
    """
    Manually end your team's current turn.
    
    Use this when you've finished all the actions you want to take this turn.
    The turn will automatically end if a turnover occurs, but you can end it early
    if desired.
    
    After your turn ends:
    - The other team becomes active
    - Your players' movement is reset for next turn
    - Turn number may increment
    
    Returns:
        Dictionary with success status and new game state information
    
    Example:
        end_turn(game_id="game123", team_id="team1")
    """
    manager = get_manager()
    game_state = manager.get_game(game_id)
    
    if not game_state:
        raise ToolError(f"Game '{game_id}' not found. Check the game ID and try again.")
    
    if not game_state.turn:
        raise ToolError("Game has not started yet.")
    
    active_team = game_state.get_active_team()
    if team_id != active_team.id:
        raise ToolError(
            f"Not your turn! It's {active_team.id}'s turn, not {team_id}'s turn."
        )
    
    try:
        new_state = manager.end_turn(game_id)
        new_active = new_state.get_active_team()
        
        return {
            "success": True,
            "turn_ended": team_id,
            "new_active_team": new_active.id,
            "turn_number": new_state.turn.team_turn if new_state.turn else None,
            "message": f"Turn ended. Now {new_active.id}'s turn."
        }
    except Exception as e:
        raise ToolError(f"Failed to end turn: {str(e)}")


@mcp.tool
def use_reroll(
    game_id: Annotated[str, "The unique identifier of the game"],
    team_id: Annotated[str, "Your team's identifier"]
) -> dict:
    """
    Use one of your team's reroll tokens.
    
    Rerolls allow you to reroll a failed dice roll. Each team has a limited
    number of rerolls per half. Use them wisely!
    
    Typically rerolls are used automatically when you set use_reroll=True in
    execute_action, but this tool exists if you need to track or verify reroll usage.
    
    Returns:
        Dictionary with success status and remaining rerolls
    
    Example:
        use_reroll(game_id="game123", team_id="team1")
    """
    manager = get_manager()
    game_state = manager.get_game(game_id)
    
    if not game_state:
        raise ToolError(f"Game '{game_id}' not found. Check the game ID and try again.")
    
    try:
        team = game_state.get_team_by_id(team_id)
        team.use_reroll()
        
        return {
            "success": True,
            "team_id": team_id,
            "rerolls_remaining": team.rerolls_remaining,
            "message": f"Reroll used. {team.rerolls_remaining} rerolls remaining."
        }
    except Exception as e:
        raise ToolError(f"Failed to use reroll: {str(e)}")


@mcp.tool
def get_history(
    game_id: Annotated[str, "The unique identifier of the game"],
    limit: Annotated[int, "Maximum number of recent events to retrieve"] = 50
) -> dict:
    """
    Get the event history log for the game.
    
    The history contains all significant game events in chronological order:
    - Player movements and actions
    - Dice rolls and outcomes
    - Turnovers and scoring
    - Player injuries and knockdowns
    - Turn changes
    
    This helps you understand what has happened so far in the game.
    
    Returns:
        Dictionary with game_id and list of event strings
    
    Example:
        history = get_history(game_id="game123", limit=20)
        print("Recent events:", history["events"])
    """
    manager = get_manager()
    game_state = manager.get_game(game_id)
    
    if not game_state:
        raise ToolError(f"Game '{game_id}' not found. Check the game ID and try again.")
    
    return {
        "game_id": game_id,
        "total_events": len(game_state.event_log),
        "events": game_state.event_log[-limit:]
    }


@mcp.tool
def send_message(
    game_id: Annotated[str, "The unique identifier of the game"],
    sender_id: Annotated[str, "Your identifier (usually your team_id)"],
    sender_name: Annotated[str, "Your display name"],
    content: Annotated[str, "The message content to send"]
) -> dict:
    """
    Send a message to your opponent in the game.
    
    Use this to communicate during the game. Good sportsmanship is encouraged!
    Messages are visible to both teams.
    
    Returns:
        Dictionary with success status and the message that was sent
    
    Example:
        send_message(
            game_id="game123",
            sender_id="team1",
            sender_name="Watch Commander",
            content="Good luck and have fun!"
        )
    """
    manager = get_manager()
    game_state = manager.get_game(game_id)
    
    if not game_state:
        raise ToolError(f"Game '{game_id}' not found. Check the game ID and try again.")
    
    try:
        message = game_state.add_message(sender_id, sender_name, content)
        return {
            "success": True,
            "message": message
        }
    except Exception as e:
        raise ToolError(f"Failed to send message: {str(e)}")


@mcp.tool
def get_messages(
    game_id: Annotated[str, "The unique identifier of the game"],
    turn_number: Annotated[Optional[int], "Get messages from a specific turn number only"] = None,
    limit: Annotated[Optional[int], "Maximum number of recent messages to retrieve"] = None
) -> dict:
    """
    Get messages from the game.
    
    You can filter messages by turn number to see only messages from a specific turn,
    or limit the number of messages to get the most recent ones.
    
    Returns:
        Dictionary with game_id, count, and list of message objects
    
    Example:
        # Get all messages
        messages = get_messages(game_id="game123")
        
        # Get last 10 messages
        messages = get_messages(game_id="game123", limit=10)
        
        # Get messages from turn 3
        messages = get_messages(game_id="game123", turn_number=3)
    """
    manager = get_manager()
    game_state = manager.get_game(game_id)
    
    if not game_state:
        raise ToolError(f"Game '{game_id}' not found. Check the game ID and try again.")
    
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
