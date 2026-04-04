# Game Log Improvements Plan

> **For Cline or Hermes:** Implement in order. Each task is a self-contained commit.
> No new npm dependencies. No new Python packages. Vanilla JS and FastAPI only.

**Goal:** Replace the fragile markdown-based game log with a structured, event-typed,
incrementally-updated log panel that renders directly from `state.events` (already in the
game state response). Add visual hierarchy, a filter bar, inline dice display, and an event
count badge.

**Root cause of current problems:**
1. A separate HTTP fetch (`/game/{id}/log?format=markdown`) fires on every state poll —
   a redundant round-trip since `state.events` is already in the main `/game/{id}` response.
2. `parseMarkdownToHTML()` is a five-regex kludge that breaks on nested structures, emoji
   in code, and any markdown the backend generates that wasn't anticipated.
3. `reverseMarkdownSections()` is a bespoke section-reversal hack with off-by-one edge cases.
4. `gameLogEntries.innerHTML = html` replaces the entire DOM on every poll — causing reflow,
   scroll position fighting, and three variables of compensating state.
5. All events look identical: monospace, same muted colour, no visual hierarchy.
6. No filter bar. No dice display. No event count badge.

**Architecture of the fix:** Three-file change — no backend changes required.
1. `app/web/templates/dashboard.html` — HTML structure (log header + filter bar)
2. `app/web/templates/dashboard.html` — CSS (new event-typed rules, remove markdown rules)
3. `app/web/templates/dashboard.html` — JS (new `renderGameLog()`, remove dead code)

All tasks touch the same file (dashboard.html) and should be committed separately for
easy review and rollback.

---

## Current state assessment

### What works
- The log panel exists and renders something every poll.
- The markdown endpoint (`/game/{id}/log`) produces a reasonable narrative.
- Scroll-position preservation logic exists (even if flawed).

### What is broken / painful
| Problem | Root cause |
|---|---|
| Double HTTP request per poll | `fetchGameLog()` hits `/log?format=markdown` separately from the state fetch |
| Regex markdown parser | `parseMarkdownToHTML()` — 5 fragile regexes, breaks on emoji/special chars |
| Full DOM replacement | `innerHTML = html` — flicker, scroll fights, wasted work |
| Section reversal hack | `reverseMarkdownSections()` — 30 lines of bespoke parser |
| Monochrome events | All events are `color: var(--muted)`, `font-family: monospace` |
| No filter bar | Can't focus on combat / ball / turnovers |
| No dice display | `dice_rolls` on `GameEvent` is completely ignored |
| No event count badge | Header just says "Recent Events" |

### What `state.events` already gives us
Every `GET /game/{id}` response includes `state.events: list[GameEvent]` where each event has:
- `event_id` (UUID string) — stable identity
- `event_type` (string enum: move, dodge, block, touchdown, turnover, …)
- `result` (success | failure | partial | turnover | neutral)
- `player_name`, `target_player_name` — display-ready names
- `half`, `turn_number` — timing context
- `dice_rolls: [{type, result, target, success, modifiers}]`
- `description` — a pre-built human-readable string

We do not need the markdown endpoint at all.

---

## Task 1: HTML — restructure the log panel header

**File:** `app/web/templates/dashboard.html`

**Objective:** Replace the plain `<h3>` with a flex row that holds the title, an event-count
badge, and a filter bar below it. Also remove the `white-space: pre-wrap` and monospace font
from `.log-entries` (done in Task 2's CSS).

**Find (around line 1065):**
```html
        <div class="game-log" id="game-log">
            <h3>Recent Events</h3>
            <div class="log-entries" id="game-log-entries">The crowd waits for the opening whistle…</div>
        </div>
```

**Replace with:**
```html
        <div class="game-log" id="game-log">
            <div class="log-header">
                <h3>Match Events</h3>
                <span class="log-count-badge" id="log-count-badge" title="Total events logged">0</span>
            </div>
            <div class="log-filter-bar" id="log-filter-bar" role="group" aria-label="Filter events">
                <button class="log-filter active" data-filter="all">All</button>
                <button class="log-filter" data-filter="combat">Combat</button>
                <button class="log-filter" data-filter="ball">Ball</button>
                <button class="log-filter" data-filter="turnovers">Turnovers</button>
            </div>
            <div class="log-entries" id="game-log-entries" role="log" aria-live="polite" aria-label="Match events">
                <div class="log-event log-event--tier-quiet log-event--placeholder">
                    <span class="log-event-icon" aria-hidden="true">⏳</span>
                    <div class="log-event-body">
                        <span class="log-event-desc">The crowd waits for the opening whistle…</span>
                    </div>
                </div>
            </div>
        </div>
```

**Commit:** `feat(log): restructure log panel HTML — header badge + filter bar`

---

## Task 2: CSS — event-typed styles

**File:** `app/web/templates/dashboard.html`

**Objective:** Replace the monospace/pre-wrap log styles with structured event-row styles.
Add per-tier and per-type overrides. Add filter bar and badge styles. Add die face styles.

### Step A — remove the markdown-era rules

**Find (around line 545):**
```css
        .game-log .log-entries {
            flex: 1;
            font-size: 0.88rem;
            color: var(--muted);
            line-height: 1.6;
            overflow-y: auto;
            max-height: 400px;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
        }
```

**Replace with:**
```css
        .game-log .log-entries {
            flex: 1;
            font-size: 0.85rem;
            color: var(--muted);
            line-height: 1.5;
            overflow-y: auto;
            max-height: 420px;
            display: flex;
            flex-direction: column;
            gap: 0;
        }
```

**Find and delete in full** (lines ~556-609) — the markdown-rendered heading/list/hr rules
that are only needed for the now-dead HTML-from-markdown approach:
```css
        .game-log .log-entries h1,
        .game-log .log-entries h2,
        .game-log .log-entries h3 {
            color: var(--accent-gold);
            font-family: "Cinzel", "Times New Roman", serif;
            margin: 0.8rem 0 0.4rem;
            line-height: 1.3;
        }

        .game-log .log-entries h1 {
            font-size: 1.3rem;
            border-bottom: 2px solid rgba(217, 180, 91, 0.3);
            padding-bottom: 0.3rem;
        }

        .game-log .log-entries h2 {
            font-size: 1.1rem;
            border-bottom: 1px solid rgba(217, 180, 91, 0.2);
            padding-bottom: 0.25rem;
        }

        .game-log .log-entries h3 {
            font-size: 1rem;
        }

        .game-log .log-entries strong {
            color: var(--text);
            font-weight: 600;
        }

        .game-log .log-entries hr {
            border: none;
            border-top: 1px solid rgba(217, 180, 91, 0.25);
            margin: 0.8rem 0;
        }

        .game-log .log-entries ul {
            margin: 0.3rem 0;
            padding-left: 1.2rem;
        }

        .game-log .log-entries li {
            margin: 0.2rem 0;
        }
```

Also delete the table rules inside `.game-log .log-entries` (~lines 601-609):
```css
        .game-log .log-entries table {
            margin: 0.5rem 0;
            font-size: 0.85rem;
        }

        .game-log .log-entries th {
            color: var(--accent-gold);
            font-weight: 600;
        }
```

### Step B — add new structured event styles

**After the updated `.game-log .log-entries` block, insert the following CSS block in full.**
Place it immediately after the closing `}` of the `.game-log .log-entries` rule.

```css
        /* Log panel header: title + count badge on one row */
        .log-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.5rem;
            margin-bottom: 0.4rem;
        }

        .log-header h3 {
            margin: 0;
        }

        .log-count-badge {
            background: rgba(217, 180, 91, 0.18);
            border: 1px solid rgba(217, 180, 91, 0.35);
            color: var(--accent-gold);
            font-size: 0.72rem;
            font-family: "Cinzel", "Times New Roman", serif;
            padding: 0.1em 0.55em;
            border-radius: 999px;
            letter-spacing: 0.04em;
            min-width: 1.8em;
            text-align: center;
        }

        /* Filter bar */
        .log-filter-bar {
            display: flex;
            gap: 0.3rem;
            margin-bottom: 0.5rem;
            flex-wrap: wrap;
        }

        .log-filter {
            background: rgba(217, 180, 91, 0.06);
            border: 1px solid rgba(217, 180, 91, 0.22);
            color: rgba(242, 227, 198, 0.6);
            font-size: 0.72rem;
            font-family: "Cinzel", "Times New Roman", serif;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            padding: 0.2em 0.75em;
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.15s, color 0.15s, border-color 0.15s;
        }

        .log-filter:hover {
            background: rgba(217, 180, 91, 0.14);
            color: rgba(242, 227, 198, 0.85);
        }

        .log-filter.active {
            background: rgba(217, 180, 91, 0.22);
            border-color: rgba(217, 180, 91, 0.5);
            color: var(--accent-gold);
        }

        /* Base event row */
        .log-event {
            display: flex;
            align-items: baseline;
            gap: 0.4rem;
            padding: 0.25rem 0.5rem;
            border-left: 2px solid transparent;
            transition: background 0.1s;
            font-size: 0.82rem;
        }

        .log-event:hover {
            background: rgba(242, 227, 198, 0.04);
        }

        .log-event-icon {
            flex-shrink: 0;
            width: 1.2em;
            text-align: center;
            font-size: 0.85em;
            opacity: 0.8;
        }

        .log-event-body {
            flex: 1;
            min-width: 0;
            display: flex;
            flex-wrap: wrap;
            align-items: baseline;
            gap: 0.35rem;
        }

        .log-event-desc {
            color: var(--muted);
            word-break: break-word;
        }

        .log-event-turn {
            flex-shrink: 0;
            font-size: 0.68rem;
            color: rgba(217, 180, 91, 0.45);
            letter-spacing: 0.04em;
            margin-left: auto;
            padding-left: 0.4rem;
            font-family: "Cinzel", serif;
        }

        /* Result colour overrides */
        .log-event-desc.result--success {
            color: rgba(190, 220, 175, 0.85);
        }

        .log-event-desc.result--failure {
            color: rgba(220, 140, 120, 0.85);
        }

        .log-event-desc.result--turnover {
            color: rgba(230, 100, 90, 0.9);
        }

        /* Tier: quiet — MOVE, STAND_UP, TURN_START, TURN_END, ARMOR_BREAK, SCATTER, REROLL */
        .log-event--tier-quiet {
            opacity: 0.65;
            padding-top: 0.15rem;
            padding-bottom: 0.15rem;
            font-size: 0.78rem;
        }

        .log-event--tier-quiet .log-event-icon {
            opacity: 0.5;
        }

        /* Tier: action — BLOCK, FOUL, PASS, CATCH, PICKUP, DROP, HANDOFF, KICKOFF,
                          DODGE, RUSH, KNOCKDOWN */
        .log-event--tier-action {
            border-left-color: rgba(217, 180, 91, 0.2);
        }

        .log-event--tier-action .log-event-desc {
            color: rgba(242, 227, 198, 0.82);
        }

        /* Tier: dramatic — TURNOVER, INJURY, CASUALTY */
        .log-event--tier-dramatic {
            border-left-color: rgba(220, 100, 80, 0.6);
            background: rgba(220, 100, 80, 0.06);
        }

        .log-event--tier-dramatic .log-event-desc {
            color: rgba(242, 210, 180, 0.9);
        }

        /* Tier: landmark — TOUCHDOWN, HALF_START, HALF_END, GAME_START, GAME_END */
        .log-event--tier-landmark {
            border-left: none;
            background: rgba(217, 180, 91, 0.1);
            border-top: 1px solid rgba(217, 180, 91, 0.25);
            border-bottom: 1px solid rgba(217, 180, 91, 0.25);
            padding: 0.45rem 0.6rem;
            margin: 0.35rem 0;
        }

        .log-event--tier-landmark .log-event-desc {
            font-family: "Cinzel", "Times New Roman", serif;
            font-size: 0.88em;
            color: var(--accent-gold);
            letter-spacing: 0.04em;
        }

        /* TOUCHDOWN: gold banner */
        .log-event--touchdown {
            background: rgba(217, 180, 91, 0.18) !important;
            border-top: 1px solid rgba(217, 180, 91, 0.45) !important;
            border-bottom: 1px solid rgba(217, 180, 91, 0.45) !important;
            padding: 0.55rem 0.7rem !important;
            margin: 0.5rem 0 !important;
        }

        .log-event--touchdown .log-event-desc {
            font-size: 0.95em !important;
            font-weight: 600;
            color: #f0d87a !important;
        }

        /* TURNOVER: red accent */
        .log-event--turnover {
            border-left-color: rgba(220, 70, 60, 0.75) !important;
            background: rgba(220, 70, 60, 0.08) !important;
        }

        /* CASUALTY: dark red */
        .log-event--casualty {
            border-left-color: rgba(180, 40, 40, 0.8) !important;
            background: rgba(180, 40, 40, 0.1) !important;
        }

        /* HALF_START divider */
        .log-event--half-start {
            border-left: none !important;
            border-top: 2px solid rgba(217, 180, 91, 0.35) !important;
            border-bottom: 2px solid rgba(217, 180, 91, 0.35) !important;
            background: rgba(217, 180, 91, 0.07) !important;
            margin: 0.5rem 0 !important;
            text-align: center;
            justify-content: center;
        }

        /* Inline die display */
        .log-dice {
            display: inline-flex;
            gap: 0.2rem;
            align-items: center;
            font-size: 0.9em;
        }

        .die {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 1.4em;
            height: 1.4em;
            border-radius: 3px;
            font-size: 1em;
            cursor: default;
            border: 1px solid rgba(217, 180, 91, 0.2);
            background: rgba(217, 180, 91, 0.07);
            color: var(--muted);
        }

        .die--success {
            border-color: rgba(120, 200, 120, 0.45);
            background: rgba(100, 180, 100, 0.1);
            color: rgba(160, 220, 140, 0.9);
        }

        .die--failure {
            border-color: rgba(220, 100, 80, 0.45);
            background: rgba(200, 80, 60, 0.1);
            color: rgba(230, 140, 120, 0.9);
        }

        /* Placeholder row (shown before game starts) */
        .log-event--placeholder {
            opacity: 0.5;
            font-style: italic;
        }
```

**Commit:** `feat(log): replace markdown-era CSS with structured event-row styles`

---

## Task 3: JS — renderGameLog() and helpers

**File:** `app/web/templates/dashboard.html`

**Objective:** Add a `renderGameLog(events)` function plus four helper functions. Wire it
into `fetchState()`. This is the main work of the plan.

### Step A — add module-level state variables

**Find (around line 2132):**
```javascript
    // State tracking
    let consecutiveFailures = 0;
    let pollIntervalId = null;
    let isPolling = false;
    let scoreboardVisible = false;
    let scoreboardStatsCache = null;
    let prevTeam1Score = -1;
    let prevTeam2Score = -1;
    let lastUpdateTime = Date.now();
    let prevPlayerPositions = {};
```

**Replace with** (add two new tracking variables at the bottom of that block):
```javascript
    // State tracking
    let consecutiveFailures = 0;
    let pollIntervalId = null;
    let isPolling = false;
    let scoreboardVisible = false;
    let scoreboardStatsCache = null;
    let prevTeam1Score = -1;
    let prevTeam2Score = -1;
    let lastUpdateTime = Date.now();
    let prevPlayerPositions = {};
    let lastRenderedEventCount = 0;  // incremental log rendering
    let activeLogFilter = 'all';     // current filter tab
```

### Step B — add helper functions

**Find the line:**
```javascript
    function parseMarkdownToHTML(markdown) {
```

**Insert the following block immediately BEFORE that line** (the `parseMarkdownToHTML`
function itself will be deleted in Task 5, so don't touch it yet):

```javascript
    // -----------------------------------------------------------------------
    // Game log helpers
    // -----------------------------------------------------------------------

    /** Minimal HTML entity escaping for user-visible strings. */
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    /** Unicode die faces for d6 results 1-6. */
    const DICE_FACES = ['', '⚀', '⚁', '⚂', '⚃', '⚄', '⚅'];

    /** Icon for each event type. */
    const EVENT_ICONS = {
        touchdown:   '🏈',
        turnover:    '🔄',
        casualty:    '🚑',
        injury:      '⚡',
        knockdown:   '💫',
        armor_break: '🛡',
        block:       '💥',
        foul:        '👢',
        pass:        '📤',
        catch:       '🤲',
        pickup:      '⬆',
        drop:        '💧',
        scatter:     '🌬',
        handoff:     '🤝',
        kickoff:     '⚡',
        move:        '→',
        dodge:       '↩',
        rush:        '💨',
        stand_up:    '↑',
        reroll:      '🎲',
        half_start:  '📊',
        half_end:    '🏁',
        game_start:  '🎺',
        game_end:    '🏆',
        turn_start:  '▶',
        turn_end:    '⏸',
    };

    /** Visual tier for each event type — controls size and background. */
    function getEventTier(eventType) {
        const LANDMARK = new Set([
            'touchdown', 'half_start', 'half_end', 'game_start', 'game_end'
        ]);
        const DRAMATIC = new Set([
            'turnover', 'casualty', 'injury'
        ]);
        const QUIET = new Set([
            'move', 'stand_up', 'turn_start', 'turn_end', 'armor_break', 'scatter', 'reroll'
        ]);
        if (LANDMARK.has(eventType)) return 'landmark';
        if (DRAMATIC.has(eventType)) return 'dramatic';
        if (QUIET.has(eventType)) return 'quiet';
        return 'action';
    }

    /** Filter category for each event type. */
    function getEventCategory(eventType) {
        const COMBAT = new Set([
            'block', 'knockdown', 'armor_break', 'injury', 'casualty', 'foul'
        ]);
        const BALL = new Set([
            'pickup', 'drop', 'pass', 'catch', 'scatter', 'handoff', 'kickoff', 'touchdown'
        ]);
        if (COMBAT.has(eventType)) return 'combat';
        if (BALL.has(eventType)) return 'ball';
        return 'other';
    }

    /** Whether an event is visible under the currently active filter. */
    function eventMatchesFilter(eventType, result, filter) {
        if (filter === 'all') return true;
        if (filter === 'combat') return getEventCategory(eventType) === 'combat';
        if (filter === 'ball')   return getEventCategory(eventType) === 'ball';
        if (filter === 'turnovers') {
            return eventType === 'turnover' || result === 'failure';
        }
        return true;
    }

    /** Render dice rolls as inline die-face spans. */
    function renderDiceHTML(diceRolls) {
        if (!diceRolls || diceRolls.length === 0) return '';
        const dice = diceRolls.map(d => {
            const face = (d.result >= 1 && d.result <= 6)
                ? DICE_FACES[d.result]
                : String(d.result);
            const cls = d.success ? 'die--success' : 'die--failure';
            const tip = d.target
                ? `${d.type}: rolled ${d.result}, needed ${d.target}+`
                : `${d.type}: ${d.result}`;
            return `<span class="die ${cls}" title="${escapeHtml(tip)}">${face}</span>`;
        });
        return `<span class="log-dice">${dice.join('')}</span>`;
    }

    /**
     * Build a single event row DOM element.
     * Uses createElement (not innerHTML) to avoid nested escaping issues for the
     * description text; innerHTML is only used for the dice sub-element where we
     * control the content entirely.
     */
    function buildEventRow(event) {
        const el = document.createElement('div');
        const tier = getEventTier(event.event_type);
        const category = getEventCategory(event.event_type);
        const icon = EVENT_ICONS[event.event_type] || '•';
        const turnLabel = (event.turn_number > 0)
            ? `H${event.half}T${event.turn_number}`
            : '';

        // CSS class list: base + tier + specific type (underscores → hyphens)
        const typeClass = 'log-event--' + event.event_type.replace(/_/g, '-');
        el.className = `log-event ${typeClass} log-event--tier-${tier}`;

        // Data attributes used by the filter logic
        el.dataset.eventId   = event.event_id;
        el.dataset.category  = category;
        el.dataset.eventType = event.event_type;
        el.dataset.result    = event.result || '';

        // Icon
        const iconSpan = document.createElement('span');
        iconSpan.className = 'log-event-icon';
        iconSpan.setAttribute('aria-hidden', 'true');
        iconSpan.textContent = icon;
        el.appendChild(iconSpan);

        // Body: description + dice
        const body = document.createElement('div');
        body.className = 'log-event-body';

        const desc = document.createElement('span');
        const resultClass = event.result === 'success'  ? 'result--success'
                          : event.result === 'failure'  ? 'result--failure'
                          : event.result === 'turnover' ? 'result--turnover'
                          : '';
        desc.className = 'log-event-desc' + (resultClass ? ' ' + resultClass : '');
        desc.textContent = event.description || '';
        body.appendChild(desc);

        const diceHTML = renderDiceHTML(event.dice_rolls);
        if (diceHTML) {
            const diceEl = document.createElement('span');
            diceEl.innerHTML = diceHTML;
            body.appendChild(diceEl.firstChild);  // append the .log-dice span
        }

        el.appendChild(body);

        // Turn label
        if (turnLabel) {
            const turn = document.createElement('span');
            turn.className = 'log-event-turn';
            turn.textContent = turnLabel;
            el.appendChild(turn);
        }

        return el;
    }

    /**
     * Incrementally render new events into the log panel.
     *
     * Called with the full `state.events` array on every state poll.
     * Only events beyond `lastRenderedEventCount` are processed, so DOM
     * work is O(new events), not O(total events).
     *
     * If the events array has shrunk (game reset / rematch), the log is
     * cleared and rebuilt from scratch.
     *
     * Events are appended at the bottom (chronological order). The panel
     * auto-scrolls to show new events only when the user was already near
     * the bottom.
     */
    function renderGameLog(events) {
        if (!events) return;

        const container = document.getElementById('game-log-entries');
        if (!container) return;

        // Game reset detected — clear and restart
        if (events.length < lastRenderedEventCount) {
            container.innerHTML = '';
            lastRenderedEventCount = 0;
        }

        const newEvents = events.slice(lastRenderedEventCount);
        if (newEvents.length === 0) return;

        // Remove placeholder row on first real event
        if (lastRenderedEventCount === 0) {
            const placeholder = container.querySelector('.log-event--placeholder');
            if (placeholder) placeholder.remove();
        }

        // Determine scroll position before touching DOM
        const wasNearBottom =
            container.scrollHeight - container.scrollTop - container.clientHeight < 80;

        // Build and append new rows
        const fragment = document.createDocumentFragment();
        for (const event of newEvents) {
            const el = buildEventRow(event);
            // Apply current filter immediately so the row has the right visibility
            el.hidden = !eventMatchesFilter(
                event.event_type,
                event.result || '',
                activeLogFilter
            );
            fragment.appendChild(el);
        }
        container.appendChild(fragment);

        // Advance the pointer
        lastRenderedEventCount = events.length;

        // Update count badge
        const badge = document.getElementById('log-count-badge');
        if (badge) badge.textContent = String(events.length);

        // Auto-scroll to bottom only when user was already there
        if (wasNearBottom) {
            container.scrollTop = container.scrollHeight;
        }
    }
```

### Step C — wire renderGameLog into fetchState

**Find (around line 2173):**
```javascript
            // Fetch and render game log
            fetchGameLog();
```

**Replace with:**
```javascript
            // Render game log from structured events (already in state response)
            renderGameLog(data.events || []);
```

### Step D — wire renderGameLog into the rematch handler

**Find (around line 1948):**
```javascript
            fetchGameLog();
```
(This is the call inside the `startNewGameBtn` click handler, after `renderRoster(nextState)`)

**Replace with:**
```javascript
            renderGameLog(nextState.events || []);
```

### Step E — wire filter bar click handler

**Find the line:**
```javascript
    function startPolling() {
```

**Insert immediately BEFORE that line:**
```javascript
    // Filter bar — toggle active button and hide/show existing event rows
    document.getElementById('log-filter-bar').addEventListener('click', (e) => {
        const btn = e.target.closest('.log-filter');
        if (!btn) return;

        document.querySelectorAll('.log-filter').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeLogFilter = btn.dataset.filter;

        const container = document.getElementById('game-log-entries');
        container.querySelectorAll('.log-event').forEach(el => {
            el.hidden = !eventMatchesFilter(
                el.dataset.eventType || '',
                el.dataset.result || '',
                activeLogFilter
            );
        });
    });

```

### Step F — update the initial boot call

**Find (around line 2268):**
```javascript
    // Initialize
    initPitchGrid();
    fetchGameLog();  // Initial log fetch
    startPolling();
```

**Replace with:**
```javascript
    // Initialize
    initPitchGrid();
    startPolling();  // fetchState() will call renderGameLog() on first poll
```

**Commit:** `feat(log): renderGameLog() — incremental structured-event rendering`

---

## Task 4: JS — remove dead code

**File:** `app/web/templates/dashboard.html`

**Objective:** Delete the three functions that are now completely unused.

### Delete `parseMarkdownToHTML`

Find and delete the entire block (approximately lines 1702-1724):
```javascript
    function parseMarkdownToHTML(markdown) {
        let html = markdown;

        // Headers
        html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
        html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');

        // Horizontal rules
        html = html.replace(/^---$/gm, '<hr>');

        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        // Lists (basic support)
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

        // Line breaks
        html = html.replace(/\n/g, '<br>');

        return html;
    }
```

### Delete `reverseMarkdownSections`

Find and delete the entire block (approximately lines 1997-2028):
```javascript
    function reverseMarkdownSections(markdown) {
        if (!markdown || markdown.trim() === '') {
            return markdown;
        }

        // Split by major sections (lines starting with # or ##)
        const lines = markdown.split('\n');
        const sections = [];
        let currentSection = [];
        
        for (const line of lines) {
            // Check if this is a major heading (# or ##)
            if (line.match(/^##?\s/)) {
                // Save previous section if it exists
                if (currentSection.length > 0) {
                    sections.push(currentSection.join('\n'));
                    currentSection = [];
                }
            }
            currentSection.push(line);
        }
        
        // Don't forget the last section
        if (currentSection.length > 0) {
            sections.push(currentSection.join('\n'));
        }
        
        // Reverse sections (newest first)
        sections.reverse();
        
        return sections.join('\n\n');
    }
```

### Delete `fetchGameLog`

Find and delete the entire block (approximately lines 1961-1995):
```javascript
    async function fetchGameLog() {
        try {
            const response = await fetch(`/game/${gameId}/log?format=markdown`);
            if (!response.ok) {
                throw new Error(`Failed to load game log (${response.status})`);
            }
            const markdown = await response.text();

            // Reverse the markdown content to show newest events first
            const reversedMarkdown = reverseMarkdownSections(markdown);
            
            // Parse and render markdown
            const html = parseMarkdownToHTML(reversedMarkdown);
            
            // Preserve scroll position or stay at top for new content
            const wasAtTop = gameLogEntries.scrollTop === 0;
            const oldScrollHeight = gameLogEntries.scrollHeight;
            const oldScrollTop = gameLogEntries.scrollTop;
            
            gameLogEntries.innerHTML = html;
            
            // Scroll: snap to bottom if near it, otherwise preserve relative position
            const isNearBottom = gameLogEntries.scrollHeight - gameLogEntries.scrollTop - gameLogEntries.clientHeight < 120;
            if (isNearBottom) {
                gameLogEntries.scrollTop = gameLogEntries.scrollHeight;
            } else if (!wasAtTop && oldScrollHeight > 0) {
                const newScrollHeight = gameLogEntries.scrollHeight;
                const heightDifference = newScrollHeight - oldScrollHeight;
                gameLogEntries.scrollTop = oldScrollTop + heightDifference;
            }
        } catch (error) {
            console.error('Failed to fetch game log:', error);
            // Keep existing content on error
        }
    }
```

**Commit:** `refactor(log): remove fetchGameLog, parseMarkdownToHTML, reverseMarkdownSections`

---

## Task 5 (optional): Backend — slim events endpoint for large games

**This task is not required for correctness.** Implement it if playtesting reveals the
`/game/{id}` state payload is slow (>200ms) due to large event arrays in long games.

**Problem:** Every state poll returns ALL events ever recorded, even though the frontend
only needs events since `lastRenderedEventCount`. For a full game with many MOVE events,
`state.events` can grow to 500+ objects, adding ~150KB to every poll response.

**Solution:** Add `GET /game/{game_id}/events?after=N` that returns only events at index
N and beyond, plus the total count.

**File:** `app/main.py`

**After the `/game/{game_id}/history` endpoint (around line 703), insert:**

```python
@app.get("/game/{game_id}/events")
def get_game_events(game_id: str, after: int = Query(0, ge=0)):
    """
    Return structured game events after a given index.

    Use `after=N` where N is the number of events already held by the client
    to receive only new events. Returns the total event count so the client can
    track the pointer.

    Returns:
        {"total": int, "events": list[GameEvent]}
    """
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    all_events = game_state.events
    return {
        "total": len(all_events),
        "events": all_events[after:]
    }
```

**Frontend changes (if Task 5 backend is deployed):**
- In `fetchState()`, remove the `renderGameLog(data.events || [])` call.
- Add a separate `fetchNewEvents()` async function that calls
  `/game/{id}/events?after={lastRenderedEventCount}`, receives `{total, events}`, and calls
  `renderGameLog` with a synthetic array of the right total length.
- Call `fetchNewEvents()` from `fetchState()` instead.

Because this is a non-trivial refactor and only matters at scale, defer it unless needed.

**Commit (if implemented):** `feat(api): GET /game/{id}/events?after=N — incremental event fetch`

---

## Verification steps

### After Task 1 (HTML)
```
Open the dashboard. Confirm the log panel shows:
- "Match Events" title on the left
- A "0" badge on the right
- Four filter buttons: All, Combat, Ball, Turnovers
- A placeholder "The crowd waits..." row
```

### After Task 2 (CSS)
```
Open the dashboard before a game starts.
Confirm the log panel does NOT use monospace font and pre-wrap layout.
The placeholder row should be italic and slightly faded.
```

### After Task 3 (renderGameLog)
```
Start a game and watch the log panel:
1. GAME_START / HALF_START should appear as a gold banner row (landmark tier)
2. TOUCHDOWN should appear as a prominent gold-background row with bold text
3. TURNOVER rows should have a red left border and reddish background
4. MOVE / TURN_START rows should be visually compact and faded (quiet tier)
5. Rows with dice rolls should show die faces (⚀–⚅) coloured green (success) or red (failure)
6. The "0" badge should increment as events accumulate
7. The panel auto-scrolls when near the bottom; does NOT scroll when you have scrolled up
8. No 404 errors appear in browser console (fetchGameLog no longer called)
9. No second HTTP request to /game/{id}/log in the Network tab
```

### After Task 4 (dead code removal)
```
Confirm in browser DevTools → Network that only ONE request per poll fires:
    GET /game/{game_id}
(Not two: the old code fired GET /game/{game_id} + GET /game/{game_id}/log)

Search dashboard.html source for "fetchGameLog" — should return 0 results.
Search for "parseMarkdownToHTML" — should return 0 results.
Search for "reverseMarkdownSections" — should return 0 results.
```

### Filter bar
```
Click "Combat": only BLOCK, KNOCKDOWN, INJURY, CASUALTY, FOUL, ARMOR_BREAK rows visible.
Click "Ball":   only PICKUP, DROP, PASS, CATCH, SCATTER, HANDOFF, KICKOFF, TOUCHDOWN visible.
Click "Turnovers": only TURNOVER events and failed-result events visible.
Click "All":    all events visible again.
Start a new game while on "Combat" filter: new events still respect the active filter.
```

### Game reset (rematch)
```
Complete a game, start a new one via "Start New Game".
Confirm the log panel clears and begins fresh (event count badge resets to 0).
```

---

---

## Task 5 (added): Newest-first ordering — log and team messages

### Game log: prepend instead of append

The current plan appends new events at the bottom and auto-scrolls. Change `renderGameLog()`
to **prepend** new events at the top so the most recent action is always visible without
scrolling.

In `renderGameLog()`, change the scroll logic and insertion point:

```javascript
// Replace:
container.appendChild(fragment);
// ...
if (wasNearBottom) {
    container.scrollTop = container.scrollHeight;
}

// With:
container.insertBefore(fragment, container.firstChild);
// No auto-scroll needed — newest is always at the top.
// Remove the wasNearBottom scroll block entirely.
```

Also remove the `wasNearBottom` variable and its setup since it's no longer needed.

The `lastRenderedEventCount` tracking still works correctly — we still only process
`events.slice(lastRenderedEventCount)`, but we insert the fragment before existing rows.

For the game-reset path (`events.length < lastRenderedEventCount`), clear and rebuild
from scratch as before — no change needed there.

### Team messages: reverse order

In `renderThoughts()`, the messages are fetched as `.slice(-4)` (last 4). Reverse this
slice before rendering so the newest message appears at the top of each team panel.

**Find in `renderThoughts()`:**
```javascript
[state.team1.id]: data.messages.filter(m => m.sender_id === state.team1.id).slice(-4),
[state.team2.id]: data.messages.filter(m => m.sender_id === state.team2.id).slice(-4)
```

**Replace with:**
```javascript
[state.team1.id]: data.messages.filter(m => m.sender_id === state.team1.id).slice(-4).reverse(),
[state.team2.id]: data.messages.filter(m => m.sender_id === state.team2.id).slice(-4).reverse()
```

Also update `renderFallbackThoughts()` — after `.sort((a, b) => a.priority - b.priority).slice(0, 4)`,
add `.reverse()` so the fallback matches.

**Commit:** `feat(log): newest-first ordering for game log and team messages`

---

## Task 6 (added): Layout — remove fixed heights, use full screen

### Problem

`.positions-panel` has `max-height: 400px; overflow-y: auto` which creates an awkward
scroll box inside the sidebar. The sidebar panels don't stretch to use the full screen
height. The three-column layout (`main` grid) doesn't tell columns to fill vertically.

### CSS fixes

**1. Remove the fixed max-height on `.positions-panel`:**

Find:
```css
        .positions-panel {
            margin-top: 1.5rem;
            background: rgba(30, 19, 10, 0.75);
            border-radius: 14px;
            border: 1px solid rgba(217, 180, 91, 0.22);
            padding: 1rem 1.25rem;
            max-height: 400px;
            overflow-y: auto;
        }
```

Replace with:
```css
        .positions-panel {
            margin-top: 1.5rem;
            background: rgba(30, 19, 10, 0.75);
            border-radius: 14px;
            border: 1px solid rgba(217, 180, 91, 0.22);
            padding: 1rem 1.25rem;
        }
```

**2. Make the three-column grid fill the viewport height:**

Find:
```css
        main {
            flex: 1;
            padding: clamp(1.5rem, 3vw, 3rem);
            display: grid;
            grid-template-columns: minmax(220px, 1fr) minmax(560px, 2fr) minmax(220px, 1fr);
            gap: clamp(1rem, 2.5vw, 2rem);
        }
```

Replace with:
```css
        main {
            flex: 1;
            padding: clamp(1.5rem, 3vw, 3rem);
            display: grid;
            grid-template-columns: minmax(220px, 1fr) minmax(560px, 2fr) minmax(220px, 1fr);
            grid-template-rows: 1fr;
            align-items: start;
            gap: clamp(1rem, 2.5vw, 2rem);
            min-height: 0;
        }
```

**3. Make sidebar panels stretch and scroll internally rather than capping at fixed heights:**

Add after the `.panel` block:
```css
        .thoughts,
        aside.panel {
            display: flex;
            flex-direction: column;
        }

        .thoughts ul {
            flex: 1;
            overflow-y: auto;
            max-height: 60vh;
        }
```

This allows the thoughts/strategy panels to grow to use available space but caps their
scroll area at 60% of viewport height so they don't push everything else off screen on
small viewports.

**4. Cap the game log at a viewport-relative height instead of a fixed pixel value:**

Find:
```css
        .game-log .log-entries {
            ...
            max-height: 420px;
```

Change `max-height: 420px` to `max-height: 55vh`.

This means on a tall monitor the log shows more events; on a laptop it stays reasonable.

**Commit:** `fix(layout): remove fixed heights, use viewport-relative sizing`

---

## What this fixes

| Before | After |
|---|---|
| 2 HTTP requests per poll (state + markdown log) | 1 HTTP request per poll |
| Fragile 5-regex markdown parser | Structured `GameEvent` data, no parsing |
| Full DOM replacement every 2.5s | O(new events) append only |
| Bespoke section-reversal hack | Monotonic append, no reversal needed |
| All events look identical (monospace, one colour) | 4 visual tiers + per-type overrides |
| No filter bar | All / Combat / Ball / Turnovers |
| Dice rolls ignored | Die faces (⚀–⚅) with success/failure colour |
| No event count badge | Live counter in panel header |
| No `escapeHtml()` utility | Added as `escapeHtml()` in JS module scope |
| Newest events buried at bottom, requires scrolling | Newest events at top — visible immediately |
| Team messages in chronological order | Newest message first in each team panel |
| positions-panel fixed at 400px — awkward scroll box | No fixed height — flows naturally |
| Layout doesn't fill screen height | Viewport-relative heights, columns fill available space |

## Execution notes

- Tasks 1 and 2 (HTML + CSS) can be done first and tested independently — the placeholder
  row will still show until Task 3 adds the JS.
- Tasks 3 and 4 must be done together in one session; Task 4 (dead code removal) makes the
  file safe to deploy only after Task 3 has replaced all call sites.
- The `escapeHtml()` function added in Task 3 is useful beyond the log — it can be used
  anywhere in the file that currently does unsafe string interpolation into innerHTML.
- MOVE events are the most frequent. If they clutter the "All" view too much in practice,
  add a fifth filter "Actions" that hides move/stand_up/turn_start/turn_end, or add a
  "collapse consecutive moves" post-processing step in `renderGameLog`. That is out of scope
  here.
- The `aria-live="polite"` on `.log-entries` tells screen readers to announce new log entries
  without interrupting ongoing speech — appropriate for a live game ticker.
