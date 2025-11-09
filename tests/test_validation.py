"""Tests for enhanced validation functionality"""
import pytest
from pydantic import ValidationError

from app.models.pitch import Position
from app.models.actions import ActionRequest
from app.models.enums import ActionType, TeamType
from app.models.game_state import GameState
from app.models.team import Team
from app.models.player import Player, PlayerPosition
from app.validation import GameStateValidator
from app.state.game_manager import GameManager


class TestPositionValidation:
    """Test Position model validation"""

    def test_valid_position(self):
        """Valid positions should be accepted"""
        pos = Position(x=0, y=0)
        assert pos.x == 0
        assert pos.y == 0

        pos = Position(x=25, y=14)
        assert pos.x == 25
        assert pos.y == 14

        pos = Position(x=12, y=7)
        assert pos.x == 12
        assert pos.y == 7

    def test_invalid_x_coordinate_negative(self):
        """Negative x coordinates should be rejected"""
        with pytest.raises(ValidationError) as exc_info:
            Position(x=-1, y=7)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_invalid_x_coordinate_too_large(self):
        """x coordinates > 25 should be rejected"""
        with pytest.raises(ValidationError) as exc_info:
            Position(x=26, y=7)
        assert "less than 26" in str(exc_info.value)

    def test_invalid_y_coordinate_negative(self):
        """Negative y coordinates should be rejected"""
        with pytest.raises(ValidationError) as exc_info:
            Position(x=12, y=-1)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_invalid_y_coordinate_too_large(self):
        """y coordinates > 14 should be rejected"""
        with pytest.raises(ValidationError) as exc_info:
            Position(x=12, y=15)
        assert "less than 15" in str(exc_info.value)


class TestActionRequestValidation:
    """Test ActionRequest model validation"""

    def test_move_requires_target_position(self):
        """MOVE action without target_position should be rejected"""
        with pytest.raises(ValidationError) as exc_info:
            ActionRequest(
                action_type=ActionType.MOVE,
                player_id="player1"
                # Missing target_position
            )
        assert "MOVE action requires target_position" in str(exc_info.value)

    def test_move_with_target_position_valid(self):
        """MOVE action with target_position should be accepted"""
        action = ActionRequest(
            action_type=ActionType.MOVE,
            player_id="player1",
            target_position=Position(x=5, y=5)
        )
        assert action.action_type == ActionType.MOVE
        assert action.target_position.x == 5

    def test_scuffle_requires_target_player_id(self):
        """SCUFFLE action without target_player_id should be rejected"""
        with pytest.raises(ValidationError) as exc_info:
            ActionRequest(
                action_type=ActionType.SCUFFLE,
                player_id="player1"
                # Missing target_player_id
            )
        assert "SCUFFLE action requires target_player_id" in str(exc_info.value)

    def test_scuffle_with_target_player_valid(self):
        """SCUFFLE action with target_player_id should be accepted"""
        action = ActionRequest(
            action_type=ActionType.SCUFFLE,
            player_id="player1",
            target_player_id="opponent1"
        )
        assert action.action_type == ActionType.SCUFFLE
        assert action.target_player_id == "opponent1"

    def test_charge_requires_target_player_id(self):
        """CHARGE action without target_player_id should be rejected"""
        with pytest.raises(ValidationError) as exc_info:
            ActionRequest(
                action_type=ActionType.CHARGE,
                player_id="player1"
            )
        assert "CHARGE action requires target_player_id" in str(exc_info.value)

    def test_hurl_requires_target(self):
        """HURL action without target_receiver_id or target_position should be rejected"""
        with pytest.raises(ValidationError) as exc_info:
            ActionRequest(
                action_type=ActionType.HURL,
                player_id="player1"
            )
        assert "HURL action requires" in str(exc_info.value)

    def test_hurl_with_receiver_valid(self):
        """HURL action with target_receiver_id should be accepted"""
        action = ActionRequest(
            action_type=ActionType.HURL,
            player_id="player1",
            target_receiver_id="player2"
        )
        assert action.action_type == ActionType.HURL
        assert action.target_receiver_id == "player2"

    def test_hurl_with_position_valid(self):
        """HURL action with target_position should be accepted"""
        action = ActionRequest(
            action_type=ActionType.HURL,
            player_id="player1",
            target_position=Position(x=10, y=10)
        )
        assert action.action_type == ActionType.HURL
        assert action.target_position.x == 10

    def test_quick_pass_requires_target_receiver(self):
        """QUICK_PASS action without target_receiver_id should be rejected"""
        with pytest.raises(ValidationError) as exc_info:
            ActionRequest(
                action_type=ActionType.QUICK_PASS,
                player_id="player1"
            )
        assert "QUICK_PASS action requires target_receiver_id" in str(exc_info.value)

    def test_boot_requires_target_player_id(self):
        """BOOT action without target_player_id should be rejected"""
        with pytest.raises(ValidationError) as exc_info:
            ActionRequest(
                action_type=ActionType.BOOT,
                player_id="player1"
            )
        assert "BOOT action requires target_player_id" in str(exc_info.value)

    def test_stand_up_no_extra_params_needed(self):
        """STAND_UP action should not require additional parameters"""
        action = ActionRequest(
            action_type=ActionType.STAND_UP,
            player_id="player1"
        )
        assert action.action_type == ActionType.STAND_UP


class TestGameStateValidator:
    """Test GameStateValidator utility methods"""

    @pytest.fixture
    def simple_game_state(self):
        """Create a simple game state for testing"""
        manager = GameManager()
        game_state = manager.create_game("test-game")

        # Set up team1
        manager.setup_team(
            "test-game",
            "team1",
            TeamType.CITY_WATCH,
            {"constable": "3"}
        )

        # Set up team2
        manager.setup_team(
            "test-game",
            "team2",
            TeamType.UNSEEN_UNIVERSITY,
            {"apprentice_wizard": "3"}
        )

        # Place players
        team1_positions = {
            "team1_player_0": Position(x=5, y=7),
            "team1_player_1": Position(x=6, y=7),
            "team1_player_2": Position(x=7, y=7),
        }
        manager.place_players("test-game", "team1", team1_positions)

        team2_positions = {
            "team2_player_0": Position(x=20, y=7),
            "team2_player_1": Position(x=19, y=7),
            "team2_player_2": Position(x=18, y=7),
        }
        manager.place_players("test-game", "team2", team2_positions)

        # Mark teams as joined (required before starting)
        game_state = manager.get_game("test-game")
        game_state.team1_joined = True
        game_state.team2_joined = True

        # Start the game
        manager.start_game("test-game")

        return manager.get_game("test-game")

    def test_validate_player_exists_success(self, simple_game_state):
        """Should validate that an existing player exists"""
        is_valid, error = GameStateValidator.validate_player_exists(
            simple_game_state, "team1_player_0"
        )
        assert is_valid is True
        assert error is None

    def test_validate_player_exists_failure(self, simple_game_state):
        """Should reject non-existent player"""
        is_valid, error = GameStateValidator.validate_player_exists(
            simple_game_state, "nonexistent_player"
        )
        assert is_valid is False
        assert "not found" in error

    def test_validate_player_can_act_success(self, simple_game_state):
        """Should validate that active team player can act"""
        active_team = simple_game_state.get_active_team()
        player_id = active_team.player_ids[0]

        is_valid, error = GameStateValidator.validate_player_can_act(
            simple_game_state, player_id
        )
        assert is_valid is True
        assert error is None

    def test_validate_player_can_act_wrong_team(self, simple_game_state):
        """Should reject player from inactive team"""
        inactive_team = simple_game_state.get_inactive_team()
        player_id = inactive_team.player_ids[0]

        is_valid, error = GameStateValidator.validate_player_can_act(
            simple_game_state, player_id
        )
        assert is_valid is False
        assert "turn" in error.lower()

    def test_validate_player_can_act_prone_player(self, simple_game_state):
        """Should reject prone player"""
        active_team = simple_game_state.get_active_team()
        player_id = active_team.player_ids[0]
        player = simple_game_state.get_player(player_id)

        # Knock the player down
        player.knock_down()

        # Note: is_standing checks for PlayerState.STANDING
        # A prone player should fail validation
        is_valid, error = GameStateValidator.validate_player_can_act(
            simple_game_state, player_id
        )
        assert is_valid is False
        # Error should mention the player state
        assert player.state.value in error.lower()

    def test_validate_position_on_pitch_success(self):
        """Should validate positions within bounds"""
        is_valid, error = GameStateValidator.validate_position_on_pitch(
            Position(x=0, y=0)
        )
        assert is_valid is True
        assert error is None

        is_valid, error = GameStateValidator.validate_position_on_pitch(
            Position(x=25, y=14)
        )
        assert is_valid is True
        assert error is None

    def test_validate_position_unoccupied_success(self, simple_game_state):
        """Should validate unoccupied position"""
        is_valid, error = GameStateValidator.validate_position_unoccupied(
            simple_game_state, Position(x=10, y=10)
        )
        assert is_valid is True
        assert error is None

    def test_validate_position_unoccupied_failure(self, simple_game_state):
        """Should reject occupied position"""
        is_valid, error = GameStateValidator.validate_position_unoccupied(
            simple_game_state, Position(x=5, y=7)  # team1_player_0 position
        )
        assert is_valid is False
        assert "occupied" in error.lower()

    def test_validate_players_adjacent_success(self, simple_game_state):
        """Should validate adjacent players"""
        is_valid, error = GameStateValidator.validate_players_adjacent(
            simple_game_state, "team1_player_0", "team1_player_1"
        )
        assert is_valid is True
        assert error is None

    def test_validate_players_adjacent_failure(self, simple_game_state):
        """Should reject non-adjacent players"""
        is_valid, error = GameStateValidator.validate_players_adjacent(
            simple_game_state, "team1_player_0", "team2_player_0"
        )
        assert is_valid is False
        assert "not adjacent" in error.lower()

    def test_validate_move_action_success(self, simple_game_state):
        """Should validate valid MOVE action"""
        active_team = simple_game_state.get_active_team()
        player_id = active_team.player_ids[0]

        action = ActionRequest(
            action_type=ActionType.MOVE,
            player_id=player_id,
            target_position=Position(x=5, y=8)
        )

        is_valid, error = GameStateValidator.validate_move_action(
            simple_game_state, action
        )
        assert is_valid is True
        assert error is None

    def test_validate_move_action_no_movement(self, simple_game_state):
        """Should reject move when player has no movement remaining"""
        active_team = simple_game_state.get_active_team()
        player_id = active_team.player_ids[0]
        player = simple_game_state.get_player(player_id)

        # Exhaust movement by setting movement_used to position's MA
        player.movement_used = player.position.ma

        action = ActionRequest(
            action_type=ActionType.MOVE,
            player_id=player_id,
            target_position=Position(x=5, y=8)
        )

        is_valid, error = GameStateValidator.validate_move_action(
            simple_game_state, action
        )
        assert is_valid is False
        assert "no movement remaining" in error.lower()

    def test_validate_move_action_occupied_target(self, simple_game_state):
        """Should reject move to occupied position"""
        active_team = simple_game_state.get_active_team()
        player_id = active_team.player_ids[0]

        action = ActionRequest(
            action_type=ActionType.MOVE,
            player_id=player_id,
            target_position=Position(x=6, y=7)  # team1_player_1 position
        )

        is_valid, error = GameStateValidator.validate_move_action(
            simple_game_state, action
        )
        assert is_valid is False
        assert "occupied" in error.lower()

    def test_validate_block_action_success(self, simple_game_state):
        """Should validate valid SCUFFLE action"""
        # Move team2 player adjacent to team1 player for testing
        simple_game_state.pitch.player_positions["team2_player_0"] = Position(x=6, y=8)
        simple_game_state.pitch.player_positions["team1_player_1"] = Position(x=6, y=7)

        action = ActionRequest(
            action_type=ActionType.SCUFFLE,
            player_id="team1_player_1",
            target_player_id="team2_player_0"
        )

        is_valid, error = GameStateValidator.validate_block_action(
            simple_game_state, action
        )
        assert is_valid is True
        assert error is None

    def test_validate_block_action_not_adjacent(self, simple_game_state):
        """Should reject scuffle when players not adjacent"""
        active_team = simple_game_state.get_active_team()
        player_id = active_team.player_ids[0]

        action = ActionRequest(
            action_type=ActionType.SCUFFLE,
            player_id=player_id,
            target_player_id="team2_player_0"  # Not adjacent
        )

        is_valid, error = GameStateValidator.validate_block_action(
            simple_game_state, action
        )
        assert is_valid is False
        assert "not adjacent" in error.lower()

    def test_validate_block_action_target_teammate(self, simple_game_state):
        """Should reject blocking teammate"""
        active_team = simple_game_state.get_active_team()
        player_id = active_team.player_ids[0]
        teammate_id = active_team.player_ids[1]

        action = ActionRequest(
            action_type=ActionType.SCUFFLE,
            player_id=player_id,
            target_player_id=teammate_id
        )

        is_valid, error = GameStateValidator.validate_block_action(
            simple_game_state, action
        )
        assert is_valid is False
        assert "teammate" in error.lower()

    def test_validate_pass_action_success(self, simple_game_state):
        """Should validate valid HURL action"""
        active_team = simple_game_state.get_active_team()
        player_id = active_team.player_ids[0]

        # Give player the ball
        simple_game_state.pitch.ball_carrier = player_id
        simple_game_state.pitch.ball_position = simple_game_state.pitch.player_positions[player_id]

        action = ActionRequest(
            action_type=ActionType.HURL,
            player_id=player_id,
            target_receiver_id=active_team.player_ids[1]
        )

        is_valid, error = GameStateValidator.validate_pass_action(
            simple_game_state, action
        )
        assert is_valid is True
        assert error is None

    def test_validate_pass_action_no_ball(self, simple_game_state):
        """Should reject hurl when player doesn't have ball"""
        active_team = simple_game_state.get_active_team()
        player_id = active_team.player_ids[0]

        action = ActionRequest(
            action_type=ActionType.HURL,
            player_id=player_id,
            target_receiver_id=active_team.player_ids[1]
        )

        is_valid, error = GameStateValidator.validate_pass_action(
            simple_game_state, action
        )
        assert is_valid is False
        assert "does not have the ball" in error.lower()

    def test_validate_pass_action_to_opponent(self, simple_game_state):
        """Should reject hurl to opponent"""
        active_team = simple_game_state.get_active_team()
        inactive_team = simple_game_state.get_inactive_team()
        player_id = active_team.player_ids[0]

        # Give player the ball
        simple_game_state.pitch.ball_carrier = player_id
        simple_game_state.pitch.ball_position = simple_game_state.pitch.player_positions[player_id]

        action = ActionRequest(
            action_type=ActionType.HURL,
            player_id=player_id,
            target_receiver_id=inactive_team.player_ids[0]  # Opponent
        )

        is_valid, error = GameStateValidator.validate_pass_action(
            simple_game_state, action
        )
        assert is_valid is False
        assert "opponent" in error.lower()

    def test_validate_hand_off_action_success(self, simple_game_state):
        """Should validate valid QUICK_PASS action"""
        active_team = simple_game_state.get_active_team()
        player_id = active_team.player_ids[0]
        receiver_id = active_team.player_ids[1]

        # Give player the ball
        simple_game_state.pitch.ball_carrier = player_id
        simple_game_state.pitch.ball_position = simple_game_state.pitch.player_positions[player_id]

        action = ActionRequest(
            action_type=ActionType.QUICK_PASS,
            player_id=player_id,
            target_receiver_id=receiver_id
        )

        is_valid, error = GameStateValidator.validate_hand_off_action(
            simple_game_state, action
        )
        assert is_valid is True
        assert error is None

    def test_validate_hand_off_action_not_adjacent(self, simple_game_state):
        """Should reject quick_pass when players not adjacent"""
        active_team = simple_game_state.get_active_team()
        player_id = active_team.player_ids[0]
        receiver_id = active_team.player_ids[2]

        # Move receiver far away
        simple_game_state.pitch.player_positions[receiver_id] = Position(x=10, y=10)

        # Give player the ball
        simple_game_state.pitch.ball_carrier = player_id
        simple_game_state.pitch.ball_position = simple_game_state.pitch.player_positions[player_id]

        action = ActionRequest(
            action_type=ActionType.QUICK_PASS,
            player_id=player_id,
            target_receiver_id=receiver_id
        )

        is_valid, error = GameStateValidator.validate_hand_off_action(
            simple_game_state, action
        )
        assert is_valid is False
        assert "not adjacent" in error.lower()
