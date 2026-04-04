# Mobile Layout + Split View Plan

> **For Cline or Hermes:** Implement in order. Each task is a self-contained commit.
> One file only: `app/web/templates/dashboard.html`

---

## Problems being fixed

### Mobile / vertical screens
- `body { overflow: hidden; height: 100vh }` — the whole layout is a fixed-viewport
  desktop app. On a phone it clips silently and nothing scrolls.
- Column order: DOM order is `team1-sidebar → pitch → team2-sidebar`. When the grid
  collapses to a single column (≤1100px breakpoint already exists), the pitch ends up
  buried below a full-height strategy panel.
- `.pitch-wrapper { flex: 1; min-height: 0 }` — size comes from the flex parent. In a
  stacked single-column layout the parent has no fixed height so the pitch collapses.
- Sidebars are too tall stacked — user has to scroll past two large panels to see the
  pitch.

### Simultaneous commentary + events
- Commentary and events are exclusive tabs. There is no way to see the referee's lines
  while watching the event log scroll.

---

## Architecture

Three-task change, all in `app/web/templates/dashboard.html`:

1. **CSS** — extend the existing `≤1100px` breakpoint + add `≤768px` and `≤480px`
   blocks to make the layout scrollable, ordered correctly, pitch self-sizing.
2. **HTML** — add a `⊞ Split` button to the tab bar.
3. **CSS + JS** — split-view styles and tab-switching logic update.

---

## Task 1: CSS — mobile layout

### Step A — fix the existing `≤1100px` breakpoint

**Find:**
```css
        @media (max-width: 1100px) {
            main {
                grid-template-columns: 1fr;
                overflow-y: auto;
            }
        }
```

**Replace with:**
```css
        @media (max-width: 1100px) {
            main {
                grid-template-columns: 1fr;
                overflow-y: auto;
            }

            /* Pitch section always first in single-column layout */
            main > section.pitch-panel {
                order: -1;
            }
        }
```

### Step B — add `≤768px` block

**Find the closing `</style>` tag (just before `</head>`). Insert immediately before it:**

```css
        /* ── Mobile layout (≤768px) ──────────────────────────────────────── */
        @media (max-width: 768px) {

            /* Convert fixed-viewport app to scrollable document */
            html, body {
                height: auto;
                min-height: 100vh;
                overflow-y: auto;
            }

            /* Allow main to grow with content */
            main {
                overflow: visible;
                padding: 0.5rem;
                gap: 0.5rem;
                align-items: start;
            }

            /* Pitch panel: self-sizing via aspect ratio, no longer flex-fill */
            .pitch-panel {
                overflow: visible;
            }

            .pitch-wrapper {
                flex: 0 0 auto;
                height: auto;
                max-height: none;
                aspect-ratio: 26 / 15;
            }

            .pitch-canvas {
                height: auto;
                aspect-ratio: 26 / 15;
            }

            /* Sidebars: capped so they don't dominate — user can scroll inside */
            .team-sidebar {
                max-height: 220px;
            }

            /* Hide footer — no room */
            footer {
                display: none;
            }

            /* Pitch-panel tab area: let it grow naturally */
            .pitch-panel .tab-panel {
                max-height: 280px;
            }

            /* Hide split button on mobile — not enough vertical room */
            [data-tab="split"] {
                display: none;
            }
        }

        /* ── Very small screens (≤480px) ─────────────────────────────────── */
        @media (max-width: 480px) {
            header {
                padding: 0.3rem 0.5rem;
            }

            main {
                padding: 0.35rem;
                gap: 0.35rem;
            }

            /* Even more compact sidebars */
            .team-sidebar {
                max-height: 160px;
            }

            /* Tighter tab buttons */
            .tab-btn {
                padding: 0.3rem 0.5rem;
                font-size: 0.68rem;
            }

            /* Smaller log events */
            .log-event {
                font-size: 0.75rem;
                padding: 0.2rem 0.35rem;
            }
        }
```

**Commit:** `fix(ui): mobile layout — scrollable, pitch first, aspect-ratio sizing`

---

## Task 2: HTML — add Split tab button

**Find:**
```html
        <div class="tab-bar" id="pitch-tab-bar">
            <button class="tab-btn active" data-tab="commentary">⚖ Commentary</button>
            <button class="tab-btn" data-tab="events">📋 Events</button>
            <button class="tab-btn" data-tab="roster">👥 Roster</button>
        </div>
```

**Replace with:**
```html
        <div class="tab-bar" id="pitch-tab-bar">
            <button class="tab-btn active" data-tab="commentary">⚖ Commentary</button>
            <button class="tab-btn" data-tab="events">📋 Events</button>
            <button class="tab-btn" data-tab="roster">👥 Roster</button>
            <button class="tab-btn tab-btn--split" data-tab="split" title="Show commentary and events side by side">⊞ Split</button>
        </div>
```

**Commit:** `feat(ui): add split-view tab button`

---

## Task 3: CSS + JS — split view

### Step A — CSS for split view

**In the `</style>` block, immediately before the mobile media queries added in Task 1,
insert:**

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

### Step B — JS: update tab switching

Find the existing tab-switching event listener. It will look something like:

```javascript
    document.getElementById('pitch-tab-bar').addEventListener('click', (e) => {
```

**Read the full existing handler.** It will be doing something like showing/hiding
`.tab-panel` elements and toggling `.active` on `.tab-btn` elements.

**Replace the entire handler with:**

```javascript
    document.getElementById('pitch-tab-bar').addEventListener('click', (e) => {
        const btn = e.target.closest('.tab-btn');
        if (!btn) return;
        const name = btn.dataset.tab;
        if (!name) return;

        const pitchPanel = document.querySelector('.pitch-panel');
        const allPanels = document.querySelectorAll('.tab-panel');
        const allBtns = document.querySelectorAll('.tab-btn');

        // Clear active states
        allBtns.forEach(b => b.classList.remove('active'));
        allPanels.forEach(p => { p.hidden = true; });
        pitchPanel.classList.remove('split-active');

        btn.classList.add('active');

        if (name === 'split') {
            // Split mode: show both commentary and events, apply layout class
            pitchPanel.classList.add('split-active');
            document.getElementById('tab-commentary').hidden = false;
            document.getElementById('tab-events').hidden = false;
        } else {
            // Single tab mode
            const panel = document.getElementById(`tab-${name}`);
            if (panel) panel.hidden = false;
        }
    });
```

**Commit:** `feat(ui): split view — commentary and events simultaneously`

---

## Verification

```
Desktop (≥1100px):
- Three-column layout unchanged
- Tab bar has new ⊞ Split button on the far right
- Click Split: commentary shrinks to compact strip at top, events fill below
- Click Commentary / Events / Roster: returns to normal single-tab layout

Tablet (768–1100px):
- Single column, pitch FIRST (not after sidebars)
- Sidebars visible but compact below pitch
- Pitch renders at correct 26:15 aspect ratio
- Scrolling works, no content clipped

Mobile (≤768px):
- Pitch is the first thing you see
- Sidebars show below as capped 220px panels with internal scroll
- Split button hidden (not enough vertical space)
- No horizontal overflow
- Score line: team names truncate cleanly, model names visible
- Header wraps to two rows

Very small (≤480px):
- Everything above, but sidebars even more compact
- Tab buttons still accessible

Pitch sizing sanity check:
- On a 390px wide screen, pitch-wrapper should be ~225px tall (390 * 15/26)
- Player tokens should be visible and correctly positioned
```

---

## What this does NOT change
- The desktop layout (unchanged)
- The polling / data model
- Any backend code
- Sidebar content (still shows treasury + strategy)
- The tab content itself (commentary text, events, roster — all unchanged)
