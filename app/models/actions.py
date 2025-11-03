"""Action request and result models"""
from typing import Optional, Any
from pydantic import BaseModel, Field
from app.models.enums import ActionType, BlockResult, PassResult
from app.models.pitch import Position


class DiceRoll(BaseModel):
    """Result of a dice roll"""
    type: str = Field(..., description="Type of roll (dodge, block, pass, etc.)")
    result: int = Field(..., description="Dice result")
    target: Optional[int] = Field(None, description="Target number needed")
    success: bool = Field(..., description="Whether the roll succeeded")
    modifiers: dict[str, int] = Field(default_factory=dict, description="Applied modifiers")


class ActionRequest(BaseModel):
    """Request to perform an action"""
    action_type: ActionType
    player_id: str
    
    # Target position (for moves, blocks if not adjacent)
    target_position: Optional[Position] = None
    
    # For movement: path of positions
    path: Optional[list[Position]] = None
    
    # For blocks/blitz: target player
    target_player_id: Optional[str] = None
    
    # For pass/hand-off: target position or player
    target_receiver_id: Optional[str] = None
    
    # Optional: request to use reroll
    use_reroll: bool = False


class ActionResult(BaseModel):
    """Result of an action execution"""
    success: bool
    message: str
    
    # Dice rolls that occurred
    dice_rolls: list[DiceRoll] = Field(default_factory=list)
    
    # State changes
    turnover: bool = False
    player_moved: Optional[str] = None
    new_position: Optional[Position] = None
    
    # Block results
    block_result: Optional[BlockResult] = None
    defender_knocked_down: bool = False
    attacker_knocked_down: bool = False
    
    # Ball handling
    ball_picked_up: bool = False
    ball_dropped: bool = False
    ball_caught: bool = False
    
    # Pass results
    pass_result: Optional[PassResult] = None
    
    # Injuries
    armor_broken: bool = False
    injury_result: Optional[str] = None
    
    # Additional context
    details: dict[str, Any] = Field(default_factory=dict)


class SetupRequest(BaseModel):
    """Request to set up players during kick-off"""
    team_id: str
    positions: dict[str, Position] = Field(
        ...,
        description="Map of player_id to Position"
    )


class ValidActionsResponse(BaseModel):
    """Response showing all valid actions for current state"""
    current_team: str
    phase: str

    # Action limits
    can_blitz: bool
    can_pass: bool
    can_hand_off: bool
    can_foul: bool

    # Players who can act
    movable_players: list[str] = Field(default_factory=list)
    blockable_targets: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Map of player_id to list of valid block targets"
    )

    # Ball state
    ball_carrier: Optional[str] = None
    ball_on_ground: bool = False
    ball_position: Optional[Position] = None


class BudgetStatus(BaseModel):
    """Budget information for a team"""
    initial: int = Field(..., description="Initial budget amount")
    spent: int = Field(..., description="Amount spent so far")
    remaining: int = Field(..., description="Remaining budget")
    purchases: list[str] = Field(default_factory=list, description="Purchase history")


class PurchaseResult(BaseModel):
    """Result of a purchase action"""
    success: bool = Field(..., description="Whether purchase succeeded")
    item_purchased: str = Field(..., description="Name of item purchased")
    cost: int = Field(..., description="Cost of the item")
    budget_status: BudgetStatus = Field(..., description="Updated budget status")
    message: str = Field(..., description="Human-readable result message")


class AvailablePosition(BaseModel):
    """Information about a player position available for purchase"""
    position_key: str = Field(..., description="Key to use when purchasing (e.g., 'constable')")
    role: str = Field(..., description="Display name (e.g., 'Constable')")
    cost: int = Field(..., description="Cost in gold")
    quantity_limit: int = Field(..., description="Maximum allowed of this position")
    quantity_owned: int = Field(..., description="Number already purchased")
    can_afford: bool = Field(..., description="Whether team can afford this")
    stats: dict[str, Any] = Field(default_factory=dict, description="Player stats")


class AvailablePositionsResponse(BaseModel):
    """Response showing available positions for purchase"""
    team_id: str
    team_type: str
    budget_status: BudgetStatus
    positions: list[AvailablePosition] = Field(default_factory=list)
    reroll_cost: int = Field(..., description="Cost of a team reroll")
    rerolls_owned: int = Field(..., description="Number of rerolls owned")
    rerolls_max: int = Field(..., description="Maximum rerolls allowed")
    can_afford_reroll: bool = Field(..., description="Whether team can afford a reroll")
