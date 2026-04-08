"""FastAPI application for Ankh-Morpork Scramble"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Header, Query
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from app.logging_utils import configure_root_logger
from app.web import router as ui_router
from app.web.versus_get_started import router as versus_router
from app.api.middleware import rate_limiter, sanitize_id

from app.models.game_state import GameState
from app.models.team import TeamType
from app.models.actions import (
    ActionRequest,
    ActionResult,
    SetupRequest,
    ValidActionsResponse,
    BudgetStatus,
    PurchaseResult,
    AvailablePositionsResponse
)
from app.models.pitch import Position
from app.setup.default_game import DEFAULT_GAME_ID, bootstrap_default_game
from app.setup.interactive_game import INTERACTIVE_GAME_ID, bootstrap_interactive_game
from app.state.game_manager import GameManager
from app.game.statistics import StatisticsAggregator
from app.models.events import GameStatistics
from app.models.leaderboard import LeaderboardResponse
from app.models.agent import AgentIdentity, AgentContext, JoinRequest, JoinResponse, LobbyStatusResponse
from app.state.agent_registry import AgentRegistry, init_db, _get_conn
from app.state.lobby import LobbyManager
from app.api.versus_auth import optional_agent_auth

# Global game manager instance
game_manager = GameManager()
agent_registry = AgentRegistry()
lobby_manager = LobbyManager(game_manager)

# Configure logging early so startup hooks can log useful information
_LOG_FILE = configure_root_logger(service_name="api", env_prefix="APP_")
logger = logging.getLogger("app.main")
if _LOG_FILE:
    logger.info("API log file initialised at %s", _LOG_FILE)

# Initialize game based on DEMO_MODE setting
# DEMO_MODE=true: Pre-configured demo game ready to play
# DEMO_MODE=false (default): Interactive setup where agents must buy and place players
demo_mode = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")

if demo_mode:
    # Demo mode: Create pre-configured game ready to play
    default_demo_game_id = os.getenv("DEFAULT_GAME_ID", DEFAULT_GAME_ID)
    demo_game_state = bootstrap_default_game(
        game_manager,
        game_id=default_demo_game_id,
        logger=logger
    )
    logger.info(
        "Demo game '%s' is ready with %d players",
        default_demo_game_id,
        len(demo_game_state.players)
    )
else:
    # Interactive mode: Create empty game requiring setup
    default_demo_game_id = None
    interactive_game_id = os.getenv("INTERACTIVE_GAME_ID", INTERACTIVE_GAME_ID)
    team1_name = os.getenv("TEAM1_NAME", "City Watch Constables")
    team2_name = os.getenv("TEAM2_NAME", "Unseen University Adepts")
    demo_game_state = bootstrap_interactive_game(
        game_manager,
        game_id=interactive_game_id,
        team1_name=team1_name,
        team2_name=team2_name,
        logger=logger
    )
    logger.info(
        "Interactive game '%s' created in DEPLOYMENT phase. Agents must purchase and place players.",
        interactive_game_id
    )

# Turn timeout watcher helper
async def _turn_timeout_watcher():
    """Background task: forfeit versus games where a turn has exceeded 5 minutes."""
    from datetime import timedelta
    TIMEOUT_MINUTES = 5
    CHECK_INTERVAL = 60  # seconds

    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        try:
            now = datetime.now(timezone.utc)
            for game_id, game_state in list(game_manager.games.items()):
                # Only check versus games (have agent assignments) that are active
                if game_state.phase not in ("playing", "kickoff"):
                    continue
                if not game_state.turn:
                    continue
                turn_started = game_state.turn.turn_started_at
                if not turn_started:
                    continue
                # Make timezone-aware if naive
                if turn_started.tzinfo is None:
                    turn_started = turn_started.replace(tzinfo=timezone.utc)
                elapsed = now - turn_started
                if elapsed > timedelta(minutes=TIMEOUT_MINUTES):
                    # Check this is a versus game
                    from app.state.agent_registry import _get_conn
                    with _get_conn() as conn:
                        row = conn.execute(
                            "SELECT agent_id FROM game_agents WHERE game_id=? LIMIT 1",
                            (game_id,)
                        ).fetchone()
                    if row:
                        active_team = game_state.turn.active_team_id
                        logger.warning(
                            "Turn timeout: game %s team %s exceeded %d minutes",
                            game_id, active_team, TIMEOUT_MINUTES
                        )
                        game_manager.record_forfeit(game_id, active_team)
            # ── Ack deadline checks for matched pairs ──
            # Case A: ack deadline expired
            with _get_conn() as conn:
                matched_rows = conn.execute(
                    "SELECT agent_id, paired_with, scheduled_start FROM lobby WHERE status='matched' AND paired_with IS NOT NULL"
                ).fetchall()
            # Deduplicate pairs (each pair appears twice)
            seen_pairs: set[tuple[str, str]] = set()
            for row in matched_rows:
                pair_key = tuple(sorted([row["agent_id"], row["paired_with"]]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                if not row["scheduled_start"]:
                    continue
                deadline = datetime.fromisoformat(row["scheduled_start"])
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                if now > deadline:
                    with _get_conn() as conn:
                        both = conn.execute(
                            "SELECT agent_id, acked_at FROM lobby WHERE agent_id IN (?,?)",
                            (row["agent_id"], row["paired_with"])
                        ).fetchall()
                    unacked = [r["agent_id"] for r in both if not r["acked_at"]]
                    acked = [r["agent_id"] for r in both if r["acked_at"]]
                    if len(unacked) == 2:
                        lobby_manager.cancel_match(row["agent_id"], row["paired_with"])
                    elif len(unacked) == 1:
                        lobby_manager.forfeit_unacked(unacked[0], acked[0])
                    # If both acked, game should already be live — skip

            # Case B: both acked but game not created yet (belt-and-braces)
            with _get_conn() as conn:
                both_acked = conn.execute(
                    "SELECT agent_id, paired_with FROM lobby "
                    "WHERE status='matched' AND acked_at IS NOT NULL AND game_id IS NULL AND paired_with IS NOT NULL"
                ).fetchall()
            seen_pairs_b: set[tuple[str, str]] = set()
            for row in both_acked:
                pair_key = tuple(sorted([row["agent_id"], row["paired_with"]]))
                if pair_key in seen_pairs_b:
                    continue
                seen_pairs_b.add(pair_key)
                # Verify opponent also acked
                with _get_conn() as conn:
                    opp = conn.execute(
                        "SELECT acked_at FROM lobby WHERE agent_id=?",
                        (row["paired_with"],)
                    ).fetchone()
                if opp and opp["acked_at"]:
                    lobby_manager._create_game_for_pair(row["agent_id"], row["paired_with"])

        except Exception as exc:
            logger.error("Turn timeout watcher error: %s", exc)


# Simple lifespan for FastAPI
@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """FastAPI application lifespan."""
    # Startup
    logger.info("FastAPI application starting up...")
    logger.info("Game manager initialized with %d active games", len(game_manager.games))
    init_db()
    logger.info("versus.db initialised")
    
    # Start turn timeout watcher
    _timeout_task = asyncio.create_task(_turn_timeout_watcher())
    logger.info("Turn timeout watcher started")
    
    yield
    
    # Shutdown
    _timeout_task.cancel()
    logger.info("FastAPI application shutting down...")


# Configure CORS origins
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Ankh-Morpork Scramble API",
    description="Turn-based sports game server based on Blood Bowl mechanics",
    version="0.1.0",
    lifespan=app_lifespan
)

# Configure CORS for web dashboard and external clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.middleware("http")(rate_limiter)

# Expose the lightweight monitoring dashboard
app.include_router(ui_router)
app.include_router(versus_router, prefix="/versus")


@app.get("/versus/ui", include_in_schema=False)
def redirect_versus_ui():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/versus", status_code=301)


@app.get("/health")
def health_check():
    """Health check endpoint for Railway monitoring"""
    return {
        "status": "healthy",
        "active_games": len(game_manager.games)
    }


# ── service status ─────────────────────────────────────────────────────────
# Surfaces LLM-backend health to the UI so we can show a maintenance screen
# when OpenRouter is out of credits or every model in the pool is dead.
import time as _svc_time

_VALID_SERVICE_STATES = {"ok", "out_of_credits", "no_models", "degraded"}
service_status: dict = {
    "status": "ok",
    "reason": None,
    "updated_at": _svc_time.time(),
}


@app.get("/service-status")
def get_service_status():
    """Public endpoint the dashboard polls to show/hide the maintenance banner."""
    return service_status


@app.post("/admin/service-status")
def set_service_status(
    status: str = Query(..., description="One of: ok, out_of_credits, no_models, degraded"),
    reason: Optional[str] = Query(None),
    x_admin_key: Optional[str] = Header(None),
):
    """Allow the match runner to flip the service status (admin only)."""
    verify_admin_key(x_admin_key)
    if status not in _VALID_SERVICE_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {sorted(_VALID_SERVICE_STATES)}",
        )
    service_status["status"] = status
    service_status["reason"] = reason or None
    service_status["updated_at"] = _svc_time.time()
    logger.warning("service-status updated: %s (reason=%s)", status, reason)
    return service_status


def verify_admin_key(x_admin_key: Optional[str] = Header(None)) -> bool:
    """Verify admin API key from header"""
    admin_key = os.getenv("ADMIN_API_KEY")
    if not admin_key:
        raise HTTPException(
            status_code=500,
            detail="Admin functionality not configured (ADMIN_API_KEY not set)"
        )
    if not x_admin_key or x_admin_key != admin_key:
        raise HTTPException(status_code=403, detail="Invalid admin API key")
    return True


@app.get("/admin/logs")
def list_logs(x_admin_key: Optional[str] = Header(None)):
    """List all available log files (requires admin API key)"""
    verify_admin_key(x_admin_key)

    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    if not log_dir.exists():
        return {"logs": [], "log_dir": str(log_dir)}

    log_files = []
    for log_file in sorted(log_dir.glob("*.log")):
        stat = log_file.stat()
        log_files.append({
            "name": log_file.name,
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
            "path": f"/admin/logs/{log_file.name}"
        })

    return {
        "log_dir": str(log_dir),
        "logs": log_files
    }


@app.get("/admin/logs/all")
def view_all_logs(
    x_admin_key: Optional[str] = Header(None),
    tail: Optional[int] = Query(None, description="Show last N lines per log file"),
    format: str = Query("combined", description="Format: 'combined' or 'separated'")
):
    """View all log files in a unified view (requires admin API key)

    This endpoint aggregates logs from all components:
    - server.log: FastAPI server logs
    - mcp.log: MCP server logs
    - team1.log: Team 1 agent logs
    - team2.log: Team 2 agent logs
    - referee.log: Referee agent logs
    - api.log: API-specific logs

    Query parameters:
    - tail: Show last N lines from each log file
    - format: 'combined' (interleaved by timestamp) or 'separated' (grouped by file)

    Examples:
    - /admin/logs/all - All logs in combined format
    - /admin/logs/all?tail=100 - Last 100 lines from each log
    - /admin/logs/all?format=separated - Logs grouped by file
    """
    verify_admin_key(x_admin_key)

    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    if not log_dir.exists():
        return PlainTextResponse(
            content=f"Log directory not found: {log_dir}",
            media_type="text/plain"
        )

    # Define expected log files in priority order
    log_files = ["server.log", "api.log", "mcp.log", "team1.log", "team2.log", "referee.log"]

    if format == "separated":
        # Separated format: group logs by file
        output_lines = []
        for log_name in log_files:
            log_file = log_dir / log_name
            if not log_file.exists():
                continue

            output_lines.append("=" * 80)
            output_lines.append(f"LOG FILE: {log_name}")
            output_lines.append("=" * 80)

            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    if tail:
                        lines = f.readlines()
                        content_lines = lines[-tail:]
                    else:
                        content_lines = f.readlines()

                    output_lines.extend(line.rstrip() for line in content_lines)

            except Exception as e:
                output_lines.append(f"Error reading {log_name}: {str(e)}")

            output_lines.append("")  # Blank line between files

        content = "\n".join(output_lines)

    else:
        # Combined format: interleave logs by timestamp
        all_log_lines = []

        for log_name in log_files:
            log_file = log_dir / log_name
            if not log_file.exists():
                continue

            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    if tail:
                        lines = f.readlines()
                        lines = lines[-tail:]
                    else:
                        lines = f.readlines()

                    # Add source tag to each line
                    for line in lines:
                        line = line.rstrip()
                        if line:
                            # Try to extract timestamp for sorting
                            # Expected format: "2024-01-01 12:00:00,123 | ..."
                            timestamp_str = None
                            if len(line) > 23 and line[4] == '-' and line[10] == ' ':
                                timestamp_str = line[:23]

                            all_log_lines.append({
                                'timestamp': timestamp_str,
                                'source': log_name,
                                'content': line
                            })

            except Exception as e:
                all_log_lines.append({
                    'timestamp': None,
                    'source': log_name,
                    'content': f"Error reading {log_name}: {str(e)}"
                })

        # Sort by timestamp (None timestamps go to the end)
        all_log_lines.sort(key=lambda x: (x['timestamp'] is None, x['timestamp'] or ''))

        # Format output with source tags
        output_lines = []
        output_lines.append("=" * 80)
        output_lines.append("UNIFIED LOG VIEW (sorted by timestamp)")
        output_lines.append("=" * 80)
        output_lines.append("")

        for entry in all_log_lines:
            source_tag = f"[{entry['source']}]".ljust(15)
            output_lines.append(f"{source_tag} {entry['content']}")

        content = "\n".join(output_lines)

    return PlainTextResponse(
        content=content,
        media_type="text/plain",
        headers={
            "X-Log-Count": str(len([f for f in log_files if (log_dir / f).exists()])),
            "X-Log-Format": format
        }
    )


@app.get("/admin/logs/{log_name}")
def view_log(
    log_name: str,
    x_admin_key: Optional[str] = Header(None),
    tail: Optional[int] = Query(None, description="Show last N lines"),
    head: Optional[int] = Query(None, description="Show first N lines")
):
    """View a specific log file (requires admin API key)

    Query parameters:
    - tail: Show last N lines
    - head: Show first N lines (ignored if tail is set)

    Examples:
    - /admin/logs/api.log - Full log
    - /admin/logs/api.log?tail=100 - Last 100 lines
    - /admin/logs/mcp.log?head=50 - First 50 lines
    """
    verify_admin_key(x_admin_key)

    # Sanitize log name to prevent directory traversal
    if "/" in log_name or ".." in log_name:
        raise HTTPException(status_code=400, detail="Invalid log file name")

    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_file = log_dir / log_name

    if not log_file.exists():
        raise HTTPException(status_code=404, detail=f"Log file '{log_name}' not found")

    if not log_file.is_file():
        raise HTTPException(status_code=400, detail=f"'{log_name}' is not a file")

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            if tail:
                # Read last N lines
                lines = f.readlines()
                content = ''.join(lines[-tail:])
            elif head:
                # Read first N lines
                lines = []
                for i, line in enumerate(f):
                    if i >= head:
                        break
                    lines.append(line)
                content = ''.join(lines)
            else:
                # Read entire file
                content = f.read()

        return PlainTextResponse(
            content=content,
            media_type="text/plain",
            headers={
                "X-Log-File": log_name,
                "X-Log-Size": str(log_file.stat().st_size)
            }
        )

    except Exception as e:
        logger.error(f"Error reading log file {log_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")


@app.post("/game", response_model=GameState)
def create_game(game_id: Optional[str] = None):
    """Create a new game"""
    try:
        game_state = game_manager.create_game(game_id)
        return game_state
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/current-game", response_model=GameState)
def get_current_game():
    """Get the current/default game state.
    
    The server always has an active game running. This endpoint provides
    the simplest way for agents to access it without needing to know the game ID.
    
    Returns the bootstrapped game (either demo or interactive mode).
    """
    # Return the bootstrapped game
    if demo_mode and default_demo_game_id:
        game_state = game_manager.get_game(default_demo_game_id)
    else:
        game_state = game_manager.get_game(INTERACTIVE_GAME_ID)
    
    if not game_state:
        raise HTTPException(status_code=500, detail="No active game available")
    return game_state


@app.get("/game/{game_id}", response_model=GameState)
def get_game(game_id: str):
    """Get current game state"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    return game_state


@app.get("/game/{game_id}/statistics", response_model=GameStatistics)
def get_game_statistics(game_id: str):
    """Return aggregated statistics for a completed or in-progress game."""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    aggregator = StatisticsAggregator(game_state)
    return aggregator.aggregate()


@app.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard():
    """Return aggregated season standings — wins/losses/draws per team and per AI model.
    
    Reads from data/results.jsonl. Returns empty standings if no games have been played.
    """
    return game_manager.leaderboard.get_leaderboard()


@app.post("/game/{game_id}/setup-team", response_model=GameState)
def setup_team(
    game_id: str,
    team_id: str,
    team_type: TeamType,
    player_positions: dict[str, str]
):
    """
    Set up a team with player roster
    
    Example player_positions:
    {
        "constable": "5",
        "clerk_runner": "1",
        "fleet_recruit": "2",
        "watch_sergeant": "3"
    }
    """
    try:
        game_state = game_manager.setup_team(
            game_id,
            team_id,
            team_type,
            player_positions
        )
        return game_state
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/game/{game_id}/team/{team_id}/budget", response_model=BudgetStatus)
def get_team_budget(game_id: str, team_id: str):
    """Get budget information for a team"""
    try:
        budget_status = game_manager.get_budget_status(game_id, team_id)
        return budget_status
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/game/{game_id}/team/{team_id}/available-positions", response_model=AvailablePositionsResponse)
def get_available_positions(game_id: str, team_id: str):
    """Get available player positions and rerolls for purchase"""
    try:
        available = game_manager.get_available_positions(game_id, team_id)
        return available
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/team/{team_id}/buy-player", response_model=PurchaseResult)
def buy_player(
    game_id: str,
    team_id: str,
    position_key: str,
    agent_ctx: Optional[AgentContext] = Depends(optional_agent_auth),
):
    """
    Purchase a player for a team during setup phase

    Args:
        game_id: Game identifier
        team_id: Team identifier (e.g., "team1")
        position_key: Position to purchase (e.g., "constable", "apprentice_wizard")

    Returns:
        PurchaseResult with updated budget status
    """
    if agent_ctx and agent_ctx.team_id != team_id:
        raise HTTPException(status_code=403, detail="You can only buy players for your own team")
    try:
        result = game_manager.buy_player(game_id, team_id, position_key)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/team/{team_id}/buy-reroll", response_model=PurchaseResult)
def buy_reroll(
    game_id: str,
    team_id: str,
    agent_ctx: Optional[AgentContext] = Depends(optional_agent_auth),
):
    """
    Purchase a team reroll during setup phase

    Args:
        game_id: Game identifier
        team_id: Team identifier (e.g., "team1")

    Returns:
        PurchaseResult with updated budget status
    """
    if agent_ctx and agent_ctx.team_id != team_id:
        raise HTTPException(status_code=403, detail="You can only buy rerolls for your own team")
    try:
        result = game_manager.buy_reroll(game_id, team_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/place-players", response_model=GameState)
def place_players(
    game_id: str,
    request: SetupRequest,
    agent_ctx: Optional[AgentContext] = Depends(optional_agent_auth),
):
    """Place players on the pitch during setup"""
    if agent_ctx and agent_ctx.team_id != request.team_id:
        raise HTTPException(status_code=403, detail="You can only place players for your own team")
    try:
        game_state = game_manager.place_players(
            game_id,
            request.team_id,
            request.positions
        )
        return game_state
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/start", response_model=GameState)
def start_game(
    game_id: str,
    team1_model: Optional[str] = None,
    team2_model: Optional[str] = None,
    agent_ctx: Optional[AgentContext] = Depends(optional_agent_auth),
):
    """Start the game"""
    try:
        game_state = game_manager.start_game(game_id)
        if team1_model:
            game_state.team1_model = team1_model
        if team2_model:
            game_state.team2_model = team2_model
        lobby_manager.mark_game_playing(game_id)
        return game_state
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/action", response_model=ActionResult)
def execute_action(
    game_id: str,
    action: ActionRequest,
    agent_ctx: Optional[AgentContext] = Depends(optional_agent_auth),
):
    """Execute a game action"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    # Versus auth: confirm it's this agent's turn
    if agent_ctx and game_state.turn:
        active_team = game_state.get_active_team()
        if agent_ctx.team_id != active_team.id:
            raise HTTPException(
                status_code=403,
                detail=f"It is not your turn (active team: {active_team.id})"
            )
    
    # Verify player belongs to active team
    if game_state.turn and not game_state.is_player_on_active_team(action.player_id):
        raise HTTPException(
            status_code=400,
            detail="Not this team's turn"
        )
    
    try:
        result = game_manager.executor.execute_action(game_state, action)
        
        # Check for scoring after action
        if result.success:
            scored_team = game_manager.check_scoring(game_id)
            if scored_team:
                result.details["scored"] = scored_team
                # Scoring auto-ends the turn inside check_scoring
                result.details["turn_ended"] = True

            # Attach current game state context to result
            result.details['pitch'] = game_state.pitch.model_dump()
            result.details['turn'] = game_state.turn.model_dump() if game_state.turn else None
            result.details['phase'] = game_state.phase.value

        # If turnover, automatically end turn
        if result.turnover:
            # Set flag before calling end_turn to prevent double calls
            game_state.turn.turnover_ended_turn = True
            game_manager.end_turn(game_id)
            result.details["turn_ended"] = True
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/end-turn", response_model=GameState)
def end_turn(
    game_id: str,
    team_id: Optional[str] = None,
    agent_ctx: Optional[AgentContext] = Depends(optional_agent_auth),
):
    """Manually end the current turn.

    If team_id is provided, validates that it matches the currently active team
    before ending the turn. This prevents agents from accidentally skipping the
    opponent's turn.

    Raises HTTP 400 if the game has already concluded, if no turn is active,
    or if team_id doesn't match the active team.
    """
    try:
        game_state = game_manager.get_game(game_id)
        if not game_state:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

        # Versus auth: use agent's team_id if available, override client param
        if agent_ctx:
            team_id = agent_ctx.team_id

        if team_id is not None and game_state.turn:
            active_team = game_state.get_active_team()
            if team_id != active_team.id:
                raise HTTPException(
                    status_code=403,
                    detail=f"It is not {team_id}'s turn (active team: {active_team.id})"
                )

        game_state = game_manager.end_turn(game_id)
        return game_state
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/reroll")
def use_reroll(
    game_id: str,
    team_id: str,
    agent_ctx: Optional[AgentContext] = Depends(optional_agent_auth),
):
    """Use a team re-roll"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    if agent_ctx and agent_ctx.team_id != team_id:
        raise HTTPException(status_code=403, detail="You can only use rerolls for your own team")
    
    try:
        team = game_state.get_team_by_id(team_id)
        team.use_reroll()
        return {"success": True, "rerolls_remaining": team.rerolls_remaining}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/game/{game_id}/valid-actions", response_model=ValidActionsResponse)
def get_valid_actions(game_id: str):
    """Get all valid actions for current game state"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    if not game_state.turn:
        raise HTTPException(status_code=400, detail="Game not started")
    
    active_team = game_state.get_active_team()
    
    # Get movable players (standing, has movement)
    movable_players = []
    blockable_targets = {}
    
    for player_id in active_team.player_ids:
        player = game_state.get_player(player_id)
        
        if player.is_standing and player.movement_remaining > 0 and not player.has_acted:
            movable_players.append(player_id)

        # Find blockable targets for this player
        if player.is_standing and not player.has_acted:
            player_pos = game_state.pitch.player_positions.get(player_id)
            if player_pos:
                targets = []
                for adj_player_id in game_state.pitch.get_adjacent_players(player_pos):
                    adj_player = game_state.get_player(adj_player_id)
                    # Check adjacency (distance <= 1 in both x and y)
                    adj_pos = game_state.pitch.player_positions.get(adj_player_id)
                    if adj_pos:
                        dx = abs(player_pos.x - adj_pos.x)
                        dy = abs(player_pos.y - adj_pos.y)
                        if dx <= 1 and dy <= 1 and adj_player.team_id != player.team_id and adj_player.is_active:
                            targets.append(adj_player_id)
                
                if targets:
                    blockable_targets[player_id] = targets
    
    # Pre-compute reachable squares for each movable player
    from app.game.movement import MovementHandler
    from app.game.dice import DiceRoller
    movement_handler = MovementHandler(DiceRoller())
    reachable_squares: dict[str, list[dict]] = {}
    for player_id in movable_players:
        reachable_squares[player_id] = movement_handler.get_reachable_squares(
            game_state, player_id
        )

    return ValidActionsResponse(
        current_team=active_team.id,
        phase=game_state.phase.value,
        can_charge=not game_state.turn.charge_used,
        can_hurl=not game_state.turn.hurl_used,
        can_quick_pass=not game_state.turn.quick_pass_used,
        can_boot=not game_state.turn.boot_used,
        movable_players=movable_players,
        blockable_targets=blockable_targets,
        ball_carrier=game_state.pitch.ball_carrier,
        ball_on_ground=game_state.pitch.ball_position is not None and game_state.pitch.ball_carrier is None,
        ball_position=game_state.pitch.ball_position,
        reachable_squares=reachable_squares,
    )


@app.get("/game/{game_id}/history")
def get_history(game_id: str, limit: int = 50):
    """Get game event history"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    return {
        "game_id": game_id,
        "events": game_state.event_log[-limit:]
    }


@app.get("/game/{game_id}/log")
def export_game_log(game_id: str, format: str = "markdown"):
    """
    Export complete game log with events, dice rolls, and statistics.

    Formats:
    - markdown: Human-readable narrative with full details
    - json: Structured event data

    The log includes:
    - All game events chronologically
    - Dice rolls and outcomes
    - Turn-by-turn breakdown
    - Game statistics
    """
    if format not in ["markdown", "json"]:
        raise HTTPException(
            status_code=400,
            detail="Format must be 'markdown' or 'json'"
        )

    log_content = game_manager.export_game_log(game_id, format=format)

    if not log_content:
        raise HTTPException(
            status_code=404,
            detail=f"Game {game_id} not found or has no events"
        )

    # Return as appropriate content type
    if format == "markdown":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=log_content, media_type="text/markdown")
    else:
        from fastapi.responses import JSONResponse
        import json
        return JSONResponse(content=json.loads(log_content))


@app.get("/game/{game_id}/suggest-path")
def suggest_path(game_id: str, player_id: str, target_x: int, target_y: int):
    """
    Suggest a path for a player to reach a target position with risk assessment.
    
    Returns path with detailed risk information including:
    - Dodge requirements
    - Rush square identification
    - Success probabilities
    - Total risk score
    """
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    try:
        from app.game.pathfinding import PathFinder
        from app.game.movement import MovementHandler
        from app.game.dice import DiceRoller
        
        # Create pathfinder
        dice_roller = DiceRoller()
        movement_handler = MovementHandler(dice_roller)
        pathfinder = PathFinder(movement_handler)
        
        # Generate suggestion
        target_pos = Position(x=target_x, y=target_y)
        suggestion = pathfinder.suggest_path(game_state, player_id, target_pos)
        
        return suggestion
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/join")
def join_game(
    game_id: str,
    team_id: str,
    agent_ctx: Optional[AgentContext] = Depends(optional_agent_auth),
):
    """Mark a team as joined"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    if agent_ctx and agent_ctx.team_id != team_id:
        raise HTTPException(status_code=403, detail="You can only join as your own team")
    
    try:
        if team_id == game_state.team1.id:
            game_state.team1_joined = True
            game_state.team1_ready = True
            game_state.add_event(f"Team {team_id} joined")
        elif team_id == game_state.team2.id:
            game_state.team2_joined = True
            game_state.team2_ready = True
            game_state.add_event(f"Team {team_id} joined")
        else:
            raise HTTPException(status_code=400, detail=f"Invalid team_id: {team_id}")
        
        return {
            "success": True,
            "team_id": team_id,
            "players_ready": game_state.players_ready
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/message")
def send_message(
    game_id: str,
    sender_id: str,
    sender_name: str,
    content: str,
    agent_ctx: Optional[AgentContext] = Depends(optional_agent_auth),
):
    """Send a message in the game"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    # If agent_ctx present, use authenticated identity instead of trusting query params
    if agent_ctx:
        sender_id = agent_ctx.agent_id
        sender_name = agent_ctx.name
    
    try:
        message = game_state.add_message(sender_id, sender_name, content)
        return {
            "success": True,
            "message": message
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/game/{game_id}/messages")
def get_messages(game_id: str, turn_number: Optional[int] = None, limit: Optional[int] = None):
    """Get messages from the game"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    messages = game_state.messages
    
    # Filter by turn if specified
    if turn_number is not None:
        messages = [m for m in messages if m.turn_number == turn_number]
    
    # Apply limit if specified
    if limit is not None:
        messages = messages[-limit:]
    
    return {
        "game_id": game_id,
        "count": len(messages),
        "messages": messages
    }


@app.post("/game/{game_id}/reset", response_model=GameState)
def reset_game(game_id: str):
    """Reset game to setup phase, preserving join status and message history"""
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    try:
        game_manager._record_result_if_concluded(game_state)
        game_state.reset_to_setup()
        game_manager._recorded_games.discard(game_id)
        return game_state
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/game/{game_id}/rematch", response_model=GameState)
def rematch_game(game_id: str):
    """Prepare and start a fresh match after the current game concludes.
    
    Records the completed game result to the leaderboard before resetting.
    The 'Play Again' button in the UI calls this endpoint.
    """
    game_state = game_manager.get_game(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    try:
        # ── NEW: record result before we wipe the state ──────────────
        game_manager._record_result_if_concluded(game_state)
        # ─────────────────────────────────────────────────────────────
        
        if demo_mode and default_demo_game_id and game_id == default_demo_game_id:
            # Remove the existing entry so ``bootstrap_default_game`` creates a new instance
            game_manager.games.pop(game_id, None)
            game_manager._recorded_games.discard(game_id)
            fresh_state = bootstrap_default_game(
                game_manager,
                game_id=game_id,
                logger=logger
            )
            # Mark teams as joined so the kickoff can start immediately
            fresh_state.team1_joined = True
            fresh_state.team2_joined = True
            fresh_state.team1_ready = True
            fresh_state.team2_ready = True
            return game_manager.start_game(game_id)

        # Fallback for interactive/custom games: reset to setup and let clients configure
        game_state.reset_to_setup()
        game_manager._recorded_games.discard(game_id)
        return game_state

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── versus mode endpoints ────────────────────────────────────────────────────

@app.post("/versus/join", response_model=JoinResponse)
def versus_join(request: JoinRequest):
    """
    Register a new agent or authenticate a returning one, then join the lobby.

    New agent: provide { name, model (optional) }
    Returning agent: provide { token }

    Token is returned ONLY on first registration. Save it — it is never shown again.
    """
    if request.token:
        # Returning agent
        identity = agent_registry.resolve_token(request.token)
        if not identity:
            raise HTTPException(status_code=401, detail="Invalid token")
        raw_token = None
    elif request.name:
        # New agent — register. register() wraps sqlite IntegrityError as ValueError
        # so a name collision is always surfaced as ValueError("... already taken").
        try:
            identity, raw_token = agent_registry.register(request.name, request.model)
        except ValueError as e:
            msg = str(e)
            if "already taken" in msg:
                raise HTTPException(status_code=409, detail=msg)
            raise HTTPException(status_code=400, detail=msg)
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'token' (returning agent) or 'name' (new agent)"
        )

    # Join the lobby
    result = lobby_manager.join(identity.agent_id)

    # Resolve opponent name if matched
    opponent_name = None
    if result.get("opponent_agent_id"):
        opp = agent_registry.get_by_id(result["opponent_agent_id"])
        if opp:
            opponent_name = opp.name

    return JoinResponse(
        agent_id=identity.agent_id,
        name=identity.name,
        token=raw_token,
        status=result["status"],
        game_id=result.get("game_id"),
        team_id=result.get("team_id"),
        opponent_name=opponent_name,
        scheduled_start=result.get("scheduled_start"),
        poll_interval_seconds=result.get("poll_interval_seconds"),
    )


@app.get("/versus/lobby/status", response_model=LobbyStatusResponse)
def versus_lobby_status(x_agent_token: Optional[str] = Header(None)):
    """
    Poll lobby status for the authenticated agent.
    Returns waiting / matched / playing / not_in_lobby.
    """
    if not x_agent_token:
        raise HTTPException(status_code=401, detail="X-Agent-Token header required")
    identity = agent_registry.resolve_token(x_agent_token)
    if not identity:
        raise HTTPException(status_code=401, detail="Invalid token")

    status = lobby_manager.get_status(identity.agent_id)

    return LobbyStatusResponse(
        agent_id=identity.agent_id,
        name=identity.name,
        status=status["status"],
        game_id=status.get("game_id"),
        team_id=status.get("team_id"),
        opponent_name=status.get("opponent_name"),
        scheduled_start=status.get("scheduled_start"),
        poll_interval_seconds=status.get("poll_interval_seconds"),
    )


@app.delete("/versus/lobby/leave")
def versus_lobby_leave(x_agent_token: Optional[str] = Header(None)):
    """Remove the authenticated agent from the lobby if waiting."""
    if not x_agent_token:
        raise HTTPException(status_code=401, detail="X-Agent-Token header required")
    identity = agent_registry.resolve_token(x_agent_token)
    if not identity:
        raise HTTPException(status_code=401, detail="Invalid token")

    removed = lobby_manager.leave(identity.agent_id)
    return {"removed": removed, "agent_id": identity.agent_id}


@app.post("/versus/ready/{agent_id}")
def versus_ready(agent_id: str, x_agent_token: Optional[str] = Header(None)):
    """Acknowledge a match. Both agents must call this within the ack window.

    Once both agents ack, the game is created immediately and both transition
    to 'playing'. If only one acks before the deadline, the non-responder is
    forfeited and the acked agent is re-queued.
    """
    if not x_agent_token:
        raise HTTPException(status_code=401, detail="X-Agent-Token header required")
    identity = agent_registry.resolve_token(x_agent_token)
    if not identity or identity.agent_id != agent_id:
        raise HTTPException(status_code=401, detail="Invalid token or agent_id mismatch")
    result = lobby_manager.ack(agent_id)
    return result


@app.get("/versus/leaderboard", response_model=LeaderboardResponse)
def versus_leaderboard():
    """
    Return aggregated standings by agent, model, and team.
    Includes both arena and versus games. Agent fields populated for versus games.
    """
    return game_manager.leaderboard.get_leaderboard()


@app.get("/versus/agents/{agent_id}")
def versus_get_agent(agent_id: str):
    """Get public profile for an agent (no token, no token_hash returned)."""
    identity = agent_registry.get_by_id(agent_id)
    if not identity:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "agent_id": identity.agent_id,
        "name": identity.name,
        "model": identity.model,
        "registered_at": identity.registered_at,
    }


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
        # Get active game details for spectators
        active_rows = conn.execute(
            "SELECT ga.game_id, ga.team_id, a.name "
            "FROM game_agents ga "
            "JOIN agents a ON ga.agent_id = a.agent_id "
            "JOIN lobby l ON ga.agent_id = l.agent_id "
            "WHERE l.status IN ('matched', 'playing') "
            "ORDER BY ga.game_id, ga.team_id"
        ).fetchall()

    # Group active game rows by game_id and enrich with live state
    games_by_id: dict[str, dict] = {}
    for row in active_rows:
        gid = row["game_id"]
        if gid not in games_by_id:
            games_by_id[gid] = {"game_id": gid}
        games_by_id[gid][row["team_id"] + "_name"] = row["name"]

    active_games = []
    for gid, info in games_by_id.items():
        gs = game_manager.games.get(gid)
        if gs is None:
            continue  # game already concluded and cleaned up
        info["team1_score"] = gs.team1.score
        info["team2_score"] = gs.team2.score
        info["phase"] = gs.phase.value if hasattr(gs.phase, "value") else str(gs.phase)
        if gs.turn:
            info["half"] = gs.turn.half
            info["turn"] = gs.turn.team_turn
        else:
            info["half"] = None
            info["turn"] = None
        active_games.append(info)

    return {
        "waiting": waiting,
        "active_players": matched,
        "waiting_agents": [r["name"] for r in waiting_agents],
        "active_games": active_games,
    }


@app.get("/versus/how-to-play")
def versus_how_to_play():
    """
    Return the agent skill markdown — instructions for playing versus mode.
    No auth required. Public documentation.
    """
    from pathlib import Path
    skill_path = Path(__file__).parent.parent / "docs" / "agent-skill.md"
    if not skill_path.exists():
        raise HTTPException(status_code=404, detail="How-to-play guide not found")
    
    from fastapi.responses import PlainTextResponse
    content = skill_path.read_text(encoding="utf-8")
    return PlainTextResponse(content, media_type="text/markdown")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
