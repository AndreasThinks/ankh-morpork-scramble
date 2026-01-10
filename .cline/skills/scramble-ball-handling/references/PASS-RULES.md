# Passing Mechanics Reference

**Auto-generated from `app/game/ball_handling.py`** - Do not edit manually!

Complete rules for passing, catching, and ball scatter in Ankh-Morpork Scramble.

## Pass Ranges and Modifiers

| Range | Distance | Modifier | Risk Level |
|-------|----------|----------|------------|
| Quick | 1-3 | +1 | Low |
| Short | 4-6 | 0 | Medium |
| Long | 7-12 | -1 | High |
| Long Bomb | 13+ | -2 | Very High |

## Pass Accuracy Results

After rolling d6 and adding modifiers, compare to passer's Passing target:

| Condition | Result | Scatter | From | Turnover? |
|-----------|--------|---------|------|-----------|
| Natural 1 | FUMBLE | 1x | thrower | ✅ |
| < Target | WILDLY_INACCURATE | 3x | target | ❌ |
| Target to Target+2 | INACCURATE | 1x | target | ❌ |
| ≥ Target+3 | ACCURATE | 0x | — | ❌ |

## Scatter Directions

When ball scatters, roll d8 for direction:

```
      8(N)
    7   1
  6       2
    5   3
      4(S)
```

| Roll | Direction | Movement |
|------|-----------|----------|
| 1 | NE | (+1, +1) |
| 2 | E | (+1, +0) |
| 3 | SE | (+1, -1) |
| 4 | S | (+0, -1) |
| 5 | SW | (-1, -1) |
| 6 | W | (-1, +0) |
| 7 | NW | (-1, +1) |
| 8 | N | (+0, +1) |

## Catching

**Roll d6 ≥ Agility target**

**Modifiers**: −1 per tackle zone, +1 for Quick Grab skill

**Failure**: Ball scatters + TURNOVER

## Pickup

**Roll d6 ≥ Agility target**

**Modifiers**: −1 per tackle zone, +1 for Chain of Custody skill

**Failure**: Ball scatters + TURNOVER

## Hand-Off

**Requirements**: Adjacent teammates only

**Roll Needed**: None (automatic success)

**Failure**: Never (if legal)

## Summary

- **Quick passes (1-3 squares)**: Safest option with +1 modifier
- **Fumble on natural 1**: Always causes turnover, regardless of modifiers
- **Hand-offs never fail**: If adjacent teammates, automatic success
- **Failed catch/pickup**: Always causes turnover

---

*This file is auto-generated from game mechanics. To update, edit `app/game/ball_handling.py` constants and run `make generate-docs`.*