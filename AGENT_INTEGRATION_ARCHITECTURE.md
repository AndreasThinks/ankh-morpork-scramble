# Ankh-Morpork Scramble: Cline Agent Integration Architecture Analysis

## Executive Summary

The Ankh-Morpork Scramble system is a FastAPI-based sports game server with an integrated web UI and autonomous AI agents managed through Cline CLI. Currently, the web-ui strategy boxes display dynamically-generated player state information. To integrate actual Cline agent conversations, we need to capture and surface the agent communication through the existing message infrastructure.

---

## 1. Web-UI Structure: Strategy Boxes

### Current Implementation

**File:** `/home/user/ankh-morpork-scramble/app/web/templates/dashboard.html`

The strategy boxes are currently located in two sidebar panels:

```html
<!-- Team 1 Strategy Box (lines 686-688) -->
<aside class="panel thoughts" id="team1-thoughts-panel">
    <h2 id="team1-thoughts-title">Team 1 Strategy</h2>
    <ul id="team1-thoughts"></ul>
</aside>

<!-- Team 2 Strategy Box (lines 729-731) -->
<aside class="panel thoughts" id="team2-thoughts-panel">
    <h2 id="team2-thoughts-title">Team 2 Strategy</h2>
    <ul id="team2-thoughts"></ul>
</aside>
```

### Current Content Generation

The `renderThoughts()` function (lines 1007-1049) currently:
- Generates player-based observations from pitch state
- Creates snippets like: "Constable is charging ahead with the ball at (5, 7)"
- Shows up to 4 items per team, sorted by priority (ball carrier first)
- Replaces underscore characters in player states with spaces

**Current Function Location:** Lines 1007-1049 in `dashboard.html`

```javascript
function renderThoughts(state) {
    const thoughts = {
        [state.team1.id]: [],
        [state.team2.id]: []
    };
    
    // Currently generates from pitch.player_positions
    Object.entries(state.pitch.player_positions || {}).forEach(([playerId, pos]) => {
        // Creates snippets based on player state
    });
    
    // Renders to DOM
    container.innerHTML = teamThoughts.map(({ speaker, text }) => `
        <li>
            <span class="speaker">${speaker}</span>
            ${text}
        </li>
    `).join('');
}
```

### CSS Styling

The strategy boxes use the `.thoughts` CSS class with:
- Panel height: flexible, scrollable up to 400px
- Styling: Dark brown theme, gold accents, serif fonts
- Responsive: Single column on mobile, 3-column layout on desktop

---

## 2. Cline Agent Setup & Configuration

### Run Game Script Configuration

**File:** `/home/user/ankh-morpork-scramble/run_game.py`

The game uses `run_game.py` to orchestrate all agents in a single Python process. This script:
- Starts the FastAPI game server automatically
- Launches two Cline agents (City Watch vs Unseen University)
- Starts a referee agent that provides live commentary
- Manages agent lifecycle (auto-restart when tasks complete)
- Logs all agent activity to separate files

**Environment Variables:**
- `OPENROUTER_API_KEY` - Required for agent LLM calls
- `DEMO_MODE` - Set to `true` for pre-configured rosters, `false` for interactive setup (default: `true`)
- `OPENROUTER_MODEL` - Model for team agents (default: `anthropic/claude-3.5-sonnet`)
- `REFEREE_MODEL` - Model for referee commentary (default: `anthropic/claude-3.5-haiku`)
- `ENABLE_REFEREE` - Enable/disable referee commentary (default: `true`)
- `INTERACTIVE_GAME_ID` - Custom game ID (default: `demo-game`)

### Agent Configuration

**File:** `/home/user/ankh-morpork-scramble/app/agents/config.py`

The `AgentConfig` dataclass controls:
- `team_id`: Team identifier (team1, team2)
- `team_name`: Display name (City Watch Constables, Unseen University Adepts)
- `game_id`: Game identifier
- `mcp_server_url`: URL to MCP server
- `model`: LLM model to use (default: google/gemini-2.5-flash)
- `api_key`: OpenRouter API credentials
- `memory_window`: Number of turns to remember (default: 6)
- Additional config: join_retry_delay, poll_interval, post_turn_delay, startup_timeout

### Agent Runtime

**File:** `/home/user/ankh-morpork-scramble/app/agents/run_agent.py`

The `ClineAgentRunner` class:

1. **Initialization**: Creates persistent Cline Core instance
2. **MCP Setup**: Writes MCP server configuration to `/tmp/cline-team{1|2}/data/settings/cline_mcp_settings.json`
3. **Configuration**: Sets OpenRouter API key for the instance
4. **YOLO Mode**: Enables automatic approval of all actions including MCP tools
5. **Task Creation**: Builds a prompt (see section below) and creates task via `cline task new`
6. **Execution**: Follows task with `cline task view --follow-complete`
7. **Cleanup**: Kills instance when complete

**Key Methods:**
- `_start_instance()`: Spawns Cline Core instance
- `_write_mcp_settings()`: Configures MCP server connection
- `_apply_configuration()`: Sets API keys
- `_enable_yolo_mode()`: Auto-approval configuration
- `_create_task()`: Creates the coaching task
- `_follow_task()`: Monitors execution until completion
- `_build_prompt()`: Generates the coaching instruction (lines 273-314)

#### The Agent Prompt (lines 280-314)

The prompt instructs Cline agents to:
1. Call `get_game_state` to confirm connectivity
2. During DEPLOYMENT phase: build roster with `buy_player`, `buy_reroll`, `place_players`, `ready_to_play`
3. During MATCH: loop on `get_game_state`, then on their turn call `get_valid_actions` and `execute_action`
4. Keep responses concise with STATUS updates (ACTION_TAKEN, WAITING, COMPLETE)
5. Stop once match ends

**Available MCP Tools (from prompt):**
```
join_game, get_game_state, get_team_budget, get_available_positions, 
buy_player, buy_reroll, place_players, ready_to_play, get_valid_actions, 
execute_action, end_turn, use_reroll, get_history, send_message, get_messages
```

---

## 3. Communication Architecture

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Web Browser (Dashboard)                       │
│  - Polls /game/{game_id} every 2.5 seconds (configurable)       │
│  - Fetches /game/{game_id}/messages for agent messages          │
│  - Fetches /game/{game_id}/log?format=markdown for game log    │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    HTTP GET         HTTP GET        HTTP GET
  /game/{id}    /messages?limit=10  /log?format=md
         │               │               │
    ┌────┴───────────────┴───────────────┴────┐
    │                                          │
    │   FastAPI Server (Port 8000)             │
    │   ┌──────────────────────────────────┐  │
    │   │  app/main.py                     │  │
    │   │  - GameState endpoints           │  │
    │   │  - Message endpoints             │  │
    │   │  - Log export endpoints          │  │
    │   └──────────────────────────────────┘  │
    │   ┌──────────────────────────────────┐  │
    │   │  app/mcp_server.py               │  │
    │   │  (FastMCP at /mcp)               │  │
    │   │  - send_message                  │  │
    │   │  - get_messages                  │  │
    │   │  - execute_action, etc.          │  │
    │   └──────────────────────────────────┘  │
    │   ┌──────────────────────────────────┐  │
    │   │  GameManager (State)             │  │
    │   │  - GameState instances           │  │
    │   │  - Message storage               │  │
    │   └──────────────────────────────────┘  │
    └─────────────────────────────────────────┘
         │                │
    HTTP POST         HTTP POST
  /mcp/tools    /message (REST)
         │                │
         └────┬───────────┘
              │
    ┌─────────┴──────────┐
    │                    │
    │  Cline Agents      │
    │  ┌──────────────┐  │ ┌──────────────┐
    │  │ team1 agent  │  │ │ team2 agent  │
    │  └──────────────┘  │ └──────────────┘
    │                    │
    │  - MCP client      │
    │  - LLM (OpenRouter)│
    │  - Strategy logic  │
    │                    │
    └────────────────────┘
```

### Data Flow

1. **Agents → Backend:**
   - Agents connect via MCP HTTP client
   - Call tools like `send_message`, `execute_action`, `get_game_state`
   - MCP server routes to FastMCP tools in `mcp_server.py`

2. **Backend → GameState:**
   - Messages are stored in `GameState.messages` list
   - GameMessage model contains: sender_id, sender_name, content, timestamp, turn_number, game_phase

3. **Backend → UI:**
   - REST API endpoints serve JSON game state
   - Dashboard polls `/game/{game_id}` and `/game/{game_id}/messages`
   - JavaScript fetches and renders in browser

---

## 4. Data Format: Cline Agent Conversations

### Message Storage Model

**File:** `/home/user/ankh-morpork-scramble/app/models/game_state.py` (lines 19-26)

```python
class GameMessage(BaseModel):
    """Message sent during a game"""
    sender_id: str = Field(description="ID of the sender (player or team)")
    sender_name: str = Field(description="Display name of sender")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    turn_number: Optional[int] = Field(None, description="Turn when message was sent")
    game_phase: str = Field(description="Phase when message was sent")
```

### Sample Message JSON

```json
{
  "sender_id": "team1",
  "sender_name": "City Watch Constables",
  "content": "STATUS: ACTION_TAKEN - Moved Constable to (6,7) using execute_action. MCP: execute_action, end_turn",
  "timestamp": "2025-11-09T15:23:45.123456",
  "turn_number": 3,
  "game_phase": "active_match"
}
```

### MCP send_message Tool

**File:** `/home/user/ankh-morpork-scramble/app/mcp_server.py` (lines 723-774)

```python
@mcp.tool(name="send_message")
def send_message(
    game_id: str,           # Game identifier
    sender_id: str,         # Team ID (team1, team2)
    sender_name: str,       # Display name
    content: str            # Message content
) -> dict:
    """Send a message to your opponent in the game."""
    # Stores in game_state.add_message()
    # Logged via message_logger
```

The agents can send messages in any format. Currently they're using:
- "STATUS: ACTION_TAKEN - [description] MCP: [tools used]"
- "STATUS: WAITING - [reason]"
- "STATUS: COMPLETE - [final summary]"

---

## 5. Current Data Flow: Game to Web-UI

### REST API Endpoints

**File:** `/home/user/ankh-morpork-scramble/app/main.py`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/game/{game_id}` | GET | Returns full GameState (includes all data) |
| `/game/{game_id}/messages` | GET | Returns GameMessage list (supports filtering) |
| `/game/{game_id}/messages?limit=10` | GET | Returns last 10 messages |
| `/game/{game_id}/messages?turn_number=3` | GET | Returns messages from turn 3 |
| `/game/{game_id}/message` | POST | Sends a new message |
| `/game/{game_id}/log` | GET | Exports markdown/JSON game log |
| `/game/{game_id}/log?format=markdown` | GET | Returns formatted narrative |

### Dashboard Polling Cycle

**File:** `/home/user/ankh-morpork-scramble/app/web/templates/dashboard.html`

```javascript
const POLL_INTERVAL = {{ poll_interval }};  // Default: 2500ms

async function fetchState() {
    const response = await fetch(`/game/${gameId}`);
    const data = await response.json();
    
    // Updates:
    updateScoreboard(data);      // Score, phase, turn
    renderPitch(data);           // Player positions
    renderThoughts(data);        // CURRENT: Player-based thoughts
    renderRoster(data);          // Roster table
    fetchGameLog();              // Separate fetch for game events
}

async function fetchGameLog() {
    const response = await fetch(`/game/${gameId}/log?format=markdown`);
    const markdown = await response.text();
    // Renders as HTML to game-log-entries
}

// Note: Currently does NOT fetch messages for display
```

**Currently Missing:** The dashboard doesn't fetch `/game/{game_id}/messages` to display agent conversations.

---

## 6. Existing APIs for Agent Conversations

### Available Endpoints

1. **Store Messages:**
   - `POST /game/{game_id}/message`
   - Parameters: `sender_id`, `sender_name`, `content`
   - Returns: `{"success": true, "message": {...}}`

2. **Retrieve Messages:**
   - `GET /game/{game_id}/messages` - All messages
   - `GET /game/{game_id}/messages?limit=10` - Last 10 messages
   - `GET /game/{game_id}/messages?turn_number=3` - Messages from turn 3
   - Returns: `{"game_id": "...", "count": N, "messages": [...]}`

3. **MCP Tools (for agents):**
   - `send_message(game_id, sender_id, sender_name, content)`
   - `get_messages(game_id, turn_number=None, limit=None)`

### Message Retrieval Example

```bash
# Get last 10 messages
curl http://localhost:8000/game/interactive-game/messages?limit=10

# Get messages from turn 5
curl http://localhost:8000/game/interactive-game/messages?turn_number=5

# Response format:
{
  "game_id": "interactive-game",
  "count": 10,
  "messages": [
    {
      "sender_id": "team1",
      "sender_name": "City Watch Constables",
      "content": "STATUS: ACTION_TAKEN - Moved player",
      "timestamp": "2025-11-09T15:23:45.123456",
      "turn_number": 3,
      "game_phase": "active_match"
    },
    ...
  ]
}
```

---

## 7. Integration Recommendations

### Option 1: Display Agent Messages Directly (Recommended)

**Approach:** Replace the player-based thoughts with actual agent messages sent via MCP `send_message` tool.

**Implementation Steps:**

1. **Modify `renderThoughts()` in dashboard.html** (lines 1007-1049):
   - Fetch messages from `/game/{game_id}/messages?limit=4`
   - Group messages by sender_id (team1, team2)
   - For each team, display the 4 most recent messages

```javascript
async function renderThoughts(state) {
    try {
        const response = await fetch(`/game/${gameId}/messages?limit=20`);
        const data = await response.json();
        
        const messagesByTeam = {
            [state.team1.id]: data.messages.filter(m => m.sender_id === state.team1.id).slice(-4),
            [state.team2.id]: data.messages.filter(m => m.sender_id === state.team2.id).slice(-4)
        };
        
        [
            [state.team1, team1Thoughts, team1Title],
            [state.team2, team2Thoughts, team2Title]
        ].forEach(([team, container, title]) => {
            title.textContent = `${team.name} Strategy`;
            const messages = messagesByTeam[team.id] || [];
            
            if (messages.length === 0) {
                container.innerHTML = '<li>Awaiting team communication...</li>';
                return;
            }
            
            container.innerHTML = messages.map(msg => `
                <li>
                    <span class="speaker">${msg.sender_name}</span>
                    <span class="timestamp">[Turn ${msg.turn_number}]</span>
                    ${escapeHtml(msg.content)}
                </li>
            `).join('');
        });
    } catch (error) {
        console.error('Failed to fetch messages:', error);
    }
}
```

2. **Update CSS** for better message display:
   - Add timestamp styling
   - Improve readability with better whitespace
   - Add status indicators (ACTION_TAKEN, WAITING, COMPLETE)

3. **Encourage agents to send messages:**
   - Agents already have `send_message` in their MCP tools
   - Prompt could be updated to send status messages on key decisions
   - Example: "After executing an action, send a message with your status update"

**Pros:**
- ✅ Direct agent communication visible to viewers
- ✅ No UI changes needed, only JavaScript logic
- ✅ Messages are already stored and accessible
- ✅ Reuses existing message infrastructure

**Cons:**
- ⚠️ Depends on agents calling `send_message` (not guaranteed)
- ⚠️ Messages might be sparse or irregular

---

### Option 2: Capture Agent Thinking/Planning (Advanced)

**Approach:** Capture Cline agent stdout/stderr and log as synthetic messages.

**Implementation:**
1. Modify `run_agent.py` to capture Cline CLI output
2. Parse task status updates and convert to GameMessages
3. Send via `send_message` tool

**Example:**
```
Cline Output: "Creating task: Move team forward"
  ↓ Parse ↓
Send: send_message(
    game_id="...",
    sender_id="team1",
    sender_name="City Watch Constables",
    content="PLANNING: Creating task: Move team forward"
)
```

**Pros:**
- ✅ Captures all agent thinking
- ✅ More comprehensive strategy visibility
- ✅ Automatic, doesn't depend on agent code

**Cons:**
- ⚠️ Requires agent code modification
- ⚠️ More complex logging/parsing
- ⚠️ May create many messages (verbose output)

---

### Option 3: Hybrid Approach (Balanced)

1. **Primary:** Display agent `send_message` calls
2. **Fallback:** Show player-based observations if no messages received
3. **Supplement:** Add game event history below messages

This gives a balanced view of both agent strategy and game state.

---

## 8. File Summary & Key Locations

### Frontend (Web-UI)
| File | Purpose | Key Lines |
|------|---------|-----------|
| `/app/web/templates/dashboard.html` | Main dashboard template | 686-731 (panels), 1007-1049 (renderThoughts) |
| `/app/web/ui.py` | Dashboard route handler | 18-39 |

### Backend (Server)
| File | Purpose | Key Lines |
|------|---------|-----------|
| `/app/main.py` | FastAPI app, REST endpoints | 499-539 (message endpoints) |
| `/app/mcp_server.py` | MCP tools for agents | 723-835 (send_message, get_messages) |
| `/app/models/game_state.py` | GameState & GameMessage models | 19-26 (GameMessage), 72 (messages list) |

### Agents (Cline)
| File | Purpose | Key Lines |
|------|---------|-----------|
| `/app/agents/run_agent.py` | Agent runner/orchestrator | 68-99 (run), 273-314 (prompt) |
| `/app/agents/config.py` | Agent configuration | 19-100 |
| `/docker-compose.yml` | Agent containers | 21-61 |

### State Management
| File | Purpose |
|------|---------|
| `/app/state/game_manager.py` | Manages game state, coordinates actions |
| `/app/state/action_executor.py` | Executes game actions |

---

## 9. Quick Start: Enable Agent Messages in UI

### Step 1: Verify Message Endpoint Works

```bash
# Start server
uv run uvicorn app.main:app --reload

# Test message endpoint
curl http://localhost:8000/game/demo-game/messages?limit=5
```

### Step 2: Send Test Message

```bash
curl -X POST "http://localhost:8000/game/demo-game/message" \
  -G \
  --data-urlencode "sender_id=team1" \
  --data-urlencode "sender_name=City Watch Constables" \
  --data-urlencode "content=Testing message integration"
```

### Step 3: Update Dashboard to Fetch Messages

Replace the `renderThoughts()` function in `dashboard.html` with the implementation from Option 1 above.

### Step 4: Encourage Agents to Send Messages

Add to agent prompt (in `run_agent.py` line ~305):
```
"After each turn, call send_message to report your team's strategy and next moves."
```

---

## 10. Recommendations Summary

| Aspect | Recommendation |
|--------|-----------------|
| **Short-term** | Option 1: Display existing agent messages in strategy boxes |
| **Implementation** | Modify JavaScript `renderThoughts()` to fetch `/messages` instead of generating from pitch state |
| **Effort** | Low (UI change only, no backend changes needed) |
| **Dependencies** | Agents must use `send_message` MCP tool |
| **Long-term** | Enhance agent prompt to encourage/require message sending on key decisions |
| **Future** | Consider Option 2 for automatic thinking capture if messages are sparse |

---

## Conclusion

The infrastructure to support agent conversation display already exists:
- ✅ Messages are stored in GameState
- ✅ REST API endpoints provide retrieval
- ✅ MCP tools allow agents to send messages
- ✅ Web-UI panels are ready for content

The key missing piece is connecting the messaging layer to the UI. A simple modification to the dashboard's `renderThoughts()` function to fetch and display messages would immediately expose agent strategy to viewers, enhancing the transparency and interactivity of the game viewing experience.
