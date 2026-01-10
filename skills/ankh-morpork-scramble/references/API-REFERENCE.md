# API Reference

Complete REST API documentation for Ankh-Morpork Scramble server.

## Base URL

Default: `http://localhost:8000`

## Authentication

No authentication required for local games. For hosted games, check with your server administrator.

## Common Response Format

All endpoints return JSON. Successful responses include relevant data. Error responses include:

```json
{
  "detail": "Error message description"
}
```

## Endpoints

### Game Management

#### GET /

Root endpoint - returns API information.

**Response:**
```json
{
  "name": "Ankh-Morpork Scramble API",
  "version": "0.1.0",
  "status": "running"
}
```

#### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "active_games": 1
}
```

#### POST /game

Create a new game.

**Query Parameters:**
- `game_id` (optional): Custom game ID

**Response:** Complete GameState object

#### GET /game/{game_id}

Get current game state.

**Response:** Complete GameState object including:
- `game_id`: Game identifier
- `phase`: Current phase (setup/kickoff/playing)
- `team1`, `team2`: Team objects with rosters
- `players`: Dictionary of all players
- `pitch`: Player positions and ball location
- `turn`: Turn information
- `event_log`: Game history

### Team Setup (DEPLOYMENT Phase)

#### POST /game/{game_id}/join

Mark a team as joined.

**Query Parameters:**
- `team_id`: Your team ID (e.g., "team1" or "team2")

**Response:**
```json
{
  "success": true,
  "team_id": "team1",
  "players_ready": false
}
```

#### GET /game/{game_id}/team/{team_id}/budget

Get team budget information.

**Response:**
```json
{
  "team_id": "team1",
  "initial_budget": 1000000,
  "spent": 200000,
  "remaining": 800000,
  "purchases": [...]
}
```

#### GET /game/{game_id}/team/{team_id}/available-positions

Get available player positions for purchase.

**Response:**
```json
{
  "positions": [
    {
      "key": "constable",
      "role": "Constable",
      "cost": 50000,
      "quantity_limit": 16,
      "quantity_owned": 2,
      "can_afford": true,
      "stats": {...}
    }
  ],
  "budget_status": {...},
  "reroll_cost": 50000,
  "rerolls_owned": 0,
  "max_rerolls": 8
}
```

#### POST /game/{game_id}/team/{team_id}/buy-player

Purchase a player.

**Query Parameters:**
- `position_key`: Position to buy (e.g., "constable")

**Response:**
```json
{
  "success": true,
  "player_id": "team1_player_3",
  "position": "Constable",
  "cost": 50000,
  "budget": {...}
}
```

#### POST /game/{game_id}/team/{team_id}/buy-reroll

Purchase a team reroll.

**Response:**
```json
{
  "success": true,
  "cost": 50000,
  "rerolls_total": 1,
  "budget": {...}
}
```

#### POST /game/{game_id}/place-players

Place players on the pitch.

**Request Body:**
```json
{
  "team_id": "team1",
  "positions": {
    "team1_player_0": {"x": 5, "y": 7},
    "team1_player_1": {"x": 6, "y": 6},
    "team1_player_2": {"x": 6, "y": 8}
  }
}
```

**Response:** Updated GameState

### Gameplay

#### POST /game/{game_id}/start

Start the game (moves from DEPLOYMENT to KICKOFF).

**Response:** Updated GameState

#### GET /game/{game_id}/valid-actions

Get all valid actions for the current active team.

**Response:**
```json
{
  "current_team": "team1",
  "phase": "playing",
  "can_charge": true,
  "can_hurl": true,
  "can_quick_pass": true,
  "can_boot": true,
  "can_blitz": true,
  "can_pass": true,
  "can_hand_off": true,
  "can_foul": true,
  "movable_players": ["team1_player_0", "team1_player_1"],
  "blockable_targets": {
    "team1_player_0": ["team2_player_5"]
  },
  "ball_carrier": "team1_player_2",
  "ball_on_ground": false,
  "ball_position": {"x": 10, "y": 7}
}
```

#### POST /game/{game_id}/action

Execute a game action.

**Request Body:**
```json
{
  "action_type": "move",
  "player_id": "team1_player_0",
  "target_position": {"x": 10, "y": 7},
  "path": [{"x": 10, "y": 7}],
  "target_player_id": null,
  "target_receiver_id": null,
  "use_reroll": false
}
```

**Action Types:**
- `move`: Move to target_position (requires path)
- `scuffle`: Block target_player_id (must be adjacent)
- `charge`: Move then block (requires target_player_id and optional target_position)
- `hurl`: Pass ball to target_receiver_id or target_position
- `quick_pass`: Hand off to adjacent target_receiver_id
- `boot`: Attack prone target_player_id
- `stand_up`: Stand up from prone

**Response:**
```json
{
  "success": true,
  "message": "Player moved to (10, 7)",
  "dice_rolls": [],
  "turnover": false,
  "player_moved": "team1_player_0",
  "new_position": {"x": 10, "y": 7},
  "details": {}
}
```

#### POST /game/{game_id}/end-turn

Manually end the current turn.

**Response:** Updated GameState with new active team

#### POST /game/{game_id}/reroll

Use a team reroll (if available).

**Query Parameters:**
- `team_id`: Your team ID

**Response:**
```json
{
  "success": true,
  "rerolls_remaining": 2
}
```

### Information

#### GET /game/{game_id}/history

Get game event history.

**Query Parameters:**
- `limit` (default: 50): Number of recent events

**Response:**
```json
{
  "game_id": "demo-game",
  "events": [
    "Game created",
    "Team team1 joined",
    "Player moved to (10, 7)",
    ...
  ]
}
```

#### GET /game/{game_id}/suggest-path

Get suggested path for movement with risk assessment.

**Query Parameters:**
- `player_id`: Player to move
- `target_x`: Target X coordinate
- `target_y`: Target Y coordinate

**Response:**
```json
{
  "path": [{"x": 10, "y": 7}, {"x": 11, "y": 7}],
  "movement_cost": 2,
  "requires_rushing": false,
  "total_risk_score": 0.0,
  "risks": [],
  "is_valid": true
}
```

### Messaging

#### POST /game/{game_id}/message

Send a message in the game.

**Query Parameters:**
- `sender_id`: Your ID
- `sender_name`: Your display name
- `content`: Message text

**Response:**
```json
{
  "success": true,
  "message": {
    "sender_id": "team1",
    "sender_name": "Player1",
    "content": "Good game!",
    "timestamp": "2026-01-10T12:00:00",
    "turn_number": 5
  }
}
```

#### GET /game/{game_id}/messages

Get messages from the game.

**Query Parameters:**
- `turn_number` (optional): Filter by turn
- `limit` (optional): Limit number of messages

**Response:**
```json
{
  "game_id": "demo-game",
  "count": 3,
  "messages": [...]
}
```

## Error Codes

- **400**: Bad Request - Invalid parameters or illegal action
- **404**: Not Found - Game or resource doesn't exist
- **429**: Too Many Requests - Rate limit exceeded
- **500**: Internal Server Error - Server-side error

## Rate Limiting

- 100 requests per minute per IP address per endpoint
- Exceeding limit returns 429 error

## Tips

1. Always check game phase before actions
2. Use `valid-actions` to see available options
3. Check `turnover` field in action responses
4. Monitor `event_log` for game history
5. Use `suggest-path` for complex movements
