"""Action execution - applies validated actions to game state"""
from typing import Optional
from app.models.game_state import GameState
from app.models.actions import ActionRequest, ActionResult, ActionType
from app.models.enums import PassResult
from app.game.dice import DiceRoller
from app.game.movement import MovementHandler
from app.game.ball_handling import BallHandler
from app.game.combat import CombatHandler


class ActionExecutor:
    """Executes validated actions and updates game state"""
    
    def __init__(self, dice_roller: Optional[DiceRoller] = None):
        self.dice = dice_roller or DiceRoller()
        self.movement = MovementHandler(self.dice)
        self.ball = BallHandler(self.dice)
        self.combat = CombatHandler(self.dice)
    
    def execute_action(
        self,
        game_state: GameState,
        action: ActionRequest
    ) -> ActionResult:
        """Execute an action and return the result"""
        
        if action.action_type == ActionType.MOVE:
            return self._execute_move(game_state, action)
        
        elif action.action_type == ActionType.STAND_UP:
            return self._execute_stand_up(game_state, action)
        
        elif action.action_type == ActionType.SCUFFLE:
            return self._execute_scuffle(game_state, action)

        elif action.action_type == ActionType.CHARGE:
            return self._execute_charge(game_state, action)

        elif action.action_type == ActionType.HURL:
            return self._execute_hurl(game_state, action)

        elif action.action_type == ActionType.QUICK_PASS:
            return self._execute_quick_pass(game_state, action)

        elif action.action_type == ActionType.BOOT:
            return self._execute_boot(game_state, action)
        
        else:
            return ActionResult(
                success=False,
                message=f"Unknown action type: {action.action_type}"
            )
    
    def _execute_move(self, game_state: GameState, action: ActionRequest) -> ActionResult:
        """Execute a move action"""
        if not action.path:
            return ActionResult(success=False, message="No path provided for move")
        
        player = game_state.get_player(action.player_id)
        
        # Check if player is at ball position after move - auto pickup
        final_pos = action.path[-1]
        ball_at_destination = (
            game_state.pitch.ball_position == final_pos 
            and not game_state.pitch.ball_carrier
        )
        
        # Attempt movement
        success, dice_rolls, error = self.movement.move_player(
            game_state,
            action.player_id,
            action.path
        )
        
        if not success:
            return ActionResult(
                success=False,
                message=error or "Movement failed",
                dice_rolls=dice_rolls,
                turnover=True
            )
        
        result = ActionResult(
            success=True,
            message=f"Player moved to ({final_pos.x}, {final_pos.y})",
            dice_rolls=dice_rolls,
            player_moved=action.player_id,
            new_position=final_pos
        )
        
        # Auto-pickup if ball is at destination
        if ball_at_destination:
            pickup_success, pickup_roll = self.ball.attempt_pickup(game_state, player)
            result.dice_rolls.append(pickup_roll)
            
            if pickup_success:
                result.ball_picked_up = True
                result.message += " and picked up the ball"
            else:
                result.turnover = True
                result.ball_dropped = True
                result.message += " but failed to pick up the ball"
        
        player.has_acted = True
        game_state.add_event(result.message)
        
        return result
    
    def _execute_stand_up(self, game_state: GameState, action: ActionRequest) -> ActionResult:
        """Execute stand up action"""
        player = game_state.get_player(action.player_id)
        
        success, error = self.movement.stand_up_player(player)
        
        if not success:
            return ActionResult(success=False, message=error or "Failed to stand up")
        
        game_state.add_event(f"Player {action.player_id} stood up")
        
        return ActionResult(
            success=True,
            message="Player stood up"
        )
    
    def _execute_scuffle(self, game_state: GameState, action: ActionRequest) -> ActionResult:
        """Execute a scuffle action (block/brawl)"""
        if not action.target_player_id:
            return ActionResult(success=False, message="No target player specified")
        
        attacker = game_state.get_player(action.player_id)
        defender = game_state.get_player(action.target_player_id)
        
        # Check if block is valid
        can_block, error = self.combat.can_block(game_state, attacker, defender)
        if not can_block:
            return ActionResult(success=False, message=error or "Cannot block")
        
        # Execute block
        block_result, dice_rolls, defender_down, attacker_down = self.combat.execute_block(
            game_state,
            attacker,
            defender
        )
        
        result = ActionResult(
            success=True,
            message=f"Block result: {block_result.value}",
            dice_rolls=dice_rolls,
            block_result=block_result,
            defender_knocked_down=defender_down,
            attacker_knocked_down=attacker_down
        )
        
        # Check for turnover - if ball carrier is knocked down
        if defender_down and game_state.pitch.ball_carrier == defender.id:
            game_state.pitch.drop_ball()
            result.turnover = True
            result.ball_dropped = True
            result.message += " - Ball carrier knocked down!"
        
        if attacker_down and game_state.pitch.ball_carrier == attacker.id:
            game_state.pitch.drop_ball()
            result.turnover = True
            result.ball_dropped = True
            result.message += " - Attacker knocked down with ball!"
        
        attacker.has_acted = True
        game_state.add_event(result.message)
        
        return result
    
    def _execute_charge(self, game_state: GameState, action: ActionRequest) -> ActionResult:
        """Execute a charge action (move + scuffle)"""
        if not game_state.turn:
            return ActionResult(success=False, message="No active turn")

        if game_state.turn.charge_used:
            return ActionResult(success=False, message="Charge already used this turn")
        
        player = game_state.get_player(action.player_id)
        all_dice_rolls = []
        
        # First, move if path provided
        if action.path:
            success, dice_rolls, error = self.movement.move_player(
                game_state,
                action.player_id,
                action.path,
                allow_rush=True
            )
            all_dice_rolls.extend(dice_rolls)
            
            if not success:
                return ActionResult(
                    success=False,
                    message=f"Charge movement failed: {error}",
                    dice_rolls=all_dice_rolls,
                    turnover=True
                )

        # Then scuffle
        if not action.target_player_id:
            return ActionResult(
                success=False,
                message="No target player for charge",
                dice_rolls=all_dice_rolls
            )
        
        defender = game_state.get_player(action.target_player_id)
        
        can_block, error = self.combat.can_block(game_state, player, defender)
        if not can_block:
            return ActionResult(
                success=False,
                message=f"Cannot block: {error}",
                dice_rolls=all_dice_rolls
            )
        
        block_result, block_dice, defender_down, attacker_down = self.combat.execute_block(
            game_state,
            player,
            defender
        )
        all_dice_rolls.extend(block_dice)
        
        result = ActionResult(
            success=True,
            message=f"Charge! Block result: {block_result.value}",
            dice_rolls=all_dice_rolls,
            block_result=block_result,
            defender_knocked_down=defender_down,
            attacker_knocked_down=attacker_down
        )

        # Check for turnover
        if defender_down and game_state.pitch.ball_carrier == defender.id:
            game_state.pitch.drop_ball()
            result.ball_dropped = True

        if attacker_down and game_state.pitch.ball_carrier == player.id:
            game_state.pitch.drop_ball()
            result.turnover = True
            result.ball_dropped = True

        game_state.turn.charge_used = True
        player.has_acted = True
        game_state.add_event(result.message)
        
        return result
    
    def _execute_hurl(self, game_state: GameState, action: ActionRequest) -> ActionResult:
        """Execute a hurl action (throw ball)"""
        if not game_state.turn:
            return ActionResult(success=False, message="No active turn")

        if game_state.turn.hurl_used:
            return ActionResult(success=False, message="Hurl already used this turn")
        
        if not action.target_position:
            return ActionResult(success=False, message="No target position for pass")
        
        passer = game_state.get_player(action.player_id)
        
        # Attempt pass
        pass_result, ball_pos, dice_rolls = self.ball.attempt_pass(
            game_state,
            passer,
            action.target_position
        )
        
        result = ActionResult(
            success=True,
            message=f"Pass result: {pass_result.value}",
            dice_rolls=dice_rolls,
            pass_result=pass_result
        )
        
        # Check for turnover on fumble
        if pass_result == PassResult.FUMBLE:
            result.turnover = True
            result.ball_dropped = True
        else:
            # Check if anyone can catch
            receiver_id = game_state.pitch.get_player_at(ball_pos)
            if receiver_id:
                receiver = game_state.get_player(receiver_id)
                catch_success, catch_roll = self.ball.attempt_catch(
                    game_state,
                    receiver,
                    from_pass=True
                )
                result.dice_rolls.append(catch_roll)
                
                if catch_success:
                    result.ball_caught = True
                    result.message += f" - Caught by {receiver_id}!"
                    
                    # If caught by opponent, it's a turnover
                    if receiver.team_id != passer.team_id:
                        result.turnover = True
                else:
                    # Failed catch by active team is turnover
                    if receiver.team_id == passer.team_id:
                        result.turnover = True
                    result.ball_dropped = True
        
        game_state.turn.hurl_used = True
        passer.has_acted = True
        game_state.add_event(result.message)

        return result

    def _execute_quick_pass(self, game_state: GameState, action: ActionRequest) -> ActionResult:
        """Execute a quick pass action (short hand-off)"""
        if not game_state.turn:
            return ActionResult(success=False, message="No active turn")

        if game_state.turn.quick_pass_used:
            return ActionResult(success=False, message="Quick pass already used this turn")
        
        if not action.target_receiver_id:
            return ActionResult(success=False, message="No receiver specified")
        
        giver = game_state.get_player(action.player_id)
        receiver = game_state.get_player(action.target_receiver_id)
        
        success, error = self.ball.hand_off(game_state, giver, receiver)
        
        if not success:
            return ActionResult(success=False, message=error or "Hand-off failed")
        
        result = ActionResult(
            success=True,
            message=f"Ball handed off to {action.target_receiver_id}",
            ball_caught=True
        )
        
        game_state.turn.quick_pass_used = True
        giver.has_acted = True
        game_state.add_event(result.message)

        return result

    def _execute_boot(self, game_state: GameState, action: ActionRequest) -> ActionResult:
        """Execute a boot action (foul/kick opponent when down)"""
        if not game_state.turn:
            return ActionResult(success=False, message="No active turn")

        if game_state.turn.boot_used:
            return ActionResult(success=False, message="Boot already used this turn")
        
        if not action.target_player_id:
            return ActionResult(success=False, message="No target player specified")
        
        attacker = game_state.get_player(action.player_id)
        target = game_state.get_player(action.target_player_id)
        
        success, dice_rolls, injury = self.combat.attempt_foul(
            game_state,
            attacker,
            target
        )
        
        if not success:
            return ActionResult(
                success=False,
                message=injury or "Foul failed",
                dice_rolls=dice_rolls
            )
        
        result = ActionResult(
            success=True,
            message=f"Boot! Injury: {injury or 'none'}",
            dice_rolls=dice_rolls,
            injury_result=injury
        )

        game_state.turn.boot_used = True
        attacker.has_acted = True
        game_state.add_event(result.message)
        
        return result
