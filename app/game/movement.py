"""Movement and dodging logic"""
from typing import Optional
from app.models.game_state import GameState
from app.models.player import Player
from app.models.pitch import Position, PITCH_WIDTH, PITCH_HEIGHT
from app.models.enums import SkillType, PlayerState
from app.models.actions import DiceRoll
from app.game.dice import DiceRoller


class MovementHandler:
    """Handles player movement, dodging, and rushing"""
    
    def __init__(self, dice_roller: DiceRoller):
        self.dice = dice_roller
    
    def get_tackle_zones(self, game_state: GameState, team_id: str, pos: Position) -> int:
        """Count enemy tackle zones affecting a position"""
        opposing_team_id = (
            game_state.team2.id if team_id == game_state.team1.id else game_state.team1.id
        )
        
        count = 0
        for player_id in game_state.pitch.get_adjacent_players(pos):
            player = game_state.get_player(player_id)
            if player.team_id == opposing_team_id and player.is_standing:
                count += 1
        
        return count
    
    def requires_dodge(
        self,
        game_state: GameState,
        player: Player,
        from_pos: Position,
        to_pos: Position
    ) -> bool:
        """Check if movement requires a dodge roll"""
        # Only need to dodge when leaving an enemy tackle zone
        enemy_zones_at_start = self.get_tackle_zones(game_state, player.team_id, from_pos)
        return enemy_zones_at_start > 0
    
    def calculate_dodge_modifiers(
        self,
        game_state: GameState,
        player: Player,
        from_pos: Position,
        to_pos: Position
    ) -> dict[str, int]:
        """Calculate modifiers for a dodge roll"""
        modifiers = {}
        
        # Enemy tackle zones at destination
        enemy_zones_at_dest = self.get_tackle_zones(game_state, player.team_id, to_pos)
        if enemy_zones_at_dest > 0:
            modifiers["tackle_zones"] = -enemy_zones_at_dest
        
        # Skills could add modifiers here (e.g., Dodge skill)
        if player.has_skill(SkillType.BLINK) or player.has_skill(SkillType.SIDESTEP_SHUFFLE):
            modifiers["dodge_skill"] = 1
        
        return modifiers
    
    def attempt_dodge(
        self,
        game_state: GameState,
        player: Player,
        from_pos: Position,
        to_pos: Position
    ) -> DiceRoll:
        """Attempt a dodge roll"""
        agility_target = player.get_agility_target()
        modifiers = self.calculate_dodge_modifiers(game_state, player, from_pos, to_pos)
        
        return self.dice.roll_dodge(agility_target, modifiers)
    
    def can_move_to(
        self,
        game_state: GameState,
        player: Player,
        target_pos: Position
    ) -> tuple[bool, Optional[str]]:
        """Check if player can move to a position"""
        # Check if player can act
        if not player.is_active:
            return False, f"Player is {player.state.value}"
        
        if not player.is_standing:
            return False, "Player must be standing to move"
        
        # Check if position is on the pitch
        if not (0 <= target_pos.x < PITCH_WIDTH and 0 <= target_pos.y < PITCH_HEIGHT):
            return False, "Position is outside pitch bounds"
        
        # Check if position is occupied
        if game_state.pitch.is_occupied(target_pos):
            return False, "Position is occupied"
        
        return True, None
    
    def move_player(
        self,
        game_state: GameState,
        player_id: str,
        path: list[Position],
        allow_rush: bool = True
    ) -> tuple[bool, list[DiceRoll], Optional[str]]:
        """
        Move a player along a path
        Returns: (success, dice_rolls, error_message)
        """
        player = game_state.get_player(player_id)
        dice_rolls = []
        
        if not path:
            return False, dice_rolls, "No path provided"
        
        current_pos = game_state.pitch.player_positions.get(player_id)
        if not current_pos:
            return False, dice_rolls, "Player not on pitch"
        
        # Calculate path length
        path_length = len(path)
        normal_movement = min(path_length, player.movement_remaining)
        rush_needed = path_length - normal_movement
        
        # Check if rushing is allowed and needed
        if rush_needed > 0:
            if not allow_rush:
                return False, dice_rolls, "Rushing not allowed for this action"
            if rush_needed > 2:
                return False, dice_rolls, "Can only rush up to 2 squares"
        
        # Move along path
        for i, target_pos in enumerate(path):
            # Check if move is valid
            can_move, error = self.can_move_to(game_state, player, target_pos)
            if not can_move:
                return False, dice_rolls, error
            
            # Check if adjacent (only orthogonal and diagonal moves)
            if not current_pos.is_adjacent(target_pos):
                return False, dice_rolls, "Can only move to adjacent squares"
            
            # Check if dodge is needed
            if self.requires_dodge(game_state, player, current_pos, target_pos):
                dodge_roll = self.attempt_dodge(game_state, player, current_pos, target_pos)
                dice_rolls.append(dodge_roll)
                
                if not dodge_roll.success:
                    # Failed dodge - player is knocked down
                    player.knock_down()
                    return False, dice_rolls, "Dodge failed"
            
            # Check if this is a rush square
            is_rush_square = i >= normal_movement
            if is_rush_square:
                # Rush requires 2+ roll
                rush_roll = self.dice.roll_target(2, "rush", {})
                dice_rolls.append(rush_roll)
                
                if not rush_roll.success:
                    # Failed rush - player is knocked down
                    player.knock_down()
                    return False, dice_rolls, "Rush failed"
            
            # Move player
            game_state.pitch.move_player(player_id, target_pos)
            current_pos = target_pos
            
            # Track movement used
            player.use_movement(1)
        
        return True, dice_rolls, None
    
    def stand_up_player(self, player: Player) -> tuple[bool, Optional[str]]:
        """Attempt to stand up a prone player"""
        if player.state != PlayerState.PRONE:
            return False, "Player is not prone"
        
        if player.movement_remaining < 3:
            return False, "Not enough movement to stand up (requires 3 MA)"
        
        player.stand_up()
        return True, None
