# Movement Rules Reference

Detailed movement mechanics for Ankh-Morpork Scramble.

## Movement Allowance (MA)

Each player has an MA stat indicating how many squares they can move per turn.

| MA Value | Speed | Example Positions |
|----------|-------|-------------------|
| 4 | Very Slow | Troll Constable, Heavy players |
| 5 | Slow | Battle Mage, Archchancellor |
| 6 | Average | Most linemen, Constables |
| 7 | Fast | Watch Sergeant, Orangutan |
| 8 | Very Fast | Fleet Recruit, Haste Mage, Librarian |

## Dodge Roll Tables

### Base Agility Success

| AG | Target | Success Rate | With -1 | With -2 | With -3 |
|----|--------|--------------|---------|---------|---------|
| 2+ | 2-6 | 83% | 67% | 50% | 33% |
| 3+ | 3-6 | 67% | 50% | 33% | 17% |
| 4+ | 4-6 | 50% | 33% | 17% | Fail |
| 5+ | 5-6 | 33% | 17% | Fail | Fail |
| 6+ | 6 | 17% | Fail | Fail | Fail |

### Modifiers
- **Tackle zones at destination**: -1 per zone
- **Dodge skill**: May provide bonus
- **Weather effects**: Possible modifiers

## Rush Roll Table

Rush attempts require 2+ on d6:

| Roll | Result | Chance |
|------|--------|--------|
| 1 | Fail - Player down, TURNOVER | 17% |
| 2-6 | Success | 83% |

**Recommendation**: Only rush when necessary. Two rush attempts = ~69% success rate.

## Tackle Zone Mechanics

### Definition
- Standing player exerts tackle zones on all 8 adjacent squares
- Prone, stunned, or KO'd players do not exert tackle zones

### Effects
1. **Leaving**: Must dodge when leaving square with tackle zones
2. **Entering**: Costs normal MA (no extra cost to enter)
3. **Staying**: No penalty for staying in tackle zones

### Counting Tackle Zones

```
Example pitch area:
  5 6 7
5 . E .
6 E P .
7 . . .

P = Your player at (6,6)
E = Enemy players at (6,5) and (5,6)

Tackle zones on P's square: 2 (from both enemies)
```

If P moves to (7,6):
- Leaving 2 tackle zones → dodge required
- (7,6) has 1 tackle zone (from 6,5) → -1 modifier to dodge
- Need: AG roll with -1 modifier

## Movement Patterns

### Diamond/Cage Formation
```
    . T .
    T B T
    . T .
```
- B = Ball carrier
- T = Teammates
- Protects carrier from 4 angles

### Screen Formation
```
←Opponent End

T T T T  ← Line of teammates
. . B .  ← Ball carrier behind
. . . .  
```
- Creates tackle zone barrier
- Protects carrier from blocks

### Spread Formation
```
T . . . T
. T . T .
. . B . .
```
- Controls more space
- Prevents opponent movement
- Harder to protect carrier

## Special Movement Cases

### Standing Up
- Costs 3 MA
- Can then move with remaining MA
- Example: MA 6 player stands (3 MA), moves 3 squares

### Diagonal Movement
- Diagonal counts as 1 square (same as orthogonal)
- No extra cost for diagonal
- Useful for avoiding tackle zones

### Multiple Dodge Attempts
- Each square left with tackle zones requires separate dodge
- Cumulative risk increases quickly
- Avoid multiple dodges if possible

## Safe Movement Checklist

Before moving, verify:
1. ✓ Player is standing (not prone)
2. ✓ Has sufficient MA for move
3. ✓ Target square is empty
4. ✓ Target square is in bounds (0-25 x, 0-14 y)
5. ✓ Count tackle zones at current position
6. ✓ Count tackle zones at destination
7. ✓ Calculate dodge modifiers if needed
8. ✓ Decide if dodge risk acceptable
9. ✓ Check if rush needed (beyond MA)
10. ✓ Consider if this player should move now or later

## Risk Calculation

### Dodge Risk Formula
```
Base success = AG success rate
Modified success = Base - (17% × tackle zones at dest)

Examples:
AG 3+ (67%) with -1 TZ = 50% success
AG 3+ (67%) with -2 TZ = 33% success
AG 2+ (83%) with -1 TZ = 67% success
```

### Compound Risk
Multiple risky actions multiply:
```
Dodge (67%) + Rush (83%) = 56% both succeed
Dodge (50%) + Rush (83%) = 42% both succeed
```

## Movement Priority

### Offense (Ball Carrier Protection)
1. Move non-critical players into screen positions
2. Move blockers to threaten opponents
3. Create cage around carrier
4. Move carrier last (when protected)

### Defense (Pressure Ball Carrier)
1. Move players to mark carrier
2. Fill passing lanes
3. Create multiple tackle zones near carrier
4. Force opponent into risky positions

## Common Movement Sequences

### Safe Advance
```
Turn 1: Move front line forward (safe moves)
Turn 2: Move second line to new front (safe)
Turn 3: Move carrier forward (now protected)
```

### Breakaway Run
```
Turn 1: Clear path with blocks
Turn 2: Sprint carrier through opening
Turn 3: Screen carrier from behind
```

### Defensive Collapse
```
Turn 1: Move closest players to carrier
Turn 2: Create tackle zone network
Turn 3: Block carrier or force bad dodge
```
