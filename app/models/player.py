"""Player models and statistics"""
from typing import Optional
from pydantic import BaseModel, Field
from app.models.enums import PlayerState, SkillType


class PlayerPosition(BaseModel):
    """Player roster position definition"""
    role: str
    cost: int
    max_quantity: int = Field(..., description="Maximum allowed of this position (e.g., 16 for constables, 1 for stars)")
    ma: int = Field(..., description="Movement Allowance")
    st: int = Field(..., description="Strength")
    ag: str = Field(..., description="Agility (e.g., '3+')")
    pa: str = Field(..., description="Passing Ability (e.g., '4+')")
    av: str = Field(..., description="Armour Value (e.g., '9+')")
    skills: list[SkillType] = Field(default_factory=list)
    primary: list[str] = Field(default_factory=list, description="Primary skill categories")
    secondary: list[str] = Field(default_factory=list, description="Secondary skill categories")
    is_star_player: bool = Field(default=False, description="True for unique named star players")


class Player(BaseModel):
    """Individual player instance in a game"""
    id: str
    team_id: str
    position: PlayerPosition
    number: Optional[int] = Field(
        default=None,
        ge=1,
        description="Jersey number used for display/logging",
    )

    # Current state
    state: PlayerState = PlayerState.STANDING

    # Movement tracking
    movement_used: int = 0
    has_acted: bool = False

    # Skills and modifications
    skills: list[SkillType] = Field(default_factory=list)

    # Injuries and effects
    stunned_until_turn: Optional[int] = None

    @property
    def position_name(self) -> str:
        """Return the roster role name for this player."""
        return self.position.role

    @property
    def display_number(self) -> Optional[int]:
        """Best-effort jersey number for logging and summaries."""
        if self.number is not None:
            return self.number

        suffix = self.id.rsplit("_", 1)[-1]
        if suffix.isdigit():
            # Convert zero-based identifier to a human-friendly number
            return int(suffix) + 1
        return None

    @property
    def display_name(self) -> str:
        """Formatted name combining position role and jersey number if available."""
        number = self.display_number
        if number is not None:
            return f"{self.position_name} #{number}"
        return self.position_name
    
    @property
    def is_active(self) -> bool:
        """Check if player can take actions"""
        return self.state in [PlayerState.STANDING, PlayerState.PRONE]
    
    @property
    def is_standing(self) -> bool:
        """Check if player is standing"""
        return self.state == PlayerState.STANDING
    
    @property
    def movement_remaining(self) -> int:
        """Get remaining movement allowance"""
        return max(0, self.position.ma - self.movement_used)
    
    def reset_turn(self) -> None:
        """Reset per-turn tracking"""
        self.movement_used = 0
        self.has_acted = False
        
        # Remove stunned state if turn has passed
        if self.state == PlayerState.STUNNED:
            self.state = PlayerState.PRONE
    
    def use_movement(self, squares: int) -> None:
        """Use movement points"""
        self.movement_used += squares
    
    def stand_up(self) -> None:
        """Stand up from prone (costs 3 MA)"""
        if self.state != PlayerState.PRONE:
            raise ValueError("Player must be prone to stand up")
        
        if self.movement_used + 3 > self.position.ma:
            raise ValueError("Not enough movement to stand up")
        
        self.state = PlayerState.STANDING
        self.movement_used += 3
    
    def knock_down(self) -> None:
        """Knock player down"""
        if self.state == PlayerState.STANDING:
            self.state = PlayerState.PRONE
    
    def stun(self) -> None:
        """Stun the player"""
        self.state = PlayerState.STUNNED
    
    def knock_out(self) -> None:
        """Knock out the player"""
        self.state = PlayerState.KNOCKED_OUT
    
    def casualty(self) -> None:
        """Remove player as casualty"""
        self.state = PlayerState.CASUALTY
    
    def has_skill(self, skill: SkillType) -> bool:
        """Check if player has a specific skill"""
        return skill in self.skills or skill in self.position.skills
    
    def get_agility_target(self) -> int:
        """Parse agility string to target number (e.g., '3+' -> 3)"""
        return int(self.position.ag.replace('+', ''))
    
    def get_passing_target(self) -> int:
        """Parse passing ability string to target number"""
        return int(self.position.pa.replace('+', ''))
    
    def get_armor_value(self) -> int:
        """Parse armor value string to target number"""
        return int(self.position.av.replace('+', ''))
