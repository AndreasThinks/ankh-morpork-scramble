"""Dice rolling system"""
import random
from typing import Optional
from app.models.actions import DiceRoll


class DiceRoller:
    """Handles all dice rolling with optional seeding for testing"""
    
    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
    
    def roll_d6(self) -> int:
        """Roll a single d6"""
        return self.rng.randint(1, 6)
    
    def roll_2d6(self) -> int:
        """Roll 2d6"""
        return self.roll_d6() + self.roll_d6()
    
    def roll_d16(self) -> int:
        """Roll a d16 for casualty table"""
        return self.rng.randint(1, 16)
    
    def roll_target(
        self,
        target: int,
        roll_type: str,
        modifiers: Optional[dict[str, int]] = None
    ) -> DiceRoll:
        """Roll against a target number (e.g., 3+ means need 3 or higher)"""
        if modifiers is None:
            modifiers = {}
        
        result = self.roll_d6()
        total_modifier = sum(modifiers.values())
        final_result = result + total_modifier
        
        success = final_result >= target
        
        return DiceRoll(
            type=roll_type,
            result=result,
            target=target,
            success=success,
            modifiers=modifiers
        )
    
    def roll_agility(self, target: int, modifiers: Optional[dict[str, int]] = None) -> DiceRoll:
        """Roll an agility test"""
        return self.roll_target(target, "agility", modifiers)
    
    def roll_dodge(self, target: int, modifiers: Optional[dict[str, int]] = None) -> DiceRoll:
        """Roll a dodge test"""
        return self.roll_target(target, "dodge", modifiers)
    
    def roll_pickup(self, target: int, modifiers: Optional[dict[str, int]] = None) -> DiceRoll:
        """Roll a pick-up test"""
        return self.roll_target(target, "pickup", modifiers)
    
    def roll_catch(self, target: int, modifiers: Optional[dict[str, int]] = None) -> DiceRoll:
        """Roll a catch test"""
        return self.roll_target(target, "catch", modifiers)
    
    def roll_pass(self, target: int, modifiers: Optional[dict[str, int]] = None) -> DiceRoll:
        """Roll a pass test"""
        return self.roll_target(target, "pass", modifiers)
    
    def roll_armor(self, armor_value: int) -> DiceRoll:
        """Roll armor break (2d6 vs AV)"""
        result = self.roll_2d6()
        success = result >= armor_value
        
        return DiceRoll(
            type="armor",
            result=result,
            target=armor_value,
            success=success,
            modifiers={}
        )
    
    def roll_injury(self) -> tuple[DiceRoll, str]:
        """
        Roll injury result (2d6)
        Returns: (dice_roll, injury_type)
        """
        result = self.roll_2d6()
        
        # Determine injury type
        if result <= 7:
            injury = "stunned"
        elif result <= 9:
            injury = "knocked_out"
        else:
            injury = "casualty"
        
        dice_roll = DiceRoll(
            type="injury",
            result=result,
            target=None,
            success=True,
            modifiers={}
        )
        
        return dice_roll, injury
    
    def roll_casualty(self) -> int:
        """Roll on casualty table (d16)"""
        return self.roll_d16()
    
    def scatter(self) -> tuple[int, int]:
        """Roll scatter direction (returns x, y offset)"""
        roll = self.roll_d6()
        
        # Scatter directions (clockwise from top)
        directions = [
            (0, -1),   # 1: North
            (1, -1),   # 2: NE
            (1, 0),    # 3: East
            (1, 1),    # 4: SE
            (0, 1),    # 5: South
            (-1, 1),   # 6: SW
        ]
        
        # Handle wrap (6 options, but d6 gives 1-6)
        if roll == 6:
            # Continue with next roll for SW, West, NW
            roll2 = self.roll_d6()
            if roll2 <= 2:
                return (-1, 1)   # SW
            elif roll2 <= 4:
                return (-1, 0)   # West
            else:
                return (-1, -1)  # NW
        
        return directions[roll - 1]
