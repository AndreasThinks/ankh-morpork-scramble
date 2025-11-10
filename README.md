# Ankh-Morpork Scramble - FastAPI Server

> **DISCLAIMER**: This is an unofficial, non-commercial fan project created purely for entertainment and educational purposes. It is inspired by Games Workshop's Blood Bowl and Terry Pratchett's Discworld universe. This project is not affiliated with, endorsed by, or connected to Games Workshop Limited, Terry Pratchett's estate, or any official Discworld or Blood Bowl properties. All rights to Blood Bowl belong to Games Workshop. All rights to Discworld characters and settings belong to the Terry Pratchett estate. This is a tribute project by fans, for fans.

A turn-based sports game server inspired by Blood Bowl, featuring the City Watch vs. Wizards of Unseen University.

## Installation

This project uses **UV** as the package manager. UV is fast, reliable, and handles dependency resolution better than pip.

```bash
# Install UV if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install project with dependencies
uv pip install -e .

# Or install with dev dependencies for testing
uv pip install -e ".[dev]"

# Alternative: Use uv sync (recommended for reproducible installs)
uv sync --extra dev
```

## Running the Server

```bash
# Run with uvicorn
uvicorn app.main:app --reload

# Or run the main file directly
python -m app.main
```

The server will start at `http://localhost:8000`

## Playing a Full Match

### Quick demo (default `DEMO_MODE=true`)

1. Start the API with logging enabled:

   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. Open [`http://localhost:8000/ui`](http://localhost:8000/ui) to watch the
   pre-seeded `demo-game` progress. You can advance the match by calling the
   `POST /game/demo-game/end-turn` endpoint (from the Swagger UI or with
   `curl`). Logs stream to the console and rotate under `logs/`.

### Interactive setup (`DEMO_MODE=false`)

1. Disable demo mode when launching the server so both teams must assemble
   their own rosters:

   ```bash
   DEMO_MODE=false uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

2. Create a fresh match (replace `my-match` with any ID you like):

   ```bash
   curl -X POST "http://localhost:8000/game?game_id=my-match"
   ```

3. Have each side join so setup actions are permitted:

   ```bash
   curl -X POST "http://localhost:8000/game/my-match/join?team_id=team1"
   curl -X POST "http://localhost:8000/game/my-match/join?team_id=team2"
   ```

4. Purchase the players and rerolls you want. For example, buying two City
   Watch constables:

   ```bash
   curl -X POST "http://localhost:8000/game/my-match/team/team1/buy-player?position_key=constable"
   curl -X POST "http://localhost:8000/game/my-match/team/team1/buy-player?position_key=constable"
   ```

   Use `GET /game/{game_id}/team/{team_id}/available-positions` to inspect the
   full shopping list and costs.

5. Deploy the roster once you have at least eleven players (or however many you
   plan to field). Send a JSON payload that maps player IDs to board
   coordinates:

   ```bash
   curl -X POST "http://localhost:8000/game/my-match/place-players" \
        -H "Content-Type: application/json" \
        -d '{"team_id": "team1", "positions": {"team1_player_0": {"x": 5, "y": 7}, "team1_player_1": {"x": 6, "y": 7}}}'
   ```

   Repeat for the other team. You can confirm placements via
   `GET /game/{game_id}`.

6. Start the match:

   ```bash
   curl -X POST "http://localhost:8000/game/my-match/start"
   ```

7. Play turns using the main action loop:

   - `GET /game/{game_id}/valid-actions` to see the legal moves for your active
     players.
   - `POST /game/{game_id}/action` with the action payload you want to execute
     (move, scuffle, hurl, etc.).
   - `POST /game/{game_id}/end-turn` when your turn is complete. The server
     now rejects this call with HTTP 400 once the phase is `finished`, ensuring
     the turn counter and logs stay consistent.

8. Review logs during or after the session. Structured records live in
   `logs/api.log`, while per-game markdown/JSON exports are written under
   `logs/games/<game_id>/` whenever `LOG_DIR` is configured or auto-save is
   enabled.

## Testing

Use UV to install the development extras and execute the test suite:

```bash
uv sync --extra dev
uv run pytest
```

The `uv run` wrapper ensures the virtual environment and dependency versions from
`uv.lock` are respected while invoking `pytest`.

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

## AI vs AI Gameplay with Cline Agents

### Quick Start (Single Python File) - Recommended

The easiest way to watch two AI agents play against each other is using the `run_game.py` script. This approach runs everything in a single Python process - no Docker required!

**Prerequisites:**
- Python 3.12+
- UV package manager installed
- Cline CLI installed globally: `npm install -g @cline/cli`
- OpenRouter API key

**Setup:**

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Set your OpenRouter API key:
   ```bash
   export OPENROUTER_API_KEY=your-api-key-here
   ```

3. Run the game:
   ```bash
   python run_game.py
   ```

That's it! The script will:
- ✅ Start the FastAPI game server automatically
- ✅ Launch two Cline agents (City Watch vs Unseen University)
- ✅ Start a referee agent that provides live commentary
- ✅ Each agent builds their roster and plays autonomously
- ✅ Agents send in-character messages explaining their strategy
- ✅ Auto-restart agents when tasks complete
- ✅ Log all agent activity to `logs/team1.log`, `logs/team2.log`, and `logs/referee.log`

**Monitoring the game:**
- Web UI: Open http://localhost:8000/ui to watch live with referee commentary
- Agent logs: `tail -f logs/team1.log` and `tail -f logs/team2.log`
- Referee log: `tail -f logs/referee.log`
- Server log: `tail -f logs/server.log`
- Game API: http://localhost:8000/docs

**Configuration options:**
```bash
# Use demo mode (pre-configured rosters, instant play)
DEMO_MODE=true python run_game.py

# Use different model for team agents
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet python run_game.py

# Use different model for referee (default: claude-3.5-haiku for fast, cheap commentary)
REFEREE_MODEL=anthropic/claude-3.5-sonnet python run_game.py

# Disable referee commentary
ENABLE_REFEREE=false python run_game.py

# Adjust referee commentary interval (seconds between updates)
REFEREE_COMMENTARY_INTERVAL=45 python run_game.py

# Custom referee prompt (for different commentary styles)
REFEREE_PROMPT="You are a dramatic sports announcer..." python run_game.py

# Custom game ID
INTERACTIVE_GAME_ID=my-epic-match python run_game.py

# Adjust logging
AGENT_LOG_LEVEL=DEBUG python run_game.py
REFEREE_LOG_LEVEL=DEBUG python run_game.py
```

**How it works:**
The script creates two Cline instances plus a referee agent that all communicate with the game:

**Team Agents (via MCP - Model Context Protocol):**
1. Join the game as their assigned team
2. Build a roster within their 1M gold budget
3. Place players on the pitch
4. Play turns by calling MCP tools (get_valid_actions, execute_action, end_turn)
5. Use `send_message` to explain their coaching decisions in character
6. Automatically restart when the game ends to play again

**Referee Agent:**
1. Watches the game state and recent events
2. Generates colorful, character-driven commentary using an LLM (default: Claude 3.5 Haiku)
3. Posts commentary every 30 seconds (configurable)
4. Uses a Discworld-themed prompt with gruff, humorous observations
5. Commentary appears prominently above the pitch in the web UI

**Security:** Agents use selective auto-approval for **MCP tools only**. File operations and bash commands are **actively rejected** with helpful feedback, forcing agents to interact with the game purely through the MCP interface. This prevents agents from hanging while waiting for manual approval and gives them clear guidance to use MCP tools instead.

## Logging

Structured logging is enabled for both the FastAPI server and the autonomous
agents. By default all services stream to stdout *and* write rotating log files
under `./logs/`:

- `api.log` – high-level server activity plus every in-game event and chat
  message emitted by the `GameState`.
- `mcp.log` – MCP server logs (agent communication via Model Context Protocol)
- `server.log` – uvicorn server logs
- `team1.log` – City Watch Constables agent activity
- `team2.log` – Unseen University Adepts agent activity
- `referee.log` – Referee commentary and analysis

Tune the behaviour with environment variables:

- `LOG_DIR` sets a shared directory for all log files (default: `logs`).
- `APP_LOG_LEVEL` adjusts server verbosity (default: `INFO`).
- `MCP_LOG_LEVEL` adjusts MCP server verbosity (default: `INFO`).
- `AGENT_LOG_LEVEL` tunes the Cline agent logs (default: `INFO`).
- `REFEREE_LOG_LEVEL` tunes the referee agent logs (default: `INFO`).
- `LOG_MAX_BYTES` / `LOG_BACKUP_COUNT` control rotation for every handler.

### Unified Log Viewing (Admin Endpoints)

Access all logs through a unified endpoint with admin API key:

```bash
# Set admin API key
export ADMIN_API_KEY=your-secret-key

# View all logs combined (sorted by timestamp)
curl -H "X-Admin-Key: $ADMIN_API_KEY" http://localhost:8000/admin/logs/all

# View separated by component
curl -H "X-Admin-Key: $ADMIN_API_KEY" "http://localhost:8000/admin/logs/all?format=separated"

# Last 100 lines from each log
curl -H "X-Admin-Key: $ADMIN_API_KEY" "http://localhost:8000/admin/logs/all?tail=100"

# List available logs
curl -H "X-Admin-Key: $ADMIN_API_KEY" http://localhost:8000/admin/logs

# View specific log
curl -H "X-Admin-Key: $ADMIN_API_KEY" http://localhost:8000/admin/logs/team1.log
```

You can also monitor the game by tailing the log files directly:
```bash
tail -f logs/server.log logs/team1.log logs/team2.log logs/referee.log
```

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

LLM agents have access to **16 specialized tools** for game interaction, all with enhanced validation to provide clear error messages:

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

### Available MCP Resources

In addition to tools, the MCP server provides **5 read-only resources** using URI-based access. Resources are optimized for frequent polling and state observation without executing actions:

1. **game://{game_id}/state** - Complete game state snapshot
2. **game://{game_id}/actions** - Valid actions for current turn
3. **game://{game_id}/history** - Full event log
4. **game://{game_id}/team/{team_id}/budget** - Budget status and purchase history
5. **game://{game_id}/team/{team_id}/positions** - Available positions and costs

**Tools vs Resources:**
- **Tools** = Actions that modify game state (buy player, execute move, end turn) with validation
- **Resources** = Read-only queries using URI patterns (efficient for polling game state)

**Enhanced Validation:**
All MCP tools include comprehensive validation that catches errors early and provides clear, specific error messages to LLM agents:
- Position validators ensure coordinates are within pitch bounds (0-25, 0-14)
- Action validators check required parameters (e.g., MOVE needs target_position, SCUFFLE needs target_player_id)
- Game state validators verify preconditions (player can act, players are adjacent, etc.)
- Better error context helps LLM agents understand what went wrong and how to fix it

Resources use the MCP resource protocol for efficient data access:

```python
# Read a resource using URI pattern
state = await client.read_resource("game://demo-game/state")
actions = await client.read_resource("game://demo-game/actions")
budget = await client.read_resource("game://demo-game/team/team1/budget")
```

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

# Run tests with coverage
uv run --with pytest --with pytest-asyncio --with pytest-cov pytest --cov=app --cov-report=term-missing

# Run with hot reload
uvicorn app.main:app --reload
```

## Deployment

### Railway Deployment

This project is configured for easy deployment on Railway. See [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md) for complete deployment instructions including:
- Required environment variables
- Dynamic port configuration
- Unified logging endpoint access
- Health check configuration
- Monitoring the game in production

The Railway deployment runs the full game simulation (`run_game.py`) with:
- FastAPI server with game API and MCP endpoints
- Two AI agent teams playing autonomously
- Referee agent providing live commentary
- All logs accessible via admin endpoints

## License

MIT

## Credits

Based on Blood Bowl rules, adapted for the Discworld universe by Terry Pratchett.
