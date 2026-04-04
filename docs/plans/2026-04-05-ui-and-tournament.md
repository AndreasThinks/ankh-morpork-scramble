# UI & Tournament Plan

> Implement in order. Each task is a self-contained commit.
> No new npm dependencies. No new Python packages. Vanilla JS and FastAPI only.

---

## Task 1: Fix stale UI test assertions

**File:** `tests/test_frontend.py`

Two assertions still check for `"Recent Events"` which was renamed to `"Match Events"`.
Lines 26 and 62. Change both. One-liner each.

**Commit:** `fix(tests): update Recent Events → Match Events assertions`

---

## Task 2: Referee commentary — richer context

**Files:** `simple_agents/state_summary.py`, `simple_agents/commentator.py`

### state_summary.py — richer `summarize_for_commentator()`

Replace the flat bullet-list with structured context:
- Single **headline event** (priority: touchdown > turnover > casualty > injury > knockdown > block > other)
- Ball carrier name (or "loose" / "off pitch")
- Score delta this round (did either team score?)
- Secondary events as brief list

The LLM needs to know *what mattered* this round, not just a flat dump of every move.

### commentator.py — tighten system prompt

Add one line: "Your first sentence must name the action and the players involved.
Discworld flavour belongs in sentences 2–3."

This prevents the LLM from leading with atmosphere and burying the actual event.

**Commit:** `feat(commentary): richer commentator context + prompt tightening`

---

## Task 3: Model tournament pool

**New file:** `simple_agents/model_picker.py`
**Modified:** `run_simple_game.py`

### model_picker.py

```python
MODEL_POOL = [
    "qwen/qwen3-8b:free",
    "qwen/qwen3-14b:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3-27b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-nemo:free",
    "microsoft/phi-4:free",
    "deepseek/deepseek-r1-0528:free",
    "deepseek/deepseek-chat-v3-5:free",
]
```

`pick_models(leaderboard_url: str) -> tuple[str, str]`:
- Fetch `GET /leaderboard`, build `{model_id: games}` dict
- Weight each model in pool as `1 / (games + 1)`
- Pick two *distinct* models using weighted random
- Return `(model1, model2)`
- Falls back to uniform random if leaderboard fetch fails

`OPENROUTER_MODELS` env var overrides the pool (comma-separated).

### run_simple_game.py

At start of each outer `while True` loop iteration (before `run_setup()`):
- If `TEAM1_MODEL` or `TEAM2_MODEL` are explicitly set, respect them (manual override)
- Otherwise call `pick_models(SERVER_URL)` and update `TEAM_CONFIGS` dynamically
- Log which models were selected

**Commit:** `feat(agents): weighted random model selection from tournament pool`

---

## Task 4: Single-screen viewport-locked layout

**File:** `app/web/templates/dashboard.html` only. No backend changes.

**Goal:** Everything fits on one wide screen (1920×1080) without scrolling.
The pitch dominates the centre. Tabs provide access to commentary/events/roster below it.
Team sidebars are compact and informative. Status chips live in the header row.

### Layout structure

```
┌──────────────────────────────────────────────────────────────────┐
│  ANKH-MORPORK SCRAMBLE  │  Team1  3 — 1  Team2  │ Phase · LIVE  │ ~48px
├─────────────┬────────────────────────────────────┬───────────────┤
│ TEAM 1      │                                    │ TEAM 2        │
│ name        │   PITCH SVG (flex: 1, fills ht)    │ name          │
│             │                                    │               │
│ Treasury    │   legend                           │ Treasury      │
│             │ ─────────────────────────────────  │               │
│ Strategy    │ [Commentary] [Events] [Roster]     │ Strategy      │
│ messages    │  tab content (~28vh, scrollable)   │ messages      │
│             │                                    │ Leaderboard → │
└─────────────┴────────────────────────────────────┴───────────────┘
```

### CSS changes

1. **Viewport lock:** `html { height: 100vh; overflow: hidden; }` +
   `body { height: 100%; overflow: hidden; display: flex; flex-direction: column; }`

2. **Header — compact, single row:**
   - `padding: 0.3rem clamp(0.75rem, 2vw, 2rem)` (was 0.5rem / 4rem)
   - `flex-wrap: nowrap; flex-shrink: 0`
   - `h1` font-size down to `clamp(0.75rem, 1vw, 0.9rem)`
   - Score values down to `clamp(1rem, 1.8vw, 1.5rem)`
   - Remove status-bar styles (element removed from HTML)
   - Add `.header-status { display: flex; gap: 0.4rem; flex-shrink: 0; }` for inline chips

3. **Main:**
   ```css
   main {
       flex: 1; min-height: 0; overflow: hidden;
       padding: 0.6rem clamp(0.6rem, 1.2vw, 1.2rem);
       display: grid;
       grid-template-columns: 230px 1fr 230px;
       gap: 0.75rem;
       align-items: stretch;
   }
   ```

4. **Pitch panel** (centre column):
   ```css
   .pitch-panel { display: flex; flex-direction: column; gap: 0.4rem;
                  min-height: 0; overflow: hidden; }
   .pitch-wrapper { flex: 1; min-height: 0; overflow: hidden; position: relative; }
   .pitch-canvas  { width: 100%; height: 100%; display: block; filter: saturate(85%); }
   ```
   `preserveAspectRatio="xMidYMid meet"` on the SVG (set in JS) handles ratio internally.

5. **Tab bar + panels:**
   ```css
   .tab-bar { display: flex; gap: 0; border-bottom: 1px solid rgba(217,180,91,0.25);
              flex-shrink: 0; }
   .tab-btn { background: none; border: none; border-bottom: 2px solid transparent;
              color: rgba(242,227,198,0.5); font-family: "Cinzel",...; font-size: 0.72rem;
              letter-spacing: 0.08em; text-transform: uppercase; padding: 0.35rem 0.8rem;
              cursor: pointer; margin-bottom: -1px; transition: color .15s, border-color .15s; }
   .tab-btn.active { color: var(--accent-gold); border-bottom-color: var(--accent-gold); }
   .tab-panel { overflow-y: auto; padding: 0.4rem 0.25rem; }
   .tab-panel[hidden] { display: none; }
   ```
   The tab panel height is implicitly constrained because `.pitch-panel` is a flex column
   with `min-height: 0` — pitch takes `flex: 1`, tab panel takes whatever remains.

6. **Team sidebar** (replace `.panel.thoughts`):
   ```css
   .team-sidebar { background: linear-gradient(...); border: 1px solid var(--panel-border);
                   border-radius: 18px; padding: 0.9rem 1rem; display: flex;
                   flex-direction: column; gap: 0.5rem; overflow-y: auto; min-height: 0; }
   .sidebar-team-name { font-family: "Cinzel",...; font-size: 0.88rem; color: var(--accent-gold);
                        text-transform: uppercase; letter-spacing: 0.08em; margin: 0; }
   .sidebar-section-label { font-size: 0.65rem; letter-spacing: 0.12em; text-transform: uppercase;
                             color: rgba(217,180,91,0.5); border-top: 1px solid rgba(217,180,91,0.15);
                             padding-top: 0.4rem; font-family: "Cinzel",...; }
   .sidebar-footer { margin-top: auto; padding-top: 0.5rem;
                     border-top: 1px solid rgba(217,180,91,0.15); }
   .leaderboard-link { color: rgba(217,180,91,0.6); text-decoration: none;
                       font-size: 0.7rem; font-family: "Cinzel",...; letter-spacing: 0.06em; }
   .leaderboard-link:hover { color: var(--accent-gold); }
   .sidebar-thoughts { list-style: none; padding: 0; margin: 0; display: flex;
                       flex-direction: column; gap: 0.4rem; overflow-y: auto; flex: 1; }
   .sidebar-thoughts li { background: rgba(46,30,16,0.82); border: 1px solid rgba(217,180,91,0.18);
                          border-radius: 10px; padding: 0.45rem 0.7rem;
                          font-size: 0.8rem; line-height: 1.3; }
   ```

### HTML changes

**Remove entirely:** `<div id="status-bar" class="status-bar">...</div>`

**Header — add `.header-status` after `#game-meta`:**
```html
<header>
    <h1>Ankh-Morpork Scramble</h1>
    <div class="score-line" id="score-line">...</div>
    <div class="header-status" id="header-status">
        <span id="status-phase" class="status-chip"></span>
        <span id="status-turn" class="status-chip"></span>
        <span id="status-ball" class="status-chip"></span>
        <span id="status-live" class="status-chip status-live">● LIVE</span>
    </div>
    <div class="meta" id="game-meta"></div>  <!-- kept hidden for error display -->
</header>
```

**Left aside — replace with compact sidebar (keep all existing IDs):**
```html
<aside class="team-sidebar" id="team1-thoughts-panel">
    <h2 class="sidebar-team-name" id="team1-thoughts-title">Team 1</h2>
    <div class="sidebar-section-label">Treasury</div>
    <div id="team1-budget"><div class="budget-details">Loading...</div></div>
    <div class="sidebar-section-label">Strategy</div>
    <ul class="sidebar-thoughts" id="team1-thoughts"></ul>
    <details id="team1-roster-section" hidden></details>  <!-- kept for JS -->
</aside>
```

**Centre section — remove h2, ref commentary, game-log wrapper, roster-toggle. Add tabs:**
```html
<section class="panel pitch-panel">
    <div class="pitch-wrapper" id="pitch-container">
        <svg id="pitch-canvas" ...></svg>
        <div class="tooltip" id="pitch-tooltip" ...></div>
    </div>
    <div class="legend" id="legend">...</div>

    <div class="tab-bar" id="pitch-tab-bar">
        <button class="tab-btn active" data-tab="commentary">⚖ Commentary</button>
        <button class="tab-btn" data-tab="events">📋 Events</button>
        <button class="tab-btn" data-tab="roster">👥 Roster</button>
    </div>

    <div class="tab-panel" id="tab-commentary">
        <div class="commentary-text loading" id="commentary-text">...</div>
        <span class="commentary-timestamp" id="commentary-timestamp"></span>
    </div>

    <div class="tab-panel" id="tab-events" hidden>
        <!-- log-header, log-filter-bar, log-entries (existing IDs unchanged) -->
    </div>

    <div class="tab-panel" id="tab-roster" hidden>
        <!-- roster table (id="roster-body"), then team1/team2 positions panels -->
    </div>

    <details id="roster-toggle" hidden></details>  <!-- kept for JS -->
</section>
```

**Right aside — same pattern as left + leaderboard link:**
```html
<aside class="team-sidebar" id="team2-thoughts-panel">
    <h2 class="sidebar-team-name" id="team2-thoughts-title">Team 2</h2>
    <div class="sidebar-section-label">Treasury</div>
    <div id="team2-budget"><div class="budget-details">Loading...</div></div>
    <div class="sidebar-section-label">Strategy</div>
    <ul class="sidebar-thoughts" id="team2-thoughts"></ul>
    <details id="team2-roster-section" hidden></details>
    <div class="sidebar-footer">
        <a href="/leaderboard/ui" target="_blank" class="leaderboard-link">
            View Season Standings →
        </a>
    </div>
</aside>
```

### JS changes

1. **Remove redundant meta chips** from `updateScoreboard()` — the phase/half/turn/ball
   chips block that writes to `meta.innerHTML`. Status chips already show this info.
   Keep the `meta` variable for connection error display.

2. **Tab switching** — new event listener on `#pitch-tab-bar`:
   ```javascript
   document.getElementById('pitch-tab-bar').addEventListener('click', e => {
       const btn = e.target.closest('.tab-btn');
       if (!btn) return;
       const tab = btn.dataset.tab;
       document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
       document.querySelectorAll('.tab-panel').forEach(p => { p.hidden = true; });
       btn.classList.add('active');
       document.getElementById('tab-' + tab).hidden = false;
   });
   ```

3. **Auto-switch to Events tab** when new log events arrive (optional UX touch):
   If the user is on Commentary tab and events arrive, add a subtle badge on the Events
   button. Do not auto-switch (that would be annoying). Just update the badge count
   (already done by `log-count-badge`).

**Commit:** `feat(ui): single-screen viewport-locked layout — tabs, compact header, team sidebars`

---

## Completion checklist

- [ ] Task 1: tests green (279/279)
- [ ] Task 2: commentary quality improved
- [ ] Task 3: model pool wired, leaderboard weighting working
- [ ] Task 4: no scrolling on 1920×1080, pitch fills centre, tabs work
