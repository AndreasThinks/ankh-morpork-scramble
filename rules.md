# Ankh-Morpork Scramble — Official Rules (Server Edition)

> **DISCLAIMER**: This is an unofficial, non-commercial fan project created purely for entertainment and educational purposes. It is inspired by Games Workshop's Blood Bowl and Terry Pratchett's Discworld universe. This project is not affiliated with, endorsed by, or connected to Games Workshop Limited, Terry Pratchett's estate, or any official Discworld or Blood Bowl properties. All rights to Blood Bowl belong to Games Workshop. All rights to Discworld characters and settings belong to the Terry Pratchett estate. This is a tribute project by fans, for fans.

Welcome to **Ankh-Morpork Scramble**, the city's most prestigious, least-regulated street-sport where the **City Watch** attempts to maintain order while the **Wizards of the Unseen University** attempt to… *improvise applied thaumic physics on the opposing team*. The ball is regulation-approved (the paperwork says so), violence is discouraged but deeply traditional, and the Patrician absolutely denies ever having sanctioned this.

This specification defines a machine-readable, server-oriented rulebook. It is designed for deterministic, turn-based execution where the server stores and validates all game state. The rules below are written as clean formal Markdown — suitable for programmatic reference or rule-engine implementation.

---

## 1. Game Summary

- Two teams compete to score **Scratches** by carrying the ball into the opponent's end zone.
- A match consists of **two halves**, each **8 turns per team**.
- The team with the most Scratches at the end of the match wins.
- Draws are allowed, unless the Patrician says otherwise (consult optional overtime rules).

---

## 2. Pitch & Setup

- Pitch size: **26 × 15 squares**.
- Each half begins with a **Kick-Off**.
- Team size on pitch: **3–11 players**.
- Maximum **2** players per wide zone during setup.
- Receiving team may place up to **2** players in opponent half during setup (not beyond LOS).

---

## 3. Turn Structure

Each turn consists of:

1. Validate active team
2. Declare and execute actions (see below)
3. Check turnover conditions
4. End turn

A **turnover** immediately ends the active turn.

---

## 4. Actions (Per Turn)

| Action | Limit |
|---|---|
| Move | Unlimited (1 per player) |
| Block (Scuffle) | Unlimited |
| Blitz | **1 per turn** |
| Pass | **1 per turn** |
| Hand-off | **1 per turn** |
| Foul | **1 per turn** |
| Stand Up | As needed |

Players may perform **one action** per turn unless otherwise permitted by skills.

---

## 5. Player States

- **Standing**
- **Prone**
- **Stunned**
- **Knocked Out**
- **Casualty/Removed**

---

## 6. Movement Rules

- A player may move up to **Movement Allowance (MA)**.
- **Rush** (extra movement): up to **2 squares**, each requiring a **2+** roll.
- Leaving a square in an enemy **Tackle Zone** requires a **Dodge** roll.
- Standing up costs **3 MA**.
- No entering occupied squares.

---

## 7. Ball Handling

- **Pick-Up**: Agility test; failure causes turnover.
- **Catch**: Agility test; success required to gain possession.
- **Scatter**: If ball is dropped or missed, scatter one square for drop, or per pass result.

---

## 8. Passing

- One **Pass Action** per turn.
- Roll vs **Passing Ability (PA)**.
- Result categories:
  - Accurate
  - Inaccurate
  - Wildly Inaccurate
  - Fumble (turnover)

Interference (interception attempt) is one roll by a single eligible opponent.

---

## 9. Blocking (Scuffling)

- Adjacent opponent required.
- Compare Strength; determine dice:
  - Stronger: attacker chooses result
  - Equal: dice per standard strength table
- Block dice outcomes:
  - Attacker Down
  - Both Down
  - Push
  - Defender Stumbles
  - Defender Down

Follow-ups optional unless compelled by a trait.

---

## 10. Armour & Injury

1. If knocked down, roll **2d6 vs Armour Value (AV)**.
2. On success, roll **2d6 injury**:
   - **2–7** Stunned
   - **8–9** Knocked Out
   - **10+** Casualty

Casualties roll on **d16 lasting injury** table (e.g. stat loss, miss next game, death).

---

## 11. Turnovers

Turn ends immediately if:

- Ball carrier is knocked down
- Failed pick-up
- Failed pass (fumble or no valid catch after scatter)
- Failed catch by active team
- Failed dodge
- Failed rush
- Illegal action attempt
- Team commits a foul and is sent off

---

## 12. Re-Rolls

- Team re-rolls: one per roll, per turn.
- Skill-based re-rolls follow individual rules.
- No roll may be re-rolled more than once.

---

## 13. Teams & Rosters

### 13.1 City Watch

| Role | Qty | Cost | MA | ST | AG | PA | AV | Skills | Prim | Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| Constable | 0–16 | 50k | 6 | 3 | 3+ | 4+ | 9+ | — | G | A,S |
| Clerk-Runner | 0–2 | 80k | 6 | 3 | 3+ | 2+ | 9+ | Pigeon Post, Chain of Custody | G,P | A,S |
| Fleet Recruit | 0–4 | 65k | 8 | 2 | 3+ | 5+ | 8+ | Quick Grab, Sidestep Shuffle | A,G | P,S |
| Watch Sergeant | 0–4 | 85k | 7 | 3 | 3+ | 4+ | 9+ | Drill-Hardened | G,S | A,P |

**Team Re-rolls:** 50k each (max 8)

### 13.2 Unseen University Wizards

| Role | Qty | Cost | MA | ST | AG | PA | AV | Skills/Traits | Prim | Sec |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| Apprentice Wizard | 0–12 | 45k | 6 | 2 | 3+ | 4+ | 8+ | Blink, Small & Sneaky, Portable, Pointy Hat Padding | A | G,P,S |
| Senior Wizard | 0–6 | 90k | 4 | 4 | 4+ | 5+ | 10+ | Reroll the Thesis, Grappling Cantrip | G,S | A,P |
| Animated Gargoyle | 0–1 | 115k | 4 | 5 | 5+ | 5+ | 10+ | Bound Spirit, Stone-Thick, Pigeon-Proof, Mindless Masonry, Weathered, Lob the Lackey, Occasional Bite Mark | S | A,G,P |

**Team Re-rolls:** 60k each (max 8)

---

## 14. Skills (Thematic Names)

| Themed Name | Effect |
|---|---|
| Drill-Hardened | Block |
| Pigeon Post | Pass |
| Chain of Custody | Sure Hands |
| Quick Grab | Catch |
| Sidestep Shuffle | Dodge |
| Blink | Dodge |
| Small & Sneaky | Stunty |
| Portable | Right Stuff |
| Pointy Hat Padding | Thick Skull |
| Reroll the Thesis | Brawler |
| Grappling Cantrip | Grab |
| Bound Spirit | Loner (3+) |
| Stone-Thick | Mighty Blow (+1) |
| Pigeon-Proof | Projectile Vomit |
| Mindless Masonry | Really Stupid |
| Weathered | Regeneration |
| Lob the Lackey | Throw Team-Mate |
| Occasional Bite Mark | Always Hungry |

---

## 15. Weather (Optional)

| Roll | Weather | Effect |
|---:|---|---|
| 2 | Sweltering Heat | D3 players rest next drive |
| 3 | Very Sunny | –1 to passing |
| 4–10 | Perfect | Normal |
| 11 | Pouring Rain | –1 to ball handling |
| 12 | Blizzard | –1 rush; only short passes |

---

## 16. Server Requirements

- Server maintains authoritative state: board, players, turn, re-rolls, ball, modifiers.
- All moves validated against state rules before execution.
- Server logs all events and dice rolls.
- Suggested API actions:
  - `/create`, `/join`, `/state`
  - `/setup`, `/action`, `/reroll`
  - `/valid-actions`, `/end-turn`

---

## 17. Victory

- Highest Scratches at end of second half wins.
- Optional sudden-death overtime if configured.

---

##End of Specification
