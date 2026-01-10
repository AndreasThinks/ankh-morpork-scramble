---
name: ankh-morpork-scramble
description: Play Ankh-Morpork Scramble, a turn-based sports game via REST API. Manages game flow, coordinates gameplay phases (setup, kickoff, playing), and makes tactical decisions for team management.
metadata:
  author: ankh-morpork-scramble
  version: "1.0"
---

# Ankh-Morpork Scramble

## When to use this skill

Use this skill when:
- Playing an Ankh-Morpork Scramble game
- Controlling a team in a match
- Making strategic decisions during gameplay
- Need to understand game phases and turn structure

## Game Overview

Ankh-Morpork Scramble is a turn-based sports game where two teams compete to score "Scratches" by getting the ball into the opponent's end zone. The game consists of:

- **Two halves**: 8 turns per team each half
- **Pitch size**: 26×15 squares
- **Team size**: 3-11 players on pitch
- **Actions per turn**: Move, Scuffle (block), Charge, Hurl (pass), etc.

## Game Phases

The game progresses through these phases:

1. **DEPLOYMENT**: Setup phase - buy players, place them on pitch
2. **KICKOFF**: Ball kick-off, determine receiving team
3. **PLAYING**: Main gameplay - teams take turns executing actions

## API Configuration

**Base URL**: `http://localhost:8000` (or your server URL)

All API calls use REST HTTP methods with JSON payloads.

## Core Workflow

### 1. Join a Game

```bash
curl -X POST "http://localhost:8000/game/{game_id}/join?team_id={your_team_id}"
```

Response indicates if you've successfully joined.

### 2. Check Game State

```bash
curl http://localhost:8000/game/{game_id}
```

Returns complete game state including:
- Phase (setup, kickoff, playing)
- Player positions
- Ball location
- Active team
- Turn number

### 3. Phase-Specific Actions

**If phase is DEPLOYMENT**:
- Activate the `scramble-setup` skill
- Buy players and place them on pitch

**If phase is KICKOFF or PLAYING**:
- Check whose turn it is
- If it's your turn, proceed with turn execution

### 4. Turn Execution Loop

When it's your turn:

1. **Get valid actions**:
```bash
curl http://localhost:8000/game/{game_id}/valid-actions
```

2. **Analyze the situation**:
   - Where is the ball?
   - Which players can move?
   - Are there opponents to block?
   - What's the score?

3. **Choose and execute actions**:
   - **Movement**: Activate `scramble-movement` skill
   - **Combat**: Activate `scramble-combat` skill  
   - **Ball handling**: Activate `scramble-ball-handling` skill

4. **Execute action via API**:
```bash
curl -X POST http://localhost:8000/game/{game_id}/action \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "move",
    "player_id": "team1_player_0",
    "target_position": {"x": 10, "y": 7},
    "path": [{"x": 10, "y": 7}]
  }'
```

5. **End turn when done**:
```bash
curl -X POST "http://localhost:8000/game/{game_id}/end-turn"
```

### 5. Opponent's Turn

When it's the opponent's turn:
- Wait for them to complete their actions
- Monitor game state periodically
- Plan your next turn strategy

## Decision Framework

### Offensive Strategy (You have the ball)
1. Protect ball carrier - surround with teammates
2. Advance toward opponent's end zone
3. Create passing lanes if needed
4. Score when in range

### Defensive Strategy (Opponent has ball)
1. Block opponent ball carrier
2. Create tackle zones around their players
3. Intercept passing lanes
4. Prevent scoring opportunities

### General Priorities
1. **Safety first**: Avoid risky moves that cause turnovers
2. **Ball control**: Protect your ball carrier
3. **Territory**: Advance when safe
4. **Player preservation**: Don't unnecessarily risk injuries

## Turnover Events (Avoid These!)

A turnover immediately ends your turn. Avoid:
- Failed dodge rolls when leaving tackle zones
- Failed rush (extra movement) rolls
- Dropping the ball
- Failed pass attempts
- Ball carrier getting knocked down

## Common Action Types

| Action | Description | Usage |
|--------|-------------|-------|
| `move` | Move a player to adjacent square | Basic movement |
| `scuffle` | Block an adjacent opponent | Combat |
| `charge` | Move then block (1 per turn) | Aggressive play |
| `hurl` | Pass the ball | Ball movement |
| `quick_pass` | Hand off to adjacent player | Safe transfer |
| `boot` | Attack prone opponent | Risky but effective |

## Key Game Concepts

### Tackle Zones
- Each standing player exerts a tackle zone on adjacent squares
- Leaving a tackle zone requires a dodge roll
- More tackle zones = harder dodge

### Movement Allowance (MA)
- Each player has a MA value (usually 4-8)
- Can move up to MA squares per turn
- Rush: 2 extra squares with 2+ roll each

### Strength (ST)
- Used for blocking
- Higher strength = better block dice odds
- Compare attacker ST vs defender ST

## Reference Materials

For detailed information:
- [API Reference](references/API-REFERENCE.md) - Complete API documentation
- [Game Rules](references/GAME-RULES.md) - Condensed rule summary

## Example Turn

```bash
# 1. Check game state
curl http://localhost:8000/game/demo-game

# 2. Get valid actions
curl http://localhost:8000/game/demo-game/valid-actions

# 3. Move a player forward
curl -X POST http://localhost:8000/game/demo-game/action \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "move",
    "player_id": "team1_player_0",
    "target_position": {"x": 8, "y": 7},
    "path": [{"x": 8, "y": 7}]
  }'

# 4. Block an opponent
curl -X POST http://localhost:8000/game/demo-game/action \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "scuffle",
    "player_id": "team1_player_1",
    "target_player_id": "team2_player_0"
  }'

# 5. End turn
curl -X POST http://localhost:8000/game/demo-game/end-turn
```

## Tips for Success

1. **Always check valid actions** before planning your turn
2. **Protect your ball carrier** with adjacent teammates
3. **Use safe plays** early in the turn, risky plays at the end
4. **Count opponent tackle zones** before moving
5. **Save rerolls** for critical moments
6. **End turn manually** when satisfied (don't wait for forced turnover)

## Multi-Skill Coordination

This core skill coordinates with specialized skills:

- **scramble-setup**: Called during DEPLOYMENT phase
- **scramble-movement**: Called when moving players
- **scramble-combat**: Called for block decisions
- **scramble-ball-handling**: Called for ball-related actions

Activate the appropriate skill based on the current situation.
