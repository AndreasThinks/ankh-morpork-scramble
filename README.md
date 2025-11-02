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

## Environment Configuration

Use the provided sample file to configure environment variables locally:

```bash
cp .env.example .env
```

Populate at least one of `OPENROUTER_API_KEY` or `openrouter_api_key` with your
OpenRouter credentials so automated agents can call the API. The defaults in the
sample file will spin up the demo match (`DEFAULT_GAME_ID=demo-game`) and assign
the first agent as `team1`. Duplicate the agent section in `.env` with a unique
`TEAM_ID` / `TEAM_NAME` pair if you want to run multiple local agents.

## Web Dashboard

A lightweight dashboard is available at [`/ui`](http://localhost:8000/ui). It refreshes
every few seconds to display the live score, current turn information, recent
events, and the in-game chat log for the default demo match.

## Dockerised Multi-Agent Demo

A ready-to-play demo match is packaged in the repository. The docker compose
configuration spins up the FastAPI server plus two LangGraph-powered LLM agents
that use the MCP tools to control each team.

```bash
export openrouter_api_key=<your-api-key>
docker compose up --build
```

The server exposes port `8000` locally so you can watch the game state while the
agents play. The `openrouter_api_key` environment variable is required because
the agents call the OpenRouter API through LangChain.

## Logging

Structured logging is enabled for both the FastAPI server and the autonomous
agents. By default all services stream to stdout *and* write rotating log files
under `./logs/`:

- `api.log` – high-level server activity plus every in-game event and chat
  message emitted by the `GameState`.
- `agent-<team_id>.log` – step-by-step reasoning, MCP tool usage, and HTTP
  polling summaries for each LLM-controlled team.

Tune the behaviour with environment variables:

- `LOG_DIR` sets a shared directory for all log files. Use `APP_LOG_DIR` or
  `AGENT_LOG_DIR` to override the API or agent destinations individually.
- `APP_LOG_LEVEL` adjusts server verbosity (default: `INFO`).
- `AGENT_LOG_LEVEL` tunes the LangGraph agent logs (default: `INFO`).
- `LOG_MAX_BYTES` / `LOG_BACKUP_COUNT` control rotation for every handler.

During a docker-compose match you can tail the files directly on the host (when
`LOG_DIR` points to a mounted volume) or rely on `docker compose logs -f` for
live monitoring.

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

### Player Communication

- `POST /game/{game_id}/join` - Mark a team as joined
- `POST /game/{game_id}/message` - Send a message
- `GET /game/{game_id}/messages` - Get messages

## MCP Integration for LLM Agents

The server includes an MCP (Model Context Protocol) interface at `http://localhost:8000/mcp` that allows LLM agents to play the game. This enables AI-vs-AI matches or AI-vs-human gameplay.

### Available MCP Tools

LLM agents have access to 9 specialized tools:

1. **join_game** - Join a game that's been set up
2. **get_game_state** - View complete game state
3. **get_valid_actions** - Check available moves
4. **execute_action** - Perform game actions (move, block, pass, etc.)
5. **end_turn** - Finish your turn
6. **use_reroll** - Use a team reroll token
7. **get_history** - View event log
8. **send_message** - Chat with opponent
9. **get_messages** - Read messages

### How LLM Agents Play

**Setup (done by coordinator):**
1. Create game with `POST /game`
2. Setup both teams with `POST /game/{game_id}/setup-team`
3. Place all players with `POST /game/{game_id}/place-players`
4. Start game with `POST /game/{game_id}/start`

**Gameplay (LLM agents):**
1. Connect to MCP server at `http://localhost:8000/mcp`
2. Join game using `join_game(game_id, team_id)`
3. Wait for your turn
4. Check options with `get_valid_actions(game_id)`
5. Execute moves with `execute_action(...)`
6. End turn with `end_turn(game_id, team_id)`
7. Communicate with `send_message` and `get_messages`

### MCP Client Example

```python
from fastmcp.client import Client
import asyncio

async def play_game():
    # Connect to MCP server
    async with Client("http://localhost:8000/mcp") as client:
        # Join the game
        await client.call_tool("join_game", {
            "game_id": "game123",
            "team_id": "team1"
        })
        
        # Check game state
        state = await client.call_tool("get_game_state", {
            "game_id": "game123"
        })
        
        # Send greeting
        await client.call_tool("send_message", {
            "game_id": "game123",
            "sender_id": "team1",
            "sender_name": "AI Watch Captain",
            "content": "Good luck!"
        })
        
        # Get available actions
        actions = await client.call_tool("get_valid_actions", {
            "game_id": "game123"
        })
        
        # Execute a move
        result = await client.call_tool("execute_action", {
            "game_id": "game123",
            "action_type": "move",
            "player_id": "team1_player_0",
            "target_position": {"x": 7, "y": 7}
        })
        
        # End turn
        await client.call_tool("end_turn", {
            "game_id": "game123",
            "team_id": "team1"
        })

asyncio.run(play_game())
```

### Testing MCP Integration

```bash
# Run MCP tests
pytest tests/test_mcp_server.py -v

# Run specific MCP test
pytest tests/test_mcp_server.py::test_integration_two_llm_agents_playing -v
```

### MCP vs REST API

- **REST API**: Full game setup and management, suitable for coordinators
- **MCP Interface**: Focused on gameplay actions, designed for LLM agents
- Both share the same game state and can work together
- MCP provides better tool descriptions and validation for LLM understanding

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
