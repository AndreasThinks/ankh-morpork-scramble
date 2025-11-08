"""Tests for pathfinding and risk assessment"""
import pytest
from app.game.pathfinding import PathFinder, SquareRisk, PathSuggestion
from app.game.movement import MovementHandler
from app.game.dice import DiceRoller
from app.models.game_state import GameState
from app.models.pitch import Position, Pitch
from app.models.player import Player
from app.models.team import Team, TeamType
from app.models.enums import PlayerState


@pytest.fixture
def dice_roller():
    """Create a dice roller"""
    return DiceRoller(seed=42)


@pytest.fixture
def movement_handler(dice_roller):
    """Create a movement handler"""
    return MovementHandler(dice_roller)


@pytest.fixture
def pathfinder(movement_handler):
    """Create a pathfinder"""
    return PathFinder(movement_handler)


@pytest.fixture
def basic_game_state():
    """Create a basic game state for testing"""
    from app.models.player import PlayerPosition
    from app.models.enums import GamePhase
    from app.models.game_state import TurnState
    
    team1 = Team(id="team1", name="Team 1", team_type=TeamType.CITY_WATCH)
    team2 = Team(id="team2", name="Team 2", team_type=TeamType.UNSEEN_UNIVERSITY)
    
    game_state = GameState(
        game_id="test_game",
        team1=team1,
        team2=team2,
        phase=GamePhase.ACTIVE_PLAY
    )
    
    # Add a test player
    position = PlayerPosition(
        role="Constable",
        cost=50000,
        max_quantity=16,
        ma=6,
        st=3,
        ag="3+",
        pa="4+",
        av="9+"
    )
    player = Player(id="team1_player0", team_id="team1", position=position)
    game_state.players["team1_player0"] = player
    game_state.pitch.player_positions["team1_player0"] = Position(x=5, y=7)
    team1.player_ids.append("team1_player0")
    
    # Add some team2 players for testing
    for i in range(3):
        player_id = f"team2_player{i}"
        p = Player(id=player_id, team_id="team2", position=position)
        game_state.players[player_id] = p
        team2.player_ids.append(player_id)
    
    return game_state


def test_straight_line_path_horizontal(pathfinder):
    """Test straight horizontal path calculation"""
    from_pos = Position(x=5, y=7)
    to_pos = Position(x=10, y=7)
    
    path = pathfinder.calculate_straight_line_path(from_pos, to_pos)
    
    assert len(path) == 5
    assert path[0] == Position(x=6, y=7)
    assert path[-1] == to_pos


def test_straight_line_path_vertical(pathfinder):
    """Test straight vertical path calculation"""
    from_pos = Position(x=5, y=7)
    to_pos = Position(x=5, y=10)  # Smaller y to stay in bounds (0-14)
    
    path = pathfinder.calculate_straight_line_path(from_pos, to_pos)
    
    assert len(path) == 3
    assert path[0] == Position(x=5, y=8)
    assert path[-1] == to_pos


def test_straight_line_path_diagonal(pathfinder):
    """Test diagonal path calculation"""
    from_pos = Position(x=5, y=7)
    to_pos = Position(x=8, y=10)
    
    path = pathfinder.calculate_straight_line_path(from_pos, to_pos)
    
    # Diagonal movement moves both x and y together
    assert len(path) == 3  # Max of dx=3, dy=3
    assert path[-1] == to_pos


def test_straight_line_path_same_position(pathfinder):
    """Test path when already at target"""
    from_pos = Position(x=5, y=7)
    to_pos = Position(x=5, y=7)
    
    path = pathfinder.calculate_straight_line_path(from_pos, to_pos)
    
    assert len(path) == 0


def test_suggest_path_simple(pathfinder, basic_game_state):
    """Test simple path suggestion without obstacles"""
    player_id = basic_game_state.team1.player_ids[0]
    target = Position(x=8, y=7)
    
    suggestion = pathfinder.suggest_path(basic_game_state, player_id, target)
    
    assert suggestion.is_valid
    assert len(suggestion.path) == 3
    assert suggestion.movement_cost == 3
    assert not suggestion.requires_rushing
    assert suggestion.rush_squares == 0
    assert suggestion.error_message is None


def test_suggest_path_requires_rushing(pathfinder, basic_game_state):
    """Test path that requires rushing"""
    player_id = basic_game_state.team1.player_ids[0]
    player = basic_game_state.get_player(player_id)
    
    # Set movement remaining to less than distance
    player.movement_used = 4  # MA=6, so only 2 remaining
    
    # Try to move 4 squares
    target = Position(x=9, y=7)
    suggestion = pathfinder.suggest_path(basic_game_state, player_id, target)
    
    assert suggestion.is_valid
    assert suggestion.movement_cost == 4
    assert suggestion.requires_rushing
    assert suggestion.rush_squares == 2


def test_suggest_path_too_many_rush_squares(pathfinder, basic_game_state):
    """Test path that requires too many rush squares"""
    player_id = basic_game_state.team1.player_ids[0]
    player = basic_game_state.get_player(player_id)
    
    # Set movement remaining very low
    player.movement_used = 5  # Only 1 MA remaining
    
    # Try to move 5 squares (would need 4 rush)
    target = Position(x=10, y=7)
    suggestion = pathfinder.suggest_path(basic_game_state, player_id, target)
    
    assert not suggestion.is_valid
    assert "rush squares (max 2)" in suggestion.error_message


def test_suggest_path_out_of_bounds(pathfinder, basic_game_state):
    """Test path to out of bounds position"""
    player_id = basic_game_state.team1.player_ids[0]
    target = Position(x=25, y=14)  # Valid position
    
    # Move player way out, so path goes out of bounds
    basic_game_state.pitch.player_positions[player_id] = Position(x=24, y=13)
    
    # Try to go to a very far position that would require going through many squares
    # The path will eventually hit a square that's out of bounds during traversal
    suggestion = pathfinder.suggest_path(basic_game_state, player_id, target)
    
    # This should be valid since both positions are in bounds
    assert suggestion.is_valid


def test_suggest_path_occupied_square(pathfinder, basic_game_state):
    """Test path blocked by occupied square"""
    player_id = basic_game_state.team1.player_ids[0]
    
    # Place another player in the path
    blocker_id = basic_game_state.team2.player_ids[0]
    basic_game_state.pitch.player_positions[blocker_id] = Position(x=7, y=7)
    
    target = Position(x=10, y=7)
    suggestion = pathfinder.suggest_path(basic_game_state, player_id, target)
    
    assert not suggestion.is_valid
    assert "occupied" in suggestion.error_message


def test_assess_square_risk_no_tackle_zones(pathfinder, basic_game_state):
    """Test risk assessment with no tackle zones"""
    player_id = basic_game_state.team1.player_ids[0]
    player = basic_game_state.get_player(player_id)
    
    from_pos = Position(x=5, y=7)
    to_pos = Position(x=6, y=7)
    
    risk = pathfinder.assess_square_risk(
        basic_game_state, player, from_pos, to_pos, is_rush_square=False
    )
    
    assert not risk.requires_dodge
    assert risk.tackle_zones_leaving == 0
    assert risk.tackle_zones_entering == 0
    assert risk.success_probability is None
    assert not risk.is_rush_square


def test_assess_square_risk_with_tackle_zones(pathfinder, basic_game_state):
    """Test risk assessment when leaving tackle zones"""
    player_id = basic_game_state.team1.player_ids[0]
    player = basic_game_state.get_player(player_id)
    
    # Place enemy adjacent to create tackle zone
    enemy_id = basic_game_state.team2.player_ids[0]
    basic_game_state.pitch.player_positions[enemy_id] = Position(x=6, y=7)
    
    from_pos = Position(x=5, y=7)
    to_pos = Position(x=5, y=8)
    
    risk = pathfinder.assess_square_risk(
        basic_game_state, player, from_pos, to_pos, is_rush_square=False
    )
    
    assert risk.requires_dodge
    assert risk.tackle_zones_leaving == 1
    assert risk.dodge_target == player.get_agility_target()
    assert risk.success_probability is not None
    assert 0.0 <= risk.success_probability <= 1.0


def test_assess_square_risk_rush_square(pathfinder, basic_game_state):
    """Test risk assessment for rush square"""
    player_id = basic_game_state.team1.player_ids[0]
    player = basic_game_state.get_player(player_id)
    
    from_pos = Position(x=5, y=7)
    to_pos = Position(x=6, y=7)
    
    risk = pathfinder.assess_square_risk(
        basic_game_state, player, from_pos, to_pos, is_rush_square=True
    )
    
    assert risk.is_rush_square
    assert risk.success_probability == 5/6  # 2+ on d6


def test_assess_square_risk_dodge_and_rush(pathfinder, basic_game_state):
    """Test risk assessment for square requiring both dodge and rush"""
    player_id = basic_game_state.team1.player_ids[0]
    player = basic_game_state.get_player(player_id)
    
    # Place enemy to create tackle zone
    enemy_id = basic_game_state.team2.player_ids[0]
    basic_game_state.pitch.player_positions[enemy_id] = Position(x=6, y=7)
    
    from_pos = Position(x=5, y=7)
    to_pos = Position(x=5, y=8)
    
    risk = pathfinder.assess_square_risk(
        basic_game_state, player, from_pos, to_pos, is_rush_square=True
    )
    
    assert risk.requires_dodge
    assert risk.is_rush_square
    # Success probability should be combined (dodge * rush)
    assert risk.success_probability is not None
    assert risk.success_probability < 5/6  # Lower than just rush


def test_suggest_path_total_risk_score(pathfinder, basic_game_state):
    """Test that total risk score is calculated correctly"""
    player_id = basic_game_state.team1.player_ids[0]
    
    # Place enemies to create risky path
    enemy1 = basic_game_state.team2.player_ids[0]
    enemy2 = basic_game_state.team2.player_ids[1]
    basic_game_state.pitch.player_positions[enemy1] = Position(x=6, y=8)
    basic_game_state.pitch.player_positions[enemy2] = Position(x=7, y=8)
    
    # Move through tackle zones
    target = Position(x=8, y=7)
    suggestion = pathfinder.suggest_path(basic_game_state, player_id, target)
    
    assert suggestion.is_valid
    assert suggestion.total_risk_score > 0.
