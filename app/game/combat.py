"""Combat system - blocks, armor, and injury"""
from typing import Optional
from app.models.game_state import GameState
from app.models.player import Player
from app.models.pitch import Position
from app.models.enums import SkillType, BlockResult, InjuryResult, PlayerState
from app.models.actions import DiceRoll
from app.game.dice import DiceRoller


class CombatHandler:
    """Handles blocking, armor rolls, and injuries"""
    
    def __init__(self, dice_roller: DiceRoller):
        self.dice = dice_roller
    
    def can_block(
        self,
        game_state: GameState,
        attacker: Player,
        defender: Player
    ) -> tuple[bool, Optional[str]]:
        """Check if attacker can block defender"""
        # Check if attacker is standing
        if not attacker.is_standing:
            return False, "Attacker must be standing"
        
        # Check if defender is on pitch
        attacker_pos = game_state.pitch.player_positions.get(attacker.id)
        defender_pos = game_state.pitch.player_positions.get(defender.id)
        
        if not attacker_pos or not defender_pos:
            return False, "Players not on pitch"
        
        # Check if adjacent
        if not attacker_pos.is_adjacent(defender_pos):
            return False, "Players must be adjacent to block"
        
        # Check if defender is on opposing team
        if attacker.team_id == defender.team_id:
            return False, "Cannot block teammate"
        
        # Check if defender can be blocked
        if defender.state == PlayerState.KNOCKED_OUT or defender.state == PlayerState.CASUALTY:
            return False, "Defender is not active"
        
        return True, None
    
    def get_block_dice_count(
        self,
        attacker: Player,
        defender: Player,
        assist_count_attacker: int = 0,
        assist_count_defender: int = 0
    ) -> tuple[int, bool]:
        """
        Get number of block dice and who chooses result
        Returns: (dice_count, attacker_chooses)
        """
        attacker_strength = attacker.position.st + assist_count_attacker
        defender_strength = defender.position.st + assist_count_defender
        
        # Apply skill modifiers
        if attacker.has_skill(SkillType.STONE_THICK):  # Mighty Blow
            attacker_strength += 1
        
        if attacker_strength > defender_strength * 2:
            return 3, True
        elif attacker_strength > defender_strength:
            return 2, True
        elif attacker_strength == defender_strength:
            return 1, True  # Both can choose, but we'll handle this specially
        elif defender_strength > attacker_strength:
            return 2, False
        else:  # defender_strength > attacker_strength * 2
            return 3, False
    
    def roll_block_dice(self, count: int) -> list[BlockResult]:
        """Roll block dice"""
        results = []
        for _ in range(count):
            roll = self.dice.roll_d6()
            
            # Map d6 results to block results
            # 1-2: Defender choices, 3-4: Push, 5-6: Attacker choices
            if roll == 1:
                results.append(BlockResult.ATTACKER_DOWN)
            elif roll == 2:
                results.append(BlockResult.BOTH_DOWN)
            elif roll == 3 or roll == 4:
                results.append(BlockResult.PUSH)
            elif roll == 5:
                results.append(BlockResult.DEFENDER_STUMBLES)
            else:  # roll == 6
                results.append(BlockResult.DEFENDER_DOWN)
        
        return results
    
    def choose_block_result(
        self,
        results: list[BlockResult],
        attacker_chooses: bool,
        attacker: Player,
        defender: Player
    ) -> BlockResult:
        """Choose the best block result from available dice"""
        if len(results) == 1:
            return results[0]
        
        if attacker_chooses:
            # Prefer results that knock down or stumble defender
            if BlockResult.DEFENDER_DOWN in results:
                return BlockResult.DEFENDER_DOWN
            elif BlockResult.DEFENDER_STUMBLES in results:
                return BlockResult.DEFENDER_STUMBLES
            elif BlockResult.PUSH in results:
                return BlockResult.PUSH
            elif BlockResult.BOTH_DOWN in results:
                # Choose both down if attacker has Block skill
                if attacker.has_skill(SkillType.DRILL_HARDENED):
                    return BlockResult.BOTH_DOWN
                return BlockResult.PUSH if BlockResult.PUSH in results else results[0]
            else:
                return results[0]
        else:
            # Defender chooses - prefer results that hurt attacker
            if BlockResult.ATTACKER_DOWN in results:
                return BlockResult.ATTACKER_DOWN
            elif BlockResult.BOTH_DOWN in results:
                # Choose both down if defender has Block skill
                if defender.has_skill(SkillType.DRILL_HARDENED):
                    return BlockResult.BOTH_DOWN
                return BlockResult.PUSH if BlockResult.PUSH in results else results[0]
            elif BlockResult.PUSH in results:
                return BlockResult.PUSH
            else:
                return results[0]
    
    def execute_block(
        self,
        game_state: GameState,
        attacker: Player,
        defender: Player
    ) -> tuple[BlockResult, list[DiceRoll], bool, bool]:
        """
        Execute a block
        Returns: (block_result, dice_rolls, defender_knocked_down, attacker_knocked_down)
        """
        dice_rolls = []
        
        # Get block dice
        dice_count, attacker_chooses = self.get_block_dice_count(attacker, defender)
        
        # Roll block dice
        block_results = self.roll_block_dice(dice_count)
        
        # Choose result
        chosen_result = self.choose_block_result(
            block_results,
            attacker_chooses,
            attacker,
            defender
        )
        
        # Record the block roll
        dice_rolls.append(DiceRoll(
            type="block",
            result=dice_count,
            target=None,
            success=True,
            modifiers={"chosen_result": chosen_result.value}
        ))
        
        # Apply result
        defender_knocked_down = False
        attacker_knocked_down = False
        
        if chosen_result == BlockResult.DEFENDER_DOWN or chosen_result == BlockResult.DEFENDER_STUMBLES:
            defender.knock_down()
            defender_knocked_down = True
            
            # Roll armor and injury if knocked down
            armor_rolls, injury_result = self.resolve_injury(defender)
            dice_rolls.extend(armor_rolls)
            
        elif chosen_result == BlockResult.ATTACKER_DOWN:
            # Check if attacker has Block skill
            if not attacker.has_skill(SkillType.DRILL_HARDENED):
                attacker.knock_down()
                attacker_knocked_down = True
                
                armor_rolls, injury_result = self.resolve_injury(attacker)
                dice_rolls.extend(armor_rolls)
                
        elif chosen_result == BlockResult.BOTH_DOWN:
            # Both knocked down unless they have Block skill
            if not attacker.has_skill(SkillType.DRILL_HARDENED):
                attacker.knock_down()
                attacker_knocked_down = True
                armor_rolls, _ = self.resolve_injury(attacker)
                dice_rolls.extend(armor_rolls)
            
            if not defender.has_skill(SkillType.DRILL_HARDENED):
                defender.knock_down()
                defender_knocked_down = True
                armor_rolls, _ = self.resolve_injury(defender)
                dice_rolls.extend(armor_rolls)
        
        # PUSH result requires no further action (handled by caller)
        
        return chosen_result, dice_rolls, defender_knocked_down, attacker_knocked_down
    
    def resolve_injury(
        self,
        player: Player
    ) -> tuple[list[DiceRoll], Optional[str]]:
        """
        Roll armor and injury for a knocked down player
        Returns: (dice_rolls, injury_result)
        """
        dice_rolls = []
        
        # Roll armor
        armor_value = player.get_armor_value()
        armor_roll = self.dice.roll_armor(armor_value)
        dice_rolls.append(armor_roll)
        
        if armor_roll.success:
            # Armor broken - roll injury
            injury_roll, injury_type = self.dice.roll_injury()
            dice_rolls.append(injury_roll)
            
            if injury_type == "stunned":
                player.stun()
                return dice_rolls, "stunned"
            elif injury_type == "knocked_out":
                player.knock_out()
                return dice_rolls, "knocked_out"
            else:  # casualty
                player.casualty()
                casualty_roll = self.dice.roll_casualty()
                dice_rolls.append(DiceRoll(
                    type="casualty",
                    result=casualty_roll,
                    target=None,
                    success=True,
                    modifiers={}
                ))
                return dice_rolls, f"casualty_{casualty_roll}"
        
        # Armor held - just prone
        return dice_rolls, None
    
    def attempt_foul(
        self,
        game_state: GameState,
        attacker: Player,
        target: Player
    ) -> tuple[bool, list[DiceRoll], Optional[str]]:
        """
        Attempt a foul on a prone player
        Returns: (success, dice_rolls, injury_result)
        """
        # Check if target is prone
        if target.state != PlayerState.PRONE:
            return False, [], "Target must be prone to foul"
        
        # Check if adjacent
        attacker_pos = game_state.pitch.player_positions.get(attacker.id)
        target_pos = game_state.pitch.player_positions.get(target.id)
        
        if not attacker_pos or not target_pos:
            return False, [], "Players not on pitch"
        
        if not attacker_pos.is_adjacent(target_pos):
            return False, [], "Must be adjacent to foul"
        
        # Foul always hits - roll armor and injury
        dice_rolls, injury_result = self.resolve_injury(target)
        
        # TODO: Roll for sent off (not implemented in basic version)
        
        return True, dice_rolls, injury_result
