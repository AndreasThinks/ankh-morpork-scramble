"""Action request and result models"""
from typing import Optional, Any
from pydantic import BaseModel, Field, model_validator
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

    @model_validator(mode='after')
    def validate_action_requirements(self) -> 'ActionRequest':
        """
        Validate that required fields are present for each action type.

        This provides early validation before attempting to execute the action,
        giving clearer error messages to LLM agents about what parameters are missing.
        """
        action = self.action_type

        # MOVE requires path
        if action == ActionType.MOVE:
            if not self.path:
                raise ValueError("MOVE action requires path (list of Position objects)")

        # SCUFFLE (block) requires target_player_id
        elif action == ActionType.SCUFFLE:
            if not self.target_player_id:
                raise ValueError("SCUFFLE action requires target_player_id (adjacent opponent)")

        # CHARGE (blitz) requires target_player_id (and optionally target_position for movement)
        elif action == ActionType.CHARGE:
            if not self.target_player_id:
                raise ValueError("CHARGE action requires target_player_id (opponent to block)")

        # HURL (pass) requires target_receiver_id or target_position
        elif action == ActionType.HURL:
            if not self.target_receiver_id and not self.target_position:
                raise ValueError("HURL action requires target_receiver_id or target_position")

        # QUICK_PASS (hand-off) requires target_receiver_id
        elif action == ActionType.QUICK_PASS:
            if not self.target_receiver_id:
                raise ValueError("QUICK_PASS action requires target_receiver_id (adjacent teammate)")

        # BOOT (foul) requires target_player_id
        elif action == ActionType.BOOT:
            if not self.target_player_id:
                raise ValueError("BOOT action requires target_player_id (prone adjacent opponent)")

        # STAND_UP doesn't require additional parameters

        return self


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

    # Action limits (using Discworld terminology)
    can_charge: bool  # was can_blitz
    can_hurl: bool  # was can_pass
    can_quick_pass: bool  # was can_hand_off
    can_boot: bool  # was can_foul

    # Legacy field names maintained for backwards compatibility with the API
    can_blitz: bool | None = None
    can_pass: bool | None = None
    can_hand_off: bool | None = None
    can_foul: bool | None = None

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

    @model_validator(mode="after")
    def populate_legacy_flags(self) -> "ValidActionsResponse":
        """Ensure legacy flag names mirror the new Discworld terminology."""

        self.can_blitz = self.can_charge
        self.can_pass = self.can_hurl
        self.can_hand_off = self.can_quick_pass
        self.can_foul = self.can_boot
        return self


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
