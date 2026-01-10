# Passing Mechanics Reference

Complete rules for passing, catching, and ball scatter in Ankh-Morpork Scramble.

## Pass Ranges and Modifiers

### Distance Categories

| Range | Distance | Modifier | Risk Level |
|-------|----------|----------|------------|
| Quick | 1-3 squares | +1 | Low |
| Short | 4-6 squares | 0 | Medium |
| Long | 7-12 squares | -1 | High |
| Long Bomb | 13+ squares | -2 | Very High |

**Distance Calculation**: Euclidean distance between thrower and target position:
```
distance = √((x2-x1)² + (y2-y1)²)
```

### Pass Roll Modifiers

Total modifier = Range + Tackle Zones + Skills

| Modifier Source | Value | Notes |
|----------------|-------|-------|
| Quick Pass | +1 | 1-3 square distance |
| Short Pass | 0 | 4-6 square distance |
| Long Pass | -1 | 7-12 square distance |
| Long Bomb | -2 | 13+ square distance |
| Each Tackle Zone (thrower) | -1 | Per enemy adjacent to thrower |
| Pigeon Post skill | +1 | Passer has pass skill |

## Pass Accuracy Results

### Result Interpretation

After rolling d6, add modifiers and compare to passer's Passing target (typically 3+ or 4+):

| Final Result | Outcome | Ball Location |
|-------------|---------|---------------|
| 1 (always) | **Fumble** | Scatters from thrower position |
| < Target | **Wildly Inaccurate** | Scatters 3 times from target |
| Target to Target+2 | **Inaccurate** | Scatters once from target |
| ≥ Target+3 | **Accurate** | Lands exactly on target |

**Critical Rule**: A natural roll of 1 is always a fumble, regardless of modifiers!

### Examples

**Example 1: Safe Quick Pass**
- Passer: 3+ Passing target
- Range: 2 squares (Quick) = +1
- Tackle Zones: 0
- Skill: Pigeon Post = +1
- Roll: 3
- **Result**: 3 + 1 + 1 = 5 ≥ 6 (3+3) → **Accurate**

**Example 2: Risky Long Bomb**
- Passer: 4+ Passing target  
- Range: 15 squares (Long Bomb) = -2
- Tackle Zones: 2 = -2
- Skill: None
- Roll: 4
- **Result**: 4 - 2 - 2 = 0 < 4 → **Wildly Inaccurate** (scatter 3x)

**Example 3: Fumble**
- Passer: 3+ Passing target
- Range: Short = 0
- Tackle Zones: 0
- Skill: Pigeon Post = +1
- Roll: 1
- **Result**: 1 (natural) → **Fumble** (scatter from thrower)

## Ball Scatter

### Scatter Direction

When the ball scatters, roll d8 to determine direction:

```
      8
    7   1
  6       2
    5   3
      4
```

| Roll | Direction | dx | dy |
|------|-----------|----|----|
| 1 | NE | +1 | +1 |
| 2 | E | +1 | 0 |
| 3 | SE | +1 | -1 |
| 4 | S | 0 | -1 |
| 5 | SW | -1 | -1 |
| 6 | W | -1 | 0 |
| 7 | NW | -1 | +1 |
| 8 | N | 0 | +1 |

### Scatter Iterations

- **Fumble**: 1 scatter from thrower position
- **Inaccurate**: 1 scatter from target position
- **Wildly Inaccurate**: 3 scatters from target position

Each scatter moves ball 1 square in rolled direction. Multiple scatters can accumulate (ball may end up far from target).

### Pitch Boundaries

Ball position is clamped to pitch boundaries:
- **X**: 0 to 25 (26 columns)
- **Y**: 0 to 14 (15 rows)

If scatter would move ball off pitch, it stops at edge.

## Catching

### When Catch Attempts Occur

1. **After Pass**: If player is at final ball location (after scatters)
2. **System Automatic**: Game automatically attempts catch for player at ball position

### Catch Roll

Roll d6 + modifiers ≥ catcher's Agility target

| Modifier Source | Value |
|----------------|-------|
| Each Tackle Zone | -1 |
| Quick Grab skill | +1 |

### Catch Outcomes

- **Success**: Player picks up ball, becomes ball_carrier
- **Failure**: Ball scatters 1 square from catch position → **TURNOVER**

### Catch Examples

**Example 1: Clean Catch**
- Catcher: 3+ Agility
- Tackle Zones: 0
- Skill: Quick Grab = +1
- Roll: 2
- **Result**: 2 + 1 = 3 ≥ 3 → **Success**

**Example 2: Difficult Catch**
- Catcher: 4+ Agility
- Tackle Zones: 2 = -2
- Skill: None
- Roll: 5
- **Result**: 5 - 2 = 3 < 4 → **Failure** → Turnover

## Pickup Rules

### Pickup Roll

When picking up ball from ground:

Roll d6 + modifiers ≥ player's Agility target

| Modifier Source | Value |
|----------------|-------|
| Each Tackle Zone | -1 |
| Chain of Custody (Sure Hands) skill | +1 |

### Pickup Outcomes

- **Success**: Player picks up ball, becomes ball_carrier
- **Failure**: Ball scatters 1 square → **TURNOVER**

## Hand-Off Rules

### Requirements

1. **Ball Carrier**: Acting player must have the ball
2. **Adjacency**: Receiver must be in adjacent square (orthogonal or diagonal)
3. **Same Team**: Cannot hand-off to opponent
4. **Action Limit**: One HAND_OFF per turn

### Hand-Off Process

**No roll required!** Hand-off automatically succeeds if requirements met.

1. Ball carrier drops ball
2. Ball placed at receiver's position
3. Receiver picks up ball
4. Receiver becomes new ball_carrier

### Tactical Uses

- **Reposition**: Move ball within protective cage
- **Speed**: Transfer to faster player for scoring run
- **Safety**: Avoid risky dodge rolls with ball carrier

## Turnover Triggers

Ball actions that cause immediate turnover on failure:

| Action | Failure Condition | Turnover? |
|--------|------------------|-----------|
| PICKUP | Roll < Agility target | ✅ Yes |
| PASS | Natural 1 (fumble) | ✅ Yes |
| CATCH | Roll < Agility target | ✅ Yes |
| HAND_OFF | N/A | ❌ Never |

## Scoring

### Touchdown Requirements

1. **Ball Carrier**: Player must be holding the ball
2. **Endzone**: Player must be in opponent's endzone
   - **Team 1** scores in x=25 column (rightmost)
   - **Team 2** scores in x=0 column (leftmost)

### Scoring Process

Movement into endzone with ball = Immediate touchdown!
- Game ends instantly
- Scoring team wins
- No further actions processed

## Risk Assessment Guidelines

### Safe Ball Handling (Recommended)

- Hand-off instead of pass when adjacent
- Quick passes (1-3 squares) with +1 modifier
- Pickup with ≤1 tackle zone
- High Agility players (3+ or better) for all ball actions
- Clear tackle zones before catch/pickup

### Medium Risk

- Short passes (4-6 squares)
- Pickup with 2 tackle zones
- Catch with 1 tackle zone
- 4+ Agility for ball actions

### High Risk (Avoid Unless Necessary)

- Long passes (7-12 squares)
- Long bombs (13+ squares)
- Pickup/catch with 3+ tackle zones
- Pass from thrower in multiple tackle zones
- Low Agility players (5+ or worse) for ball actions

## Player Skills That Affect Ball Handling

### Chain of Custody (Sure Hands)
- **Effect**: +1 to pickup rolls
- **Strategy**: Best player to pickup loose balls

### Quick Grab (Catch)
- **Effect**: +1 to catch rolls
- **Strategy**: Ideal receiver for passes

### Pigeon Post (Pass)
- **Effect**: +1 to pass rolls
- **Strategy**: Primary passer for your team

### Block Breaker (Dodge)
- **Effect**: +1 to dodge rolls when moving with ball
- **Strategy**: Mobile ball carrier, can escape tackle zones

## Common Pass Scenarios

### Scenario 1: Desperate Long Bomb
**Situation**: Need touchdown this turn, ball far from endzone

**Analysis**:
- Long bomb (13+ squares) = -2 modifier
- Each tackle zone = additional -1
- High risk of wildly inaccurate (3 scatters)

**Decision**: Only if no other option. Better to advance with cage.

### Scenario 2: Quick Lateral Pass
**Situation**: Ball carrier surrounded, teammate adjacent 2 squares away

**Analysis**:
- Quick pass (2 squares) = +1 modifier
- If clear of tackle zones, very safe roll
- Receiver auto-attempts catch

**Decision**: Good option if hand-off not possible (not adjacent).

### Scenario 3: Safe Hand-Off
**Situation**: Ball carrier in cage, need to reposition

**Analysis**:
- Automatic success (no roll)
- Zero turnover risk
- Can move ball to better position

**Decision**: Always prefer hand-off over risky passes when possible.

## Advanced Tactics

### Screening Failed Pickups
Position 4+ players around ball before pickup attempt. If pickup fails and ball scatters, high chance it lands near your player for another attempt.

### Calculating Pass Success Probability
```
Target: 3+ (need 3-6 on d6)
Modifiers: +1 (quick pass), -1 (tackle zone) = 0
Effective target: 3+
Success chance: 4/6 = 67%
Fumble risk: 1/6 = 17%
```

### Two-Turn Touchdown
**Turn 1**: Advance with cage, position for quick pass
**Turn 2**: Quick pass to receiver near endzone, receiver scores

This splits risk across turns and uses safe quick pass range.

## API Request Examples

### Execute Pass Action
```http
POST /game/{game_id}/action
Content-Type: application/json

{
  "action_type": "PASS",
  "player_id": "abc-123",
  "target_position": {
    "x": 15,
    "y": 7
  }
}
```

### Execute Pickup Action
```http
POST /game/{game_id}/action
Content-Type: application/json

{
  "action_type": "PICKUP",
  "player_id": "def-456",
  "position": {
    "x": 12,
    "y": 8
  }
}
```

### Execute Hand-Off Action
```http
POST /game/{game_id}/action
Content-Type: application/json

{
  "action_type": "HAND_OFF",
  "player_id": "ghi-789",
  "target_player_id": "jkl-012"
}
```

## Quick Reference

### Pass Success Formula
```
Roll d6 + Range Modifier + Tackle Zone Modifier + Skill Modifier
Compare to Passing Target (usually 3+ or 4+)

Natural 1 = Always Fumble
Result < Target = Wildly Inaccurate (3 scatters)
Result ≥ Target but < Target+3 = Inaccurate (1 scatter)
Result ≥ Target+3 = Accurate (exact target)
```

### Catch Success Formula
```
Roll d6 - Tackle Zones + Quick Grab (if skill)
Compare to Agility Target (usually 3+ or 4+)

Success = Pick up ball
Failure = Scatter + Turnover
```

### Remember
- Natural 1 on pass = Always fumble (turnover)
- Failed catch = Always turnover
- Failed pickup = Always turnover
- Hand-off = Never fails (if legal)
- First touchdown = Instant win!
