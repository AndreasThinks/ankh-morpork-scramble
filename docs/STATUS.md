# Ankh-Morpork Scramble — Project Status
Last updated: 2026-04-05

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
- UI: player state on pitch tokens (standing/stunned/KO visuals), event flash on involved players, active team border (2026-04-04) [COMPLETE]
- UI: mixed ticker infrastructure — tickerQueue, pushToTicker, refreshTicker, styled CSS classes, collapsible info panel, tab-collapse-btn, mobile max-height 40vh (2026-04-04) [PARTIALLY COMPLETE — see outstanding issues]

## Code review findings — 2026-04-05

Reviewed both Cline implementation jobs against their plan files. Plan files were already
moved to docs/plans/done/ prior to this review.

### Job 2: Pitch state visuals (plan: 2026-04-04-pitch-state-visuals.md) — COMPLETE ✓

All expected changes are present and correctly implemented:

- buildPlayerToken(playerId, player, pos, team, isCarrier): present, full standing/stunned/KO
  branching on playerState, correct labels (✕ for KO, ~ for stunned, role initials for standing)
- updatePlayerToken(token, playerId, player, pos, team, isCarrier): present, re-applies state
  styling on every poll update so mid-turn knockdowns are reflected immediately
- fireEventFlash(playerId, result, role): present, correct color logic (gold attacker, red
  failure/turnover, blue defender push), SVG circle appended and removed on animationend
- renderPitch() uses buildPlayerToken / updatePlayerToken: present (lines ~2548-2560)
- Active team border: present (lines ~2603-2625), reads SVG viewBox for sizing, blue/orange/gold
  colour per active team
- @keyframes eventFlash + .event-flash CSS: present (lines 231-239)
- renderGameLog wires fireEventFlash for attacker + defender: present (lines ~3171-3179)

Minor deviation: circle r=0.45 in code vs r=0.42 in plan spec — harmless, slightly larger token.

### Job 1: Mixed ticker + collapsible panel + mobile polish (plan: 2026-04-04-ticker-mix-collapse-mobile.md) — PARTIALLY COMPLETE

Items confirmed present and correctly implemented:

- tickerQueue array + TICKER_MAX = 10: present (lines ~3559-3560)
- pushToTicker(type, icon, text, category): present, correctly shifts queue, calls refreshTicker
- refreshTicker(): present, builds fragment of styled spans, recalculates scroll animation duration
- Collapsible panel HTML (tab-collapse-btn button in tab bar): present (lines ~1948-1949)
- Collapsible CSS (.tab-collapse-btn, .panels-collapsed rules): present (lines ~712-738)
- Collapse toggle IIFE with localStorage key 'ams-panels-collapsed': present (lines ~3765-3783)
- Ticker CSS classes (.ticker-item--commentary/event/combat/ball/turnover, .ticker-sep): present (lines ~1719-1736)
- Ticker badge label changed to "📡 Live": present (line 1908)
- Mobile tab panel max-height: 40vh: present (line 1820)

Outstanding gaps — unchanged from previous review, still need fixing:

- MISSING: pushToTicker is never called from injectCommentaryIntoLog (function ends at ~line 3042
  without a pushToTicker call) — commentary never enters the ticker feed
- MISSING: pushToTicker is never called from renderGameLog (function ends at ~line 3180 with only
  a fireEventFlash call, no pushToTicker) — game events never enter the ticker feed
- WRONG: Mobile CSS still contains `.global-ticker { display: none; }` (line 1861 inside
  @media max-width: 768px) — ticker remains hidden on mobile despite plan requiring removal

The ticker infrastructure is complete and correct. Only the three call-site wiring points and
one CSS rule need fixing.

Note on display artifacts: the read_file tool shows some long lines abbreviated as e.g.
`const token=tokenE...Id);` and `let tokenElements=*** Map();`. These are display truncations
only — confirmed via od(1) that the actual file bytes contain valid JS (`tokenElements.get(playerId)`
and `new Map()`). There are no real syntax errors in the file.

## Outstanding issues

The ticker/collapse/mobile job (plan: 2026-04-04-ticker-mix-collapse-mobile.md) has three gaps:

- MISSING: `pushToTicker` is never called from `injectCommentaryIntoLog` — commentary never enters the ticker feed
- MISSING: `pushToTicker` is never called from `renderGameLog` — game events never enter the ticker feed
- WRONG: Mobile CSS still contains `.global-ticker { display: none; }` (line ~1861) — ticker remains hidden on mobile despite plan requiring removal

The ticker infrastructure (tickerQueue, TICKER_MAX, pushToTicker, refreshTicker, all CSS) is implemented and correct. Only the call-site wiring and the mobile display rule need fixing.

## Current priority

1. **uu-roster-completion** — add 5 missing positions (Haste Mage, Divination Wizard, Transformed Wizard, The Librarian, Archchancellor Ridcully), fix fallback roster 422 in simple_agents/player.py, regenerate ROSTERS.md (plan: 2026-04-04-uu-roster-completion.md)
2. Fix ticker wiring gaps listed above (small targeted edits to dashboard.html)
3. Tackle zones — visualise threatened squares on the pitch so players can see where they need dodge rolls

## Deferred / backlog

- Tackle zones visualisation (not yet planned in detail)
- Tournament bracket / season management UI
- Replay / game history viewer
- Sound / notification on goal or casualty
- Dark/light theme toggle
