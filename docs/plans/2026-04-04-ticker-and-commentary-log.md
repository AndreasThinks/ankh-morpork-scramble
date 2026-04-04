# Ticker Bar + Commentary in Event Log Plan

> **For Cline or Hermes:** Implement in order. One file: `app/web/templates/dashboard.html`

---

## What this does

1. **Removes** the ⊞ Split view button (user disliked it — takes too much space)
2. **Adds** a persistent one-line commentary ticker between the pitch and the tab bar
   (always visible, shows Dibbler's latest line, clicking switches to Commentary tab)
3. **Injects** Dibbler's commentary lines into the event log as a distinct visual row,
   so the Events tab shows game events AND commentary in one chronological feed

---

## Task 1: Remove split view

### CSS — delete the split view styles

Find and delete this entire CSS block:

```css
        /* ── Split view: commentary + events simultaneously ─────────────── */
        .tab-btn--split {
            margin-left: auto;
            opacity: 0.7;
            border-left: 1px solid rgba(217, 180, 91, 0.2);
            padding-left: 0.65rem;
        }

        .tab-btn--split.active {
            opacity: 1;
        }

        /* When split is active, pitch-panel shows both panels as flex column */
        .pitch-panel.split-active {
            overflow: hidden;
        }

        /* Commentary in split mode: compact, fixed portion at top */
        .pitch-panel.split-active #tab-commentary {
            display: flex !important;
            flex-direction: column;
            flex: 0 0 auto;
            max-height: 130px;
            overflow-y: auto;
            border-bottom: 1px solid rgba(217, 180, 91, 0.2);
            padding-bottom: 0.4rem;
            margin-bottom: 0;
        }

        /* Compact the referee box in split mode */
        .pitch-panel.split-active .referee-commentary {
            padding: 0.55rem 0.85rem;
            border-radius: 10px;
        }

        .pitch-panel.split-active .referee-commentary::before {
            height: 2px;
        }

        .pitch-panel.split-active .commentary-text {
            font-size: 0.88rem;
            line-height: 1.5;
        }

        /* Events in split mode: fills remaining space */
        .pitch-panel.split-active #tab-events {
            display: flex !important;
            flex-direction: column;
            flex: 1;
            min-height: 0;
            overflow: hidden;
        }
```

### HTML — remove the split button

Find:
```html
            <button class="tab-btn tab-btn--split" data-tab="split" title="Show commentary and events side by side">⊞ Split</button>
```
Delete that line entirely.

### JS — remove split case from tab handler

Find the tab-switching handler. It will contain a block like:
```javascript
        if (name === 'split') {
            // Split mode: show both commentary and events, apply layout class
            pitchPanel.classList.add('split-active');
            document.getElementById('tab-commentary').hidden = false;
            document.getElementById('tab-events').hidden = false;
        } else {
```

Simplify the handler by removing the split branch entirely. The final handler should be:

```javascript
    document.getElementById('pitch-tab-bar').addEventListener('click', (e) => {
        const btn = e.target.closest('.tab-btn');
        if (!btn) return;
        const name = btn.dataset.tab;
        if (!name) return;

        document.querySelectorAll('.tab-panel').forEach(p => { p.hidden = true; });
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

        btn.classList.add('active');
        const panel = document.getElementById(`tab-${name}`);
        if (panel) panel.hidden = false;
    });
```

**Commit:** `refactor(ui): remove split view`

---

## Task 2: Commentary ticker bar

### HTML — add ticker between pitch wrapper and tab bar

Find:
```html
        <div class="tab-bar" id="pitch-tab-bar">
```

Insert immediately BEFORE it:
```html
        <div class="commentary-ticker" id="commentary-ticker" role="status" aria-live="polite">
            <span class="ticker-label">⚖</span>
            <span class="ticker-text" id="ticker-text">Awaiting Dibbler's first remark…</span>
        </div>
```

### CSS — ticker styles

Add these styles to the main stylesheet (before the mobile media queries):

```css
        /* ── Commentary ticker bar ───────────────────────────────────────── */
        .commentary-ticker {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.3rem 0.7rem;
            background: rgba(217, 180, 91, 0.05);
            border: 1px solid rgba(217, 180, 91, 0.15);
            border-radius: 6px;
            flex-shrink: 0;
            cursor: pointer;
            transition: background 0.15s;
            min-height: 0;
        }

        .commentary-ticker:hover {
            background: rgba(217, 180, 91, 0.1);
        }

        .ticker-label {
            flex-shrink: 0;
            font-size: 0.7rem;
            opacity: 0.5;
            user-select: none;
        }

        .ticker-text {
            font-size: 0.78rem;
            color: rgba(242, 227, 198, 0.6);
            font-style: italic;
            line-height: 1.3;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            font-family: "Spectral", Georgia, serif;
        }

        /* Flash animation when ticker updates */
        @keyframes tickerUpdate {
            0%   { color: rgba(242, 227, 198, 0.6); }
            30%  { color: var(--accent-gold); }
            100% { color: rgba(242, 227, 198, 0.6); }
        }

        .ticker-text.updated {
            animation: tickerUpdate 1.2s ease;
        }
```

In the `≤768px` media query, the ticker is already handled by the `ref-strip` from the
previous mobile plan. On mobile, hide the commentary-ticker (the ref-strip does the same
job in the sticky tab bar area):
```css
            .commentary-ticker {
                display: none;
            }
```

### JS — wire ticker to renderRefereeCommentary

Find in `renderRefereeCommentary`:
```javascript
            commentaryText.textContent = latestComment.content;
            commentaryText.classList.remove('loading');
```

Replace with:
```javascript
            commentaryText.textContent = latestComment.content;
            commentaryText.classList.remove('loading');

            // Update commentary ticker
            const tickerText = document.getElementById('ticker-text');
            if (tickerText && tickerText.textContent !== latestComment.content) {
                tickerText.textContent = latestComment.content;
                tickerText.classList.remove('updated');
                // Force reflow to restart animation
                void tickerText.offsetWidth;
                tickerText.classList.add('updated');
            }
```

Also wire the ticker click to switch to the Commentary tab. Find the JS section where
the page initialises (near the bottom, around `initPitchGrid` / `startPolling`). Add:

```javascript
    // Ticker click → switch to Commentary tab
    document.getElementById('commentary-ticker').addEventListener('click', () => {
        document.querySelectorAll('.tab-panel').forEach(p => { p.hidden = true; });
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        const commentaryPanel = document.getElementById('tab-commentary');
        const commentaryBtn = document.querySelector('[data-tab="commentary"]');
        if (commentaryPanel) commentaryPanel.hidden = false;
        if (commentaryBtn) commentaryBtn.classList.add('active');
    });
```

**Commit:** `feat(ui): commentary ticker bar — Dibbler's latest always visible`

---

## Task 3: Inject commentary into event log

### JS — add tracking state and inject function

Find the module-level state variables block (where `lastRenderedEventCount` and
`activeLogFilter` are declared). Add:

```javascript
    let lastInjectedCommentaryText = '';  // prevents duplicate injection
```

Add this new helper function near the other log helpers (near `buildEventRow`):

```javascript
    /**
     * Inject a commentary line into the event log as a special styled row.
     * Called after renderRefereeCommentary updates with new content.
     * Uses the content string to deduplicate — only injects if content changed.
     */
    function injectCommentaryIntoLog(text) {
        if (!text || text === lastInjectedCommentaryText) return;
        lastInjectedCommentaryText = text;

        const container = document.getElementById('game-log-entries');
        if (!container) return;

        // Remove placeholder if present
        const placeholder = container.querySelector('.log-event--placeholder');
        if (placeholder) placeholder.remove();

        const el = document.createElement('div');
        el.className = 'log-event log-event--commentary log-event--tier-action';
        el.dataset.eventType = 'commentary';
        el.dataset.category = 'commentary';
        el.dataset.result = 'neutral';
        el.innerHTML = `
            <span class="log-event-icon" aria-hidden="true">⚖</span>
            <div class="log-event-body">
                <span class="log-event-desc log-event-desc--commentary">${escapeHtml(text)}</span>
            </div>
        `;

        // Apply current filter — commentary rows always visible except on combat/ball filters
        const filter = activeLogFilter;
        el.hidden = (filter === 'combat' || filter === 'ball' || filter === 'turnovers');

        // Determine scroll position before touching DOM
        const wasNearBottom =
            container.scrollHeight - container.scrollTop - container.clientHeight < 80;

        container.appendChild(el);

        if (wasNearBottom) {
            container.scrollTop = container.scrollHeight;
        }
    }
```

### CSS — commentary row styles

Add to the main stylesheet (after the `.log-event--casualty` rule):

```css
        /* Commentary rows in the event log */
        .log-event--commentary {
            border-left-color: rgba(217, 180, 91, 0.35) !important;
            background: rgba(217, 180, 91, 0.04) !important;
            font-style: italic;
        }

        .log-event-desc--commentary {
            color: rgba(242, 227, 198, 0.6) !important;
            font-family: "Spectral", Georgia, serif;
            font-size: 0.82em;
        }
```

### JS — call injectCommentaryIntoLog from renderRefereeCommentary

In `renderRefereeCommentary`, find the block you updated in Task 2 where the ticker is
updated. After the ticker update block, add:

```javascript
            // Inject into event log
            injectCommentaryIntoLog(latestComment.content);
```

### JS — update filter bar to handle commentary rows

Find the filter bar click handler. In the section that applies visibility to existing
rows, it currently does something like:

```javascript
        container.querySelectorAll('.log-event').forEach(el => {
            const type = el.dataset.eventType || '';
            const result = el.dataset.result || '';
            let visible;
            if (activeLogFilter === 'all') visible = true;
            ...
```

Update the filter logic so commentary rows are visible on 'all' but hidden on specific
category filters. The `el.dataset.category === 'commentary'` check should map to hidden
when filter is 'combat', 'ball', or 'turnovers':

The `eventMatchesFilter` function already returns false for commentary on category
filters (since `getEventCategory('commentary')` returns `'other'` which doesn't match
combat/ball). But the turnovers filter checks `result === 'failure'` — commentary rows
have `result = 'neutral'`, so they'll correctly be hidden on the turnovers filter too.
No change needed to `eventMatchesFilter` — it already handles this correctly.

**Commit:** `feat(ui): inject Dibbler commentary into event log feed`

---

## Verification

```
Desktop:
- No ⊞ Split button in the tab bar
- Thin ticker bar visible between pitch and tabs, showing latest Dibbler line
- Ticker text animates gold briefly when a new line arrives
- Clicking ticker switches to Commentary tab
- Events tab: Dibbler's lines appear as italic gold-tinted rows with ⚖ icon
  mixed in with the game events chronologically
- Commentary rows hidden on Combat / Ball / Turnovers filters
- Commentary rows shown on All filter

Mobile (≤768px):
- Ticker bar hidden (ref-strip from mobile plan handles this role)
- Event log still shows injected commentary rows

No regressions:
- Commentary tab still shows full referee panel as before
- Roster tab works
- Events filter bar works
- renderGameLog() incremental appending still works
- Tests pass: uv run pytest tests/ -q
```

---

## Notes

- `injectCommentaryIntoLog` uses the text content itself as a deduplication key
  (`lastInjectedCommentaryText`). This means if Dibbler says the same thing twice
  (unlikely), the second one won't appear in the log. Acceptable trade-off vs complexity.
- Commentary log rows do NOT go through `renderGameLog()` — they're appended directly.
  This means they live alongside game events but `lastRenderedEventCount` doesn't track
  them. This is intentional — commentary messages come from a different API endpoint.
- The ticker `aria-live="polite"` means screen readers will announce new commentary
  without interrupting current speech.
