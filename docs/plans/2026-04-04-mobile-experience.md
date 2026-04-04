# Mobile Experience Plan

> **For Cline or Hermes:** Implement in order. Each task is a self-contained commit.
> All changes are in `app/web/templates/dashboard.html` only.

---

## Problems being fixed

1. **No viewport meta tag** — mobile browsers render at a virtual 980px desktop width
   and scale everything down. Every CSS media query fires at the wrong breakpoint. This
   is why the page is tiny. It is the most critical fix.

2. **Tab targets too small** — `.tab-btn` has `padding: 0.3rem 0.8rem` and
   `font-size: 0.68rem`. On mobile, tap targets should be a minimum of 44px tall.

3. **Sidebar scroll problem** — both team strategy panels stack below the pitch in
   single-column layout. User must scroll past two panels of strategy content to reach
   the Commentary/Events tabs. On mobile, sidebars should be hidden and their content
   surfaced inside a dedicated Strategy tab instead.

4. **No persistent referee strip** — commentary and events are exclusive tabs. On
   mobile, there is no way to see the latest Bluntt line while looking at the event log.
   A slim always-visible strip above the tab bar fixes this.

---

## Architecture

Four tasks, all in `dashboard.html`:

```
Task 1 — HTML  : Add viewport meta tag (1 line)
Task 2 — CSS   : Enlarge tab targets on mobile
Task 3 — HTML + CSS + JS : Strategy tab + hide sidebars on mobile
Task 4 — HTML + CSS + JS : Persistent ref strip above tab bar on mobile
```

Target layout on mobile (≤768px):

```
┌──────────────────────┐
│ Score  0 VS 0  LIVE  │  ← sticky header (done)
├──────────────────────┤
│                      │
│       PITCH          │  ← full width, aspect-ratio 26:15
│                      │
├──────────────────────┤
│ 💬 "Bluntt: ..."     │  ← persistent ref strip (Task 4)
├──────────────────────┤
│  ⚖   📋   👥   💭   │  ← big thumb-friendly tab bar (Task 2 + 3)
├──────────────────────┤
│   active tab content │  ← scrollable
└──────────────────────┘
```

---

## Task 1: Add viewport meta tag

**File:** `app/web/templates/dashboard.html`

**Find:**
```html
    <meta charset="UTF-8">
    <title>Ankh-Morpork Scramble – Match View</title>
```

**Replace with:**
```html
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Ankh-Morpork Scramble – Match View</title>
```

That is the entire task. One line. It makes every other mobile fix actually work.

**Commit:** `fix(ui): add viewport meta tag — fixes all mobile media queries`

---

## Task 2: Larger tab targets on mobile

**File:** `app/web/templates/dashboard.html`

**Find the existing `≤480px` media query block** (added in the previous mobile plan).
It contains a `.tab-btn` override like:

```css
            /* Tighter tab buttons */
            .tab-btn {
                padding: 0.3rem 0.5rem;
                font-size: 0.68rem;
            }
```

**Replace that `.tab-btn` block inside the `≤480px` query with:**
```css
            .tab-btn {
                font-size: 0.7rem;
                padding: 0 0.5rem;
            }
```

**Then find the `≤768px` media query block and add inside it** (anywhere within the
block is fine):

```css
            /* Larger, thumb-friendly tab bar on mobile */
            .tab-bar {
                position: sticky;
                bottom: 0;
                z-index: 10;
                background: rgba(24, 15, 7, 0.97);
                border-top: 1px solid rgba(217, 180, 91, 0.25);
                border-bottom: none;
                padding: 0 0.25rem;
                backdrop-filter: blur(8px);
            }

            .tab-btn {
                min-height: 44px;
                font-size: 0.75rem;
                padding: 0 0.6rem;
                flex: 1;
                display: flex;
                align-items: center;
                justify-content: center;
                border-bottom: none;
                border-top: 2px solid transparent;
                margin-bottom: 0;
                margin-top: -1px;
            }

            .tab-btn.active {
                border-bottom-color: transparent;
                border-top-color: var(--accent-gold);
            }

            /* Hide split button on mobile — not enough vertical room for two panels */
            .tab-btn--split {
                display: none;
            }
```

Note: making the tab bar `position: sticky; bottom: 0` pins it to the bottom of the
viewport on mobile, which is where thumbs naturally reach. The active indicator flips
from a bottom border to a top border to suit the new position.

**Commit:** `fix(ui): mobile tab bar — sticky bottom, 44px touch targets`

---

## Task 3: Strategy tab + hide sidebars on mobile

### Step A — HTML: add Strategy tab button and panel

**Find:**
```html
        <div class="tab-bar" id="pitch-tab-bar">
            <button class="tab-btn active" data-tab="commentary">⚖ Commentary</button>
            <button class="tab-btn" data-tab="events">📋 Events</button>
            <button class="tab-btn" data-tab="roster">👥 Roster</button>
            <button class="tab-btn tab-btn--split" data-tab="split" title="Show commentary and events side by side">⊞ Split</button>
        </div>
```

**Replace with:**
```html
        <div class="tab-bar" id="pitch-tab-bar">
            <button class="tab-btn active" data-tab="commentary">⚖ Commentary</button>
            <button class="tab-btn" data-tab="events">📋 Events</button>
            <button class="tab-btn" data-tab="roster">👥 Roster</button>
            <button class="tab-btn" data-tab="strategy">💭 Strategy</button>
            <button class="tab-btn tab-btn--split" data-tab="split" title="Show commentary and events side by side">⊞ Split</button>
        </div>
```

**Find the roster tab panel closing tag and the roster-toggle details element:**
```html
        </div>

        <!-- Kept for JS collapse logic -->
        <details id="roster-toggle" hidden></details>
    </section>
```

**Insert the Strategy tab panel immediately before the `<!-- Kept for JS -->` comment:**
```html
        <!-- Strategy tab (mobile: shows both teams' thoughts) -->
        <div class="tab-panel" id="tab-strategy" hidden>
            <div class="strategy-team-block">
                <div class="strategy-team-label" id="strategy-team1-label">Team 1 Strategy</div>
                <ul class="sidebar-thoughts" id="strategy-team1-thoughts"></ul>
            </div>
            <div class="strategy-team-block">
                <div class="strategy-team-label" id="strategy-team2-label">Team 2 Strategy</div>
                <ul class="sidebar-thoughts" id="strategy-team2-thoughts"></ul>
            </div>
        </div>
```

### Step B — CSS: Strategy tab styles + hide sidebars on mobile

**In the `≤768px` media query block, add:**

```css
            /* Hide sidebars — their content surfaces in the Strategy tab */
            main > aside.team-sidebar {
                display: none;
            }
```

**After (outside) the media query blocks, add these styles for the strategy tab panel:**

```css
        .strategy-team-block {
            margin-bottom: 1rem;
        }

        .strategy-team-label {
            font-family: "Cinzel", "Times New Roman", serif;
            font-size: 0.7rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: rgba(217, 180, 91, 0.6);
            margin-bottom: 0.4rem;
            padding-bottom: 0.25rem;
            border-bottom: 1px solid rgba(217, 180, 91, 0.15);
        }
```

### Step C — JS: render thoughts into Strategy tab

**Find the `renderThoughts` function. It currently ends with:**
```javascript
        } catch (error) {
            console.error('Failed to fetch messages:', error);
            renderFallbackThoughts(state);
        }
    }
```

**In the success path of `renderThoughts`, after the forEach that updates
`team1Thoughts` / `team2Thoughts`, add a block that mirrors the same content into the
Strategy tab elements.** Find the forEach block:

```javascript
            [
                [state.team1, team1Thoughts, team1Title],
                [state.team2, team2Thoughts, team2Title]
            ].forEach(([team, container, title]) => {
```

**Replace with:**
```javascript
            // Strategy tab elements (mobile)
            const strategyTeam1 = document.getElementById('strategy-team1-thoughts');
            const strategyTeam2 = document.getElementById('strategy-team2-thoughts');
            const strategyTeam1Label = document.getElementById('strategy-team1-label');
            const strategyTeam2Label = document.getElementById('strategy-team2-label');

            [
                [state.team1, team1Thoughts, team1Title, strategyTeam1, strategyTeam1Label],
                [state.team2, team2Thoughts, team2Title, strategyTeam2, strategyTeam2Label]
            ].forEach(([team, container, title, strategyContainer, strategyLabel]) => {
```

And inside the forEach body, after `container.innerHTML = messages.map(...)`:

```javascript
                // Mirror into Strategy tab
                if (strategyContainer) strategyContainer.innerHTML = container.innerHTML;
                if (strategyLabel) strategyLabel.textContent = `${team.name} Strategy`;
                if (title) title.textContent = `${team.name} Strategy`;
```

Do the same mirroring in `renderFallbackThoughts` — after it sets `team1Thoughts.innerHTML`
and `team2Thoughts.innerHTML`, mirror the same content to `strategy-team1-thoughts` and
`strategy-team2-thoughts`.

**Commit:** `feat(ui): Strategy tab — team thoughts accessible on mobile, sidebars hidden`

---

## Task 4: Persistent referee strip

### Step A — HTML: add the strip element

**Find the tab-bar div:**
```html
        <div class="tab-bar" id="pitch-tab-bar">
```

**Insert immediately BEFORE it:**
```html
        <!-- Persistent referee strip: always visible on mobile above the tab bar -->
        <div class="ref-strip" id="ref-strip" hidden>
            <span class="ref-strip-icon">⚖</span>
            <span class="ref-strip-text" id="ref-strip-text">Awaiting the referee…</span>
        </div>
```

### Step B — CSS: ref strip styles

**Add to the main stylesheet (before the mobile media queries):**

```css
        .ref-strip {
            display: none;  /* hidden on desktop */
        }
```

**In the `≤768px` media query block, add:**

```css
            /* Persistent referee strip — shown on mobile above sticky tab bar */
            .ref-strip {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.4rem 0.75rem;
                background: rgba(36, 23, 12, 0.95);
                border-top: 1px solid rgba(217, 180, 91, 0.2);
                flex-shrink: 0;
                min-height: 0;
            }

            .ref-strip-icon {
                flex-shrink: 0;
                font-size: 0.75rem;
                opacity: 0.6;
            }

            .ref-strip-text {
                font-size: 0.75rem;
                color: var(--muted);
                line-height: 1.35;
                font-style: italic;
                /* Truncate to 2 lines */
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }
```

### Step C — JS: update renderRefereeCommentary to also update the strip

**Find in `renderRefereeCommentary`:**
```javascript
            commentaryText.textContent = latestComment.content;
            commentaryText.classList.remove('loading');
```

**Replace with:**
```javascript
            commentaryText.textContent = latestComment.content;
            commentaryText.classList.remove('loading');

            // Update the mobile ref strip
            const refStrip = document.getElementById('ref-strip');
            const refStripText = document.getElementById('ref-strip-text');
            if (refStrip && refStripText) {
                refStripText.textContent = latestComment.content;
                refStrip.hidden = false;
            }
```

**Also update the "no messages yet" branch** — find:
```javascript
            commentaryText.textContent = 'Havelock Bluntt has yet to pass judgement.';
            commentaryText.classList.remove('loading');
            commentaryTimestamp.textContent = '';
            return;
```

**Replace with:**
```javascript
            commentaryText.textContent = 'Havelock Bluntt has yet to pass judgement.';
            commentaryText.classList.remove('loading');
            commentaryTimestamp.textContent = '';
            const refStripText = document.getElementById('ref-strip-text');
            if (refStripText) refStripText.textContent = 'Havelock Bluntt has yet to pass judgement.';
            return;
```

**Commit:** `feat(ui): persistent ref strip on mobile — Bluntt always visible above tabs`

---

## Verification

After all four tasks are applied and pushed:

```
1. Open https://ai-at-play.online/ui in a real phone browser (or DevTools → mobile)
2. Header: compact, score and status visible, does NOT require horizontal scroll
3. Pitch: renders at full width, correct 26:15 aspect ratio (~225px tall on 390px screen)
4. Ref strip: a slim line showing Bluntt's latest comment, above the tab bar
5. Tab bar: pinned to bottom of viewport, large tap targets (≥44px)
6. Strategy tab: tapping it shows both teams' recent thoughts stacked vertically
7. No sidebars visible on mobile (they are hidden via CSS)
8. No horizontal scroll anywhere
9. Scrolling works — pitch + content scroll vertically

Desktop check (should be completely unchanged):
- Three-column layout with sidebars visible
- Tab bar at top of the pitch panel (not bottom)
- Ref strip hidden (display: none on desktop)
- Strategy tab visible but sidebars still showing too
- Split button visible and functional
```

```bash
# Run tests to confirm nothing broke
cd ~/projects/ankh-morpork-scramble && uv run pytest tests/ -q
```

---

## Notes for the implementing agent

- The `renderFallbackThoughts` function (starting around line 2328) also sets
  `team1Thoughts.innerHTML` and `team2Thoughts.innerHTML`. Mirror those to the strategy
  tab containers there too.

- The Strategy tab only needs to be visible on mobile via tab selection — on desktop,
  the sidebars show the same content, so the Strategy tab is technically redundant but
  harmless (leave it visible on desktop for power users who want it).

- Do NOT remove the `team1Thoughts` / `team2Thoughts` sidebar elements or their update
  logic — the sidebars are hidden on mobile via CSS but still rendered in the DOM, and
  they must remain functional for desktop.

- The `position: sticky; bottom: 0` tab bar on mobile means the tab bar stays at the
  bottom of the viewport as the user scrolls. The tab panel content above it scrolls
  freely. This is the standard iOS/Android navigation pattern.
