"""Tests for ball handling mechanics"""
import pytest
from app.game.ball_handling import BallHandler
from app.game.dice import DiceRoller
from app.models.game_state import GameState, TurnState
from app.models.team import Team, TeamType
from app.models.player import Player, PlayerPosition
from app.models.pitch import Position
from app.models.enums import GamePhase, PassResult


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


def create_test_player(player_id: str, team_id: str) -> Player:
    """Helper to create test player"""
    position = PlayerPosition(
        role="Test",
        cost=50000,
        max_quantity=16,
        ma=6,
        st=3,
        ag="3+",
        pa="4+",
        av="9+"
    )
    return Player(id=player_id, team_id=team_id, position=position)


def test_pickup_success():
    """Test successful ball pickup"""
    handler = BallHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1")
    game_state.players["p1"] = player
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    game_state.pitch.place_ball(Position(x=5, y=7))
    
    success, roll = handler.attempt_pickup(game_state, player)
    
    # Depending on dice roll, might succeed or fail
    assert roll.type in ["pickup", "agility"]
    if success:
        assert game_state.pitch.ball_carrier == "p1"


def test_pickup_with_tackle_zones():
    """Test pickup with tackle zone modifiers"""
    handler = BallHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1")
    enemy = create_test_player("enemy1", "team2")
    game_state.players["p1"] = player
    game_state.players["enemy1"] = enemy
    
    # Place player and enemy adjacent
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    game_state.pitch.player_positions["enemy1"] = Position(x=6, y=7)
    game_state.pitch.place_ball(Position(x=5, y=7))
    
    success, roll = handler.attempt_pickup(game_state, player)
    
    # Should have tackle zone modifier
    assert "tackle_zones" in roll.modifiers
    assert roll.modifiers["tackle_zones"] == -1


def test_failed_pickup_scatters_ball():
    """Test that failed pickup scatters the ball"""
    handler = BallHandler(DiceRoller(seed=1))  # Seed for failure
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1")
    game_state.players["p1"] = player
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    game_state.pitch.place_ball(Position(x=5, y=7))
    
    original_ball_pos = game_state.pitch.ball_position
    success, roll = handler.attempt_pickup(game_state, player)
    
    if not success:
        # Ball should have scattered
        assert game_state.pitch.ball_position != original_ball_pos
        assert game_state.pitch.ball_carrier is None


def test_calculate_pass_range():
    """Test pass range calculations"""
    handler = BallHandler(DiceRoller(seed=42))
    
    from_pos = Position(x=5, y=7)
    
    # Quick pass (≤3 squares)
    quick_target = Position(x=7, y=7)
    assert handler.calculate_pass_range(from_pos, quick_target) == "quick"
    
    # Short pass (4-6 squares)
    short_target = Position(x=10, y=7)
    assert handler.calculate_pass_range(from_pos, short_target) == "short"
    
    # Long pass (7-12 squares)
    long_target = Position(x=15, y=7)
    assert handler.calculate_pass_range(from_pos, long_target) == "long"
    
    # Long bomb (>12 squares)
    bomb_target = Position(x=20, y=7)
    assert handler.calculate_pass_range(from_pos, bomb_target) == "long_bomb"


def test_pass_modifiers_by_range():
    """Test that pass gets correct modifiers by range"""
    handler = BallHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    passer = create_test_player("p1", "team1")
    game_state.players["p1"] = passer
    from_pos = Position(x=5, y=7)
    game_state.pitch.player_positions["p1"] = from_pos
    
    # Quick pass: +1
    quick_target = Position(x=7, y=7)
    mods = handler.get_pass_modifiers(game_state, passer, from_pos, quick_target)
    assert mods["range"] == 1
    
    # Short pass: 0
    short_target = Position(x=10, y=7)
    mods = handler.get_pass_modifiers(game_state, passer, from_pos, short_target)
    assert mods["range"] == 0
    
    # Long pass: -1
    long_target = Position(x=15, y=7)
    mods = handler.get_pass_modifiers(game_state, passer, from_pos, long_target)
    assert mods["range"] == -1


def test_pass_with_tackle_zones():
    """Test pass with tackle zone modifiers"""
    handler = BallHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    passer = create_test_player("p1", "team1")
    enemy = create_test_player("enemy1", "team2")
    game_state.players["p1"] = passer
    game_state.players["enemy1"] = enemy
    
    from_pos = Position(x=5, y=7)
    game_state.pitch.player_positions["p1"] = from_pos
    game_state.pitch.player_positions["enemy1"] = Position(x=6, y=7)
    
    target = Position(x=10, y=7)
    mods = handler.get_pass_modifiers(game_state, passer, from_pos, target)
    
    # Should have tackle zone penalty
    assert "tackle_zones" in mods
    assert mods["tackle_zones"] == -1


def test_attempt_pass_releases_ball():
    """Test that attempting pass releases the ball"""
    handler = BallHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    passer = create_test_player("p1", "team1")
    game_state.players["p1"] = passer
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    
    # Give passer the ball
    game_state.pitch.ball_carrier = "p1"
    game_state.pitch.ball_position = Position(x=5, y=7)
    
    target = Position(x=10, y=7)
    result, ball_pos, dice_rolls = handler.attempt_pass(game_state, passer, target)
    
    # Ball should be released
    assert game_state.pitch.ball_carrier is None
    assert len(dice_rolls) > 0
    assert result in [PassResult.ACCURATE, PassResult.INACCURATE, 
                      PassResult.WILDLY_INACCURATE, PassResult.FUMBLE]


def test_catch_success():
    """Test successful catch"""
    handler = BallHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    catcher = create_test_player("p1", "team1")
    game_state.players["p1"] = catcher
    game_state.pitch.player_positions["p1"] = Position(x=10, y=7)
    game_state.pitch.place_ball(Position(x=10, y=7))
    
    success, roll = handler.attempt_catch(game_state, catcher, from_pass=True)
    
    assert roll.type in ["catch", "agility"]
    if success:
        assert game_state.pitch.ball_carrier == "p1"


def test_catch_with_tackle_zones():
    """Test catch with tackle zone penalties"""
    handler = BallHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    catcher = create_test_player("p1", "team1")
    enemy = create_test_player("enemy1", "team2")
    game_state.players["p1"] = catcher
    game_state.players["enemy1"] = enemy
    
    game_state.pitch.player_positions["p1"] = Position(x=10, y=7)
    game_state.pitch.player_positions["enemy1"] = Position(x=11, y=7)
    game_state.pitch.place_ball(Position(x=10, y=7))
    
    success, roll = handler.attempt_catch(game_state, catcher)
    
    # Should have tackle zone penalty
    assert "tackle_zones" in roll.modifiers
    assert roll.modifiers["tackle_zones"] == -1


def test_failed_catch_scatters():
    """Test that failed catch scatters the ball"""
    handler = BallHandler(DiceRoller(seed=1))  # Seed for failure
    game_state = create_test_game_state()
    
    catcher = create_test_player("p1", "team1")
    game_state.players["p1"] = catcher
    game_state.pitch.player_positions["p1"] = Position(x=10, y=7)
    game_state.pitch.place_ball(Position(x=10, y=7))
    
    original_pos = game_state.pitch.ball_position
    success, roll = handler.attempt_catch(game_state, catcher)
    
    if not success:
        # Ball should have scattered
        assert game_state.pitch.ball_position != original_pos or success


def test_scatter_ball():
    """Test ball scatter mechanics"""
    handler = BallHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    original_pos = Position(x=10, y=7)
    game_state.pitch.place_ball(original_pos)
    
    new_pos = handler.scatter_ball(game_state)
    
    # Should have moved (usually, unless scatter is 0,0)
    distance = original_pos.distance_to(new_pos)
    assert distance <= 2  # Scatter is max 1 square in any direction
    
    # Should stay on pitch
    assert 0 <= new_pos.x < 26
    assert 0 <= new_pos.y < 15


def test_hand_off_success():
    """Test successful hand-off"""
    handler = BallHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    giver = create_test_player("p1", "team1")
    receiver = create_test_player("p2", "team1")
    game_state.players["p1"] = giver
    game_state.players["p2"] = receiver
    
    # Place adjacent
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    game_state.pitch.player_positions["p2"] = Position(x=6, y=7)
    
    # Give ball to giver
    game_state.pitch.ball_carrier = "p1"
    game_state.pitch.ball_position = Position(x=5, y=7)
    
    success, error = handler.hand_off(game_state, giver, receiver)
    
    assert success == True
    assert game_state.pitch.ball_carrier == "p2"


def test_hand_off_requires_adjacent():
    """Test hand-off requires players to be adjacent"""
    handler = BallHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    giver = create_test_player("p1", "team1")
    receiver = create_test_player("p2", "team1")
    game_state.players["p1"] = giver
    game_state.players["p2"] = receiver
    
    # Place NOT adjacent
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    game_state.pitch.player_positions["p2"] = Position(x=10, y=7)
    
    game_state.pitch.ball_carrier = "p1"
    game_state.pitch.ball_position = Position(x=5, y=7)
    
    success, error = handler.hand_off(game_state, giver, receiver)
    
    assert success == False
    assert "adjacent" in error.lower()


def test_hand_off_same_team_only():
    """Test hand-off only works with same team"""
    handler = BallHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    giver = create_test_player("p1", "team1")
    receiver = create_test_player("p2", "team2")  # Different team!
    game_state.players["p1"] = giver
    game_state.players["p2"] = receiver
    
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    game_state.pitch.player_positions["p2"] = Position(x=6, y=7)
    
    game_state.pitch.ball_carrier = "p1"
    game_state.pitch.ball_position = Position(x=5, y=7)
    
    success, error = handler.hand_off(game_state, giver, receiver)
    
    assert success == False
    assert "team" in error.lower()
