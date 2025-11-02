"""Pathfinding and path risk assessment"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from app.models.game_state import GameState
from app.models.pitch import Position
from app.models.player import Player
from app.game.movement import MovementHandler


class SquareRisk(BaseModel):
    """Risk assessment for a single square in a path"""
    position: Position
    requires_dodge: bool
    tackle_zones_leaving: int
    tackle_zones_entering: int
    dodge_target: Optional[int] = None
    dodge_modifiers: dict[str, int] = {}
    success_probability: Optional[float] = None
    is_rush_square: bool
    is_occupied: bool = False
    out_of_bounds: bool = False


class PathSuggestion(BaseModel):
    """Complete path suggestion with risk assessment"""
    player_id: str
    from_position: Position
    target_position: Position
    path: list[Position]
    movement_cost: int
    requires_rushing: bool
    rush_squares: int
    total_risk_score: float  # 0.0 (safe) to 1.0 (very risky)
    risks: list[SquareRisk]
    is_valid: bool
    error_message: Optional[str] = None


class PathFinder:
    """Calculates paths and assesses movement risk"""
    
    def __init__(self, movement_handler: MovementHandler):
        self.movement = movement_handler
    
    def calculate_straight_line_path(
        self,
        from_pos: Position,
        to_pos: Position
    ) -> list[Position]:
        """
        Calculate a straight-line path between two positions.
        Uses simple step-by-step approach - can be enhanced with A* later.
        """
        if from_pos == to_pos:
            return []
        
        path = []
        current_x, current_y = from_pos.x, from_pos.y
        target_x, target_y = to_pos.x, to_pos.y
        
        # Calculate direction
        dx = 1 if target_x > current_x else (-1 if target_x < current_x else 0)
        dy = 1 if target_y > current_y else (-1 if target_y < current_y else 0)
        
        # Move step by step until we reach target
        while current_x != target_x or current_y != target_y:
            # Move towards target (one step at a time)
            if current_x != target_x:
                current_x += dx
            if current_y != target_y:
                current_y += dy
            
            path.append(Position(x=current_x, y=current_y))
        
        return path
    
    def assess_square_risk(
        self,
        game_state: GameState,
        player: Player,
        from_pos: Position,
        to_pos: Position,
        is_rush_square: bool
    ) -> SquareRisk:
        """Assess the risk of moving to a specific square"""
        
        # Check if out of bounds
        out_of_bounds = not (0 <= to_pos.x < 26 and 0 <= to_pos.y < 15)
        
        # Check if occupied
        is_occupied = game_state.pitch.is_occupied(to_pos) if not out_of_bounds else False
        
        # Count tackle zones
        tackle_zones_leaving = self.movement.get_tackle_zones(
            game_state, player.team_id, from_pos
        ) if not out_of_bounds else 0
        
        tackle_zones_entering = self.movement.get_tackle_zones(
            game_state, player.team_id, to_pos
        ) if not out_of_bounds else 0
        
        # Determine if dodge is required
        requires_dodge = tackle_zones_leaving > 0
        
        # Calculate dodge parameters
        dodge_target = None
        dodge_modifiers = {}
        success_probability = None
        
        if requires_dodge:
            dodge_target = player.get_agility_target()
            dodge_modifiers = self.movement.calculate_dodge_modifiers(
                game_state, player, from_pos, to_pos
            )
            
            # Calculate success probability
            # Base probability: (7 - target) / 6
            # Modified by modifiers
            total_modifier = sum(dodge_modifiers.values())
            effective_target = max(2, min(6, dodge_target - total_modifier))
            success_probability = (7 - effective_target) / 6
        
        # Rush also has risk
        if is_rush_square:
            rush_success = 5 / 6  # 2+ on d6
            if success_probability is not None:
                # Combine probabilities
                success_probability *= rush_success
            else:
                success_probability = rush_success
        
        return SquareRisk(
            position=to_pos,
            requires_dodge=requires_dodge,
            tackle_zones_leaving=tackle_zones_leaving,
            tackle_zones_entering=tackle_zones_entering,
            dodge_target=dodge_target,
            dodge_modifiers=dodge_modifiers,
            success_probability=success_probability,
            is_rush_square=is_rush_square,
            is_occupied=is_occupied,
            out_of_bounds=out_of_bounds
        )
    
    def suggest_path(
        self,
        game_state: GameState,
        player_id: str,
        target_pos: Position
    ) -> PathSuggestion:
        """
        Suggest a path for a player to reach a target position.
        Returns path with complete risk assessment.
        """
        player = game_state.get_player(player_id)
        current_pos = game_state.pitch.player_positions.get(player_id)
        
        if not current_pos:
            return PathSuggestion(
                player_id=player_id,
                from_position=Position(x=0, y=0),
                target_position=target_pos,
                path=[],
                movement_cost=0,
                requires_rushing=False,
                rush_squares=0,
                total_risk_score=1.0,
                risks=[],
                is_valid=False,
                error_message="Player not on pitch"
            )
        
        # Calculate straight-line path
        path = self.calculate_straight_line_path(current_pos, target_pos)
        
        if not path:
            return PathSuggestion(
                player_id=player_id,
                from_position=current_pos,
                target_position=target_pos,
                path=[],
                movement_cost=0,
                requires_rushing=False,
                rush_squares=0,
                total_risk_score=0.0,
                risks=[],
                is_valid=True,
                error_message=None
            )
        
        # Calculate movement cost
        movement_cost = len(path)
        normal_movement = min(movement_cost, player.movement_remaining)
        rush_squares = movement_cost - normal_movement
        requires_rushing = rush_squares > 0
        
        # Check if rushing is feasible
        if rush_squares > 2:
            return PathSuggestion(
                player_id=player_id,
                from_position=current_pos,
                target_position=target_pos,
                path=path,
                movement_cost=movement_cost,
                requires_rushing=True,
                rush_squares=rush_squares,
                total_risk_score=1.0,
                risks=[],
                is_valid=False,
                error_message=f"Path requires {rush_squares} rush squares (max 2)"
            )
        
        # Assess risk for each square
        risks = []
        from_pos = current_pos
        total_risk_score = 0.0
        is_valid = True
        error_message = None
        
        for i, to_pos in enumerate(path):
            is_rush = i >= normal_movement
            risk = self.assess_square_risk(game_state, player, from_pos, to_pos, is_rush)
            risks.append(risk)
            
            # Check validity
            if risk.out_of_bounds:
                is_valid = False
                error_message = f"Square {to_pos} is out of bounds"
                break
            
            if risk.is_occupied:
                is_valid = False
                error_message = f"Square {to_pos} is occupied"
                break
            
            # Calculate risk contribution
            if risk.success_probability is not None:
                # Risk is 1 - success probability
                square_risk = 1.0 - risk.success_probability
                total_risk_score += square_risk
            
            from_pos = to_pos
        
        # Normalize total risk score (0.0 = safe, 1.0 = very risky)
        if len(risks) > 0:
            total_risk_score = min(1.0, total_risk_score / len(risks))
        
        return PathSuggestion(
            player_id=player_id,
            from_position=current_pos,
            target_position=target_pos,
            path=path,
            movement_cost=movement_cost,
            requires_rushing=requires_rushing,
            rush_squares=rush_squares,
            total_risk_score=total_risk_score,
            risks=risks,
            is_valid=is_valid,
            error_message=error_message
        )
