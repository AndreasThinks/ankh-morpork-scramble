"""Tests for data models"""
import pytest
from app.models.pitch import Position, Pitch
from app.models.player import Player, PlayerPosition
from app.models.team import Team, TEAM_ROSTERS
from app.models.enums import PlayerState, TeamType, SkillType


def test_position_equality():
    """Test position equality and hashing"""
    pos1 = Position(x=5, y=7)
    pos2 = Position(x=5, y=7)
    pos3 = Position(x=6, y=7)
    
    assert pos1 == pos2
    assert pos1 != pos3
    assert hash(pos1) == hash(pos2)


def test_position_distance():
    """Test Manhattan distance calculation"""
    pos1 = Position(x=5, y=7)
    pos2 = Position(x=8, y=10)
    
    assert pos1.distance_to(pos2) == 6  # |8-5| + |10-7| = 3 + 3


def test_position_adjacent():
    """Test adjacency detection"""
    center = Position(x=5, y=7)
    
    # Adjacent positions
    assert center.is_adjacent(Position(x=5, y=8))  # North
    assert center.is_adjacent(Position(x=6, y=7))  # East
    assert center.is_adjacent(Position(x=6, y=8))  # NE diagonal
    
    # Not adjacent
    assert not center.is_adjacent(Position(x=5, y=7))  # Same position
    assert not center.is_adjacent(Position(x=7, y=7))  # 2 away
    assert not center.is_adjacent(Position(x=5, y=9))  # 2 away


def test_pitch_player_placement():
    """Test placing players on pitch"""
    pitch = Pitch()
    pos = Position(x=5, y=7)
    
    pitch.player_positions["player1"] = pos
    
    assert pitch.get_player_at(pos) == "player1"
    assert pitch.is_occupied(pos)
    assert not pitch.is_occupied(Position(x=6, y=7))


def test_pitch_move_player():
    """Test moving players"""
    pitch = Pitch()
    pitch.player_positions["player1"] = Position(x=5, y=7)
    
    new_pos = Position(x=6, y=7)
    pitch.move_player("player1", new_pos)
    
    assert pitch.player_positions["player1"] == new_pos
    assert not pitch.is_occupied(Position(x=5, y=7))
    assert pitch.is_occupied(new_pos)


def test_pitch_ball_handling():
    """Test ball pickup and drop"""
    pitch = Pitch()
    pitch.player_positions["player1"] = Position(x=5, y=7)
    pitch.place_ball(Position(x=5, y=7))
    
    # Pick up ball
    pitch.pick_up_ball("player1")
    assert pitch.ball_carrier == "player1"
    assert pitch.ball_position == Position(x=5, y=7)
    
    # Drop ball
    pitch.drop_ball()
    assert pitch.ball_carrier is None
    assert pitch.ball_position == Position(x=5, y=7)


def test_player_movement_tracking():
    """Test player movement tracking"""
    position = PlayerPosition(
        role="Test",
        cost=50000,
        ma=6,
        st=3,
        ag="3+",
        pa="4+",
        av="9+"
    )
    
    player = Player(id="p1", team_id="t1", position=position)
    
    assert player.movement_remaining == 6
    
    player.use_movement(3)
    assert player.movement_used == 3
    assert player.movement_remaining == 3
    
    player.reset_turn()
    assert player.movement_used == 0
    assert player.movement_remaining == 6


def test_player_state_transitions():
    """Test player state changes"""
    position = PlayerPosition(
        role="Test",
        cost=50000,
        ma=6,
        st=3,
        ag="3+",
        pa="4+",
        av="9+"
    )
    
    player = Player(id="p1", team_id="t1", position=position)
    
    assert player.is_standing
    assert player.is_active
    
    player.knock_down()
    assert player.state == PlayerState.PRONE
    assert not player.is_standing
    assert player.is_active
    
    player.stun()
    assert player.state == PlayerState.STUNNED
    assert not player.is_active


def test_team_rerolls():
    """Test team re-roll management"""
    team = Team(
        id="team1",
        name="Test Team",
        team_type=TeamType.CITY_WATCH,
        rerolls_total=3
    )
    
    assert team.rerolls_remaining == 3
    
    team.use_reroll()
    assert team.rerolls_remaining == 2
    
    team.reset_rerolls()
    assert team.rerolls_remaining == 3


def test_team_rosters_defined():
    """Test that team rosters are properly defined"""
    assert TeamType.CITY_WATCH in TEAM_ROSTERS
    assert TeamType.UNSEEN_UNIVERSITY in TEAM_ROSTERS
    
    city_watch = TEAM_ROSTERS[TeamType.CITY_WATCH]
    assert "constable" in city_watch.positions
    assert "clerk_runner" in city_watch.positions
    
    wizards = TEAM_ROSTERS[TeamType.UNSEEN_UNIVERSITY]
    assert "apprentice_wizard" in wizards.positions
    assert "senior_wizard" in wizards.positions
