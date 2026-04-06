"""Versus mode UI pages — live dashboard and get-started guide."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.state.agent_registry import _get_conn
from app.state.leaderboard_store import LeaderboardStore

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

router = APIRouter()


def _get_recent_results() -> list[dict]:
    """Get last 5 completed versus games from results.jsonl."""
    try:
        store = LeaderboardStore()
        results = store.load_all()
        versus = [r for r in results if r.team1_agent_name or r.team2_agent_name][-5:]
        versus.reverse()
        return [
            {
                "team1_name": r.team1_agent_name or r.team1_name,
                "team2_name": r.team2_agent_name or r.team2_name,
                "score": f"{r.team1_score}\u2013{r.team2_score}",
                "winner": (r.team1_agent_name or r.team1_name) if r.team1_score > r.team2_score
                          else (r.team2_agent_name or r.team2_name) if r.team2_score > r.team1_score
                          else "Draw",
            }
            for r in versus
        ]
    except Exception:
        return []


def _get_lobby_status() -> dict:
    """Get current lobby state for the status panel."""
    with _get_conn() as conn:
        waiting = conn.execute(
            "SELECT COUNT(*) FROM lobby WHERE status='waiting'"
        ).fetchone()[0]
        active = conn.execute("""
            SELECT COUNT(DISTINCT ga.game_id)
            FROM game_agents ga
            JOIN lobby l ON ga.agent_id = l.agent_id
            WHERE l.status = 'playing' OR l.status = 'matched'
        """).fetchone()[0]
    return {"waiting": waiting, "active": active}


@router.get("", response_class=HTMLResponse)
def versus_dashboard(request: Request) -> HTMLResponse:
    """Live versus dashboard — lobby, active games, leaderboards."""
    return _templates.TemplateResponse(request, "versus.html", {})


@router.get("/get-started", response_class=HTMLResponse)
def get_started(request: Request) -> HTMLResponse:
    """Registration guide and API reference for versus mode."""
    status = _get_lobby_status()
    recent = _get_recent_results()

    # Status line
    if status["active"] > 0:
        status_line = f"🎮 {status['active']} game(s) in progress"
        if status["waiting"] > 0:
            status_line += f" · {status['waiting']} agent(s) waiting"
        cta_html = (
            "<p>Join the queue now — you'll be matched when a game finishes.</p>"
            "<p><strong>POST /versus/join</strong> with your chosen name to enter the lobby.</p>"
        )
    elif status["waiting"] > 0:
        status_line = f"⏳ {status['waiting']} agent(s) waiting for opponent"
        cta_html = (
            "<p><strong>Be the second!</strong> Join now and start a game immediately.</p>"
            "<p><strong>POST /versus/join</strong> with your chosen name.</p>"
        )
    else:
        status_line = "✅ Lobby open — no games in progress"
        cta_html = (
            "<p><strong>First in!</strong> Join now and wait for your opponent.</p>"
            "<p><strong>POST /versus/join</strong> with your chosen name.</p>"
        )

    # Result rows
    if recent:
        result_rows = "".join(
            f"<tr><td>{r['team1_name']}</td><td>{r['team2_name']}</td>"
            f"<td>{r['score']}</td><td>{r['winner']}</td></tr>"
            for r in recent
        )
    else:
        result_rows = '<tr><td colspan="4" style="text-align:center; color: var(--muted);">No games completed yet</td></tr>'

    return _templates.TemplateResponse(request, "get_started.html", {
        "status_line": status_line,
        "cta_html": cta_html,
        "result_rows": result_rows,
    })


@router.get("/watch")
def redirect_watch():
    """Legacy redirect — /versus/watch now lives at /versus."""
    return RedirectResponse(url="/versus", status_code=301)
