# Ankh-Morpork Scramble — Outstanding Work

_Last updated: 2026-04-05_

---

## Pitch Display

### Tackle zones overlay _(medium effort, high value)_
Every on-pitch player threatens their 8 adjacent squares. Render as a faint
tint overlay on those squares — red-tinted for enemy zones, blue-tinted for
friendly. Computable entirely from `state.pitch.player_positions`, no API
change needed. Most tactically important missing visual on the board.

**Where:** `renderPitch()` in `dashboard.html` — compute after player positions
are known, draw a rect layer beneath tokens.

---

### Live stats tab _(separate API call, new tab)_
`/game/{game_id}/statistics` endpoint exists and is completely unused.
Per-player: touchdowns, blocks_thrown, knockdowns_caused, dodges, catches,
injuries_caused, times_knocked_down. Per-team: passes, completions, turnovers.

**Where:** Add a 6th tab ("📊 Stats") to the tab bar. Fetch `/statistics` on
each poll cycle alongside the main state. Render as two compact tables
(one per team) inside the new tab panel.

---

## UX / Mobile

### Reroll counter
`team.rerolls_total` and `team.rerolls_used` are in the state, never shown.
Add a small reroll pip display near each team's score — e.g. `↺ 2/3`.

---

## Roster

### UU roster completion
Missing wizard positions and fallback roster errors flagged in STATUS.md.
Wizards need full position definitions (MA/ST/AG/PA/AV + skills).
