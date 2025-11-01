"""Ball handling - pickup, pass, catch, scatter"""
from typing import Optional
from app.models.game_state import GameState
from app.models.player import Player
from app.models.pitch import Position
from app.models.enums import SkillType, PassResult
from app.models.actions import DiceRoll
from app.game.dice import DiceRoller


class BallHandler:
    """Handles ball pickup, passing, catching, and scatter"""
    
    def __init__(self, dice_roller: DiceRoller):
        self.dice = dice_roller
    
    def attempt_pickup(
        self,
        game_state: GameState,
        player: Player
    ) -> tuple[bool, DiceRoll]:
        """Attempt to pick up the ball"""
        agility_target = player.get_agility_target()
        modifiers = {}
        
        # Check for tackle zones
        player_pos = game_state.pitch.player_positions.get(player.id)
        if not player_pos:
            raise ValueError("Player not on pitch")
        
        # Count enemy tackle zones
        opposing_team_id = (
            game_state.team2.id if player.team_id == game_state.team1.id 
            else game_state.team1.id
        )
        
        tackle_zones = 0
        for adj_player_id in game_state.pitch.get_adjacent_players(player_pos):
            adj_player = game_state.get_player(adj_player_id)
            if adj_player.team_id == opposing_team_id and adj_player.is_standing:
                tackle_zones += 1
        
        if tackle_zones > 0:
            modifiers["tackle_zones"] = -tackle_zones
        
        # Sure Hands skill
        if player.has_skill(SkillType.CHAIN_OF_CUSTODY):
            modifiers["sure_hands"] = 1
        
        pickup_roll = self.dice.roll_pickup(agility_target, modifiers)
        
        if pickup_roll.success:
            game_state.pitch.pick_up_ball(player.id)
            return True, pickup_roll
        else:
            # Failed pickup - ball scatters
            self.scatter_ball(game_state)
            return False, pickup_roll
    
    def attempt_catch(
        self,
        game_state: GameState,
        player: Player,
        from_pass: bool = False
    ) -> tuple[bool, DiceRoll]:
        """Attempt to catch the ball"""
        agility_target = player.get_agility_target()
        modifiers = {}
        
        # Catch skill
        if player.has_skill(SkillType.QUICK_GRAB):
            modifiers["catch_skill"] = 1
        
        # Count tackle zones
        player_pos = game_state.pitch.player_positions.get(player.id)
        if player_pos:
            opposing_team_id = (
                game_state.team2.id if player.team_id == game_state.team1.id 
                else game_state.team1.id
            )
            
            tackle_zones = 0
            for adj_player_id in game_state.pitch.get_adjacent_players(player_pos):
                adj_player = game_state.get_player(adj_player_id)
                if adj_player.team_id == opposing_team_id and adj_player.is_standing:
                    tackle_zones += 1
            
            if tackle_zones > 0:
                modifiers["tackle_zones"] = -tackle_zones
        
        catch_roll = self.dice.roll_catch(agility_target, modifiers)
        
        if catch_roll.success:
            game_state.pitch.pick_up_ball(player.id)
            return True, catch_roll
        else:
            # Failed catch - ball scatters
            self.scatter_ball(game_state)
            return False, catch_roll
    
    def scatter_ball(self, game_state: GameState) -> Position:
        """Scatter the ball one square"""
        if not game_state.pitch.ball_position:
            raise ValueError("No ball position to scatter from")
        
        dx, dy = self.dice.scatter()
        old_pos = game_state.pitch.ball_position
        
        new_x = max(0, min(25, old_pos.x + dx))
        new_y = max(0, min(14, old_pos.y + dy))
        new_pos = Position(x=new_x, y=new_y)
        
        game_state.pitch.place_ball(new_pos)
        game_state.add_event(f"Ball scattered from ({old_pos.x},{old_pos.y}) to ({new_x},{new_y})")
        
        return new_pos
    
    def calculate_pass_range(self, from_pos: Position, to_pos: Position) -> str:
        """Calculate pass range category"""
        distance = from_pos.distance_to(to_pos)
        
        if distance <= 3:
            return "quick"
        elif distance <= 6:
            return "short"
        elif distance <= 12:
            return "long"
        else:
            return "long_bomb"
    
    def get_pass_modifiers(
        self,
        game_state: GameState,
        passer: Player,
        from_pos: Position,
        to_pos: Position
    ) -> dict[str, int]:
        """Calculate pass modifiers"""
        modifiers = {}
        
        # Range modifier
        pass_range = self.calculate_pass_range(from_pos, to_pos)
        range_modifiers = {
            "quick": 1,
            "short": 0,
            "long": -1,
            "long_bomb": -2
        }
        modifiers["range"] = range_modifiers[pass_range]
        
        # Tackle zones
        opposing_team_id = (
            game_state.team2.id if passer.team_id == game_state.team1.id 
            else game_state.team1.id
        )
        
        tackle_zones = 0
        for adj_player_id in game_state.pitch.get_adjacent_players(from_pos):
            adj_player = game_state.get_player(adj_player_id)
            if adj_player.team_id == opposing_team_id and adj_player.is_standing:
                tackle_zones += 1
        
        if tackle_zones > 0:
            modifiers["tackle_zones"] = -tackle_zones
        
        # Pass skill
        if passer.has_skill(SkillType.PIGEON_POST):
            modifiers["pass_skill"] = 1
        
        return modifiers
    
    def attempt_pass(
        self,
        game_state: GameState,
        passer: Player,
        target_pos: Position
    ) -> tuple[PassResult, Position, list[DiceRoll]]:
        """
        Attempt to pass the ball
        Returns: (pass_result, final_ball_position, dice_rolls)
        """
        dice_rolls = []
        
        passer_pos = game_state.pitch.player_positions.get(passer.id)
        if not passer_pos:
            raise ValueError("Passer not on pitch")
        
        # Check if passer has the ball
        if game_state.pitch.ball_carrier != passer.id:
            raise ValueError("Passer does not have the ball")
        
        # Roll pass
        pass_target = passer.get_passing_target()
        modifiers = self.get_pass_modifiers(game_state, passer, passer_pos, target_pos)
        
        pass_roll = self.dice.roll_pass(pass_target, modifiers)
        dice_rolls.append(pass_roll)
        
        # Drop the ball from carrier
        game_state.pitch.drop_ball()
        
        # Determine pass result
        result = pass_roll.result + sum(modifiers.values())
        
        if result == 1:
            # Fumble - ball scatters from passer
            pass_result = PassResult.FUMBLE
            game_state.pitch.place_ball(passer_pos)
            final_pos = self.scatter_ball(game_state)
            
        elif result < pass_target:
            # Wildly inaccurate - scatter 3 times from target
            pass_result = PassResult.WILDLY_INACCURATE
            game_state.pitch.place_ball(target_pos)
            for _ in range(3):
                final_pos = self.scatter_ball(game_state)
                
        elif result < pass_target + 3:
            # Inaccurate - scatter once from target
            pass_result = PassResult.INACCURATE
            game_state.pitch.place_ball(target_pos)
            final_pos = self.scatter_ball(game_state)
            
        else:
            # Accurate
            pass_result = PassResult.ACCURATE
            game_state.pitch.place_ball(target_pos)
            final_pos = target_pos
        
        return pass_result, final_pos, dice_rolls
    
    def hand_off(
        self,
        game_state: GameState,
        giver: Player,
        receiver: Player
    ) -> tuple[bool, Optional[str]]:
        """Hand off the ball to an adjacent player"""
        # Check if giver has ball
        if game_state.pitch.ball_carrier != giver.id:
            return False, "Giver does not have the ball"
        
        # Check if players are adjacent
        giver_pos = game_state.pitch.player_positions.get(giver.id)
        receiver_pos = game_state.pitch.player_positions.get(receiver.id)
        
        if not giver_pos or not receiver_pos:
            return False, "Players not on pitch"
        
        if not giver_pos.is_adjacent(receiver_pos):
            return False, "Players must be adjacent for hand-off"
        
        # Check if receiver is on same team
        if giver.team_id != receiver.team_id:
            return False, "Cannot hand off to opposing team"
        
        # Hand off succeeds automatically (no roll needed)
        game_state.pitch.drop_ball()
        game_state.pitch.place_ball(receiver_pos)
        game_state.pitch.pick_up_ball(receiver.id)
        
        return True, None
