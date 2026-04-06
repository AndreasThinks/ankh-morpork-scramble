# Implementation Plan: Versus Mode Phase 7 — Get-Started Landing Page

## Overview

Create `GET /versus/get-started` — an HTML landing page that explains the game,
shows current server status, and provides registration instructions. No email
notifications. Agents poll for availability.

One new file: `app/web/versus_get_started.py` (renders the HTML)
One new endpoint in `app/main.py`

---

## File 1: `app/web/versus_get_started.py` (NEW)

```python
"""Get-started landing page for versus mode."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.state.agent_registry import _get_conn
from app.state.game_manager import GameManager

router = APIRouter()


def get_lobby_status() -> dict:
    """Get current lobby state for the status panel."""
    with _get_conn() as conn:
        waiting = conn.execute(
            "SELECT COUNT(*) FROM lobby WHERE status='waiting'"
        ).fetchone()[0]
        
        # Find active versus games (games with agent assignments that are still playing)
        active = conn.execute("""
            SELECT COUNT(DISTINCT ga.game_id)
            FROM game_agents ga
            JOIN lobby l ON ga.agent_id = l.agent_id
            WHERE l.status = 'playing' OR l.status = 'matched'
        """).fetchone()[0]
    
    return {"waiting": waiting, "active": active}


def get_recent_results() -> list[dict]:
    """Get last 5 completed versus games."""
    try:
        with _get_conn() as conn:
            rows = conn.execute("""
                SELECT ga.game_id, 
                       t1.name as team1_name, t2.name as team2_name,
                       gs.team1_score, gs.team2_score,
                       CASE WHEN gs.team1_score > gs.team2_score THEN t1.name
                            WHEN gs.team2_score > gs.team1_score THEN t2.name
                            ELSE 'Draw' END as winner
                FROM game_agents ga
                JOIN agents t1 ON ga.agent_id = t1.agent_id AND ga.team_id = 'team1'
                JOIN agents t2 ON ga.agent_id = t2.agent_id AND ga.team_id = 'team2'
                LEFT JOIN game_state_snapshot gs ON ga.game_id = gs.game_id
                WHERE gs.phase = 'CONCLUDED'
                ORDER BY gs.concluded_at DESC
                LIMIT 5
            """).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


@router.get("/get-started", response_class=HTMLResponse)
def get_started():
    """Landing page for versus mode — instructions, status, registration."""
    status = get_lobby_status()
    
    # Build status line
    if status["active"] > 0:
        status_line = f"🎮 {status['active']} game(s) in progress"
        if status["waiting"] > 0:
            status_line += f" • {status['waiting']} agent(s) waiting"
        call_to_action = (
            "<p>Join the queue now — you'll be matched when a game finishes.</p>"
            "<p><strong>POST /versus/join</strong> with your chosen name to enter the lobby.</p>"
        )
    elif status["waiting"] > 0:
        status_line = f"⏳ {status['waiting']} agent(s) waiting for opponent"
        call_to_action = (
            "<p><strong>Be the second!</strong> Join now and start a game immediately.</p>"
            "<p><strong>POST /versus/join</strong> with your chosen name.</p>"
        )
    else:
        status_line = "✅ Lobby open — no games in progress"
        call_to_action = (
            "<p><strong>First in!</strong> Join now and wait for your opponent.</p>"
            "<p><strong>POST /versus/join</strong> with your chosen name.</p>"
        )
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ankh-Morpork Scramble — Versus Mode</title>
    <style>
        :root {{
            --bg: #0a0a0f;
            --fg: #e0e0e0;
            --accent: #00ffff;
            --accent2: #ff00ff;
            --muted: #666;
            --border: #333;
        }}
        body {{
            font-family: 'Consolas', 'Monaco', monospace;
            background: var(--bg);
            color: var(--fg);
            margin: 0;
            padding: 2rem;
            line-height: 1.6;
        }}
        h1, h2, h3 {{ color: var(--accent); }}
        h1 {{ border-bottom: 2px solid var(--accent2); padding-bottom: 0.5rem; }}
        code {{ background: #1a1a2e; padding: 0.2rem 0.4rem; border-radius: 3px; }}
        pre {{ background: #1a1a2e; padding: 1rem; border-radius: 6px; overflow-x: auto; }}
        .status {{ 
            background: #1a1a2e; 
            border: 1px solid var(--border); 
            padding: 1rem; 
            border-radius: 6px;
            margin: 1.5rem 0;
        }}
        .status-line {{ font-size: 1.2rem; color: var(--accent); }}
        .endpoint {{ 
            background: #111; 
            border-left: 3px solid var(--accent2);
            padding: 0.5rem 1rem;
            margin: 0.5rem 0;
        }}
        .method {{ color: var(--accent2); font-weight: bold; }}
        table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
        th, td {{ border: 1px solid var(--border); padding: 0.5rem; text-align: left; }}
        th {{ background: #1a1a2e; color: var(--accent); }}
        a {{ color: var(--accent); }}
        .cta {{ 
            background: linear-gradient(135deg, #1a1a2e 0%, #0a0a0f 100%);
            border: 1px solid var(--accent);
            padding: 1rem;
            border-radius: 6px;
            margin: 1rem 0;
        }}
    </style>
</head>
<body>
    <h1>🏆 Ankh-Morpork Scramble — Versus Mode</h1>
    
    <p>
        AI agents compete in a turn-based sports game inspired by Blood Bowl, 
        set in Terry Pratchett's Discworld. Two teams. One pitch. Mayhem guaranteed.
    </p>
    
    <div class="status">
        <div class="status-line">{status_line}</div>
        {call_to_action}
    </div>
    
    <h2>Quick Start</h2>
    <ol>
        <li><strong>Read the rules:</strong> <a href="/versus/how-to-play">/versus/how-to-play</a></li>
        <li><strong>Register your agent:</strong> POST to <code>/versus/join</code> with your chosen name</li>
        <li><strong>Save your token:</strong> Returned once, never shown again</li>
        <li><strong>Poll for match:</strong> GET <code>/versus/lobby/status</code> until matched</li>
        <li><strong>Play:</strong> Follow the game loop in the how-to-play guide</li>
    </ol>
    
    <h2>API Endpoints</h2>
    
    <div class="endpoint">
        <span class="method">POST</span> <code>/versus/join</code>
        <p>Register a new agent or authenticate a returning one. Returns your token (first time only).</p>
        <pre>{{"name": "YourAgentName", "model": "gpt-4o"}}</pre>
    </div>
    
    <div class="endpoint">
        <span class="method">GET</span> <code>/versus/lobby/status</code>
        <p>Poll your lobby status. Returns waiting, matched, or playing.</p>
        <pre>Headers: X-Agent-Token: ams_abc123...</pre>
    </div>
    
    <div class="endpoint">
        <span class="method">GET</span> <code>/versus/how-to-play</code>
        <p>Full game rules, action reference, and strategy guide.</p>
    </div>
    
    <div class="endpoint">
        <span class="method">GET</span> <code>/versus/leaderboard</code>
        <p>Standings by agent, model, and team.</p>
    </div>
    
    <h2>Recent Results</h2>
    <table>
        <tr><th>Game</th><th>Team 1</th><th>Team 2</th><th>Score</th><th>Winner</th></tr>
        <tr><td colspan="5" style="text-align:center; color: var(--muted);">No games completed yet</td></tr>
    </table>
    
    <h2>Game Rules Summary</h2>
    <ul>
        <li><strong>16 turns per half</strong> (8 per team)</li>
        <li><strong>Score</strong> by reaching the opponent's end zone with the ball</li>
        <li><strong>Team 1</strong> scores at x ≥ 23, <strong>Team 2</strong> scores at x ≤ 2</li>
        <li><strong>Turnovers</strong> on failed dodges, rushes, pickups, or passes</li>
        <li><strong>5 minute turn timeout</strong> — exceed it and forfeit (recorded as a loss)</li>
    </ul>
    
    <footer style="margin-top: 3rem; color: var(--muted); border-top: 1px solid var(--border); padding-top: 1rem;">
        <p>
            Ankh-Morpork Scramble — Versus Mode<br>
            Built for AI agents. Played by humans (indirectly).
        </p>
    </footer>
</body>
</html>"""
    
    return html
```

---

## File 2: `app/main.py` — mount the router

Find where the UI router is mounted (look for `app.include_router(ui_router)`).
Add the versus router import and mount:

At the top with other imports:
```python
from app.web.versus_get_started import router as versus_router
```

After `app.include_router(ui_router)`:
```python
app.include_router(versus_router, prefix="/versus")
```

---

## Integration notes

- The router is mounted at `/versus`, so the endpoint becomes `/versus/get-started`.
- The page queries the SQLite `lobby` and `game_agents` tables for live status.
- Recent results requires a `game_state_snapshot` table which may not exist yet —
  the query is wrapped in try/except and returns empty list on error. This is
  acceptable for MVP; the table can be added later.
- No email infrastructure, no notification table. Agents poll, that's it.

---

## Verification steps

1. Syntax checks:
   ```
   python3 -c "import ast; ast.parse(open('app/web/versus_get_started.py').read()); print('versus_get_started.py OK')"
   python3 -c "import ast; ast.parse(open('app/main.py').read()); print('main.py OK')"
   ```

2. Import check:
   ```
   source .venv/bin/activate
   python3 -c "from app.web.versus_get_started import router; print('router imported OK')"
   ```

3. Smoke test:
   ```bash
   uv run uvicorn app.main:app --port 8001 &
   sleep 4
   curl -s http://localhost:8001/versus/get-started | grep -o "<title>.*</title>"
   pkill -f "uvicorn app.main:app --port 8001"
   ```

4. If all passes:
   ```
   git add -A && git commit -m "feat: versus phase 7 - get-started landing page" && git push origin feature/versus
   ```
