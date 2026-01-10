---
name: scramble-combat
description: Handle blocking and combat in Ankh-Morpork Scramble. Make block decisions, compare strength, select block dice results, and manage knockdowns to control the pitch.
metadata:
  author: ankh-morpork-scramble
  version: "1.0"
---

# Scramble Combat

## When to use this skill

Use this skill when:
- Blocking (scuffling) an opponent
- Using Charge action (move + block)
- Deciding which opponent to target
- Managing block dice results

## Combat Overview

**Blocking** (called "scuffling" in Ankh-Morpork) is attacking an adjacent opponent to knock them down or push them away.

### Block Actions
- **Scuffle**: Block adjacent opponent (unlimited per turn)
- **Charge**: Move then block (1 per turn, only if not used)
- **Boot**: Attack prone opponent (1 per turn, risky)

## Execute Block via API

### Basic Block (Scuffle)
```bash
curl -X POST http://localhost:8000/game/{game_id}/action \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "scuffle",
    "player_id": "team1_player_0",
    "target_player_id": "team2_player_0"
  }'
```

### Charge (Move + Block)
```bash
curl -X POST http://localhost:8000/game/{game_id}/action \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "charge",
    "player_id": "team1_player_0",
    "target_player_id": "team2_player_0",
    "target_position": {"x": 8, "y": 7}
  }'
```

## Strength Comparison

Compare attacker ST vs defender ST to determine block dice:

| Comparison | Dice | Who Chooses Result |
|------------|------|-------------------|
| Attacker +2 or more ST | 3 dice | Attacker |
| Attacker +1 ST | 2 dice | Attacker |
| Equal ST | 1 die | Neither (random) |
| Defender +1 ST | 2 dice | Defender |
| Defender +2 or more ST | 3 dice | Defender |

**Example**:
- Attacker ST 4 vs Defender ST 3 = Attacker rolls 2 dice, picks best
- Attacker ST 3 vs Defender ST 5 = Defender rolls 3 dice, picks worst for attacker

## Block Dice Results

Each die shows one of these results:

| Result | Icon | Effect |
|--------|------|--------|
| Attacker Down | ☠️ | Attacker knocked down |
| Both Down | ⚔️ | Both knocked down (Block skill negates) |
| Push | ↔️ | Defender pushed 1 square |
| Defender Stumbles | 👇 | Defender pushed, may go down |
| Defender Down | ❌ | Defender knocked down |

**When choosing**: Pick result most favorable to you (or least bad).

## Blocking Strategy

### Target Selection Priority

1. **Ball Carrier**: Knockdown = turnover + ball loose
2. **Key Blockers**: Remove opponent's strong players
3. **Blocking Path**: Clear way for your advancement
4. **Assist Setup**: Position for better odds next turn

### When to Block

**Good Times to Block**:
- Strong ST advantage (you have 2+ dice)
- Target is ball carrier
- Safe blocks (attacker unlikely to fall)
- Creating space for your team

**Avoid Blocking When**:
- Equal or lower ST (risky)
- Your blocker is critical (ball carrier, key player)
- Better to position for next turn
- Would leave ball carrier exposed

## Assists

**Assist**: Friendly player adjacent to defender adds +1 ST to blocker.

```
Example:
    A D
    F .

A = Attacker (ST 3)
D = Defender (ST 3)
F = Friendly adjacent to D

A gets +1 ST from F = effective ST 4 vs 3
Result: A rolls 2 dice, chooses best
```

**Note**: Server calculates assists automatically.

## Armor and Injury

When player knocked down:

1. **Armor Roll**: 2d6 vs Armor Value (AV)
   - Roll ≥ AV: No injury (safe)
   - Roll < AV: Proceed to injury roll

2. **Injury Roll**: 2d6
   - 2-7: Stunned (miss next action)
   - 8-9: Knocked Out (off pitch)
   - 10+: Casualty (removed from game)

**Example**: AV 9+ player
- Roll 9+ on 2d6: Safe
- Roll 2-8: Check injury table

## Block Decision Framework

### 1. Identify Blockable Targets

```bash
curl http://localhost:8000/game/{game_id}/valid-actions
```

Returns `blockable_targets` showing who can block whom.

### 2. Calculate Odds

For each potential target:
- Compare ST values
- Count assists
- Check for Block skill
- Assess risk vs reward

### 3. Prioritize Targets

**Priority 1**: Opponent ball carrier (causes turnover)
**Priority 2**: Strong opponents (reduce their threat)
**Priority 3**: Positional blocks (clear path)
**Priority 4**: Safe blocks (build advantage)

### 4. Execute Best Block

Choose highest-value, lowest-risk block.

## Common Situations

### Blitzing Ball Carrier
```bash
# Use Charge to move adjacent then block
curl -X POST .../action -d '{
  "action_type": "charge",
  "player_id": "team1_player_1",
  "target_player_id": "team2_ball_carrier",
  "target_position": {"x": 9, "y": 7}
}'
```
**If successful**: Ball carrier down = turnover!

### Creating Space
```bash
# Push opponent away to open path
curl -X POST .../action -d '{
  "action_type": "scuffle",
  "player_id": "team1_player_0",
  "target_player_id": "team2_player_3"
}'
```

### Defensive Block
```bash
# Block opponent threatening your carrier
curl -X POST .../action -d '{
  "action_type": "scuffle",
  "player_id": "team1_player_2",
  "target_player_id": "team2_player_5"
}'
```

## Risk Assessment

### Low Risk Blocks
- ST advantage of +2 or more
- Defender has low AV
- Attacker has Block skill
- Non-critical attacker

### Medium Risk Blocks
- ST advantage of +1
- Equal ST with assists
- Important positional block
- Moderate armor on both sides

### High Risk Blocks
- Equal or disadvantaged ST
- Critical player blocking
- Both Down likely
- No assists available

## Block Timing

**Early Turn**: Safe blocks to set up position
**Mid Turn**: Positional blocks to advance
**Late Turn**: Risky blocks (if turnover, minimal loss)

## Tips

1. **Calculate ST carefully**: Include assists
2. **Target ball carrier**: Priority #1
3. **Use Charge wisely**: Only 1 per turn
4. **Block then move**: Clear path before advancing
5. **Protect blockers**: Don't expose strong players unnecessarily

## Reference Materials

- [BLOCK-DICE.md](references/BLOCK-DICE.md): Detailed block dice odds and injury tables
