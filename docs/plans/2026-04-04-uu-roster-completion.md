# Unseen University Roster Completion

> **For Cline or Hermes:** Implement in order. Each task is a self-contained commit.

**Goal:** Add five missing Unseen University player positions to `UNSEEN_UNIVERSITY_POSITIONS`
and fix the broken fallback roster in `simple_agents/player.py`.

**Root cause:** `app/models/enums.py` was extended with four named groups of UU skills
(`Speed skills`, `Tech skills`, `Librarian skills`, `Ridcully skills`, `Orangutan skills`)
intended for new player positions, but the positions themselves were never added to
`UNSEEN_UNIVERSITY_POSITIONS` in `app/models/team.py`. The fallback roster in
`simple_agents/player.py` references `haste_mage` — one of the missing positions — causing
a `422 Invalid position` error every time the LLM roster call fails and the hardcoded
fallback is used.

**Scope:** Two files change. No new skills needed — all are already in `SkillType`.
No test changes needed — no tests enumerate UU positions by name.

**Architecture:** Five new positions, each mapping directly to unused `SkillType` entries,
each balanced against a City Watch counterpart.

```
app/models/team.py           — add 5 positions to UNSEEN_UNIVERSITY_POSITIONS
simple_agents/player.py      — fix fallback roster (line 112)
```

Run the docs generator after both changes to keep ROSTERS.md current.

---

## Roster design rationale

City Watch has 9 positions across all archetypes. UU currently has 3. The gap:

| Archetype | City Watch | UU (before) | UU (after) |
|---|---|---|---|
| Cheap lineman | Constable | Apprentice Wizard | Apprentice Wizard |
| Fast runner | Fleet Recruit | ❌ | **Haste Mage** |
| Dedicated passer | Clerk-Runner | ❌ | **Divination Wizard** |
| Cheap agile oddity | Street Veteran | ❌ | **Transformed Wizard** |
| Blocker | Watch Sergeant | Senior Wizard | Senior Wizard |
| Big guy | Troll Constable | Animated Gargoyle | Animated Gargoyle |
| Star player 1 | Sgt. Detritus ⭐ | ❌ | **The Librarian** ⭐ |
| Star player 2 | Capt. Carrot ⭐ | ❌ | **Archchancellor Ridcully** ⭐ |

All five new positions use skills already declared in `SkillType`. The Watchdog analogue
(fast blitzer) is intentionally omitted — UU can reach parity with 8 positions.

---

## Task 1: Add five positions to UNSEEN_UNIVERSITY_POSITIONS

**File:** `app/models/team.py`

**Find:**
```python
    "animated_gargoyle": PlayerPosition(
        role="Animated Gargoyle",
        cost=115000,
        max_quantity=1,
        ma=4,
        st=5,
        ag="5+",
        pa="5+",
        av="10+",
        skills=[
            SkillType.BOUND_SPIRIT,
            SkillType.STONE_THICK,
            SkillType.PIGEON_PROOF,
            SkillType.MINDLESS_MASONRY,
            SkillType.WEATHERED,
            SkillType.LOB_THE_LACKEY,
            SkillType.OCCASIONAL_BITE_MARK
        ],
        primary=["S"],
        secondary=["A", "G", "P"]
    ),
}
```

**Replace with** (append five new positions before the closing `}`):
```python
    "animated_gargoyle": PlayerPosition(
        role="Animated Gargoyle",
        cost=115000,
        max_quantity=1,
        ma=4,
        st=5,
        ag="5+",
        pa="5+",
        av="10+",
        skills=[
            SkillType.BOUND_SPIRIT,
            SkillType.STONE_THICK,
            SkillType.PIGEON_PROOF,
            SkillType.MINDLESS_MASONRY,
            SkillType.WEATHERED,
            SkillType.LOB_THE_LACKEY,
            SkillType.OCCASIONAL_BITE_MARK
        ],
        primary=["S"],
        secondary=["A", "G", "P"]
    ),

    # --- NEW positions ---

    # Fast runner. UU answer to the Fleet Recruit (MA8, AV7+ — fast but fragile).
    # Skills: Sprint + Dodge. Max 2 — magical acceleration is rare.
    "haste_mage": PlayerPosition(
        role="Haste Mage",
        cost=75000,
        max_quantity=2,
        ma=8,
        st=2,
        ag="3+",
        pa="5+",
        av="7+",
        skills=[
            SkillType.HASTE_SPELL,    # Sprint
            SkillType.BLINK_DODGE,    # Dodge
        ],
        primary=["A", "G"],
        secondary=["P"]
    ),

    # Dedicated passer. UU answer to the Clerk-Runner (PA2+, Sure Hands, Safe Pass).
    # Slower and frailer than the Clerk-Runner (MA5, ST2) but equally gifted with the ball.
    "divination_wizard": PlayerPosition(
        role="Divination Wizard",
        cost=85000,
        max_quantity=2,
        ma=5,
        st=2,
        ag="3+",
        pa="2+",
        av="8+",
        skills=[
            SkillType.CALCULATED_TRAJECTORY,  # Pass
            SkillType.HEX_ASSISTED,           # Sure Hands
            SkillType.SAFE_PAIR_OF_HANDS,     # Safe Pass
        ],
        primary=["P", "A"],
        secondary=["G"]
    ),

    # Cheap agile oddity. A wizard who accidentally transformed themselves into an orangutan
    # and hasn't quite worked out how to change back. Surprisingly strong and very agile
    # (AG2+), but distracted and hard to direct (Loner 4+). Max 2.
    "transformed_wizard": PlayerPosition(
        role="Transformed Wizard",
        cost=60000,
        max_quantity=2,
        ma=5,
        st=3,
        ag="2+",
        pa="6+",
        av="8+",
        skills=[
            SkillType.SIMIAN_AGILITY,  # Leap
            SkillType.FOUR_LIMBS,      # Extra Arms
            SkillType.INDEPENDENT,     # Loner (4+)
        ],
        primary=["A"],
        secondary=["G", "S"]
    ),

    # Star player 1 — The Librarian. ST4, AG2+ (exceptional), Frenzy + Guard + Leap.
    # UU answer to Sergeant Detritus. Ook.
    "the_librarian": PlayerPosition(
        role="The Librarian",
        cost=150000,
        max_quantity=1,
        ma=5,
        st=4,
        ag="2+",
        pa="6+",
        av="9+",
        skills=[
            SkillType.PREHENSILE_EVERYTHING,  # Extra Arms
            SkillType.LIBRARY_SWINGING,       # Leap
            SkillType.PROTECTIVE_INSTINCT,    # Guard
            SkillType.BIBLIOPHILE_RAGE,       # Frenzy
            SkillType.TERRIFYING_GLARE,       # Disturbing Presence
        ],
        primary=["S", "A"],
        secondary=["G"],
        is_star_player=True
    ),

    # Star player 2 — Archchancellor Mustrum Ridcully. Leader + Block + Guard + Pass.
    # UU answer to Captain Carrot. Loud, stubborn, surprisingly effective.
    "archchancellor_ridcully": PlayerPosition(
        role="Archchancellor Ridcully",
        cost=140000,
        max_quantity=1,
        ma=6,
        st=4,
        ag="3+",
        pa="3+",
        av="10+",
        skills=[
            SkillType.ARCHCHANCELLOR,         # Leader
            SkillType.ROBUST_PHYSIQUE,        # Block
            SkillType.BOOMING_VOICE,          # Guard
            SkillType.ARCANE_MASTERY,         # Pass
            SkillType.HEADOLOGY_EXPERT,       # Hypnotic Gaze
            SkillType.STUBBORN,               # Stand Firm
        ],
        primary=["G", "S", "P"],
        secondary=["A"],
        is_star_player=True
    ),
}
```

**Verification:**
```bash
cd ~/projects/ankh-morpork-scramble
uv run python -c "
from app.models.team import TEAM_ROSTERS
from app.models.enums import TeamType
r = TEAM_ROSTERS[TeamType.UNSEEN_UNIVERSITY]
print('UU positions:', list(r.positions.keys()))
assert 'haste_mage' in r.positions
assert 'divination_wizard' in r.positions
assert 'transformed_wizard' in r.positions
assert 'the_librarian' in r.positions
assert 'archchancellor_ridcully' in r.positions
assert r.positions['the_librarian'].is_star_player
assert r.positions['archchancellor_ridcully'].is_star_player
print('All assertions passed.')
"
```

**Commit:** `feat(roster): add 5 missing UU positions — Haste Mage, Divination Wizard, Transformed Wizard, The Librarian, Archchancellor Ridcully`

---

## Task 2: Fix the fallback roster in the agent

**File:** `simple_agents/player.py`

**Objective:** Replace the broken `haste_mage` reference in the hardcoded fallback roster
with valid position keys. While we're here, make the fallback actually representative of a
balanced UU squad now that we have more positions to choose from.

**Find (line 112):**
```python
            roster = {"players": ["apprentice_wizard"]*6 + ["haste_mage"]*2, "rerolls": 2}
```

**Replace with:**
```python
            roster = {
                "players": (
                    ["apprentice_wizard"] * 4
                    + ["haste_mage"] * 2
                    + ["divination_wizard"] * 2
                    + ["senior_wizard"] * 1
                ),
                "rerolls": 2,
            }
```

Budget check: 4×45k + 2×75k + 2×85k + 1×90k + 2×60k rerolls = 180k + 150k + 170k + 90k + 120k = **710k** (well within 1,000k budget).

**Verification:**
```bash
cd ~/projects/ankh-morpork-scramble
uv run python -c "
from app.models.team import TEAM_ROSTERS
from app.models.enums import TeamType
r = TEAM_ROSTERS[TeamType.UNSEEN_UNIVERSITY]
fallback = (
    ['apprentice_wizard'] * 4
    + ['haste_mage'] * 2
    + ['divination_wizard'] * 2
    + ['senior_wizard'] * 1
)
for key in fallback:
    assert key in r.positions, f'Invalid position key in fallback: {key}'
cost = sum(r.positions[k].cost for k in fallback) + 2 * 60000  # 2 rerolls
assert cost <= 1_000_000, f'Fallback roster too expensive: {cost}'
print(f'Fallback valid. Total cost: {cost:,}g')
"
```

**Commit:** `fix(agents): UU fallback roster — replace haste_mage with valid position keys`

---

## Task 3: Regenerate ROSTERS.md

**File:** `skills/scramble-setup/references/ROSTERS.md`

**Objective:** The roster reference doc is auto-generated from `app/models/team.py`.
Run the generator to include the five new positions.

```bash
cd ~/projects/ankh-morpork-scramble
uv run python -m docs_generator
```

If that fails, try:
```bash
uv run python docs_generator/main.py
```

If neither works, find the entry point:
```bash
grep -r "def main\|if __name__" docs_generator/ --include="*.py" -l
```

Then run the correct script. Confirm `skills/scramble-setup/references/ROSTERS.md` now
shows all eight UU positions including the five new ones.

If the generator is broken or unavailable, manually update `ROSTERS.md` to add the five
new rows to the UU positions table, following the existing format. The table header is:
```
| Position | Cost | Qty | MA | ST | AG | PA | AV | Skills | Primary | Secondary |
```

**Commit:** `docs(roster): regenerate ROSTERS.md with new UU positions`

---

## Final verification

Run the full test suite:
```bash
cd ~/projects/ankh-morpork-scramble
uv run pytest -x -q
```

Then confirm the buy-player endpoint accepts the new positions:
```bash
# Start the server
uv run uvicorn app.main:app --port 8001 &
sleep 3

# Quick smoke test — create a game and try buying a haste_mage
curl -s -X POST "http://localhost:8001/game/test-roster/buy-player?team_id=team2&position_key=haste_mage" \
  | python3 -m json.tool

# Should return the player data, not a 422
# Clean up
kill %1
```

---

## What this fixes

| Before | After |
|---|---|
| UU has 3 positions | UU has 8 positions |
| No fast runner (Fleet Recruit equivalent) | Haste Mage: MA8, Dodge, Sprint |
| No dedicated passer (Clerk-Runner equivalent) | Divination Wizard: PA2+, Sure Hands, Safe Pass |
| No agile cheap option (Street Veteran equivalent) | Transformed Wizard: AG2+, Leap, Extra Arms |
| No star players | The Librarian ⭐ + Archchancellor Ridcully ⭐ |
| Fallback roster 422s on every LLM failure | Fallback uses 4 valid keys, costs 710k |
| 5 SkillType sections declared but unused | All UU skills now assigned to positions |
