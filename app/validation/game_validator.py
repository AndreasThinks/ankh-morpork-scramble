"""Game state validation utilities"""
from typing import Optional
from app.models.game_state import GameState
from app.models.actions import ActionRequest
from app.models.pitch import Position
from app.models.enums import ActionType


class GameStateValidator:
    """
    Validates game state and action preconditions.

    Provides reusable validation methods that can be used before executing actions
    to provide clearer error messages to LLM agents.
    """

    @staticmethod
    def validate_player_exists(
        game_state: GameState,
        player_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a player exists in the game.

        Returns:
            (is_valid, error_message)
        """
        try:
            player = game_state.get_player(player_id)
            return True, None
        except ValueError:
            return False, f"Player '{player_id}' not found in this game"

    @staticmethod
    def validate_player_can_act(
        game_state: GameState,
        player_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a player can perform any action.

        Validates:
        - Player exists
        - Player is active (not KO'd or injured)
        - Player is standing (not prone or stunned)
        - It's the player's team's turn

        Returns:
            (is_valid, error_message)
        """
        # Check player exists
        is_valid, error = GameStateValidator.validate_player_exists(game_state, player_id)
        if not is_valid:
            return False, error

        player = game_state.get_player(player_id)

        # Check player is active
        if not player.is_active:
            return False, f"Player '{player_id}' cannot act (KO'd, injured, or off pitch)"

        # Check player is standing
        if not player.is_standing:
            state_name = player.state.value if hasattr(player.state, 'value') else str(player.state)
            return False, f"Player '{player_id}' cannot act while {state_name}"

        # Check it's the player's team's turn
        if not game_state.is_player_on_active_team(player_id):
            active_team = game_state.get_active_team()
            return False, (
                f"Not your turn: team {player.team_id} cannot act "
                f"(currently {active_team.id}'s turn)"
            )

        return True, None

    @staticmethod
    def validate_position_on_pitch(pos: Position) -> tuple[bool, Optional[str]]:
        """
        Validate position is within pitch bounds.

        Note: Pydantic Position model already validates this, but this method
        provides a consistent validation interface.

        Returns:
            (is_valid, error_message)
        """
        if not 0 <= pos.x <= 25:
            return False, f"x={pos.x} out of bounds (must be 0-25)"
        if not 0 <= pos.y <= 14:
            return False, f"y={pos.y} out of bounds (must be 0-14)"
        return True, None

    @staticmethod
    def validate_position_unoccupied(
        game_state: GameState,
        pos: Position
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a position is unoccupied.

        Returns:
            (is_valid, error_message)
        """
        occupying_player = game_state.pitch.get_player_at(pos)
        if occupying_player:
            return False, f"Position ({pos.x}, {pos.y}) is occupied by {occupying_player}"
        return True, None

    @staticmethod
    def validate_player_at_position(
        game_state: GameState,
        player_id: str,
        expected_pos: Position
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a player is at the expected position.

        Returns:
            (is_valid, error_message)
        """
        actual_pos = game_state.pitch.player_positions.get(player_id)
        if not actual_pos:
            return False, f"Player '{player_id}' is not on the pitch"

        if actual_pos != expected_pos:
            return False, (
                f"Player '{player_id}' is not at expected position. "
                f"Expected ({expected_pos.x}, {expected_pos.y}), "
                f"found at ({actual_pos.x}, {actual_pos.y})"
            )

        return True, None

    @staticmethod
    def validate_players_adjacent(
        game_state: GameState,
        player1_id: str,
        player2_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if two players are adjacent to each other.

        Returns:
            (is_valid, error_message)
        """
        pos1 = game_state.pitch.player_positions.get(player1_id)
        pos2 = game_state.pitch.player_positions.get(player2_id)

        if not pos1:
            return False, f"Player '{player1_id}' is not on the pitch"
        if not pos2:
            return False, f"Player '{player2_id}' is not on the pitch"

        if not pos1.is_adjacent(pos2):
            distance = pos1.distance_to(pos2)
            return False, (
                f"Players '{player1_id}' and '{player2_id}' are not adjacent "
                f"(distance: {distance} squares)"
            )

        return True, None

    @staticmethod
    def validate_move_action(
        game_state: GameState,
        action: ActionRequest
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a MOVE action before execution.

        Checks:
        - Player can act
        - Target position is specified
        - Target position is on pitch
        - Target position is unoccupied
        - Player has movement remaining

        Returns:
            (is_valid, error_message)
        """
        # Check player can act
        can_act, error = GameStateValidator.validate_player_can_act(
            game_state, action.player_id
        )
        if not can_act:
            return False, error

        # Check target position is specified (should be caught by ActionRequest validator)
        if not action.target_position:
            return False, "MOVE action requires target_position"

        # Check target position is on pitch (Pydantic validates this, but double-check)
        valid_pos, error = GameStateValidator.validate_position_on_pitch(
            action.target_position
        )
        if not valid_pos:
            return False, error

        # Check target is unoccupied
        valid_unoccupied, error = GameStateValidator.validate_position_unoccupied(
            game_state, action.target_position
        )
        if not valid_unoccupied:
            return False, error

        # Check player has movement remaining
        player = game_state.get_player(action.player_id)
        if player.movement_remaining == 0:
            return False, f"Player '{action.player_id}' has no movement remaining this turn"

        return True, None

    @staticmethod
    def validate_block_action(
        game_state: GameState,
        action: ActionRequest
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a BLOCK action before execution.

        Checks:
        - Attacker can act
        - Target player exists
        - Target player is an opponent
        - Target player is active
        - Target player is adjacent to attacker

        Returns:
            (is_valid, error_message)
        """
        # Check attacker can act
        can_act, error = GameStateValidator.validate_player_can_act(
            game_state, action.player_id
        )
        if not can_act:
            return False, error

        # Check target is specified
        if not action.target_player_id:
            return False, "BLOCK action requires target_player_id"

        # Check target exists
        is_valid, error = GameStateValidator.validate_player_exists(
            game_state, action.target_player_id
        )
        if not is_valid:
            return False, error

        attacker = game_state.get_player(action.player_id)
        target = game_state.get_player(action.target_player_id)

        # Check target is an opponent
        if target.team_id == attacker.team_id:
            return False, f"Cannot block teammate '{action.target_player_id}'"

        # Check target is active
        if not target.is_active:
            return False, f"Cannot block inactive player '{action.target_player_id}'"

        # Check players are adjacent
        are_adjacent, error = GameStateValidator.validate_players_adjacent(
            game_state, action.player_id, action.target_player_id
        )
        if not are_adjacent:
            return False, error

        return True, None

    @staticmethod
    def validate_pass_action(
        game_state: GameState,
        action: ActionRequest
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a PASS action before execution.

        Checks:
        - Passer can act
        - Passer is carrying the ball
        - Target receiver exists (if specified)
        - Target receiver is a teammate (if specified)

        Returns:
            (is_valid, error_message)
        """
        # Check passer can act
        can_act, error = GameStateValidator.validate_player_can_act(
            game_state, action.player_id
        )
        if not can_act:
            return False, error

        # Check passer has the ball
        if game_state.pitch.ball_carrier != action.player_id:
            carrier = game_state.pitch.ball_carrier or "no one"
            return False, f"Player '{action.player_id}' does not have the ball (carrier: {carrier})"

        # If target receiver is specified, validate
        if action.target_receiver_id:
            is_valid, error = GameStateValidator.validate_player_exists(
                game_state, action.target_receiver_id
            )
            if not is_valid:
                return False, error

            passer = game_state.get_player(action.player_id)
            receiver = game_state.get_player(action.target_receiver_id)

            # Check receiver is a teammate
            if receiver.team_id != passer.team_id:
                return False, f"Cannot pass to opponent '{action.target_receiver_id}'"

        return True, None

    @staticmethod
    def validate_hand_off_action(
        game_state: GameState,
        action: ActionRequest
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a HAND_OFF action before execution.

        Checks:
        - Passer can act
        - Passer is carrying the ball
        - Target receiver exists
        - Target receiver is a teammate
        - Target receiver is active
        - Players are adjacent

        Returns:
            (is_valid, error_message)
        """
        # Check passer can act
        can_act, error = GameStateValidator.validate_player_can_act(
            game_state, action.player_id
        )
        if not can_act:
            return False, error

        # Check passer has the ball
        if game_state.pitch.ball_carrier != action.player_id:
            carrier = game_state.pitch.ball_carrier or "no one"
            return False, f"Player '{action.player_id}' does not have the ball (carrier: {carrier})"

        # Check target receiver is specified
        if not action.target_receiver_id:
            return False, "HAND_OFF action requires target_receiver_id"

        # Check receiver exists
        is_valid, error = GameStateValidator.validate_player_exists(
            game_state, action.target_receiver_id
        )
        if not is_valid:
            return False, error

        passer = game_state.get_player(action.player_id)
        receiver = game_state.get_player(action.target_receiver_id)

        # Check receiver is a teammate
        if receiver.team_id != passer.team_id:
            return False, f"Cannot hand off to opponent '{action.target_receiver_id}'"

        # Check receiver is active
        if not receiver.is_active:
            return False, f"Cannot hand off to inactive player '{action.target_receiver_id}'"

        # Check players are adjacent
        are_adjacent, error = GameStateValidator.validate_players_adjacent(
            game_state, action.player_id, action.target_receiver_id
        )
        if not are_adjacent:
            return False, error

        return True, None
