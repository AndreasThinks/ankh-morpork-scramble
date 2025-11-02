"""Game manager - orchestrates game state and rules"""
import uuid
from typing import Optional
from app.models.game_state import GameState, TurnState
from app.models.team import Team, TEAM_ROSTERS
from app.models.player import Player
from app.models.enums import TeamType, GamePhase
from app.models.pitch import Position
from app.state.action_executor import ActionExecutor


# End zone scoring thresholds
# Team 1 moves towards the right side (higher X values) to score
TEAM1_END_ZONE_X = 23  # Team 1 scores when ball carrier reaches x >= 23
# Team 2 moves towards the left side (lower X values) to score
TEAM2_END_ZONE_X = 2   # Team 2 scores when ball carrier reaches x <= 2


class GameManager:
    """Manages game creation, state transitions, and rule enforcement"""
    
    def __init__(self):
        self.games: dict[str, GameState] = {}
        self.executor = ActionExecutor()
    
    def create_game(self, game_id: Optional[str] = None) -> GameState:
        """Create a new game"""
        if game_id is None:
            game_id = str(uuid.uuid4())
        
        # Create placeholder teams - will be set during join
        team1 = Team(
            id="team1",
            name="Team 1",
            team_type=TeamType.CITY_WATCH,
            rerolls_total=3
        )
        
        team2 = Team(
            id="team2",
            name="Team 2",
            team_type=TeamType.UNSEEN_UNIVERSITY,
            rerolls_total=3
        )
        
        game_state = GameState(
            game_id=game_id,
            phase=GamePhase.SETUP,
            team1=team1,
            team2=team2
        )
        
        self.games[game_id] = game_state
        return game_state
    
    def get_game(self, game_id: str) -> Optional[GameState]:
        """Get game by ID"""
        return self.games.get(game_id)
    
    def setup_team(
        self,
        game_id: str,
        team_id: str,
        team_type: TeamType,
        player_positions: dict[str, str]  # position_key -> count
    ) -> GameState:
        """Set up a team with players"""
        game_state = self.get_game(game_id)
        if not game_state:
            raise ValueError(f"Game {game_id} not found")
        
        team = game_state.get_team_by_id(team_id)
        team.team_type = team_type
        
        roster = TEAM_ROSTERS[team_type]
        
        # Create players
        player_count = 0
        for position_key, count_str in player_positions.items():
            count = int(count_str)
            if position_key not in roster.positions:
                raise ValueError(f"Invalid position: {position_key}")
            
            position = roster.positions[position_key]
            
            for i in range(count):
                player_id = f"{team_id}_player_{player_count}"
                player = Player(
                    id=player_id,
                    team_id=team_id,
                    position=position,
                    skills=list(position.skills)
                )
                
                game_state.players[player_id] = player
                team.player_ids.append(player_id)
                player_count += 1
        
        return game_state
    
    def place_players(
        self,
        game_id: str,
        team_id: str,
        positions: dict[str, Position]
    ) -> GameState:
        """Place players on the pitch during setup"""
        game_state = self.get_game(game_id)
        if not game_state:
            raise ValueError(f"Game {game_id} not found")
        
        # Validate and place players
        for player_id, position in positions.items():
            player = game_state.get_player(player_id)
            
            if player.team_id != team_id:
                raise ValueError(f"Player {player_id} does not belong to team {team_id}")
            
            game_state.pitch.player_positions[player_id] = position
        
        return game_state
    
    def start_game(self, game_id: str) -> GameState:
        """Start the game"""
        game_state = self.get_game(game_id)
        if not game_state:
            raise ValueError(f"Game {game_id} not found")
        
        if game_state.phase != GamePhase.SETUP:
            raise ValueError(f"Game must be in setup phase to start")
        
        game_state.start_game()
        
        # Place ball at center of pitch
        game_state.pitch.place_ball(Position(x=13, y=7))
        
        return game_state
    
    def end_turn(self, game_id: str) -> GameState:
        """End the current turn and switch to other team"""
        game_state = self.get_game(game_id)
        if not game_state:
            raise ValueError(f"Game {game_id} not found")
        
        if not game_state.turn:
            raise ValueError("No active turn")
        
        game_state.switch_turn()
        game_state.add_event(f"Turn ended. Now {game_state.get_active_team().name}'s turn")
        
        return game_state
    
    def check_scoring(self, game_id: str) -> Optional[str]:
        """Check if a team has scored and handle it"""
        game_state = self.get_game(game_id)
        if not game_state:
            return None
        
        if not game_state.pitch.ball_carrier:
            return None
        
        carrier = game_state.get_player(game_state.pitch.ball_carrier)
        carrier_pos = game_state.pitch.player_positions.get(carrier.id)
        
        if not carrier_pos:
            return None
        
        # Check if ball carrier has reached the opposing team's end zone
        scored_team = None

        if carrier.team_id == game_state.team1.id and carrier_pos.x >= TEAM1_END_ZONE_X:
            scored_team = game_state.team1
        elif carrier.team_id == game_state.team2.id and carrier_pos.x <= TEAM2_END_ZONE_X:
            scored_team = game_state.team2
        
        if scored_team:
            scored_team.add_score()
            game_state.add_event(f"{scored_team.name} scored!")
            
            # Reset for new drive
            game_state.pitch.ball_carrier = None
            game_state.pitch.place_ball(Position(x=13, y=7))
            
            return scored_team.id
        
        return None
