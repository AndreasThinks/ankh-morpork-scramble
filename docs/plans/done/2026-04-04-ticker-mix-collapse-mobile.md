# Plan: Mixed Ticker, Collapsible Info Panel, Mobile Polish

**File to edit:** `app/web/templates/dashboard.html` (single file, ~3550 lines)

---

## Task 1: Mixed-feed ticker (events + commentary, styled differently)

### Goal
The header ticker currently shows only the latest Dibbler commentary line.
Replace it with a rolling queue of both game events AND commentary, visually
distinguished by style.

### New JS state (add near `lastRenderedEventCount` / `lastInjectedCommentaryText`):
```js
let tickerQueue = [];   // [{type, icon, text, category}]
const TICKER_MAX = 10;
```

### New function: `pushToTicker(type, icon, text, category)`
Called whenever a new event or commentary item arrives.
```js
function pushToTicker(type, icon, text, category) {
    tickerQueue.push({ type, icon, text, category: category || '' });
    if (tickerQueue.length > TICKER_MAX) tickerQueue.shift();
    refreshTicker();
}
```

### New function: `refreshTicker()`
Rebuilds `#ticker-text` innerHTML as a row of styled spans, then recalculates
scroll duration.
```js
function refreshTicker() {
    const inner = document.getElementById('ticker-text');
    if (!inner || tickerQueue.length === 0) return;
    const frag = document.createDocumentFragment();
    tickerQueue.forEach((item, i) => {
        if (i > 0) {
            const sep = document.createElement('span');
            sep.className = 'ticker-sep';
            sep.textContent = '  ·  ';
            frag.appendChild(sep);
        }
        const span = document.createElement('span');
        const catClass = item.category ? ` ticker-item--${item.category}` : '';
        span.className = `ticker-item ticker-item--${item.type}${catClass}`;
        span.textContent = `${item.icon} ${item.text}`;
        frag.appendChild(span);
    });
    inner.innerHTML = '';
    inner.appendChild(frag);
    const totalChars = tickerQueue.reduce((n, item) => n + item.text.length + 5, 0);
    const duration = Math.min(50, Math.max(15, Math.round(totalChars * 0.22)));
    inner.style.animation = 'none';
    void inner.offsetWidth; // force reflow
    inner.style.animation = `tickerScroll ${duration}s linear infinite`;
}
```

### Wire into `injectCommentaryIntoLog(text)`
After the existing DOM insertion logic (the `container.appendChild(el)` block),
add:
```js
pushToTicker('commentary', '⚖', text, 'commentary');
```

### Wire into `renderGameLog(events)`
After `lastRenderedEventCount = events.length;`, push the new events:
```js
for (const event of newEvents) {
    const icon = EVENT_ICONS[event.event_type] || '•';
    const cat = getEventCategory(event.event_type);
    pushToTicker('event', icon, event.description || event.event_type, cat);
}
```
(Only push the `newEvents` slice, not the full array.)

### Update ticker badge label
Change `.ticker-badge` HTML from `⚖ Dibbler` to `📡 Live` to reflect mixed feed.

### New CSS (add inside the `.global-ticker` block, after `.ticker-inner` styles):
```css
.ticker-item { display: inline; }
.ticker-item--commentary {
    font-style: italic;
    color: rgba(217, 180, 91, 0.72);
}
.ticker-item--event {
    font-style: normal;
    color: rgba(242, 227, 198, 0.88);
}
.ticker-item--combat  { color: rgba(220, 110, 90, 0.9); }
.ticker-item--ball    { color: rgba(100, 185, 230, 0.9); }
.ticker-item--turnover { color: rgba(220, 175, 60, 0.95); font-weight: 600; }
.ticker-sep {
    color: rgba(217, 180, 91, 0.25);
    font-style: normal;
    user-select: none;
}
```

### Mobile: un-hide the ticker
In the `@media (max-width: 768px)` block, remove or override the `.global-ticker { display: none; }` rule.
The ticker is now useful enough on mobile to show. Keep the ref-strip too — it shows the full commentary paragraph, the ticker shows the live feed. They serve different purposes.

---

## Task 2: Collapsible info panel

### Goal
A toggle button on the tab bar collapses all `.tab-panel` divs, leaving only
the pitch + tab bar visible. User can collapse to full-pitch view and still
follow via the ticker. State persisted in `localStorage`.

### HTML change
Add a collapse toggle at the end of `#pitch-tab-bar`, after the last `<button>`:
```html
<button class="tab-collapse-btn" id="tab-collapse-btn"
        title="Hide info panel" aria-expanded="true">▼</button>
```

### CSS (add after `.tab-btn` styles):
```css
.tab-collapse-btn {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--muted);
    font-size: 0.65rem;
    padding: 0 0.75rem;
    min-height: 44px;          /* touch-friendly */
    cursor: pointer;
    opacity: 0.55;
    transition: opacity 0.15s, transform 0.25s;
    flex-shrink: 0;
}
.tab-collapse-btn:hover { opacity: 1; }

/* Collapsed state: hide all tab panels */
.pitch-panel.panels-collapsed .tab-panel {
    display: none !important;
}
/* Rotate chevron when collapsed */
.pitch-panel.panels-collapsed .tab-collapse-btn {
    transform: rotate(180deg);
}
/* Remove bottom border gap when panels hidden */
.pitch-panel.panels-collapsed .tab-bar {
    border-bottom: 1px solid rgba(217, 180, 91, 0.12);
}
```

### JS (add in the init section, after the filter-bar click handler):
```js
// Info panel collapse toggle
(function () {
    const collapseBtn = document.getElementById('tab-collapse-btn');
    const pitchPanel  = document.querySelector('.pitch-panel');
    if (!collapseBtn || !pitchPanel) return;
    const KEY = 'ams-panels-collapsed';

    function applyCollapsed(collapsed) {
        pitchPanel.classList.toggle('panels-collapsed', collapsed);
        collapseBtn.setAttribute('aria-expanded', String(!collapsed));
        collapseBtn.title = collapsed ? 'Show info panel' : 'Hide info panel';
    }

    // Restore persisted state
    applyCollapsed(localStorage.getItem(KEY) === '1');

    collapseBtn.addEventListener('click', () => {
        const nowCollapsed = !pitchPanel.classList.contains('panels-collapsed');
        applyCollapsed(nowCollapsed);
        localStorage.setItem(KEY, nowCollapsed ? '1' : '0');
    });
})();
```

---

## Task 3: Mobile polish

### Issues to fix:

1. **Ticker hidden on mobile** — fixed in Task 1 above (remove `display:none`).

2. **Tab panel max-height too short on mobile** (currently 280px).
   In `@media (max-width: 768px)` change:
   ```css
   .pitch-panel .tab-panel { max-height: 40vh; }
   ```
   This gives ~320px on a 800px screen but adapts to device height.

3. **Touch targets** — the collapse button already has `min-height: 44px`.
   Verify existing `.log-filter` buttons also have `min-height: 44px` in mobile media query.
   Add if missing:
   ```css
   .log-filter { min-height: 36px; }
   ```

4. **Ticker height on mobile** — the ticker is 24px which is fine, but add a small
   padding bump in the mobile query so it's readable:
   ```css
   .global-ticker { height: 28px; }
   .ticker-inner  { line-height: 28px; font-size: 0.75rem; }
   ```

5. **Pitch aspect ratio on very small screens (≤480px)** — already handled via
   `aspect-ratio: 26/15`. No change needed.

6. **Collapse button on mobile sticky tab bar** — the tab bar is `position: sticky; bottom: 0`
   on mobile. The collapse button should still appear and function. No extra CSS needed —
   `margin-left: auto` pushes it to the right of the tab buttons naturally.

---

## Summary of changes

| Area | What changes |
|------|--------------|
| JS state | +`tickerQueue`, +`TICKER_MAX` |
| JS functions | +`pushToTicker()`, +`refreshTicker()` |
| JS wiring | `injectCommentaryIntoLog` + `renderGameLog` call `pushToTicker` |
| JS init | Collapse toggle IIFE |
| HTML | Ticker badge label; collapse `<button>` in tab bar |
| CSS | 7 `.ticker-item--*` rules; `.tab-collapse-btn`; collapse panel CSS; mobile fixes |

**Do NOT touch:** game logic, server files, any Python files, leaderboard, scoreboard overlay.
Only `app/web/templates/dashboard.html`.

## After implementation

Run: `git diff --stat` and confirm only `dashboard.html` changed.
Then: `git add app/web/templates/dashboard.html && git commit -m "feat: mixed ticker feed, collapsible info panel, mobile polish"`
Then push: `git push origin main`
