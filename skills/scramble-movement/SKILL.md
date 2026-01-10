---
name: scramble-movement
description: Handle player movement in Ankh-Morpork Scramble. Make movement decisions, navigate tackle zones, perform dodges, and manage rushing for extra movement.
metadata:
  author: ankh-morpork-scramble
  version: "1.0"
---

# Scramble Movement

## When to use this skill

Use this skill when:
- Need to move a player
- Planning paths around opponents
- Deciding whether to dodge or find safe route
- Using rush (extra movement)

## Movement Basics

Each player has a **Movement Allowance (MA)** - the number of squares they can move per turn.

- **Normal Movement**: Up to MA squares (orthogonal or diagonal)
- **Rush**: Up to 2 additional squares (requires 2+ roll each)
- **Cost**: 1 MA per square moved
- **Standing Up**: Costs 3 MA (player must be standing to move)

## Execute Movement via API

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

**Important**: Must provide `path` - list of positions to move through.

## Tackle Zones

**Tackle Zone**: Each standing opponent exerts control over adjacent (8) squares.

### Effects
- Must make **dodge roll** when leaving a square with tackle zones
- -1 modifier per tackle zone at **destination** square
- Failed dodge = player knocked down + **TURNOVER**

### Example
```
Player at (5,5) wants to move to (6,5)
- (5,5) has 2 enemy tackle zones
- (6,5) has 1 enemy tackle zone
- Dodge roll needed with -1 modifier (for destination)
```

## Dodge Rolls

When leaving tackle zones, roll against player's **Agility (AG)**:

| AG Value | Need to Roll | Success Chance |
|----------|--------------|----------------|
| 2+ | 2-6 | 83% |
| 3+ | 3-6 | 67% |
| 4+ | 4-6 | 50% |
| 5+ | 5-6 | 33% |
| 6+ | 6 | 17% |

**Modifiers**:
- -1 per tackle zone at destination
- Skills may provide bonuses

## Movement Decision Framework

### 1. Check Movement Situation

```bash
curl http://localhost:8000/game/{game_id}/valid-actions
```

Identifies movable players and their current status.

### 2. Identify Tackle Zones

Look at game state - count standing enemies adjacent to:
- Current position (leaving penalty)
- Destination position (dodge modifier)

### 3. Choose Safe vs Risky Path

**Safe Path**:
- No tackle zones to leave
- No dodge rolls needed
- May be longer route

**Risky Path**:
- Leaves tackle zones
- Requires dodge roll(s)
- More direct route

### 4. Consider Rush

**Rush** = Extra movement beyond MA (max 2 squares):
- Each rush square requires 2+ roll (83% success)
- Failed rush = player knocked down + **TURNOVER**
- Use only when necessary

## Movement Strategies

### Offensive Movement (You have ball)
1. **Protect carrier**: Move other players first
2. **Create screen**: Position teammates around carrier
3. **Advance safely**: Move carrier last, after screen set
4. **Avoid risks**: Don't dodge with ball carrier unless forced

### Defensive Movement (Opponent has ball)
1. **Mark ball carrier**: Get adjacent if possible
2. **Block passing lanes**: Position between carrier and receivers
3. **Pressure opponent**: Create tackle zones in key areas
4. **Cut off escape**: Prevent carrier from advancing

### General Movement Tips
1. **Move safe players first**: Those not in tackle zones
2. **Set up assists**: Position for next turn's blocks
3. **Control space**: Spread out to limit opponent movement
4. **Retreat if needed**: Sometimes backing up is safest

## Path Planning

### Simple Adjacent Move
```json
{
  "target_position": {"x": 6, "y": 7},
  "path": [{"x": 6, "y": 7}]
}
```

### Multi-Square Move
```json
{
  "target_position": {"x": 8, "y": 7},
  "path": [
    {"x": 6, "y": 7},
    {"x": 7, "y": 7},
    {"x": 8, "y": 7}
  ]
}
```

### Use Suggest Path API
```bash
curl "http://localhost:8000/game/{game_id}/suggest-path?player_id=team1_player_0&target_x=10&target_y=7"
```

Returns path with risk assessment.

## Standing Up

Prone players must stand before moving:

```bash
curl -X POST http://localhost:8000/game/{game_id}/action \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "stand_up",
    "player_id": "team1_player_0"
  }'
```

**Cost**: 3 MA
**Note**: Player can still move after standing if MA remaining

## Common Mistakes

1. **Forgetting tackle zones**: Always count before moving
2. **Moving ball carrier first**: Move screen first
3. **Unnecessary dodges**: Find safe route if possible
4. **Rushing too often**: Save rushes for critical moves
5. **Ignoring positioning**: Think ahead to next turn

## Risk Assessment

### Low Risk (Do These First)
- Moving in open field (no tackle zones)
- Standing up far from opponents
- Repositioning non-critical players

### Medium Risk (Consider Carefully)
- Dodging with 1 tackle zone (-1 modifier)
- Rushing with non-critical player
- Moving near but not through tackle zones

### High Risk (Avoid or Save for Last)
- Dodging with 2+ tackle zones
- Moving ball carrier through tackle zones
- Rushing with ball carrier

## Example Turn Sequence

```bash
# 1. Move safe player forward
curl -X POST .../action -d '{
  "action_type": "move",
  "player_id": "team1_player_0",
  "target_position": {"x": 8, "y": 7},
  "path": [{"x": 8, "y": 7}]
}'

# 2. Reposition support player
curl -X POST .../action -d '{
  "action_type": "move",
  "player_id": "team1_player_1",
  "target_position": {"x": 7, "y": 6},
  "path": [{"x": 7, "y": 6}]
}'

# 3. Move ball carrier (last, after screen set)
curl -X POST .../action -d '{
  "action_type": "move",
  "player_id": "team1_player_2",
  "target_position": {"x": 9, "y": 7},
  "path": [{"x": 9, "y": 7}]
}'
```

## Reference Materials

- [MOVEMENT-RULES.md](references/MOVEMENT-RULES.md): Detailed movement mechanics and dodge tables
