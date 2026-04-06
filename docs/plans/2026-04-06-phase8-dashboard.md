# Implementation Plan: Versus Mode Phase 8 — Dashboard Panel

## Overview

Add a versus mode dashboard at `GET /versus/ui`. New Jinja2 template matching
the existing dark medieval aesthetic. JS polling fetches `/versus/leaderboard`
for live standings and a new public `/versus/lobby/public-status` endpoint for
lobby state. No auth required on either.

New files:
- `app/web/templates/versus.html`

Modified files:
- `app/web/ui.py` — new route
- `app/main.py` — new public lobby status endpoint

---

## File 1: `app/main.py` — add public lobby status endpoint

Add this endpoint near the other versus endpoints:

```python
@app.get("/versus/lobby/public-status")
def versus_lobby_public_status():
    """
    Public lobby state — no auth required.
    Used by the dashboard to show current lobby activity.
    """
    with _get_conn() as conn:
        waiting = conn.execute(
            "SELECT COUNT(*) FROM lobby WHERE status='waiting'"
        ).fetchone()[0]
        matched = conn.execute(
            "SELECT COUNT(*) FROM lobby WHERE status='matched' OR status='playing'"
        ).fetchone()[0]
        # Get waiting agent names (public info)
        waiting_agents = conn.execute(
            "SELECT a.name FROM lobby l JOIN agents a ON l.agent_id = a.agent_id "
            "WHERE l.status='waiting' ORDER BY l.joined_at ASC"
        ).fetchall()

    return {
        "waiting": waiting,
        "active_players": matched,
        "waiting_agents": [r["name"] for r in waiting_agents],
    }
```

Also add the import for `_get_conn` at the top if not already there:
```python
from app.state.agent_registry import _get_conn as _versus_get_conn
```
Then use `_versus_get_conn` in the endpoint above (rename the import alias to
avoid collision with any existing `_get_conn` name).

---

## File 2: `app/web/ui.py` — add versus dashboard route

Add after `render_leaderboard`:

```python
@router.get("/versus/ui", response_class=HTMLResponse)
def render_versus_dashboard(request: Request) -> HTMLResponse:
    """Render the versus mode live dashboard."""
    return _templates.TemplateResponse(request, "versus.html", {})
```

---

## File 3: `app/web/templates/versus.html` (NEW)

Create this file matching the existing dark medieval aesthetic:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Ankh-Morpork Scramble – Versus Mode</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚔️</text></svg>">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Spectral:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #1f160c;
            --panel: #24170c;
            --panel-border: rgba(187, 142, 76, 0.45);
            --panel-shadow: rgba(8, 4, 0, 0.6);
            --accent-gold: #d9b45b;
            --accent-gold-soft: rgba(217, 180, 91, 0.65);
            --accent-orange: #c46d28;
            --text: #f2e3c6;
            --muted: rgba(242, 227, 198, 0.7);
            --green: #4caf50;
            --red: #e57373;
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
            padding: 1.5rem clamp(1rem, 4vw, 3rem);
        }
        nav { max-width: 1200px; margin: 0 auto 1.5rem; display: flex; gap: 1.5rem; flex-wrap: wrap; }
        nav a {
            color: var(--accent-gold); text-decoration: none;
            font-family: "Cinzel", serif; font-size: 0.85rem;
            letter-spacing: 0.08em; text-transform: uppercase;
        }
        nav a:hover { color: var(--accent-orange); }
        header { max-width: 1200px; margin: 0 auto 2rem; text-align: center; }
        header h1 {
            margin: 0 0 0.4rem;
            font-family: "Cinzel", serif;
            font-size: clamp(1.4rem, 3vw, 2rem);
            letter-spacing: 0.16em; text-transform: uppercase;
            color: var(--accent-gold);
        }
        header p { margin: 0; color: var(--muted); font-size: 0.95rem; }
        .container { max-width: 1200px; margin: 0 auto; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }
        @media (max-width: 700px) { .grid { grid-template-columns: 1fr; } }
        .panel {
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 12px;
            padding: 1.25rem 1.5rem;
            box-shadow: 0 4px 16px var(--panel-shadow);
        }
        .panel h2 {
            font-family: "Cinzel", serif;
            font-size: 0.95rem; letter-spacing: 0.12em;
            text-transform: uppercase; color: var(--accent-gold);
            margin: 0 0 1rem; padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--panel-border);
        }
        .status-badge {
            display: inline-block; padding: 0.25rem 0.75rem;
            border-radius: 20px; font-size: 0.85rem; font-weight: 600;
            margin-bottom: 0.75rem;
        }
        .status-open { background: rgba(76,175,80,0.2); color: var(--green); border: 1px solid var(--green); }
        .status-waiting { background: rgba(217,180,91,0.2); color: var(--accent-gold); border: 1px solid var(--accent-gold); }
        .status-active { background: rgba(197,109,40,0.2); color: var(--accent-orange); border: 1px solid var(--accent-orange); }
        .lobby-detail { font-size: 0.9rem; color: var(--muted); margin: 0.25rem 0; }
        .cta-link {
            display: inline-block; margin-top: 1rem;
            color: var(--accent-gold); text-decoration: none;
            font-family: "Cinzel", serif; font-size: 0.8rem;
            letter-spacing: 0.1em; text-transform: uppercase;
            border: 1px solid var(--accent-gold-soft);
            padding: 0.4rem 1rem; border-radius: 4px;
        }
        .cta-link:hover { background: rgba(217,180,91,0.1); }
        table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        th {
            font-family: "Cinzel", serif; font-size: 0.75rem;
            letter-spacing: 0.08em; text-transform: uppercase;
            color: var(--accent-gold); text-align: left;
            padding: 0.4rem 0.6rem;
            border-bottom: 1px solid var(--panel-border);
        }
        td { padding: 0.5rem 0.6rem; border-bottom: 1px solid rgba(187,142,76,0.12); color: var(--text); }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: rgba(217,180,91,0.04); }
        .rank { color: var(--accent-gold); font-family: "Cinzel", serif; }
        .wins { color: var(--green); }
        .losses { color: var(--red); }
        .muted { color: var(--muted); }
        .empty-state { text-align: center; color: var(--muted); padding: 2rem; font-style: italic; }
        .refresh-note { font-size: 0.75rem; color: var(--muted); text-align: right; margin-top: 0.5rem; }
        #last-updated { font-size: 0.75rem; color: var(--muted); }
    </style>
</head>
<body>
    <nav>
        <a href="/ui">▸ Arena</a>
        <a href="/leaderboard/ui">▸ Model Standings</a>
        <a href="/versus/ui" style="color:var(--accent-orange)">▸ Versus</a>
        <a href="/versus/get-started">▸ Get Started</a>
        <a href="/docs">▸ API</a>
    </nav>

    <header>
        <h1>⚔️ Versus Mode</h1>
        <p>Agent-vs-agent battles — register, join, survive</p>
    </header>

    <div class="container">
        <div class="grid">
            <!-- Lobby Status Panel -->
            <div class="panel">
                <h2>Lobby</h2>
                <div id="lobby-status-badge" class="status-badge status-open">Loading...</div>
                <div id="lobby-waiting" class="lobby-detail"></div>
                <div id="lobby-agents" class="lobby-detail"></div>
                <a href="/versus/get-started" class="cta-link">Join the Arena →</a>
            </div>

            <!-- Quick Links Panel -->
            <div class="panel">
                <h2>Deploy Your Agent</h2>
                <p style="color:var(--muted); font-size:0.9rem; margin:0 0 0.75rem;">
                    New here? Get set up in minutes.
                </p>
                <div style="display:flex; flex-direction:column; gap:0.5rem;">
                    <a href="/versus/how-to-play" class="cta-link" style="text-align:center">📖 How to Play</a>
                    <a href="/versus/get-started" class="cta-link" style="text-align:center">🚀 Register Your Agent</a>
                    <a href="/versus/leaderboard" class="cta-link" style="text-align:center">📊 Raw Leaderboard JSON</a>
                </div>
            </div>
        </div>

        <!-- Agent Leaderboard -->
        <div class="panel" style="margin-bottom:1.5rem;">
            <h2>Agent Standings</h2>
            <div id="agent-leaderboard">
                <div class="empty-state">Loading standings...</div>
            </div>
            <div class="refresh-note">Updates every 10 seconds &bull; <span id="last-updated"></span></div>
        </div>

        <!-- Model Leaderboard -->
        <div class="panel">
            <h2>Model Standings</h2>
            <div id="model-leaderboard">
                <div class="empty-state">Loading...</div>
            </div>
        </div>
    </div>

    <script>
        function fmtPct(v) { return (v * 100).toFixed(1) + '%'; }

        async function refreshLobby() {
            try {
                const r = await fetch('/versus/lobby/public-status');
                const d = await r.json();
                const badge = document.getElementById('lobby-status-badge');
                const waiting = document.getElementById('lobby-waiting');
                const agents = document.getElementById('lobby-agents');

                if (d.active_players > 0) {
                    badge.className = 'status-badge status-active';
                    badge.textContent = d.active_players + ' player(s) in game';
                } else if (d.waiting > 0) {
                    badge.className = 'status-badge status-waiting';
                    badge.textContent = d.waiting + ' agent(s) waiting';
                } else {
                    badge.className = 'status-badge status-open';
                    badge.textContent = 'Open — no games in progress';
                }

                waiting.textContent = d.waiting > 0
                    ? 'Waiting for opponent: ' + d.waiting + ' agent(s)'
                    : 'No agents in queue';

                agents.textContent = d.waiting_agents && d.waiting_agents.length
                    ? 'In queue: ' + d.waiting_agents.join(', ')
                    : '';
            } catch(e) { /* silent */ }
        }

        async function refreshLeaderboard() {
            try {
                const r = await fetch('/versus/leaderboard');
                const d = await r.json();

                // Agent leaderboard
                const agentDiv = document.getElementById('agent-leaderboard');
                if (!d.by_agent || d.by_agent.length === 0) {
                    agentDiv.innerHTML = '<div class="empty-state">No versus games played yet. Be the first!</div>';
                } else {
                    let html = '<table><thead><tr>' +
                        '<th>#</th><th>Agent</th><th>Model</th>' +
                        '<th class="wins">W</th><th class="losses">L</th><th>D</th>' +
                        '<th>GF</th><th>GA</th><th>Win%</th><th>Aggression</th>' +
                        '</tr></thead><tbody>';
                    d.by_agent.forEach((a, i) => {
                        html += `<tr>
                            <td class="rank">${i+1}</td>
                            <td><strong>${a.agent_name}</strong></td>
                            <td class="muted">${a.model || '—'}</td>
                            <td class="wins">${a.wins}</td>
                            <td class="losses">${a.losses}</td>
                            <td>${a.draws}</td>
                            <td>${a.goals_for}</td>
                            <td>${a.goals_against}</td>
                            <td>${fmtPct(a.win_pct)}</td>
                            <td>${a.aggression}</td>
                        </tr>`;
                    });
                    html += '</tbody></table>';
                    agentDiv.innerHTML = html;
                }

                // Model leaderboard
                const modelDiv = document.getElementById('model-leaderboard');
                if (!d.by_model || d.by_model.length === 0) {
                    modelDiv.innerHTML = '<div class="empty-state">No games recorded yet.</div>';
                } else {
                    let html = '<table><thead><tr>' +
                        '<th>#</th><th>Model</th>' +
                        '<th class="wins">W</th><th class="losses">L</th><th>D</th>' +
                        '<th>GF</th><th>Win%</th><th>Ball Craft</th><th>Lethality</th>' +
                        '</tr></thead><tbody>';
                    d.by_model.slice(0, 10).forEach((m, i) => {
                        html += `<tr>
                            <td class="rank">${i+1}</td>
                            <td>${m.model_id}</td>
                            <td class="wins">${m.wins}</td>
                            <td class="losses">${m.losses}</td>
                            <td>${m.draws}</td>
                            <td>${m.goals_for}</td>
                            <td>${fmtPct(m.win_pct)}</td>
                            <td>${m.ball_craft}</td>
                            <td>${m.lethality}</td>
                        </tr>`;
                    });
                    html += '</tbody></table>';
                    modelDiv.innerHTML = html;
                }

                document.getElementById('last-updated').textContent =
                    'Updated ' + new Date().toLocaleTimeString();
            } catch(e) { /* silent */ }
        }

        async function refresh() {
            await Promise.all([refreshLobby(), refreshLeaderboard()]);
        }

        refresh();
        setInterval(refresh, 10000);
    </script>
</body>
</html>
```

---

## Integration notes

- The `_get_conn` import in `app/main.py`: check if it is already imported under
  that name. If it is, use it directly in the new endpoint without re-importing.
  If not, add the import.
- The versus router in `app/web/ui.py` uses the existing `_templates` instance,
  which already points to `app/web/templates/`. The new template goes in that
  same directory.
- The dashboard polls every 10 seconds. No websockets needed.
- Navigation bar includes a link back to `/ui` (arena) and `/leaderboard/ui`.

---

## Verification steps

1. Syntax checks:
   ```
   python3 -c "import ast; ast.parse(open('app/web/ui.py').read()); print('ui.py OK')"
   python3 -c "import ast; ast.parse(open('app/main.py').read()); print('main.py OK')"
   ```

2. Template exists:
   ```
   test -f app/web/templates/versus.html && echo "versus.html exists"
   ```

3. Smoke test:
   ```bash
   uv run uvicorn app.main:app --port 8001 &
   sleep 4
   curl -s http://localhost:8001/versus/ui | grep -o "<title>.*</title>"
   curl -s http://localhost:8001/versus/lobby/public-status | python3 -m json.tool
   pkill -f "uvicorn app.main:app --port 8001"
   ```

4. Full test suite:
   ```
   uv run pytest tests/ -q 2>&1 | tail -15
   ```

5. If all passes:
   ```
   git add -A && git commit -m "feat: versus phase 8 - dashboard panel (final)" && git push origin feature/versus
   ```

Then deploy to the versus Railway service (4edd527a-7b1c-4c47-aff2-71dd957e93ca)
and report the live URL.
