"""Game state model"""
from typing import Optional
from datetime import datetime
import logging
from pydantic import BaseModel, Field
from app.models.enums import GamePhase, TeamType
from app.models.pitch import Pitch
from app.models.player import Player
from app.models.team import Team


event_logger = logging.getLogger("app.game.events")
message_logger = logging.getLogger("app.game.chat")


class GameMessage(BaseModel):
    """Message sent during a game"""
    sender_id: str = Field(description="ID of the sender (player or team)")
    sender_name: str = Field(description="Display name of sender")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    turn_number: Optional[int] = Field(None, description="Turn when message was sent")
    game_phase: str = Field(description="Phase when message was sent")


class TurnState(BaseModel):
    """Current turn tracking"""
    half: int = Field(1, ge=1, le=2, description="Current half (1 or 2)")
    team_turn: int = Field(0, ge=0, le=8, description="Turn number for active team")
    active_team_id: str

    # Action tracking (using new Discworld terminology)
    charge_used: bool = False  # was blitz_used
    hurl_used: bool = False  # was pass_used
    quick_pass_used: bool = False  # was hand_off_used
    boot_used: bool = False  # was foul_used


class GameState(BaseModel):
    """Complete game state"""
    game_id: str
    phase: GamePhase = GamePhase.DEPLOYMENT
    
    # Teams
    team1: Team
    team2: Team
    
    # Join status
    team1_joined: bool = False
    team2_joined: bool = False
    game_started: bool = False
    
    # Players (all players in the game)
    players: dict[str, Player] = Field(default_factory=dict)
    
    # Pitch state
    pitch: Pitch = Field(default_factory=Pitch)
    
    # Turn tracking
    turn: Optional[TurnState] = None
    
    # Game history
    event_log: list[str] = Field(default_factory=list)
    messages: list[GameMessage] = Field(default_factory=list)
    
    @property
    def players_ready(self) -> bool:
        """Check if both teams have joined"""
        return self.team1_joined and self.team2_joined
    
    def get_active_team(self) -> Team:
        """Get the currently active team"""
        if not self.turn:
            raise ValueError("No active turn")
        
        if self.turn.active_team_id == self.team1.id:
            return self.team1
        elif self.turn.active_team_id == self.team2.id:
            return self.team2
        else:
            raise ValueError(f"Invalid active team ID: {self.turn.active_team_id}")
    
    def get_inactive_team(self) -> Team:
        """Get the currently inactive team"""
        if not self.turn:
            raise ValueError("No active turn")
        
        if self.turn.active_team_id == self.team1.id:
            return self.team2
        else:
            return self.team1
    
    def get_team_by_id(self, team_id: str) -> Team:
        """Get team by ID"""
        if team_id == self.team1.id:
            return self.team1
        elif team_id == self.team2.id:
            return self.team2
        else:
            raise ValueError(f"Team not found: {team_id}")
    
    def get_player(self, player_id: str) -> Player:
        """Get player by ID"""
        if player_id not in self.players:
            raise ValueError(f"Player not found: {player_id}")
        return self.players[player_id]
    
    def get_team_players(self, team_id: str) -> list[Player]:
        """Get all players for a team"""
        return [p for p in self.players.values() if p.team_id == team_id]
    
    def is_player_on_active_team(self, player_id: str) -> bool:
        """Check if player belongs to active team"""
        if not self.turn:
            return False
        player = self.get_player(player_id)
        return player.team_id == self.turn.active_team_id
    
    def add_event(self, event: str) -> None:
        """Add event to game log"""
        self.event_log.append(event)
        turn_number = self.turn.team_turn if self.turn else "-"
        active_team = self.turn.active_team_id if self.turn else "-"
        event_logger.info(
            "[%s] phase=%s turn=%s active_team=%s | %s",
            self.game_id,
            self.phase.value,
            turn_number,
            active_team,
            event,
        )
    
    def switch_turn(self) -> None:
        """Switch to the other team's turn"""
        if not self.turn:
            raise ValueError("No active turn")
        
        # Reset active team's players
        active_team = self.get_active_team()
        for player in self.get_team_players(active_team.id):
            player.reset_turn()
        
        # Reset action tracking
        self.turn.charge_used = False
        self.turn.hurl_used = False
        self.turn.quick_pass_used = False
        self.turn.boot_used = False
        
        # Switch to other team
        if self.turn.active_team_id == self.team1.id:
            self.turn.active_team_id = self.team2.id
        else:
            self.turn.active_team_id = self.team1.id
            # Increment turn counter when returning to team 1
            self.turn.team_turn += 1
        
        # Reset team re-rolls
        active_team = self.get_active_team()
        active_team.reset_rerolls()
        
        # Check if half is over
        if self.turn.team_turn > 8:
            self.end_half()
    
    def end_half(self) -> None:
        """End the current half"""
        if not self.turn:
            return
        
        if self.turn.half == 1:
            self.turn.half = 2
            self.turn.team_turn = 0
            self.phase = GamePhase.INTERMISSION
            self.add_event("Intermission!")
        else:
            self.phase = GamePhase.CONCLUDED
            self.add_event("Match concluded!")
    
    def add_message(self, sender_id: str, sender_name: str, content: str) -> GameMessage:
        """Add a message to the game"""
        turn_number = self.turn.team_turn if self.turn else None
        message = GameMessage(
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            turn_number=turn_number,
            game_phase=self.phase.value
        )
        self.messages.append(message)
        message_logger.info(
            "[%s] %s (%s) turn=%s phase=%s | %s",
            self.game_id,
            sender_name,
            sender_id,
            turn_number if turn_number is not None else "-",
            self.phase.value,
            content,
        )
        return message
    
    def reset_to_setup(self) -> None:
        """Reset game to deployment phase, preserving join status and messages"""
        # Clear pitch
        self.pitch = Pitch()

        # Clear players
        self.players = {}

        # Reset phase
        self.phase = GamePhase.DEPLOYMENT
        self.game_started = False

        # Clear turn state
        self.turn = None

        # Keep join status and messages (preserve history)
        self.add_event("Game reset to deployment phase")
    
    def start_game(self) -> None:
        """Start the game"""
        if not self.players_ready:
            raise ValueError("Both teams must join before starting")

        self.phase = GamePhase.OPENING_SCRAMBLE
        self.game_started = True
        self.turn = TurnState(
            half=1,
            team_turn=0,
            active_team_id=self.team1.id
        )
        self.add_event("The Opening Scramble begins!")
