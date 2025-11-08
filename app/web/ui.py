"""Routes serving a lightweight dashboard for monitoring the demo game."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.setup.default_game import DEFAULT_GAME_ID

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

router = APIRouter(tags=["ui"])


@router.get("/ui", response_class=HTMLResponse)
def render_dashboard(request: Request, game_id: str = DEFAULT_GAME_ID) -> HTMLResponse:
    """Render the live game dashboard.

    The dashboard uses simple JavaScript polling to display the current game
    state, event log, and chat messages for the configured game identifier.

    Args:
        request: FastAPI request object
        game_id: Game identifier to monitor (default: demo-game)

    Returns:
        HTML response with rendered dashboard
    """
    # Allow configuring poll interval via environment variable (in milliseconds)
    poll_interval = int(os.getenv("UI_POLL_INTERVAL", "2500"))

    return _templates.TemplateResponse(
        request,
        "dashboard.html",
        {"game_id": game_id, "poll_interval": poll_interval}
    )
