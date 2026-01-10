# Team Rosters Reference

**Auto-generated from `app/models/team.py`** - Do not edit manually!

Team rosters for Ankh-Morpork Scramble, including player positions, costs, stats, and skills.

## Standard Team Budget

**1,000,000gp** gold pieces per team

---

## City Watch

**Reroll Cost**: 50,000gp  
**Maximum Rerolls**: 8

### Positions

| Position | Cost | Qty | MA | ST | AG | PA | AV | Skills | Primary | Secondary |
|----------|------|-----|----|----|----|----|----|----|---------|-----------|| Constable | 50,000gp | 16 | 6 | 3 | 3+ | 4+ | 9+ | — | G | A, S || Clerk-Runner | 80,000gp | 2 | 6 | 3 | 3+ | 2+ | 9+ | pigeon_post, chain_of_custody | G, P | A, S || Fleet Recruit | 65,000gp | 4 | 8 | 2 | 3+ | 5+ | 8+ | quick_grab, sidestep_shuffle | A, G | P, S || Watch Sergeant | 85,000gp | 4 | 7 | 3 | 3+ | 4+ | 9+ | drill_hardened | G, S | A, P || Troll Constable | 115,000gp | 2 | 4 | 5 | 5+ | 6+ | 10+ | thick_as_a_brick, rock_solid, really_thick | S | G, A || Street Veteran | 50,000gp | 4 | 6 | 2 | 3+ | 5+ | 8+ | street_fighting, slippery | G, A | S || Watchdog | 90,000gp | 2 | 7 | 3 | 3+ | 4+ | 9+ | lupine_speed, keen_senses, regenerative | G, A | S, P || Sergeant Detritus ⭐ | 150,000gp | 1 | 5 | 5 | 4+ | 6+ | 10+ | cooling_helmet, rock_solid, thick_as_a_brick, crossbow_training, break_heads, kingly_presence | S | G || Captain Carrot Ironfoundersson ⭐ | 130,000gp | 1 | 6 | 4 | 3+ | 3+ | 10+ | true_king, kingly_presence, honest_fighter, will_not_back_down, diplomatic_immunity, trusted_by_all | G, P | S, A |
**⭐** = Star Player (unique, maximum 1)

---

## Unseen University

**Reroll Cost**: 60,000gp  
**Maximum Rerolls**: 8

### Positions

| Position | Cost | Qty | MA | ST | AG | PA | AV | Skills | Primary | Secondary |
|----------|------|-----|----|----|----|----|----|----|---------|-----------|| Apprentice Wizard | 45,000gp | 12 | 6 | 2 | 3+ | 4+ | 8+ | blink, small_and_sneaky, portable, pointy_hat_padding | A | G, P, S || Senior Wizard | 90,000gp | 6 | 4 | 4 | 4+ | 5+ | 10+ | reroll_the_thesis, grappling_cantrip | G, S | A, P || Animated Gargoyle | 115,000gp | 1 | 4 | 5 | 5+ | 5+ | 10+ | bound_spirit, stone_thick, pigeon_proof, mindless_masonry, weathered, lob_the_lackey, occasional_bite_mark | S | A, G, P |
**⭐** = Star Player (unique, maximum 1)

---

## Stat Definitions

- **Cost**: Gold pieces required to purchase this position
- **Qty**: Maximum quantity allowed on roster
- **MA**: Movement Allowance (squares per turn)
- **ST**: Strength (for blocking/combat)
- **AG**: Agility (target number for dodge/catch/pickup rolls, e.g., "3+" means need 3-6 on d6)
- **PA**: Passing Ability (target number for throwing, e.g., "4+" means need 4-6 on d6)
- **AV**: Armour Value (target number for armor rolls, e.g., "9+" means need 9+ on 2d6 to injure)
- **Skills**: Starting skills for this position
- **Primary**: Primary skill categories for advancement (cheaper)
- **Secondary**: Secondary skill categories for advancement (more expensive)

## Skill Categories

- **G**: General (universal skills)
- **A**: Agility (dodging, catching, movement)
- **S**: Strength (blocking, injuries)
- **P**: Passing (throwing, hand-offs)

---

*This file is auto-generated from code. To update rosters, edit `app/models/team.py` and run `make generate-docs`.*