"""Routes serving a lightweight dashboard for monitoring the demo game."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.setup.default_game import DEFAULT_GAME_ID
from app.setup.interactive_game import INTERACTIVE_GAME_ID

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

router = APIRouter(tags=["ui"])


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
