# Ankh-Morpork Scramble - FastAPI Server

> **DISCLAIMER**: This is an unofficial, non-commercial fan project created purely for entertainment and educational purposes. It is inspired by Games Workshop's Blood Bowl and Terry Pratchett's Discworld universe. This project is not affiliated with, endorsed by, or connected to Games Workshop Limited, Terry Pratchett's estate, or any official Discworld or Blood Bowl properties. All rights to Blood Bowl belong to Games Workshop. All rights to Discworld characters and settings belong to the Terry Pratchett estate. This is a tribute project by fans, for fans.

A turn-based sports game server inspired by Blood Bowl, featuring the City Watch vs. Wizards of Unseen University.

## Installation

This project uses UV for package management:

```bash
# Install dependencies
uv pip install -e .

# Or install with dev dependencies
uv pip install -e ".[dev]"
```

## Running the Server

```bash
# Run with uvicorn
uvicorn app.main:app --reload

# Or run the main file directly
python -m app.main
```

The server will start at `http://localhost:8000`

## API Documentation

Once the server is running, visit:
- Interactive API docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

## API Endpoints

### Game Management

- `POST /game` - Create a new game
- `GET /game/{game_id}` - Get current game state
- `POST /game/{game_id}/setup-team` - Set up a team with roster
- `POST /game/{game_id}/place-players` - Place players on pitch
- `POST /game/{game_id}/start` - Start the game
- `POST /game/{game_id}/end-turn` - End current turn

### Game Actions

- `POST /game/{game_id}/action` - Execute an action (move, block, pass, etc.)
- `GET /game/{game_id}/valid-actions` - Get all valid actions for current state
- `POST /game/{game_id}/reroll` - Use a team re-roll
- `GET /game/{game_id}/history` - Get game event log

## Example Usage

### 1. Create a Game

```bash
curl -X POST http://localhost:8000/game
```

Response includes `game_id`.

### 2. Setup Teams

```bash
# Setup Team 1 (City Watch)
curl -X POST "http://localhost:8000/game/{game_id}/setup-team?team_id=team1&team_type=city_watch" \
  -H "Content-Type: application/json" \
  -d '{
    "constable": "5",
    "clerk_runner": "1",
    "fleet_recruit": "2",
    "watch_sergeant": "3"
  }'

# Setup Team 2 (Unseen University)
curl -X POST "http://localhost:8000/game/{game_id}/setup-team?team_id=team2&team_type=unseen_university" \
  -H "Content-Type: application/json" \
  -d '{
    "apprentice_wizard": "8",
    "senior_wizard": "2",
    "animated_gargoyle": "1"
  }'
```

### 3. Place Players on Pitch

```bash
curl -X POST http://localhost:8000/game/{game_id}/place-players \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "team1",
    "positions": {
      "team1_player_0": {"x": 5, "y": 7},
      "team1_player_1": {"x": 6, "y": 6},
      "team1_player_2": {"x": 6, "y": 8}
    }
  }'
```

### 4. Start the Game

```bash
curl -X POST http://localhost:8000/game/{game_id}/start
```

### 5. Execute Actions

```bash
# Move a player
curl -X POST http://localhost:8000/game/{game_id}/action \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "move",
    "player_id": "team1_player_0",
    "path": [
      {"x": 6, "y": 7},
      {"x": 7, "y": 7}
    ]
  }'

# Block an opponent
curl -X POST http://localhost:8000/game/{game_id}/action \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "block",
    "player_id": "team1_player_1",
    "target_player_id": "team2_player_0"
  }'

# Pass the ball
curl -X POST http://localhost:8000/game/{game_id}/action \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "pass",
    "player_id": "team1_player_0",
    "target_position": {"x": 15, "y": 7}
  }'
```

### 6. Get Valid Actions

```bash
curl http://localhost:8000/game/{game_id}/valid-actions
```

### 7. End Turn

```bash
curl -X POST http://localhost:8000/game/{game_id}/end-turn
```

## Game Features

### Implemented

- ✅ Turn-based gameplay with automatic turnover detection
- ✅ Player movement with dodge and rush mechanics
- ✅ Ball handling (pickup, pass, catch, hand-off, scatter)
- ✅ Combat system (block, armor, injury rolls)
- ✅ Special actions (blitz, foul)
- ✅ Team rosters (City Watch, Unseen University)
- ✅ Skill system with themed abilities
- ✅ Score tracking and game phases
- ✅ Team re-rolls
- ✅ Complete game state management

### Action Types

- **Move**: Move a player along a path (with dodge rolls if needed)
- **Stand Up**: Stand up from prone (costs 3 MA)
- **Block**: Attack an adjacent opponent
- **Blitz**: Move + Block (once per turn)
- **Pass**: Throw the ball (once per turn)
- **Hand-off**: Give ball to adjacent teammate (once per turn)
- **Foul**: Attack a prone opponent (once per turn)

### Teams

**City Watch**
- Constable: Basic lineman (MA 6, ST 3, AG 3+, AV 9+)
- Clerk-Runner: Fast passer with ball handling skills
- Fleet Recruit: Speedy catcher (MA 8)
- Watch Sergeant: Stronger blocker with Drill-Hardened skill

**Unseen University Wizards**
- Apprentice Wizard: Small and sneaky with dodge abilities
- Senior Wizard: Slow but strong with grappling skills
- Animated Gargoyle: Extremely strong but mindless (ST 5)

## Architecture

```
app/
├── models/          # Pydantic data models
│   ├── enums.py     # Game enumerations
│   ├── player.py    # Player models
│   ├── team.py      # Team and roster definitions
│   ├── pitch.py     # Pitch and position models
│   ├── actions.py   # Action request/result models
│   └── game_state.py # Complete game state
├── game/            # Core game logic
│   ├── dice.py      # Dice rolling system
│   ├── movement.py  # Movement and dodging
│   ├── ball_handling.py # Ball mechanics
│   └── combat.py    # Block and injury resolution
├── state/           # State management
│   ├── action_executor.py # Execute validated actions
│   └── game_manager.py    # Game orchestration
└── main.py          # FastAPI application
```

## Game Rules

See [rules.md](rules.md) for complete game rules and mechanics.

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests (when implemented)
pytest

# Run with hot reload
uvicorn app.main:app --reload
```

## License

MIT

## Credits

Based on Blood Bowl rules, adapted for the Discworld universe by Terry Pratchett.
