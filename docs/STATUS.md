# Ankh-Morpork Scramble — Project Status
Last updated: 2026-04-04

## Recently completed

- Bug fixes: ghost occupancy, turnover logic, memory leak watchdog (2026-04-04)
- UI: SVG pitch animations — moveFlash, ballLand, CSS transitions (2026-04-04)
- UI: persistent leaderboard (leaderboard_store.py, JSONL storage) (2026-04-04)
- UI: game log with filter tabs (All / Combat / Ball / Turnovers), newest-first (2026-04-04)
- UI: Dibbler (CMOT) replaces Havelock Bluntt as commentator — commercial voice, fires per-turn + turnovers (2026-04-04)
- UI: Dibbler commentary ticker bar in header — scrolling, always visible (2026-04-04)
- UI: Dibbler commentary injected into event log as styled rows (2026-04-04)
- UI: responsive layout — mobile scrollable, pitch first, aspect-ratio sizing (2026-04-04)
- UI: sticky bottom tab bar on mobile — 44px touch targets (2026-04-04)
- UI: Strategy tab on mobile — team thoughts accessible without sidebars (2026-04-04)
- UI: persistent ref-strip on mobile — Dibbler's latest always visible above tabs (2026-04-04)
- UI: split-view tab added then removed — superseded by ticker approach (2026-04-04)
- Leaderboard benchmark: 6 stat dimensions (Aggression, Recklessness, Ball Craft, Lethality, Verbosity, Efficiency) (2026-04-04)
- Leaderboard benchmark: card view with stat bars, sortable table, view toggle (2026-04-04)
- Agents: Dibbler remembers previous lines, players see key moments (game history context) (2026-04-04)
- About page, turtle favicon, AndreasThinks footer (2026-04-04)

## In progress

- Mixed ticker feed (game events + commentary, colour-coded), collapsible info panel, mobile polish (Cline PID 135821 — plan: 2026-04-04-ticker-mix-collapse-mobile.md)
- Player state rendered on pitch tokens (standing/stunned/KO), event flash on involved players, active team border around pitch (Cline PID 136883 — plan: 2026-04-04-pitch-state-visuals.md)

## Next steps (prioritised)

1. UU roster completion — add 5 missing positions (Haste Mage, Divination Wizard, Transformed Wizard, The Librarian, Archchancellor Ridcully), fix fallback roster 422 in simple_agents/player.py, regenerate ROSTERS.md (plan: 2026-04-04-uu-roster-completion.md)
2. Tackle zones — visualise threatened squares on the pitch so players can see where they need dodge rolls
3. Post-ticker polish — verify mixed ticker looks good once Cline finishes; review collapsible state on desktop vs mobile

## Deferred / backlog

- Tackle zones visualisation (not yet planned in detail)
- Tournament bracket / season management UI
- Replay / game history viewer
- Sound / notification on goal or casualty
- Dark/light theme toggle
