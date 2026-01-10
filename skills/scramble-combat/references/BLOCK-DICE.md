# Block Dice Reference

Detailed blocking mechanics and probability tables.

## Block Dice Distribution

Standard block die has 6 faces (equal probability):

| Result | Probability | Effect |
|--------|-------------|--------|
| Attacker Down | 16.7% | Attacker knocked down |
| Both Down | 16.7% | Both knocked down |
| Push | 33.3% | Defender pushed (2 faces) |
| Defender Stumbles | 16.7% | Defender pushed/down |
| Defender Down | 16.7% | Defender knocked down |

## Dice Selection Odds

### 1 Die (Equal ST)
- No choice, roll result applies
- 50% chance defender goes down/stumbles
- 16.7% chance attacker goes down
- 33.3% chance push only

### 2 Dice (+1 ST Advantage)
Roller picks best of 2:
- 97% chance of avoiding attacker down
- 72% chance of knockdown/stumbles
- 55% chance of pure knockdown

### 3 Dice (+2 ST Advantage)
Roller picks best of 3:
- 99.5% chance of avoiding attacker down
- 87% chance of knockdown/stumbles
- 75% chance of pure knockdown

## Strength Comparison Table

| Your ST | Their ST | Dice | Chooser | Advantage |
|---------|----------|------|---------|-----------|
| 5 | 2 | 3 | You | Huge |
| 5 | 3 | 3 | You | Huge |
| 4 | 2 | 3 | You | Huge |
| 5 | 4 | 2 | You | Good |
| 4 | 3 | 2 | You | Good |
| 3 | 2 | 2 | You | Good |
| 5 | 5 | 1 | None | Equal |
| 4 | 4 | 1 | None | Equal |
| 3 | 3 | 1 | None | Equal |
| 2 | 2 | 1 | None | Equal |
| 2 | 3 | 2 | Them | Bad |
| 3 | 4 | 2 | Them | Bad |
| 4 | 5 | 2 | Them | Bad |
| 2 | 4 | 3 | Them | Very Bad |
| 2 | 5 | 3 | Them | Very Bad |
| 3 | 5 | 3 | Them | Very Bad |

## Assist Modifiers

Each friendly player adjacent to the defender adds +1 ST to attacker:

```
Example with Assists:
    . E .
    F D F
    A . .

A = Attacker (ST 3)
D = Defender (ST 3)
F = Friendlies (2 adjacent to D)

Effective: ST 5 (3+2) vs ST 3
Result: 3 dice, attacker chooses
```

## Armor Values by Position

### City Watch
- Constable, Sergeant, Clerk: AV 9+
- Fleet Recruit, Veteran: AV 8+
- Troll, Detritus, Carrot: AV 10+
- Watchdog: AV 9+

### Unseen University
- Apprentice, Technomancer: AV 8+
- Haste Mage: AV 7+
- Senior, Battle Mage: AV 9+
- Gargoyle, Librarian, Ridcully: AV 9-10+

## Armor Roll Probabilities

| AV | 2d6 Roll Needed | Success (No Injury) | Fail (Check Injury) |
|----|-----------------|---------------------|---------------------|
| 7+ | 7-12 | 58% | 42% |
| 8+ | 8-12 | 42% | 58% |
| 9+ | 9-12 | 28% | 72% |
| 10+ | 10-12 | 17% | 83% |

## Injury Table (2d6)

| Roll | Result | Effect | Probability |
|------|--------|--------|-------------|
| 2-7 | Stunned | Miss next action | 58% |
| 8-9 | Knocked Out | Off pitch, may return | 28% |
| 10-12 | Casualty | Removed from game | 14% |

## Combined Knockdown Probabilities

Chance of knocking down AND injuring:

| Defender AV | Block Success | Armor Fail | Injury | Combined |
|-------------|---------------|------------|--------|----------|
| 7+ | 50% | 42% | 42% | ~9% serious |
| 8+ | 50% | 58% | 42% | ~12% serious |
| 9+ | 50% | 72% | 42% | ~15% serious |
| 10+ | 50% | 83% | 42% | ~17% serious |

*Note: "Block Success" assumes 1 die. Higher ST advantage increases knockdown chance.*

## Block Skill Effects

**Block Skill**: Player with this skill can ignore "Both Down" results.

Impact:
- Converts 16.7% bad result to push
- Makes blocks much safer
- Valuable for key players

## Decision Matrix

### When You Have ST Advantage (+2)

| Situation | Action | Reason |
|-----------|--------|--------|
| Target is ball carrier | BLOCK | High value, good odds |
| Target blocks your path | BLOCK | Clear space safely |
| Target is weak (low AV) | BLOCK | Likely injury |
| Your blocker critical | Consider | Risk vs reward |

### When ST is Equal

| Situation | Action | Reason |
|-----------|--------|--------|
| You have Block skill | BLOCK | Safer |
| Target is ball carrier | BLOCK IF late turn | Risk worth reward |
| Non-critical matchup | Maybe | Coin flip odds |
| Your blocker critical | AVOID | Too risky |

### When Opponent Has ST Advantage

| Situation | Action | Reason |
|-----------|--------|--------|
| Any case | AVOID | Bad odds |
| Desperate (must try) | BLOCK late turn | Minimize damage |
| Can get assists | Reconsider | May equalize ST |

## Optimal Block Timing

1. **Early Turn**: Only safe blocks (ST +2)
2. **Mid Turn**: Calculated blocks (ST +1, important targets)
3. **Late Turn**: Risky blocks acceptable (turnover less costly)

## Example Calculations

### Scenario A: ST 4 vs ST 3
- Dice: 2 (you choose)
- Knockdown probability: ~72%
- If knockdown, armor roll (assume AV 9+): 72% fail
- Injury if fail: 42% serious
- Overall serious injury: ~22%

### Scenario B: ST 3 vs ST 3 + 1 Assist
- Your ST effectively 4 vs their 3
- Same as Scenario A
- **Assists matter!**

### Scenario C: ST 3 vs ST 5
- Dice: 3 (they choose worst for you)
- Your knockdown probability: <3%
- Their knockdown of you: ~87%
- **Avoid this matchup!**
