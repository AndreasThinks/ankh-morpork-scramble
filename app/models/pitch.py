"""Pitch and position models"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Position(BaseModel):
    """Position on the pitch (26x15 grid)"""
    x: int = Field(..., ge=0, lt=26, description="X coordinate (0-25)")
    y: int = Field(..., ge=0, lt=15, description="Y coordinate (0-14)")
    
    def __eq__(self, other):
        if not isinstance(other, Position):
            return False
        return self.x == other.x and self.y == other.y
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def distance_to(self, other: "Position") -> int:
        """Calculate Manhattan distance to another position"""
        return abs(self.x - other.x) + abs(self.y - other.y)
    
    def is_adjacent(self, other: "Position") -> bool:
        """Check if position is adjacent (including diagonals)"""
        return abs(self.x - other.x) <= 1 and abs(self.y - other.y) <= 1 and self != other


class Pitch(BaseModel):
    """Game pitch with player positions and ball state"""
    # Player positions: player_id -> Position
    player_positions: dict[str, Position] = Field(default_factory=dict)
    
    # Ball state
    ball_position: Optional[Position] = None
    ball_carrier: Optional[str] = None  # player_id holding the ball
    
    @field_validator('ball_position')
    @classmethod
    def validate_ball_position(cls, v):
        """Ensure ball position is within pitch bounds"""
        if v is not None:
            if not (0 <= v.x < 26 and 0 <= v.y < 15):
                raise ValueError("Ball position must be within pitch bounds (0-25, 0-14)")
        return v
    
    def get_player_at(self, pos: Position) -> Optional[str]:
        """Get player ID at a specific position"""
        for player_id, player_pos in self.player_positions.items():
            if player_pos == pos:
                return player_id
        return None
    
    def is_occupied(self, pos: Position) -> bool:
        """Check if a position is occupied by a player"""
        return self.get_player_at(pos) is not None
    
    def get_adjacent_players(self, pos: Position) -> list[str]:
        """Get all player IDs adjacent to a position"""
        adjacent = []
        for player_id, player_pos in self.player_positions.items():
            if player_pos.is_adjacent(pos):
                adjacent.append(player_id)
        return adjacent
    
    def move_player(self, player_id: str, new_pos: Position) -> None:
        """Move a player to a new position"""
        if player_id not in self.player_positions:
            raise ValueError(f"Player {player_id} not found on pitch")
        
        if self.is_occupied(new_pos):
            raise ValueError(f"Position {new_pos} is already occupied")
        
        self.player_positions[player_id] = new_pos
        
        # If player is carrying the ball, update ball position
        if self.ball_carrier == player_id:
            self.ball_position = new_pos
    
    def place_ball(self, pos: Position) -> None:
        """Place the ball at a position (not carried)"""
        self.ball_position = pos
        self.ball_carrier = None
    
    def pick_up_ball(self, player_id: str) -> None:
        """Player picks up the ball"""
        if player_id not in self.player_positions:
            raise ValueError(f"Player {player_id} not found on pitch")
        
        player_pos = self.player_positions[player_id]
        if self.ball_position != player_pos:
            raise ValueError(f"Ball is not at player position")
        
        self.ball_carrier = player_id
        self.ball_position = player_pos
    
    def drop_ball(self) -> None:
        """Current carrier drops the ball"""
        if self.ball_carrier:
            # Ball stays at carrier's position
            if self.ball_carrier in self.player_positions:
                self.ball_position = self.player_positions[self.ball_carrier]
            self.ball_carrier = None
