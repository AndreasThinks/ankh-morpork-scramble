# Implementation Plan: Homepage + Route Restructure

## Overview

Add a proper homepage and give the two modes clean URL structures.
Old slugs become redirects — nothing breaks for existing users.

## Final Route Map

| New URL | Content | Old URL |
|---|---|---|
| `/` | New homepage | was redirect to `/ui` |
| `/model-arena` | Arena landing page | (new) |
| `/model-arena/watch` | Live arena dashboard | `/ui` |
| `/versus` | Versus landing + registration | `/versus/get-started` |
| `/versus/watch` | Live versus dashboard | `/versus/ui` |
| `/standings` | Combined leaderboard | `/leaderboard/ui` |

## Redirects to add (old → new)

- `/ui` → `/model-arena/watch`
- `/leaderboard/ui` → `/standings`
- `/versus/ui` → `/versus/watch`
- `/versus/get-started` → `/versus`

---

## File 1: `app/web/templates/homepage.html` (NEW)

A clean landing page matching the existing dark medieval aesthetic. Two lanes: watch and play.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Ankh-Morpork Scramble</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🏆</text></svg>">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Spectral:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #1f160c;
            --panel: #24170c;
            --panel-border: rgba(187, 142, 76, 0.45);
            --accent-gold: #d9b45b;
            --accent-orange: #c46d28;
            --text: #f2e3c6;
            --muted: rgba(242, 227, 198, 0.7);
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: "Spectral", Georgia, serif;
            background: radial-gradient(circle at 22% 16%, rgba(217,180,91,0.12), transparent 55%),
                        radial-gradient(circle at 78% 12%, rgba(106,76,38,0.18), transparent 50%),
                        var(--bg);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 2rem clamp(1rem, 4vw, 3rem);
        }
        header {
            text-align: center;
            margin-bottom: 3rem;
            max-width: 700px;
        }
        header h1 {
            font-family: "Cinzel", serif;
            font-size: clamp(2rem, 6vw, 3.5rem);
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--accent-gold);
            margin: 0 0 1rem;
        }
        header p {
            color: var(--muted);
            font-size: 1.1rem;
            line-height: 1.7;
            margin: 0;
        }
        .lanes {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            max-width: 900px;
            width: 100%;
        }
        @media (max-width: 600px) { .lanes { grid-template-columns: 1fr; } }
        .lane {
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 16px;
            padding: 2rem;
            text-align: center;
            text-decoration: none;
            color: var(--text);
            transition: border-color 0.2s, transform 0.2s;
            display: block;
        }
        .lane:hover {
            border-color: var(--accent-gold);
            transform: translateY(-2px);
        }
        .lane .icon { font-size: 3rem; margin-bottom: 1rem; display: block; }
        .lane h2 {
            font-family: "Cinzel", serif;
            font-size: 1.2rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--accent-gold);
            margin: 0 0 0.75rem;
        }
        .lane p { color: var(--muted); font-size: 0.95rem; line-height: 1.6; margin: 0 0 1.5rem; }
        .lane .cta {
            display: inline-block;
            font-family: "Cinzel", serif;
            font-size: 0.8rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            border: 1px solid var(--accent-gold);
            color: var(--accent-gold);
            padding: 0.5rem 1.25rem;
            border-radius: 4px;
        }
        .lane:hover .cta { background: rgba(217,180,91,0.1); }
        footer {
            margin-top: 3rem;
            color: var(--muted);
            font-size: 0.8rem;
            text-align: center;
        }
        footer a { color: var(--accent-gold); text-decoration: none; }
        footer a:hover { color: var(--accent-orange); }
    </style>
</head>
<body>
    <header>
        <h1>🏆 Ankh-Morpork Scramble</h1>
        <p>
            AI agents battle it out on the Blood Bowl pitches of the Disc.
            Watch the Model Arena — or deploy your own agent and enter the Versus league.
        </p>
    </header>

    <div class="lanes">
        <a href="/model-arena" class="lane">
            <span class="icon">🤖</span>
            <h2>Model Arena</h2>
            <p>
                Watch top AI models play automatically, 24/7.
                Track which model dominates the season standings.
            </p>
            <span class="cta">Watch →</span>
        </a>

        <a href="/versus" class="lane">
            <span class="icon">⚔️</span>
            <h2>Versus Mode</h2>
            <p>
                Register your AI agent, join the lobby, and fight for
                a place on the leaderboard.
            </p>
            <span class="cta">Play →</span>
        </a>
    </div>

    <footer>
        <a href="/standings">Standings</a> &bull;
        <a href="/docs">API</a> &bull;
        <a href="/versus/how-to-play">How to Play</a>
    </footer>
</body>
</html>
```

---

## File 2: `app/web/templates/model_arena.html` (NEW)

The arena landing page — what it is, current game status, link to watch live.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Ankh-Morpork Scramble – Model Arena</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🤖</text></svg>">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Spectral:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #1f160c; --panel: #24170c;
            --panel-border: rgba(187,142,76,0.45);
            --accent-gold: #d9b45b; --accent-orange: #c46d28;
            --text: #f2e3c6; --muted: rgba(242,227,198,0.7);
        }
        * { box-sizing: border-box; }
        body {
            margin: 0; padding: 1.5rem clamp(1rem,4vw,3rem);
            font-family: "Spectral", Georgia, serif;
            background: radial-gradient(circle at 22% 16%,rgba(217,180,91,0.12),transparent 55%),
                        radial-gradient(circle at 78% 12%,rgba(106,76,38,0.18),transparent 50%),var(--bg);
            color: var(--text); min-height: 100vh;
        }
        nav { max-width:1200px; margin:0 auto 1.5rem; display:flex; gap:1.5rem; flex-wrap:wrap; }
        nav a { color:var(--accent-gold); text-decoration:none; font-family:"Cinzel",serif;
                font-size:0.85rem; letter-spacing:0.08em; text-transform:uppercase; }
        nav a:hover { color:var(--accent-orange); }
        .container { max-width:1200px; margin:0 auto; }
        header { text-align:center; margin-bottom:2.5rem; }
        header h1 { font-family:"Cinzel",serif; font-size:clamp(1.4rem,3vw,2rem);
                    letter-spacing:0.16em; text-transform:uppercase; color:var(--accent-gold); margin:0 0 0.5rem; }
        header p { color:var(--muted); font-size:0.95rem; margin:0; }
        .panel {
            background:var(--panel); border:1px solid var(--panel-border);
            border-radius:12px; padding:1.5rem 2rem; margin-bottom:1.5rem;
        }
        .panel h2 { font-family:"Cinzel",serif; font-size:0.95rem; letter-spacing:0.12em;
                    text-transform:uppercase; color:var(--accent-gold); margin:0 0 1rem;
                    padding-bottom:0.5rem; border-bottom:1px solid var(--panel-border); }
        .cta-link {
            display:inline-block; padding:0.6rem 1.5rem; border:1px solid var(--accent-gold);
            color:var(--accent-gold); text-decoration:none; font-family:"Cinzel",serif;
            font-size:0.85rem; letter-spacing:0.1em; text-transform:uppercase; border-radius:4px;
        }
        .cta-link:hover { background:rgba(217,180,91,0.1); }
        #game-status { font-size:1rem; color:var(--muted); margin-bottom:1rem; }
        #game-status strong { color:var(--text); }
        table { width:100%; border-collapse:collapse; font-size:0.85rem; }
        th { font-family:"Cinzel",serif; font-size:0.75rem; letter-spacing:0.08em;
             text-transform:uppercase; color:var(--accent-gold); text-align:left;
             padding:0.4rem 0.6rem; border-bottom:1px solid var(--panel-border); }
        td { padding:0.5rem 0.6rem; border-bottom:1px solid rgba(187,142,76,0.12); }
        tr:last-child td { border-bottom:none; }
        .empty { text-align:center; color:var(--muted); padding:2rem; font-style:italic; }
    </style>
</head>
<body>
    <nav>
        <a href="/">← Home</a>
        <a href="/model-arena" style="color:var(--accent-orange)">▸ Model Arena</a>
        <a href="/versus">▸ Versus</a>
        <a href="/standings">▸ Standings</a>
        <a href="/docs">▸ API</a>
    </nav>

    <div class="container">
        <header>
            <h1>🤖 Model Arena</h1>
            <p>AI models battle automatically, around the clock. No registration needed — just watch.</p>
        </header>

        <div class="panel">
            <h2>Current Game</h2>
            <div id="game-status">Loading...</div>
            <a href="/model-arena/watch" class="cta-link">Watch Live →</a>
        </div>

        <div class="panel">
            <h2>Season Standings — By Model</h2>
            <div id="leaderboard"><div class="empty">Loading...</div></div>
            <p style="text-align:right; margin:0.5rem 0 0;">
                <a href="/standings" style="color:var(--accent-gold); font-size:0.85rem;">Full standings →</a>
            </p>
        </div>
    </div>

    <script>
        async function refresh() {
            try {
                const g = await fetch('/current-game').then(r=>r.json());
                const phase = g.phase || 'unknown';
                const t1 = g.team1?.name || 'Team 1';
                const t2 = g.team2?.name || 'Team 2';
                const s1 = g.team1?.score ?? 0;
                const s2 = g.team2?.score ?? 0;
                const turn = g.turn ? `Half ${g.turn.half}, Turn ${g.turn.team_turn}` : '';
                document.getElementById('game-status').innerHTML =
                    `<strong>${t1}</strong> ${s1} – ${s2} <strong>${t2}</strong>` +
                    (turn ? ` &nbsp;·&nbsp; ${turn}` : '') +
                    ` &nbsp;·&nbsp; <em>${phase}</em>`;
            } catch(e) {
                document.getElementById('game-status').textContent = 'No game data available.';
            }

            try {
                const lb = await fetch('/leaderboard').then(r=>r.json());
                const models = lb.by_model || [];
                if (!models.length) {
                    document.getElementById('leaderboard').innerHTML = '<div class="empty">No games recorded yet.</div>';
                    return;
                }
                let html = '<table><thead><tr><th>#</th><th>Model</th><th>W</th><th>L</th><th>D</th><th>GF</th><th>Win%</th></tr></thead><tbody>';
                models.slice(0,8).forEach((m,i) => {
                    html += `<tr><td>${i+1}</td><td>${m.model_id}</td><td>${m.wins}</td><td>${m.losses}</td><td>${m.draws}</td><td>${m.goals_for}</td><td>${(m.win_pct*100).toFixed(1)}%</td></tr>`;
                });
                html += '</tbody></table>';
                document.getElementById('leaderboard').innerHTML = html;
            } catch(e) {}
        }
        refresh();
        setInterval(refresh, 10000);
    </script>
</body>
</html>
```

---

## File 3: `app/web/ui.py` — add new routes + redirects

Read the full file first. Then add these routes:

```python
from fastapi.responses import RedirectResponse

@router.get("/", response_class=HTMLResponse)
def render_homepage(request: Request) -> HTMLResponse:
    """Homepage — two lanes: Model Arena and Versus."""
    return _templates.TemplateResponse(request, "homepage.html", {})

@router.get("/model-arena", response_class=HTMLResponse)
def render_model_arena(request: Request) -> HTMLResponse:
    """Model Arena landing page."""
    return _templates.TemplateResponse(request, "model_arena.html", {})

@router.get("/model-arena/watch", response_class=HTMLResponse)
def render_arena_watch(request: Request, game_id: Optional[str] = None) -> HTMLResponse:
    """Live arena game dashboard (was /ui)."""
    if game_id is None:
        demo_mode = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")
        game_id = DEFAULT_GAME_ID if demo_mode else INTERACTIVE_GAME_ID
    poll_interval = int(os.getenv("UI_POLL_INTERVAL", "2500"))
    return _templates.TemplateResponse(
        request, "dashboard.html",
        {"game_id": game_id, "poll_interval": poll_interval}
    )

@router.get("/standings", response_class=HTMLResponse)
def render_standings(request: Request) -> HTMLResponse:
    """Combined leaderboard (was /leaderboard/ui)."""
    return _templates.TemplateResponse(request, "leaderboard.html", {})

# ── Legacy redirects — keep old slugs working ──────────────────────────────

@router.get("/ui")
def redirect_ui():
    return RedirectResponse(url="/model-arena/watch", status_code=301)

@router.get("/leaderboard/ui")
def redirect_leaderboard_ui():
    return RedirectResponse(url="/standings", status_code=301)

@router.get("/about", response_class=HTMLResponse)
def render_about(request: Request) -> HTMLResponse:
    """About page."""
    return _templates.TemplateResponse(request, "about.html", {})
```

Remove the OLD `/ui`, `/leaderboard/ui`, and `/about` route definitions that existed
before — replace them with the new ones above. Do NOT keep duplicates.

---

## File 4: `app/web/versus_get_started.py` — rename routes + add redirects

Currently has `@router.get("/get-started")`. Change to `@router.get("/")` so
when mounted at `/versus` prefix it becomes `/versus`.

Add a watch route at `@router.get("/watch")` serving `versus.html`:

```python
@router.get("/watch", response_class=HTMLResponse)
def versus_watch(request: Request) -> HTMLResponse:
    """Live versus dashboard (was /versus/ui)."""
    return _templates.TemplateResponse(request, "versus.html", {})
```

Add a redirect for the old slug:
```python
@router.get("/get-started")
def redirect_get_started():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/versus", status_code=301)
```

The versus router needs access to `_templates`. Import it:
```python
from fastapi.templating import Jinja2Templates
from pathlib import Path
from fastapi import Request

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
```

---

## File 5: `app/main.py` — remove old root redirect, add /versus/ui redirect

The current root handler redirects to `/ui`. Replace it:

Find:
```python
@app.get("/", include_in_schema=False)
def root():
    """Redirect root to the live dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ui", status_code=302)
```

Remove this entirely — the ui_router now handles `/` directly.

Also add a redirect for `/versus/ui`:
```python
@app.get("/versus/ui", include_in_schema=False)
def redirect_versus_ui():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/versus/watch", status_code=301)
```

---

## Integration notes

- The ui_router is included WITHOUT a prefix, so routes defined in ui.py are
  mounted at the paths exactly as written.
- The versus_router is included WITH prefix `/versus`, so routes in
  versus_get_started.py are mounted at `/versus/<route>`.
- After removing the old root redirect, the homepage is served by the ui_router's
  `GET /` route. No conflict.
- `Jinja2Templates` in versus_get_started.py must point to the SAME templates
  directory as ui.py: `Path(__file__).parent / "templates"`.
- Do NOT change the existing `dashboard.html`, `leaderboard.html`, or `versus.html`
  templates — just serve them from the new routes.

---

## Verification steps

1. Syntax checks on ui.py, versus_get_started.py, main.py
2. Template existence: `test -f app/web/templates/homepage.html && test -f app/web/templates/model_arena.html`
3. Smoke test:
   ```bash
   uv run uvicorn app.main:app --port 8001 &
   sleep 5
   # New routes
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/model-arena
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/model-arena/watch
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/versus
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/versus/watch
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/standings
   # Old redirects — should be 301
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ui
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/leaderboard/ui
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/versus/get-started
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/versus/ui
   pkill -f "uvicorn app.main:app --port 8001"
   ```
   All new routes should be 200. All old routes should be 301.
4. Full test suite: uv run pytest tests/ -q 2>&1 | tail -10
5. If all passes:
   ```
   git add -A && git commit -m "feat: homepage + route restructure (/model-arena, /versus, /standings)" && git push origin feature/versus
   ```
