# Ball Handling Strategy

---
name: scramble-ball-handling
description: Ball handling decisions for Ankh-Morpork Scramble - pickup, pass, catch, and scoring
version: 1.0.0
guidance_level: basic
activation_mode: manual
dependencies:
  - ankh-morpork-scramble
tags:
  - game
  - sports
  - ball-handling
  - passing
---

## Purpose

This skill helps you make tactical decisions about ball handling in Ankh-Morpork Scramble. Ball control is critical - the first team to score a touchdown wins the game. You must carefully balance risk and reward when attempting pickups, passes, and catches, as failures often result in turnovers.

**When to Use**: During the PLAYING phase when you need to move the ball toward the opponent's endzone or score a touchdown.

## Core Concepts

### Ball State
- **On Ground**: Must be picked up before passing
- **Carried**: Player holding ball (ball_carrier in game state)
- **In Flight**: During pass attempt (brief moment)

### Key Actions
- **PICKUP**: Pick up loose ball (Agility roll)
- **PASS**: Throw ball to target square (Passing roll)
- **HAND_OFF**: Give ball to adjacent teammate (automatic)
- **Score**: Move ball carrier into opponent's endzone

### Critical Rule
**Failed pickup or catch = Turnover!** Always assess risk before attempting ball actions.

## Decision Framework

### 1. Assess Ball Situation

```
Check game state:
- Where is ball? (pitch.ball_position)
- Who has it? (pitch.ball_carrier)
- Where are endzone positions? (x=0-25, team1 scores at x=25, team2 at x=0)
```

### 2. Pickup Decisions

**When to Pickup**:
- Ball is loose and near your players
- You have a high-Agility player available
- Few enemy tackle zones around the ball

**Pickup Risks**:
- Base: Roll ≥ player's Agility target (typically 3+ or 4+)
- Each enemy tackle zone: -1 modifier
- Failure: Ball scatters randomly + TURNOVER

**Safer Alternative**: If risky, screen the ball with players and delay pickup until safer.

### 3. Passing Strategy

**Pass Ranges** (distance from thrower to target):
- **Quick** (1-3 squares): +1 modifier - Safest option
- **Short** (4-6 squares): 0 modifier - Standard pass
- **Long** (7-12 squares): -1 modifier - Risky
- **Long Bomb** (13+ squares): -2 modifier - Very risky

**Pass Accuracy** (based on final roll result):
- **1**: Fumble - ball scatters from thrower (TURNOVER)
- **< Target**: Wildly inaccurate - scatters 3 times from target
- **< Target+3**: Inaccurate - scatters once from target
- **≥ Target+3**: Accurate - lands on target square

**When to Pass**:
- Clear path to receiver with few scatter risks
- Receiver has good Agility for catch roll
- Quick pass range for +1 modifier
- Thrower has few enemy tackle zones

**Pass vs Run**:
- Pass: Faster but riskier (pass roll + catch roll)
- Run: Slower but safer (just movement, no rolls unless dodging)

### 4. Catching

**After a pass**, player at ball location must catch:
- Roll ≥ player's Agility target
- Each enemy tackle zone: -1 modifier
- Skills like Quick Grab: +1 modifier
- Failure: Ball scatters + TURNOVER

**Positioning Receivers**:
- Place high-Agility players at target location
- Clear enemy tackle zones if possible
- Have backup players nearby for scattered ball

### 5. Hand-Off

**Automatic success** for adjacent teammates - No roll needed!

**When to Use**:
- Safe ball transfer without risk
- Position ball carrier for better cage protection
- Move ball to faster player for final sprint

**Limitations**:
- Players must be adjacent (orthogonal or diagonal)
- Same team only
- Costs one HAND_OFF action (limited to once per turn)

### 6. Scoring

**Touchdown**: Move ball carrier into opponent's endzone
- Team 1 scores at x=25 (rightmost column)
- Team 2 scores at x=0 (leftmost column)
- **Game ends immediately** - first to score wins!

**Final Sprint**:
- Calculate moves needed to reach endzone
- Account for rush moves if needed (max 2 extra squares)
- Check for enemy players blocking path
- Consider pass if running is too slow

## Common Patterns

### Pattern 1: Safe Pickup
```
1. Move players to screen ball location
2. Clear enemy tackle zones if possible
3. Use high-Agility player for pickup
4. Have backup players ready for scatter
5. Execute PICKUP action
```

### Pattern 2: Quick Pass Play
```
1. Identify receiver 1-3 squares away (Quick range)
2. Check tackle zones on passer (<2 is good)
3. Move receiver to target square
4. Clear tackle zones around receiver
5. Execute PASS action to receiver's position
6. Receiver attempts catch automatically
```

### Pattern 3: Cage Advance
```
1. Ball carrier in center
2. 4 players surround carrier (cage formation)
3. Move entire formation forward
4. Hand-off to reposition carrier within cage
5. Repeat until scoring position
```

### Pattern 4: Score Rush
```
1. Calculate distance to endzone
2. Check ball carrier's MA + 2 rush moves
3. If sufficient: sprint directly to endzone
4. If not: pass to faster player closer to endzone
5. Execute scoring move
```

## Risk Assessment

### Low Risk
- Hand-off to adjacent teammate
- Quick pass (1-3 squares) with clear receiver
- Pickup with 0-1 tackle zones and Sure Hands skill

### Medium Risk
- Short pass (4-6 squares)
- Pickup with 2 tackle zones
- Catch with 1 tackle zone

### High Risk
- Long pass (7+ squares)
- Pickup/catch with 3+ tackle zones
- Pass from thrower in multiple tackle zones

**Default Strategy**: Minimize risk unless desperate or time pressure.

## API Usage

### Check Ball State
```http
GET /game/{game_id}
```
Response includes:
- `pitch.ball_position`: {x, y} coordinates
- `pitch.ball_carrier`: player_id if carried

### Pickup Ball
```http
POST /game/{game_id}/action
{
  "action_type": "PICKUP",
  "player_id": "player-uuid",
  "position": {"x": 10, "y": 7}
}
```

### Pass Ball
```http
POST /game/{game_id}/action
{
  "action_type": "PASS",
  "player_id": "player-uuid",  # Must be ball_carrier
  "target_position": {"x": 15, "y": 7}
}
```
**Note**: System auto-attempts catch for player at target position after scatter.

### Hand-Off Ball
```http
POST /game/{game_id}/action
{
  "action_type": "HAND_OFF",
  "player_id": "player-uuid",  # Must be ball_carrier
  "target_player_id": "receiver-uuid"  # Must be adjacent
}
```

## Tactical Tips

1. **Screen First**: Surround ball before picking up to catch scatters
2. **High Agility**: Always use best Agility player for pickups/catches
3. **Clear Zones**: Move/block enemies away from pickup/catch location
4. **Short Passes**: Prefer quick/short range over long bombs
5. **Cage Protection**: Keep ball carrier surrounded by teammates
6. **Hand-Off Safety**: Use hand-offs to avoid risky pass rolls
7. **Score Timing**: Don't score too early if opponent has more turns
8. **Backup Plans**: Always have players positioned for scattered balls

## Turnover Triggers

These ball actions cause **immediate turnover** on failure:
- ❌ Failed PICKUP
- ❌ Failed PASS (result = 1, fumble)
- ❌ Failed CATCH after pass
- ✅ HAND_OFF never causes turnover (automatic success)

## Next Steps

1. Review `references/PASS-RULES.md` for detailed passing mechanics
2. Check specific player Agility values in game state
3. Identify ball carrier or ball position
4. Calculate safest path to opponent's endzone
5. Execute ball handling actions with appropriate risk tolerance

**Remember**: Possession is critical. A safe hand-off or run is better than a risky pass that causes turnover!
