# UI Improvements Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Fix broken UI data bindings, improve information hierarchy, and make the spectator experience genuinely good.

**Architecture:** All changes are in `app/web/templates/dashboard.html` (vanilla JS + Jinja2) unless noted. No new dependencies. Backend changes only where field names need fixing.

**Tech Stack:** FastAPI, Jinja2, vanilla JS, CSS custom properties. Polling at 2500ms via setInterval.

---

## Phase 1: Bug Fixes (do these first, they're embarrassing)

### Task 1: Fix Available Positions field name mismatches

**Objective:** The positions panel shows "undefined" stats because the JS uses wrong field names vs. the API response.

**Files:**
- Modify: `app/web/templates/dashboard.html` — `fetchAndRenderPositions` function (~line 1845)

**The problem:** API returns `quantity_limit`, `quantity_owned`, and stats nested in a `stats` dict.
JS uses `pos.max_quantity`, `pos.current_quantity`, `pos.ma`, `pos.st`, `pos.ag`, `pos.pa`, `pos.av`.

**Fix:** Update the render function to use correct field names:

```javascript
const quantityText = pos.quantity_owned >= pos.quantity_limit
    ? `<span style="color: rgba(224, 86, 86, 0.8);">Max reached (${pos.quantity_owned}/${pos.quantity_limit})</span>`
    : `${pos.quantity_owned}/${pos.quantity_limit} owned`;

const s = pos.stats || {};
return `
    <div class="position-item">
        <div class="position-header">
            <span class="position-name">${escapeHtml(pos.role)}</span>
            <span class="position-cost">${formatGold(pos.cost)}</span>
        </div>
        <div class="position-stats">
            <span class="position-stat">MA ${s.ma ?? pos.ma ?? '?'}</span>
            <span class="position-stat">ST ${s.st ?? pos.st ?? '?'}</span>
            <span class="position-stat">AG ${s.ag ?? pos.ag ?? '?'}</span>
            <span class="position-stat">PA ${s.pa ?? pos.pa ?? '?'}</span>
            <span class="position-stat">AV ${s.av ?? pos.av ?? '?'}</span>
        </div>
        <div class="position-quantity">${quantityText}</div>
    </div>
`;
```

**Verify:** Load `/ui` during setup phase — position cards should show real stats.

**Commit:** `fix: available-positions field names (quantity_limit, quantity_owned, stats.*)`

---

### Task 2: Fix "Awaiting team communication..." false loading state

**Objective:** Coach comms panel says "Awaiting..." even when there are simply no messages yet. Should be neutral.

**Files:**
- Modify: `app/web/templates/dashboard.html` — `renderThoughts` function (~line 1298)

**Fix:** Change the empty-state string from loading-style language to neutral:

```javascript
container.innerHTML = '<li style="color: var(--muted); font-style: italic; padding: 0.5rem 0;">No messages yet this match.</li>';
```

Same fix for referee commentary empty state (~line 1379):
```javascript
commentaryText.textContent = 'Havelock Bluntt has yet to pass judgement.';
commentaryText.classList.remove('loading');
```

**Commit:** `fix: neutral empty states for coach comms and referee commentary`

---

### Task 3: Treasury "Loading..." stuck state

**Objective:** If the budget fetch fails or game is not in setup, show a sensible fallback.

**Files:**
- Modify: `app/web/templates/dashboard.html` — `fetchAndRenderBudget` (~line 1810)

**Fix:** Add error handling and a "not available" state:

```javascript
async function fetchAndRenderBudget(teamId, containerId) {
    try {
        const response = await fetch(`/game/${gameId}/team/${teamId}/budget`);
        if (!response.ok) {
            document.getElementById(containerId).querySelector('.budget-details').innerHTML =
                '<div style="color: var(--muted); font-style: italic;">Treasury data unavailable.</div>';
            return;
        }
        // ... existing render logic
    } catch (error) {
        document.getElementById(containerId).querySelector('.budget-details').innerHTML =
            '<div style="color: var(--muted); font-style: italic;">Treasury data unavailable.</div>';
    }
}
```

**Commit:** `fix: treasury shows unavailable state instead of stuck Loading...`

---

## Phase 2: Information Hierarchy

### Task 4: Make the score dominant

**Objective:** Score is visually buried. It should be the first thing your eye goes to.

**Files:**
- Modify: `app/web/templates/dashboard.html` — `.score-line` CSS and scoreboard HTML

**Changes:**
- Increase score value font size from `clamp(1.5rem, 3.2vw, 2.5rem)` to `clamp(2.5rem, 5vw, 4rem)`
- Add a subtle animated pulse on score change (JS: detect score delta between polls, briefly add a `.score-changed` class)
- Team names in the score line: uppercase, bold, larger

```css
.score-line .score-value {
    font-size: clamp(2.5rem, 5vw, 4rem);
    color: var(--accent-gold);
    font-weight: 700;
    letter-spacing: 0.05em;
}

@keyframes scoreFlash {
    0%   { color: var(--accent-gold); }
    50%  { color: #fff; text-shadow: 0 0 20px rgba(217,180,91,0.9); }
    100% { color: var(--accent-gold); }
}
.score-changed {
    animation: scoreFlash 0.6s ease;
}
```

**JS:** In `updateScoreboard`, compare new score to previous, add `.score-changed` class on change.

**Commit:** `feat: prominent score display with flash animation on change`

---

### Task 5: Status bar with colour-coded game state

**Objective:** "BALL OFF PITCH", "NO ACTIVE TURN", phase — currently buried in tiny chips. Promote to a visible status bar.

**Files:**
- Modify: `app/web/templates/dashboard.html`

**Add a status bar between header and main content:**

```html
<div id="status-bar" class="status-bar">
    <span id="status-phase" class="status-chip"></span>
    <span id="status-turn" class="status-chip"></span>
    <span id="status-ball" class="status-chip"></span>
    <span id="status-live" class="status-chip status-live">● LIVE</span>
</div>
```

```css
.status-bar {
    display: flex;
    gap: 0.75rem;
    padding: 0.6rem clamp(1.2rem, 4vw, 4rem);
    background: rgba(15, 9, 4, 0.6);
    border-bottom: 1px solid rgba(217, 180, 91, 0.15);
    flex-wrap: wrap;
    align-items: center;
}
.status-chip {
    padding: 0.25rem 0.7rem;
    border-radius: 999px;
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-family: "Cinzel", serif;
    border: 1px solid rgba(217, 180, 91, 0.25);
    background: rgba(73, 50, 24, 0.5);
    color: var(--muted);
}
.status-chip.danger  { background: rgba(180, 60, 60, 0.3); border-color: rgba(220, 80, 80, 0.5); color: #e07856; }
.status-chip.active  { background: rgba(60, 140, 60, 0.3); border-color: rgba(80, 180, 80, 0.5); color: #7ecb7e; }
.status-live { color: rgba(127, 200, 127, 0.9); border-color: rgba(80, 180, 80, 0.4); font-size: 0.72rem; }
```

Populate from `updateScoreboard`: phase → chip, active_team → chip (green), ball position → chip (red if off-pitch).

**Commit:** `feat: status bar with colour-coded phase, turn, and ball state`

---

### Task 6: "Updated X seconds ago" live indicator

**Objective:** Reassure spectators the view is live.

**Files:**
- Modify: `app/web/templates/dashboard.html`

**Add to status bar:**

```javascript
let lastUpdateTime = Date.now();

// In fetchState, on success:
lastUpdateTime = Date.now();

// Separate 1s interval:
setInterval(() => {
    const secs = Math.floor((Date.now() - lastUpdateTime) / 1000);
    const liveChip = document.getElementById('status-live');
    if (liveChip) {
        liveChip.textContent = secs < 5 ? '● LIVE' : `↻ ${secs}s ago`;
        liveChip.style.color = secs > 10 ? '#e07856' : '';
    }
}, 1000);
```

**Commit:** `feat: live update ticker in status bar`

---

## Phase 3: Spectator Experience

### Task 7: Auto-scroll game log to bottom

**Objective:** New events should be visible without manual scrolling.

**Files:**
- Modify: `app/web/templates/dashboard.html` — `fetchGameLog` function (~line 1739)

**Fix:** After updating innerHTML, scroll the log entries div to the bottom:

```javascript
const logEntries = logDiv.querySelector('.log-entries');
// ... existing render ...
logEntries.scrollTop = logEntries.scrollHeight;
```

Only auto-scroll if user is already near the bottom (within 100px), so manual scroll position is respected:

```javascript
const isNearBottom = logEntries.scrollHeight - logEntries.scrollTop - logEntries.clientHeight < 100;
if (isNearBottom) logEntries.scrollTop = logEntries.scrollHeight;
```

**Commit:** `feat: game log auto-scrolls to bottom on new events`

---

### Task 8: Player movement highlight on pitch

**Objective:** When players move between polls, briefly highlight their new position so spectators can follow the action.

**Files:**
- Modify: `app/web/templates/dashboard.html` — `renderPitch` function

**Approach:** Store previous player positions. On each render, compare. Any player whose position changed gets a highlight circle for 1.5s.

```javascript
let prevPlayerPositions = {};

// In renderPitch, after drawing players:
Object.entries(playerPositions).forEach(([pid, pos]) => {
    const prev = prevPlayerPositions[pid];
    if (prev && (prev.x !== pos.x || prev.y !== pos.y)) {
        // Draw a fading highlight ring at new position
        ctx.beginPath();
        ctx.arc(/* new cell centre */, cellW * 0.38, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255, 255, 180, 0.85)';
        ctx.lineWidth = 2;
        ctx.stroke();
    }
});
prevPlayerPositions = { ...playerPositions };
```

Since canvas redraws every poll, a simpler approach: store moved pids in a Set, draw a highlight ring on them during this render, clear the Set next render.

**Commit:** `feat: pitch highlights player movement between polls`

---

### Task 9: Score flash on touchdown

**Objective:** When a score changes, make it unmissable.

**Files:**
- Modify: `app/web/templates/dashboard.html`

**Approach:** Track `prevScore` per team. On score delta, add `.score-changed` (from Task 4) to the score value element. Also briefly show a full-width toast:

```javascript
function showScoringToast(teamName) {
    const toast = document.createElement('div');
    toast.className = 'scoring-toast';
    toast.textContent = `⚡ SCRATCH! ${teamName} scores!`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
```

```css
.scoring-toast {
    position: fixed;
    top: 2rem;
    left: 50%;
    transform: translateX(-50%);
    background: var(--accent-gold);
    color: #1f160c;
    font-family: "Cinzel", serif;
    font-size: 1.4rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    padding: 0.75rem 2rem;
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.6);
    z-index: 100;
    animation: toastIn 0.3s ease;
}
@keyframes toastIn {
    from { opacity: 0; transform: translateX(-50%) translateY(-1rem); }
    to   { opacity: 1; transform: translateX(-50%) translateY(0); }
}
```

**Commit:** `feat: scoring toast and score flash on touchdown`

---

## Phase 4: Polish

### Task 10: Mobile layout

**Objective:** The 3-column grid collapses badly on small screens.

**Files:**
- Modify: `app/web/templates/dashboard.html` — existing `@media (max-width: 1100px)` block

**Extend:**
```css
@media (max-width: 700px) {
    main {
        padding: 1rem;
        gap: 1rem;
    }
    header h1 { font-size: 1.6rem; }
    .score-line { flex-direction: column; gap: 0.5rem; }
    .pitch-canvas { aspect-ratio: 15 / 26; } /* portrait on mobile */
}
```

**Commit:** `fix: mobile layout at 700px breakpoint`

---

### Task 11: Turn counter in status bar

**Objective:** Show "Turn 3, Half 1" so spectators know where in the match they are.

**Files:**
- Modify: `app/web/templates/dashboard.html` — `updateScoreboard` + status bar

**Add to status bar population in updateScoreboard:**
```javascript
if (data.turn) {
    statusTurn.textContent = `Half ${data.turn.half} · Turn ${data.turn.team_turn + 1}`;
    statusTurn.className = 'status-chip active';
} else {
    statusTurn.textContent = 'No active turn';
    statusTurn.className = 'status-chip';
}
```

**Commit:** `feat: turn and half counter in status bar`

---

## Execution Order

1–3: Do these immediately (bugs, shipping embarrassment)
4–6: Information hierarchy (one session)
7–9: Spectator experience (one session)
10–11: Polish (quick wins, do last)

Each task is a self-contained commit. No task depends on a later one except Task 11 which extends Task 5's status bar.
