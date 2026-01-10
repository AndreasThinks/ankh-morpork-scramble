# Movement Mechanics Reference

**Auto-generated from `app/game/movement.py`** - Do not edit manually!

Complete movement rules for Ankh-Morpork Scramble.

## Movement Basics

- **Movement Allowance (MA)**: Each player has a base MA value (typically 4-8 squares)
- **Normal Movement**: Can move up to MA squares per turn
- **Rush Moves**: Can move up to 2 additional squares beyond MA
- **Stand Up Cost**: 3 MA to stand up from prone

## Pitch Dimensions

- **Width**: 26 columns (x: 0-25)
- **Height**: 15 rows (y: 0-14)

## Tackle Zones

- **Range**: Adjacent squares (1 square away, orthogonal or diagonal)
- **Effect**: Standing enemy players exert tackle zones
- **Dodge Required**: Must dodge when leaving enemy tackle zones

## Dodging

**When Required**: Leaving a square with enemy tackle zones

**Dodge Roll**: d6 ≥ player's Agility target

**Modifiers**:
- -1 per tackle zone at **destination** square

**Failure**: Player knocked down + **TURNOVER**

## Rush Moves

- **Maximum**: 2 rush moves per turn (beyond MA)
- **Rush Roll**: Need 2+ on d6 per rush square
- **Failure**: Player knocked down + **TURNOVER**

## Movement with the Ball

- Ball carrier can move normally
- Must dodge if leaving tackle zones (same rules)
- Failed dodge = ball scatters + **TURNOVER**

## Standing Up

- **Cost**: 3 MA
- **Action**: STAND_UP action type
- **Restriction**: Must have enough MA remaining

---

*This file is auto-generated from game mechanics. To update, edit `app/game/movement.py` constants and run `make generate-docs`.*