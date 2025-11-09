"""Routes serving a lightweight dashboard for monitoring the demo game."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.setup.default_game import DEFAULT_GAME_ID
from app.setup.interactive_game import INTERACTIVE_GAME_ID

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

router = APIRouter(tags=["ui"])


@router.get("/ui", response_class=HTMLResponse)
def render_dashboard(request: Request, game_id: Optional[str] = None) -> HTMLResponse:
    """Render the live game dashboard.

    The dashboard uses simple JavaScript polling to display the current game
    state, event log, and chat messages for the configured game identifier.

    Args:
        request: FastAPI request object
        game_id: Game identifier to monitor. If not provided, uses the appropriate
                 default based on DEMO_MODE environment variable.

    Returns:
        HTML response with rendered dashboard
    """
    # If no game_id provided, use the appropriate default based on DEMO_MODE
    if game_id is None:
        demo_mode = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")
        game_id = DEFAULT_GAME_ID if demo_mode else INTERACTIVE_GAME_ID
    
    # Allow configuring poll interval via environment variable (in milliseconds)
    poll_interval = int(os.getenv("UI_POLL_INTERVAL", "2500"))

    return _templates.TemplateResponse(
        request,
        "dashboard.html",
        {"game_id": game_id, "poll_interval": poll_interval}
    )
