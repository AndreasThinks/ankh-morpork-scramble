---
name: scramble-setup
description: Handle team setup phase in Ankh-Morpork Scramble. Purchase players, buy rerolls, place players on pitch, and optimize roster within 1,000,000 gold budget.
metadata:
  author: ankh-morpork-scramble
  version: "1.0"
---

# Scramble Setup

## When to use this skill

Use this skill when:
- Game phase is DEPLOYMENT
- Need to build a roster
- Need to place players on the pitch
- Managing team budget during setup

## Setup Phase Overview

During setup, you must:
1. Purchase players (minimum 3, maximum 11)
2. Optionally buy team rerolls (expensive but valuable)
3. Place all purchased players on your half of the pitch
4. Mark your team as ready when complete

**Budget**: 1,000,000 gold coins per team

## Step-by-Step Setup

### 1. Check Budget and Available Positions

```bash
curl http://localhost:8000/game/{game_id}/team/{team_id}/budget
curl http://localhost:8000/game/{game_id}/team/{team_id}/available-positions
```

This shows:
- Current budget status
- Available player positions
- Costs and limits for each position
- Reroll costs

### 2. Purchase Players

**Minimum**: 3 players required
**Maximum**: 11 players on pitch
**Recommended**: 7-11 players for flexibility

```bash
curl -X POST "http://localhost:8000/game/{game_id}/team/{team_id}/buy-player?position_key=constable"
```

Repeat for each player you want to buy.

### 3. Purchase Rerolls (Optional but Recommended)

Rerolls are expensive but crucial for recovering from bad dice:
- City Watch: 50,000 gold per reroll
- Unseen University: 60,000 gold per reroll
- Maximum: 8 rerolls per team

```bash
curl -X POST "http://localhost:8000/game/{game_id}/team/{team_id}/buy-reroll"
```

**Recommendation**: Buy 2-3 rerolls if budget allows

### 4. Place Players on Pitch

Once purchased, place all players on your half:
- **Team 1 (left)**: X coordinates 0-12
- **Team 2 (right)**: X coordinates 13-25
- **Y coordinates**: 0-14 (full height)

```bash
curl -X POST http://localhost:8000/game/{game_id}/place-players \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "team1",
    "positions": {
      "team1_player_0": {"x": 5, "y": 7},
      "team1_player_1": {"x": 6, "y": 6},
      "team1_player_2": {"x": 6, "y": 8},
      "team1_player_3": {"x": 7, "y": 7}
    }
  }'
```

### 5. Mark Ready

When satisfied with roster and placement:

```bash
curl -X POST "http://localhost:8000/game/{game_id}/join?team_id={team_id}"
```

Game starts when both teams are ready.

## Roster Building Strategy

### Balanced Roster (Recommended)
- 7-9 players total
- Mix of roles:
  - 3-4 linemen (cheap, reliable)
  - 2-3 specialized players (catchers, blockers)
  - 1-2 star players if budget allows
- 2-3 rerolls

### Budget Roster (Cheap)
- 9-11 players
- Mostly linemen
- 1-2 rerolls
- Leaves gold for future purchases

### Elite Roster (Expensive)
- 5-7 players
- Focus on quality over quantity
- Include star players
- 3-4 rerolls
- Higher risk (fewer players)

## Player Placement Tactics

### Defensive Setup
- **Center**: Strong blockers
- **Wings**: Fast players for mobility
- **Back**: Ball handler with good agility

### Offensive Setup
- **Front**: Blockers to push forward
- **Middle**: Ball carrier and catchers
- **Support**: Players to create passing lanes

### Safe Setup (Recommended for New Teams)
- Spread evenly across your half
- 2-3 players near line of scrimmage
- Others 2-3 squares back
- Don't cluster too tightly

## Position Selection Guide

See [ROSTERS.md](references/ROSTERS.md) for complete roster information.

### City Watch

**Budget Options:**
- **Constable** (50k): Basic lineman, good all-around
- **Street Veteran** (50k): Cheap with fighting skills

**Specialized:**
- **Fleet Recruit** (65k): Fast runner (MA 8)
- **Clerk-Runner** (80k): Ball handler with passing

**Heavy:**
- **Troll Constable** (115k): Strong blocker (ST 5)

### Unseen University

**Budget Options:**
- **Apprentice Wizard** (45k): Cheap, agile, small

**Specialized:**
- **Haste Mage** (75k): Very fast (MA 8)
- **Technomancer** (80k): Good passer

**Heavy:**
- **Animated Gargoyle** (115k): Strong (ST 5)

## Common Mistakes to Avoid

1. **Overspending early**: Leave some budget buffer
2. **Too few players**: Minimum 3, but 7+ recommended
3. **No rerolls**: At least 2 rerolls are very helpful
4. **Clustering**: Don't place all players together
5. **Ignoring roles**: Need mix of blockers, runners, handlers

## Budget Example (City Watch)

```
5x Constable @ 50k = 250k
2x Fleet Recruit @ 65k = 130k
1x Watch Sergeant @ 85k = 85k
2x Rerolls @ 50k = 100k
------------------------
Total: 565k spent
Remaining: 435k
```

This gives:
- 8 players on field
- Mix of roles
- 2 rerolls
- Budget for future needs

## Quick Start Template

For fastest setup:

1. Buy 7 cheap players (constables/apprentices)
2. Buy 2 rerolls
3. Place in basic spread formation
4. Mark ready

Total time: ~2 minutes
Cost: ~500k
Effectiveness: Good for beginners

## Reference Materials

- [ROSTERS.md](references/ROSTERS.md): Complete position stats and costs
