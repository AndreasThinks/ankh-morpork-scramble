# Block Dice Probabilities Reference

**Auto-generated from `app/game/combat.py`** - Do not edit manually!

Complete blocking/combat mechanics for Ankh-Morpork Scramble.

## Block Dice Results

### 💀 ATTACKER DOWN

Attacker Down - Attacker is knocked down

### 💥 BOTH DOWN

Both Down - Both players knocked down (unless Block skill)

### ⬅️ PUSH

Push - Defender pushed back one square

### 😵 DEFENDER STUMBLES

Defender Stumbles - Knockdown unless Dodge skill

### ☠️ DEFENDER DOWN

Defender Down - Defender knocked down


## Strength Comparison Table

Number of dice rolled and who chooses the result:

| Situation | Condition | Dice | Chooser |
|-----------|-----------|------|---------|
| Much Stronger | attacker ST ≥ defender ST + 2 | 3 | Attacker |
| Stronger | attacker ST = defender ST + 1 | 2 | Attacker |
| Equal | attacker ST = defender ST | 1 | Attacker |
| Weaker | attacker ST = defender ST - 1 | 2 | Defender |
| Much Weaker | attacker ST ≤ defender ST - 2 | 3 | Defender |

## Injury Rolls

After a player is knocked down, roll 2d6 against their Armour Value (AV).

**Armor Roll**: Roll 2d6, if ≥ player's AV, make injury roll

If armor is broken (roll ≥ AV), make an injury roll:

| Roll (2d6) | Result | Effect |
|------------|--------|--------|
| 2-7 | STUNNED | Stunned - Player stays down until next turn |
| 8-9 | KNOCKED_OUT | Knocked Out - Player removed from pitch |
| 10+ | CASUALTY | Casualty - Player permanently removed |

## Block Dice Faces (Single Die)

Each face of a standard block die shows:
- Attacker Down
- Both Down
- Push
- Push
- Defender Stumbles
- Defender Down

## Combat Strategy

- **Much Stronger (+2 ST)**: Roll 3 dice, choose best → very favorable
- **Stronger (+1 ST)**: Roll 2 dice, choose best → favorable  
- **Equal ST**: Roll 1 die, must use result → neutral
- **Weaker (-1 ST)**: Roll 2 dice, opponent chooses → unfavorable
- **Much Weaker (-2 ST)**: Roll 3 dice, opponent chooses → very unfavorable

---

*This file is auto-generated from game mechanics. To update, edit `app/game/combat.py` constants and run `make generate-docs`.*