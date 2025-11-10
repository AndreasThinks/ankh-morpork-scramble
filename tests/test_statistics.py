"""Tests for statistics aggregation."""
import pytest
from datetime import datetime
from app.game.statistics import StatisticsAggregator
from app.models.game_state import GameState
from app.models.team import Team
from app.models.player import Player, PlayerPosition
from app.models.enums import TeamType, PlayerState, GamePhase
from app.models.events import GameEvent, EventType, EventResult, DiceRoll
from app.models.pitch import Position


@pytest.fixture
def basic_game_state():
    """Create a basic game state for testing."""
    game = GameState(
        game_id="test_game",
        phase=GamePhase.PLAYING,
        team1=Team(
            id="team1",
            name="Team 1",
            team_type=TeamType.CITY_WATCH,
        ),
        team2=Team(
            id="team2",
            name="Team 2",
            team_type=TeamType.UNSEEN_UNIVERSITY,
        ),
    )

    # Add players
    pos = PlayerPosition(
        role="Constable",
        cost=50000,
        max_quantity=16,
        ma=6,
        st=3,
        ag="3+",
        pa="4+",
        av="9+",
    )

    game.players["player1"] = Player(
        id="player1",
        team_id="team1",
        position=pos,
        number=1,
        state=PlayerState.STANDING,
    )

    game.players["player2"] = Player(
        id="player2",
        team_id="team2",
        position=pos,
        number=2,
        state=PlayerState.STANDING,
    )

    return game


def test_statistics_aggregator_initialization(basic_game_state):
    """Test that aggregator initializes correctly."""
    aggregator = StatisticsAggregator(basic_game_state)
    assert aggregator.game_state == basic_game_state


def test_aggregate_empty_events(basic_game_state):
    """Test aggregating with no events."""
    aggregator = StatisticsAggregator(basic_game_state)
    stats = aggregator.aggregate([])

    assert stats.game_id == "test_game"
    assert "team1" in stats.team_stats
    assert "team2" in stats.team_stats
    assert "player1" in stats.player_stats
    assert "player2" in stats.player_stats
    assert stats.total_dice_rolls == 0


def test_aggregate_move_event(basic_game_state):
    """Test aggregating move events."""
    event = GameEvent(
        event_id="e1",
        timestamp=datetime.now(),
        game_id="test_game",
        half=1,
        turn_number=1,
        active_team_id="team1",
        event_type=EventType.MOVE,
        result=EventResult.SUCCESS,
        player_id="player1",
        from_position=Position(x=5, y=5),
        to_position=Position(x=6, y=5),
        description="Player moved",
    )

    aggregator = StatisticsAggregator(basic_game_state)
    stats = aggregator.aggregate([event])

    assert stats.player_stats["player1"].moves == 1
    assert stats.player_stats["player2"].moves == 0


def test_aggregate_dodge_success(basic_game_state):
    """Test aggregating successful dodge events."""
    event = GameEvent(
        event_id="e1",
        timestamp=datetime.now(),
        game_id="test_game",
        half=1,
        turn_number=1,
        active_team_id="team1",
        event_type=EventType.DODGE,
        result=EventResult.SUCCESS,
        player_id="player1",
        description="Player dodged",
    )

    aggregator = StatisticsAggregator(basic_game_state)
    stats = aggregator.aggregate([event])

    player_stats = stats.player_stats["player1"]
    assert player_stats.dodges_attempted == 1
    assert player_stats.dodges_succeeded == 1
    assert stats.team_stats["team1"].failed_dodges == 0


def test_aggregate_pickup_event(basic_game_state):
    """Test aggregating pickup events."""
    event = GameEvent(
        event_id="e1",
        timestamp=datetime.now(),
        game_id="test_game",
        half=1,
        turn_number=1,
        active_team_id="team1",
        event_type=EventType.PICKUP,
        result=EventResult.SUCCESS,
        player_id="player1",
        description="Player picked up ball",
    )

    aggregator = StatisticsAggregator(basic_game_state)
    stats = aggregator.aggregate([event])

    player_stats = stats.player_stats["player1"]
    assert player_stats.pickups_attempted == 1
    assert player_stats.pickups_succeeded == 1

    team_stats = stats.team_stats["team1"]
    assert team_stats.pickups_attempted == 1
    assert team_stats.pickups_succeeded == 1


def test_aggregate_block_event(basic_game_state):
    """Test aggregating block events."""
    event = GameEvent(
        event_id="e1",
        timestamp=datetime.now(),
        game_id="test_game",
        half=1,
        turn_number=1,
        active_team_id="team1",
        event_type=EventType.BLOCK,
        result=EventResult.SUCCESS,
        player_id="player1",
        target_player_id="player2",
        description="Player blocked opponent",
    )

    aggregator = StatisticsAggregator(basic_game_state)
    stats = aggregator.aggregate([event])

    player_stats = stats.player_stats["player1"]
    assert player_stats.blocks_thrown == 1

    team_stats = stats.team_stats["team1"]
    assert team_stats.blocks_thrown == 1


def test_aggregate_touchdown_event(basic_game_state):
    """Test aggregating touchdown events."""
    event = GameEvent(
        event_id="e1",
        timestamp=datetime.now(),
        game_id="test_game",
        half=1,
        turn_number=1,
        active_team_id="team1",
        event_type=EventType.TOUCHDOWN,
        result=EventResult.SUCCESS,
        player_id="player1",
        description="Touchdown!",
        details={"team_id": "team1"},
    )

    aggregator = StatisticsAggregator(basic_game_state)
    stats = aggregator.aggregate([event])

    player_stats = stats.player_stats["player1"]
    assert player_stats.touchdowns == 1

    team_stats = stats.team_stats["team1"]
    assert team_stats.touchdowns == 1


def test_aggregate_turnover_event(basic_game_state):
    """Test aggregating turnover events."""
    event = GameEvent(
        event_id="e1",
        timestamp=datetime.now(),
        game_id="test_game",
        half=1,
        turn_number=1,
        active_team_id="team1",
        event_type=EventType.TURNOVER,
        result=EventResult.NEUTRAL,
        description="Turnover!",
        details={"reason": "failed_dodge"},
    )

    aggregator = StatisticsAggregator(basic_game_state)
    stats = aggregator.aggregate([event])

    team_stats = stats.team_stats["team1"]
    assert team_stats.turnovers == 1
    assert stats.turnovers_by_reason["failed_dodge"] == 1


def test_aggregate_dice_rolls(basic_game_state):
    """Test aggregating dice rolls from events."""
    event = GameEvent(
        event_id="e1",
        timestamp=datetime.now(),
        game_id="test_game",
        half=1,
        turn_number=1,
        active_team_id="team1",
        event_type=EventType.DODGE,
        result=EventResult.SUCCESS,
        player_id="player1",
        description="Player dodged with dice rolls",
        dice_rolls=[
            DiceRoll(type="agility", result=4, target=3, success=True),
            DiceRoll(type="agility", result=2, target=3, success=False),
        ],
    )

    aggregator = StatisticsAggregator(basic_game_state)
    stats = aggregator.aggregate([event])

    assert stats.total_dice_rolls == 2
    assert stats.dice_by_type["agility"] == 2
    assert stats.success_by_type["agility"] == 1


def test_get_dice_summary(basic_game_state):
    """Test getting dice roll summary."""
    events = [
        GameEvent(
            event_id="e1",
            timestamp=datetime.now(),
            game_id="test_game",
            half=1,
            turn_number=1,
            active_team_id="team1",
            event_type=EventType.DODGE,
            result=EventResult.SUCCESS,
            player_id="player1",
            description="Dodge with rolls",
            dice_rolls=[
                DiceRoll(type="agility", result=4, target=3, success=True),
                DiceRoll(type="agility", result=2, target=3, success=False),
                DiceRoll(type="agility", result=5, target=3, success=True),
            ],
        ),
    ]

    aggregator = StatisticsAggregator(basic_game_state)
    summary = aggregator.get_dice_summary(events)

    assert "agility" in summary
    assert summary["agility"]["total"] == 3
    assert summary["agility"]["success"] == 2
    assert summary["agility"]["failure"] == 1
    assert summary["agility"]["success_rate"] == pytest.approx(66.67, rel=0.1)
