"""Tests for movement mechanics"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.game.movement import MovementHandler
from app.game.dice import DiceRoller
from app.models.game_state import GameState, TurnState
from app.models.team import Team, TeamType
from app.models.player import Player, PlayerPosition
from app.models.pitch import Pitch, Position
from app.models.enums import PlayerState, SkillType, GamePhase


client = TestClient(app)


def create_test_game_state() -> GameState:
    """Helper to create a test game state"""
    team1 = Team(id="team1", name="Team 1", team_type=TeamType.CITY_WATCH)
    team2 = Team(id="team2", name="Team 2", team_type=TeamType.UNSEEN_UNIVERSITY)
    
    game_state = GameState(
        game_id="test_game",
        team1=team1,
        team2=team2,
        phase=GamePhase.PLAYING
    )
    
    game_state.turn = TurnState(
        half=1,
        team_turn=1,
        active_team_id="team1"
    )
    
    return game_state


def create_test_player(player_id: str, team_id: str, ma: int = 6) -> Player:
    """Helper to create test player"""
    position = PlayerPosition(
        role="Test",
        cost=50000,
        ma=ma,
        st=3,
        ag="3+",
        pa="4+",
        av="9+"
    )
    return Player(id=player_id, team_id=team_id, position=position)


def test_get_tackle_zones():
    """Test tackle zone calculation"""
    handler = MovementHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    # Add enemy player
    enemy = create_test_player("enemy1", "team2")
    game_state.players["enemy1"] = enemy
    game_state.pitch.player_positions["enemy1"] = Position(x=6, y=7)
    
    # Check tackle zones at adjacent position
    tz_count = handler.get_tackle_zones(game_state, "team1", Position(x=5, y=7))
    assert tz_count == 1


def test_tackle_zones_ignore_prone():
    """Test that prone players don't exert tackle zones"""
    handler = MovementHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    # Add prone enemy
    enemy = create_test_player("enemy1", "team2")
    enemy.knock_down()
    game_state.players["enemy1"] = enemy
    game_state.pitch.player_positions["enemy1"] = Position(x=6, y=7)
    
    tz_count = handler.get_tackle_zones(game_state, "team1", Position(x=5, y=7))
    assert tz_count == 0


def test_requires_dodge():
    """Test dodge requirement detection"""
    handler = MovementHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1")
    game_state.players["p1"] = player
    
    # Add enemy adjacent to starting position
    enemy = create_test_player("enemy1", "team2")
    game_state.players["enemy1"] = enemy
    game_state.pitch.player_positions["enemy1"] = Position(x=6, y=7)
    
    # Leaving tackle zone requires dodge
    needs_dodge = handler.requires_dodge(
        game_state, player,
        Position(x=5, y=7),  # From (adjacent to enemy)
        Position(x=5, y=6)    # To (moving away)
    )
    assert needs_dodge == True


def test_no_dodge_without_tackle_zones():
    """Test that dodge isn't needed without tackle zones"""
    handler = MovementHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1")
    game_state.players["p1"] = player
    
    # No enemies nearby
    needs_dodge = handler.requires_dodge(
        game_state, player,
        Position(x=5, y=7),
        Position(x=6, y=7)
    )
    assert needs_dodge == False


def test_can_move_to_valid_position():
    """Test basic movement validation"""
    handler = MovementHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1")
    game_state.players["p1"] = player
    
    can_move, error = handler.can_move_to(game_state, player, Position(x=6, y=7))
    assert can_move == True
    assert error is None


def test_cannot_move_to_occupied_square():
    """Test that occupied squares are blocked"""
    handler = MovementHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1")
    game_state.players["p1"] = player
    
    # Occupy target position
    game_state.pitch.player_positions["p2"] = Position(x=6, y=7)
    
    can_move, error = handler.can_move_to(game_state, player, Position(x=6, y=7))
    assert can_move == False
    assert "occupied" in error.lower()


def test_cannot_move_when_prone():
    """Test that prone players cannot move"""
    handler = MovementHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1")
    player.knock_down()
    game_state.players["p1"] = player
    
    can_move, error = handler.can_move_to(game_state, player, Position(x=6, y=7))
    assert can_move == False
    assert "standing" in error.lower()


def test_move_player_simple():
    """Test simple player movement"""
    handler = MovementHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1", ma=6)
    game_state.players["p1"] = player
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    
    # Move 2 squares
    path = [Position(x=6, y=7), Position(x=7, y=7)]
    success, dice_rolls, error = handler.move_player(game_state, "p1", path, allow_rush=False)
    
    assert success == True
    assert player.movement_used == 2
    assert game_state.pitch.player_positions["p1"] == Position(x=7, y=7)


def test_move_player_with_dodge():
    """Test movement requiring dodge"""
    handler = MovementHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1", ma=6)
    game_state.players["p1"] = player
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    
    # Add enemy creating tackle zone
    enemy = create_test_player("enemy1", "team2")
    game_state.players["enemy1"] = enemy
    game_state.pitch.player_positions["enemy1"] = Position(x=6, y=7)
    
    # Move away from enemy (requires dodge)
    path = [Position(x=5, y=6)]
    success, dice_rolls, error = handler.move_player(game_state, "p1", path, allow_rush=False)
    
    # Should have dodge roll
    assert len(dice_rolls) > 0
    assert dice_rolls[0].type == "dodge"


def test_stand_up_costs_movement():
    """Test that standing up costs 3 MA"""
    handler = MovementHandler(DiceRoller(seed=42))
    
    player = create_test_player("p1", "team1", ma=6)
    player.knock_down()
    
    success, error = handler.stand_up_player(player)
    assert success == True
    assert player.is_standing
    assert player.movement_remaining == 3  # 6 - 3


def test_cannot_stand_up_without_movement():
    """Test that insufficient MA prevents standing"""
    handler = MovementHandler(DiceRoller(seed=42))
    
    player = create_test_player("p1", "team1", ma=6)
    player.use_movement(4)  # Only 2 remaining
    player.knock_down()
    
    success, error = handler.stand_up_player(player)
    assert success == False
    assert "movement" in error.lower()


def test_rush_extends_movement():
    """Test that rushing allows extra squares"""
    handler = MovementHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1", ma=6)
    game_state.players["p1"] = player
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    
    # Move 7 squares (6 normal + 1 rush)
    path = [
        Position(x=6, y=7),
        Position(x=7, y=7),
        Position(x=8, y=7),
        Position(x=9, y=7),
        Position(x=10, y=7),
        Position(x=11, y=7),
        Position(x=12, y=7),  # Rush square
    ]
    
    success, dice_rolls, error = handler.move_player(game_state, "p1", path, allow_rush=True)
    
    # Should have rush roll
    rush_rolls = [r for r in dice_rolls if r.type == "rush"]
    assert len(rush_rolls) == 1


def test_cannot_rush_more_than_2_squares():
    """Test that rushing is limited to 2 squares"""
    handler = MovementHandler(DiceRoller(seed=42))
    game_state = create_test_game_state()
    
    player = create_test_player("p1", "team1", ma=6)
    game_state.players["p1"] = player
    game_state.pitch.player_positions["p1"] = Position(x=5, y=7)
    
    # Try to move 9 squares (6 + 3 rush - should fail)
    path = [
        Position(x=6, y=7),
        Position(x=7, y=7),
        Position(x=8, y=7),
        Position(x=9, y=7),
        Position(x=10, y=7),
        Position(x=11, y=7),
        Position(x=12, y=7),
        Position(x=13, y=7),
        Position(x=14, y=7),
    ]
    
    success, dice_rolls, error = handler.move_player(game_state, "p1", path, allow_rush=True)
    assert success == False
    assert "rush" in error.lower()
