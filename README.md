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

### Game Mode Configuration

**DEMO_MODE** (default: `true`)
- `DEMO_MODE=true`: Pre-configured demo game with rosters ready to play
- `DEMO_MODE=false`: Interactive setup where agents must purchase and place players using their 1,000,000 gold budget

When using interactive mode, agents must use the MCP budget tools to build their rosters before playing.

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

LLM agents have access to 15 specialized tools:

**Setup & Budget Tools** (for DEMO_MODE=false):
1. **get_team_budget** - Check remaining budget and purchase history
2. **get_available_positions** - View purchasable players and rerolls with costs
3. **buy_player** - Purchase a player position (costs gold)
4. **buy_reroll** - Purchase a team reroll (costs gold)
5. **place_players** - Position players on the pitch
6. **ready_to_play** - Mark team as ready after setup completion

**Core Gameplay Tools**:
7. **join_game** - Join a game that's been set up
8. **get_game_state** - View complete game state
9. **get_valid_actions** - Check available moves
10. **execute_action** - Perform game actions (move, scuffle, charge, etc.)
11. **end_turn** - Finish your turn
12. **use_reroll** - Use a team reroll token
13. **get_history** - View event log
14. **send_message** - Chat with opponent
15. **get_messages** - Read messages
16. **suggest_path** - Get movement path suggestions with risk assessment

### How LLM Agents Play

**Demo Mode (DEMO_MODE=true):**
1. Server creates pre-configured game at startup
2. Agents join using `join_game(game_id, team_id)`
3. Game starts automatically when both teams join
4. Proceed to gameplay phase

**Interactive Mode (DEMO_MODE=false):**
1. Server creates empty game in DEPLOYMENT phase
2. Agents join using `join_game(game_id, team_id)`
3. Each agent builds their roster:
   - Check budget: `get_team_budget(game_id, team_id)`
   - View options: `get_available_positions(game_id, team_id)`
   - Purchase players: `buy_player(game_id, team_id, position_key)` (minimum 3)
   - Purchase rerolls: `buy_reroll(game_id, team_id)` (optional)
   - Place players: `place_players(game_id, team_id, positions)`
   - Mark ready: `ready_to_play(game_id, team_id)`
4. Game starts automatically when both teams are ready

**Gameplay Phase (both modes):**
1. Wait for your turn
2. Check options with `get_valid_actions(game_id)`
3. Execute actions with `execute_action(...)` using Discworld terminology:
   - **SCUFFLE** (was BLOCK) - Attack adjacent opponent
   - **CHARGE** (was BLITZ) - Move + attack (once per turn)
   - **HURL** (was PASS) - Throw the ball (once per turn)
   - **QUICK_PASS** (was HAND_OFF) - Give ball to adjacent teammate (once per turn)
   - **BOOT** (was FOUL) - Attack prone opponent (once per turn)
4. End turn with `end_turn(game_id, team_id)`
5. Communicate with `send_message` and `get_messages`

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
- ✅ Ball handling (pickup, hurl, catch, quick pass, scatter)
- ✅ Combat system (scuffle, armor, injury rolls)
- ✅ Special actions (charge, boot) using Discworld terminology
- ✅ Team rosters (City Watch with 9 positions, Unseen University with 9 positions)
- ✅ Star players (Captain Carrot, Sergeant Detritus, The Librarian, Archchancellor Ridcully)
- ✅ 60+ Discworld-themed skills
- ✅ Budget system (1M gold treasury with purchase tracking)
- ✅ Interactive setup mode (agents build rosters from scratch)
- ✅ Demo mode (pre-configured rosters for instant play)
- ✅ Score tracking and game phases (DEPLOYMENT → OPENING_SCRAMBLE → ACTIVE_PLAY)
- ✅ Team re-rolls
- ✅ Complete game state management
- ✅ MCP interface for LLM agents

### Action Types (Discworld Terminology)

- **MOVE**: Move a player along a path (with dodge rolls if needed)
- **STAND_UP**: Stand up from prone (costs 3 MA)
- **SCUFFLE** (was BLOCK): Attack an adjacent opponent in Ankh-Morpork street fighting style
- **CHARGE** (was BLITZ): Aggressive rush - Move + Scuffle (once per turn)
- **HURL** (was PASS): Throw the ball to a teammate (once per turn)
- **QUICK_PASS** (was HAND_OFF): Short transfer to adjacent teammate (once per turn)
- **BOOT** (was FOUL): Ankh-Morpork street tactics - attack a prone opponent (once per turn)

### Teams

**City Watch** (1M gold budget)
- **Constable** (50k, 0-16): Basic lineman (MA 6, ST 3, AG 3+, AV 9+)
- **Clerk-Runner** (80k, 0-2): Fast passer with Pigeon Post & Chain of Custody
- **Fleet Recruit** (65k, 0-4): Speedy catcher (MA 8) with Quick Grab & Sidestep Shuffle
- **Watch Sergeant** (85k, 0-4): Disciplined blocker with Drill-Hardened
- **Troll Constable** (115k, 0-2): Massive strength (ST 5) with Thick as a Brick & Rock Solid
- **Street Veteran** (50k, 0-4): Street Fighter with Slippery movement
- **Watchdog** (90k, 0-2): Werewolf with Lupine Speed, Keen Senses & Regenerative
- ⭐ **Sergeant Detritus** (150k, 0-1): Star troll with Cooling Helmet & Crossbow Training
- ⭐ **Captain Carrot** (130k, 0-1): True King with Kingly Presence & Diplomatic Immunity
- **Team Reroll**: 50k (max 8)

**Unseen University Wizards** (1M gold budget)
- **Apprentice Wizard** (45k, 0-12): Small & sneaky with Blink dodge (MA 6, ST 2, AG 3+, AV 8+)
- **Senior Wizard** (90k, 0-6): Slow but strong with Reroll the Thesis & Grappling Cantrip
- **Animated Gargoyle** (115k, 0-1): Stone construct (ST 5) with Bound Spirit & Weathered
- **Battle Mage** (85k, 0-4): Combat specialist with Combat Evocation & Arcane Strike
- **Haste Mage** (75k, 0-2): Speed specialist (MA 8) with Haste Spell & Blink Dodge
- **Technomancer** (80k, 0-2): Precision passer with Hex-Assisted & Calculated Trajectory
- **Orangutan Scholar** (115k, 0-1): Simian Agility with Four Limbs & Independent
- ⭐ **The Librarian** (145k, 0-1): Ook! Prehensile Everything, Library Swinging & Bibliophile Rage
- ⭐ **Archchancellor Ridcully** (140k, 0-1): Leader with Robust Physique, Booming Voice & Arcane Mastery
- **Team Reroll**: 60k (max 8)

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
