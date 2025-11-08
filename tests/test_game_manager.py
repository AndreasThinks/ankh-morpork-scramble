"""Tests for game manager"""
import pytest
from app.state.game_manager import GameManager
from app.models.enums import TeamType, GamePhase
from app.models.pitch import Position


def test_create_and_get_game():
    """Test game creation and retrieval"""
    manager = GameManager()
    
    # Create game
    game = manager.create_game("test_game_1")
    
    assert game.game_id == "test_game_1"
    assert game.phase == GamePhase.DEPLOYMENT
    assert game.team1 is not None
    assert game.team2 is not None
    
    # Retrieve game
    retrieved = manager.get_game("test_game_1")
    assert retrieved is not None
    assert retrieved.game_id == "test_game_1"
    
    # Non-existent game
    missing = manager.get_game("nonexistent")
    assert missing is None


def test_create_game_with_auto_id():
    """Test game creation with automatic ID generation"""
    manager = GameManager()
    
    game = manager.create_game()
    
    assert game.game_id is not None
    assert len(game.game_id) > 0
    assert game.phase == GamePhase.DEPLOYMENT


def test_setup_team_with_players():
    """Test setting up a team with players"""
    manager = GameManager()
    game = manager.create_game("test_game")
    
    # Setup team with players
    player_positions = {
        "constable": "3",  # 3 constables
        "clerk_runner": "1"  # 1 clerk-runner
    }
    
    updated_game = manager.setup_team(
        "test_game",
        "team1",
        TeamType.CITY_WATCH,
        player_positions
    )
    
    assert updated_game.team1.team_type == TeamType.CITY_WATCH
    assert len(updated_game.team1.player_ids) == 4  # 3 + 1
    assert len(updated_game.players) == 4


def test_place_players_on_pitch():
    """Test placing players on the pitch during setup"""
    manager = GameManager()
    game = manager.create_game("test_game")
    
    # Setup team first
    manager.setup_team(
        "test_game",
        "team1",
        TeamType.CITY_WATCH,
        {"constable": "2"}
    )
    
    # Get player IDs
    player_ids = game.team1.player_ids
    
    # Place players
    positions = {
        player_ids[0]: Position(x=5, y=7),
        player_ids[1]: Position(x=6, y=7)
    }
    
    updated_game = manager.place_players("test_game", "team1", positions)
    
    assert updated_game.pitch.player_positions[player_ids[0]] == Position(x=5, y=7)
    assert updated_game.pitch.player_positions[player_ids[1]] == Position(x=6, y=7)


def test_start_game_transitions_phase():
    """Test that starting game transitions to playing phase"""
    manager = GameManager()
    game = manager.create_game("test_game")
    
    assert game.phase == GamePhase.DEPLOYMENT
    
    # Mark teams as joined
    game.team1_joined = True
    game.team2_joined = True
    
    # Start game
    updated_game = manager.start_game("test_game")
    
    assert updated_game.phase == GamePhase.OPENING_SCRAMBLE  # Correct phase after start
    assert updated_game.turn is not None
    assert updated_game.turn.half == 1
    assert updated_game.turn.team_turn == 0


def test_start_game_places_ball():
    """Test that starting game places ball at center"""
    manager = GameManager()
    game = manager.create_game("test_game")
    
    # Mark teams as joined
    game.team1_joined = True
    game.team2_joined = True
    
    # Start game
    updated_game = manager.start_game("test_game")
    
    # Ball should be at center
    assert updated_game.pitch.ball_position == Position(x=13, y=7)


def test_cannot_start_game_twice():
    """Test cannot start game that's already started"""
    manager = GameManager()
    game = manager.create_game("test_game")
    
    # Mark teams as joined
    game.team1_joined = True
    game.team2_joined = True
    
    # Start once
    manager.start_game("test_game")
    
    # Try to start again (phase is no longer SETUP)
    with pytest.raises(ValueError, match="setup phase"):
        manager.start_game("test_game")


def test_end_turn_switches_teams():
    """Test ending turn switches active team"""
    manager = GameManager()
    game = manager.create_game("test_game")
    
    # Mark teams as joined
    game.team1_joined = True
    game.team2_joined = True
    
    manager.start_game("test_game")
    
    # Initial state
    initial_team = game.get_active_team().id
    initial_turn = game.turn.team_turn
    
    # End turn
    updated_game = manager.end_turn("test_game")
    
    # Should switch teams
    new_team = updated_game.get_active_team().id
    assert new_team != initial_team
    # Turn counter only increments when returning to team1
    assert updated_game.turn.team_turn == initial_turn


def test_check_scoring_team1_endzone():
    """Test scoring detection for team 1 in their endzone"""
    manager = GameManager()
    game = manager.create_game("test_game")
    
    # Setup team 1 with a player
    manager.setup_team("test_game", "team1", TeamType.CITY_WATCH, {"constable": "1"})
    
    # Mark teams as joined
    game.team1_joined = True
    game.team2_joined = True
    
    manager.start_game("test_game")
    
    # Get player and place in team1's endzone (x >= 23)
    player_id = game.team1.player_ids[0]
    game.pitch.player_positions[player_id] = Position(x=24, y=7)
    game.pitch.ball_carrier = player_id
    
    # Check scoring
    scored_team = manager.check_scoring("test_game")
    
    assert scored_team == "team1"
    assert game.team1.score == 1


def test_check_scoring_team2_endzone():
    """Test scoring detection for team 2 in their endzone"""
    manager = GameManager()
    game = manager.create_game("test_game")
    
    # Setup team 2 with a player
    manager.setup_team("test_game", "team2", TeamType.UNSEEN_UNIVERSITY, {"apprentice_wizard": "1"})
    
    # Mark teams as joined
    game.team1_joined = True
    game.team2_joined = True
    
    manager.start_game("test_game")
    
    # Get player and place in team2's endzone (x <= 2)
    player_id = game.team2.player_ids[0]
    game.pitch.player_positions[player_id] = Position(x=1, y=7)
    game.pitch.ball_carrier = player_id
    
    # Check scoring
    scored_team = manager.check_scoring("test_game")
    
    assert scored_team == "team2"
    assert game.team2.score == 1


def test_scoring_resets_ball_position():
    """Test that scoring resets ball to center"""
    manager = GameManager()
    game = manager.create_game("test_game")
    
    # Setup and start
    manager.setup_team("test_game", "team1", TeamType.CITY_WATCH, {"constable": "1"})
    
    # Mark teams as joined
    game.team1_joined = True
    game.team2_joined = True
    
    manager.start_game("test_game")
    
    # Score
    player_id = game.team1.player_ids[0]
    game.pitch.player_positions[player_id] = Position(x=24, y=7)
    game.pitch.ball_carrier = player_id
    
    manager.check_scoring("test_game")
    
    # Ball should reset to center
    assert game.pitch.ball_carrier is None
    assert game.pitch.ball_position == Position(x=13, y=7)


def test_no_scoring_in_wrong_endzone():
    """Test no scoring when in wrong endzone"""
    manager = GameManager()
    game = manager.create_game("test_game")
    
    # Setup
    manager.setup_team("test_game", "team1", TeamType.CITY_WATCH, {"constable": "1"})
    
    # Mark teams as joined
    game.team1_joined = True
    game.team2_joined = True
    
    manager.start_game("test_game")
    
    # Team 1 player in team 2's endzone (should not score)
    player_id = game.team1.player_ids[0]
    game.pitch.player_positions[player_id] = Position(x=1, y=7)
    game.pitch.ball_carrier = player_id
    
    scored_team = manager.check_scoring("test_game")
    
    assert scored_team is None
    assert game.team1.score == 0
