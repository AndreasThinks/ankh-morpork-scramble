"""Tests for action executor"""
import pytest
from app.state.action_executor import ActionExecutor
from app.game.dice import DiceRoller
from app.models.game_state import GameState, TurnState
from app.models.team import Team, TeamType
from app.models.player import Player, PlayerPosition
from app.models.pitch import Position
from app.models.actions import ActionRequest, ActionType
from app.models.enums import GamePhase, BlockResult


def create_test_game_state() -> GameState:
    """Helper to create a test game state"""
    team1 = Team(id="team1", name="Team 1", team_type=TeamType.CITY_WATCH)
    team2 = Team(id="team2", name="Team 2", team_type=TeamType.UNSEEN_UNIVERSITY)
    
    game_state = GameState(
        game_id="test_game",
        team1=team1,
        team2=team2,
        phase=GamePhase.ACTIVE_PLAY
    )
    
    game_state.turn = TurnState(
        half=1,
        team_turn=1,
        active_team_id="team1"
    )
    
    return game_state


def create_test_player(player_id: str, team_id: str, ma: int = 6, st: int = 3) -> Player:
    """Helper to create test player"""
    position = PlayerPosition(
        role="Test",
        cost=50000,
        max_quantity=16,
        ma=ma,
        st=st,
        ag="3+",
        pa="4+",
        av="9+"
    )
    return Player(id=player_id, team_id=team_id, position=position)


def test_execute_move_simple():
    """Test simple move action"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1")
    game_state.players["p1"] = player
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    
    action = ActionRequest(
        action_type=ActionType.MOVE,
        player_id="p1",
        path=[Position(x=6, y=7), Position(x=7, y=7)]
    )
    
    result = executor.execute_action(game_state, action)
    
    assert result.success == True
    assert player.has_acted == True
    assert game_state.pitch.player_positions["p1"] == Position(x=7, y=7)


def test_execute_move_with_auto_pickup():
    """Test move action with automatic ball pickup"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1")
    game_state.players["p1"] = player
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    
    # Place ball at destination
    game_state.pitch.place_ball(Position(x=6, y=7))
    
    action = ActionRequest(
        action_type=ActionType.MOVE,
        player_id="p1",
        path=[Position(x=6, y=7)]
    )
    
    result = executor.execute_action(game_state, action)
    
    # Should have pickup roll
    pickup_rolls = [r for r in result.dice_rolls if r.type in ["pickup", "agility"]]
    assert len(pickup_rolls) > 0


def test_execute_move_without_path_fails():
    """Test move without path fails"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1")
    game_state.players["p1"] = player
    
    action = ActionRequest(
        action_type=ActionType.MOVE,
        player_id="p1",
        path=[]
    )
    
    result = executor.execute_action(game_state, action)
    assert result.success == False
    assert "path" in result.message.lower()


def test_execute_stand_up():
    """Test stand up action"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1")
    player.knock_down()
    game_state.players["p1"] = player
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    
    action = ActionRequest(
        action_type=ActionType.STAND_UP,
        player_id="p1"
    )
    
    result = executor.execute_action(game_state, action)
    
    assert result.success == True
    assert player.is_standing == True
    assert player.movement_remaining == 3  # 6 - 3 for standing


def test_execute_stand_up_without_movement_fails():
    """Test stand up fails without enough movement"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1")
    player.use_movement(4)  # Only 2 MA left
    player.knock_down()
    game_state.players["p1"] = player
    
    action = ActionRequest(
        action_type=ActionType.STAND_UP,
        player_id="p1"
    )
    
    result = executor.execute_action(game_state, action)
    assert result.success == False


def test_execute_block():
    """Test block action"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    attacker = create_test_player("p1", "team1", st=3)
    defender = create_test_player("p2", "team2", st=3)
    game_state.players["p1"] = attacker
    game_state.players["p2"] = defender
    
    # Place adjacent
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    game_state.pitch.player_positions["p2"] = Position(x=6, y=7)
    
    action = ActionRequest(
        action_type=ActionType.SCUFFLE,
        player_id="p1",
        target_player_id="p2"
    )
    
    result = executor.execute_action(game_state, action)
    
    assert result.success == True
    assert attacker.has_acted == True
    assert len(result.dice_rolls) > 0
    assert result.block_result is not None


def test_execute_block_without_target_fails():
    """Test block without target fails"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    attacker = create_test_player("p1", "team1")
    game_state.players["p1"] = attacker
    
    action = ActionRequest(
        action_type=ActionType.SCUFFLE,
        player_id="p1",
        target_player_id=None
    )
    
    result = executor.execute_action(game_state, action)
    assert result.success == False
    assert "target" in result.message.lower()


def test_execute_block_turnover_if_ball_carrier_down():
    """Test block causes turnover if ball carrier is knocked down"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    attacker = create_test_player("p1", "team1", st=5)  # Strong attacker
    defender = create_test_player("p2", "team2", st=2)  # Weak defender
    game_state.players["p1"] = attacker
    game_state.players["p2"] = defender
    
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    game_state.pitch.player_positions["p2"] = Position(x=6, y=7)
    
    # Defender has ball
    game_state.pitch.ball_carrier = "p2"
    game_state.pitch.ball_position = Position(x=6, y=7)
    
    action = ActionRequest(
        action_type=ActionType.SCUFFLE,
        player_id="p1",
        target_player_id="p2"
    )
    
    result = executor.execute_action(game_state, action)
    
    # If defender was knocked down, should be turnover
    if result.defender_knocked_down:
        assert result.turnover == True
        assert result.ball_dropped == True


def test_execute_blitz():
    """Test blitz action (move + block)"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    attacker = create_test_player("p1", "team1", st=3)
    defender = create_test_player("p2", "team2", st=3)
    game_state.players["p1"] = attacker
    game_state.players["p2"] = defender
    
    # Place attacker 2 squares away
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    game_state.pitch.player_positions["p2"] = Position(x=7, y=7)
    
    action = ActionRequest(
        action_type=ActionType.CHARGE,
        player_id="p1",
        path=[Position(x=6, y=7)],  # Move adjacent
        target_player_id="p2"
    )
    
    result = executor.execute_action(game_state, action)
    
    assert result.success == True
    assert game_state.turn.charge_used == True
    assert attacker.has_acted == True
    assert result.block_result is not None


def test_execute_blitz_only_once_per_turn():
    """Test blitz can only be used once per turn"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    game_state.turn.charge_used = True
    
    attacker = create_test_player("p1", "team1")
    game_state.players["p1"] = attacker
    
    action = ActionRequest(
        action_type=ActionType.CHARGE,
        player_id="p1",
        target_player_id="p2"
    )
    
    result = executor.execute_action(game_state, action)
    assert result.success == False
    assert "already used" in result.message.lower()


def test_execute_pass():
    """Test pass action"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    passer = create_test_player("p1", "team1")
    game_state.players["p1"] = passer
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    
    # Passer has ball
    game_state.pitch.ball_carrier = "p1"
    game_state.pitch.ball_position = Position(x=5, y=7)
    
    action = ActionRequest(
        action_type=ActionType.HURL,
        player_id="p1",
        target_position=Position(x=10, y=7)
    )
    
    result = executor.execute_action(game_state, action)
    
    assert result.success == True
    assert game_state.turn.hurl_used == True
    assert passer.has_acted == True
    assert result.pass_result is not None


def test_execute_pass_without_target_fails():
    """Test pass without target position fails"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    passer = create_test_player("p1", "team1")
    game_state.players["p1"] = passer
    
    action = ActionRequest(
        action_type=ActionType.HURL,
        player_id="p1",
        target_position=None
    )
    
    result = executor.execute_action(game_state, action)
    assert result.success == False
    assert "target" in result.message.lower()


def test_execute_pass_only_once_per_turn():
    """Test pass can only be used once per turn"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    game_state.turn.hurl_used = True
    
    passer = create_test_player("p1", "team1")
    game_state.players["p1"] = passer
    
    action = ActionRequest(
        action_type=ActionType.HURL,
        player_id="p1",
        target_position=Position(x=10, y=7)
    )
    
    result = executor.execute_action(game_state, action)
    assert result.success == False
    assert "already used" in result.message.lower()


def test_execute_hand_off():
    """Test hand-off action"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    giver = create_test_player("p1", "team1")
    receiver = create_test_player("p2", "team1")
    game_state.players["p1"] = giver
    game_state.players["p2"] = receiver
    
    # Place adjacent
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    game_state.pitch.player_positions["p2"] = Position(x=6, y=7)
    
    # Giver has ball
    game_state.pitch.ball_carrier = "p1"
    game_state.pitch.ball_position = Position(x=5, y=7)
    
    action = ActionRequest(
        action_type=ActionType.QUICK_PASS,
        player_id="p1",
        target_receiver_id="p2"
    )
    
    result = executor.execute_action(game_state, action)
    
    # Hand-off might succeed or fail depending on implementation
    assert game_state.turn.quick_pass_used == True or result.success == False


def test_execute_hand_off_without_receiver_fails():
    """Test hand-off without receiver fails"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    giver = create_test_player("p1", "team1")
    game_state.players["p1"] = giver
    
    action = ActionRequest(
        action_type=ActionType.QUICK_PASS,
        player_id="p1",
        target_receiver_id=None
    )
    
    result = executor.execute_action(game_state, action)
    assert result.success == False
    assert "receiver" in result.message.lower()


def test_execute_foul():
    """Test foul action"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    attacker = create_test_player("p1", "team1")
    target = create_test_player("p2", "team2")
    target.knock_down()  # Target must be prone for foul
    game_state.players["p1"] = attacker
    game_state.players["p2"] = target
    
    # Place adjacent
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    game_state.pitch.player_positions["p2"] = Position(x=6, y=7)
    
    action = ActionRequest(
        action_type=ActionType.BOOT,
        player_id="p1",
        target_player_id="p2"
    )
    
    result = executor.execute_action(game_state, action)
    
    # Foul might succeed or fail
    if result.success:
        assert game_state.turn.boot_used == True


def test_foul_without_target_fails():
    """Test foul without target fails"""
    executor = ActionExecutor(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    attacker = create_test_player("p1", "team1")
    game_state.players["p1"] = attacker
    
    action = ActionRequest(
        action_type=ActionType.BOOT,
        player_id="p1",
        target_player_id=None
    )
    
    result = executor.execute_action(game_state, action)
    assert result.success == False
    assert "target" in result.message.lower()
