# Railway Deployment Guide

This document describes how to deploy Ankh-Morpork Scramble on Railway.

## Overview

The application runs the full game simulation via `run_game.py`, which:
1. Starts the FastAPI server with game API and MCP endpoints
2. Launches two AI agent teams (City Watch Constables vs Unseen University Adepts)
3. Runs a referee agent that provides live commentary
4. Logs all activity to separate log files for monitoring

## Required Environment Variables

Set these in your Railway project's environment variables:

### Required
- `OPENROUTER_API_KEY` - Your OpenRouter API key for running AI agents
- `ADMIN_API_KEY` - Secret key for accessing admin endpoints (logs, etc.)

### Optional (with defaults)
- `PORT` - Server port (Railway sets this automatically)
- `DEMO_MODE` - Set to `false` for interactive mode (default: `true`)
- `INTERACTIVE_GAME_ID` - Game ID for interactive mode (default: `interactive-game`)
- `OPENROUTER_MODEL` - Model for team agents (default: `google/gemini-2.5-flash`)
- `REFEREE_MODEL` - Model for referee (default: `anthropic/claude-3.5-haiku`)
- `ENABLE_REFEREE` - Enable referee commentary (default: `true`)
- `REFEREE_COMMENTARY_INTERVAL` - Seconds between commentary (default: `30`)
- `LOG_LEVEL` - Logging level (default: `INFO`)
- `LOG_DIR` - Log directory (default: `logs`)

## Deployment Files

- **`.python-version`** - Specifies Python 3.11 requirement
- **`pyproject.toml`** - Python dependencies managed via uv
- **`railway.json`** - Railway build and deployment configuration
- **`Procfile`** - Process definition for Railway

## Accessing Logs

Once deployed, you can view logs from all components using the admin endpoints:

### List Available Logs
```bash
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" https://your-app.railway.app/admin/logs
```

### View Unified Logs (All Components)
```bash
# Combined view (sorted by timestamp)
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" https://your-app.railway.app/admin/logs/all

# Separated view (grouped by component)
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" https://your-app.railway.app/admin/logs/all?format=separated

# Last 100 lines from each log
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" https://your-app.railway.app/admin/logs/all?tail=100
```

### View Individual Log Files
```bash
# Server logs
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" https://your-app.railway.app/admin/logs/server.log

# Team 1 agent logs
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" https://your-app.railway.app/admin/logs/team1.log

# Team 2 agent logs
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" https://your-app.railway.app/admin/logs/team2.log

# Referee logs
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" https://your-app.railway.app/admin/logs/referee.log

# MCP server logs
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" https://your-app.railway.app/admin/logs/mcp.log

# API logs
curl -H "X-Admin-Key: YOUR_ADMIN_KEY" https://your-app.railway.app/admin/logs/api.log
```

## Log Components

The unified logging endpoint aggregates logs from:

1. **server.log** - FastAPI uvicorn server output
2. **api.log** - API-specific application logs
3. **mcp.log** - MCP server logs (agent communication)
4. **team1.log** - City Watch Constables agent activity
5. **team2.log** - Unseen University Adepts agent activity
6. **referee.log** - Referee commentary and analysis

## Health Check

Railway will monitor the `/health` endpoint to ensure the service is running:

```bash
curl https://your-app.railway.app/health
```

## Monitoring the Game

Use the web dashboard to watch the game in real-time:

```bash
https://your-app.railway.app/
```

The dashboard shows:
- Current game state
- Team positions on the pitch
- Live event log
- Team statistics

## Notes

- The application runs continuously with agents auto-restarting when tasks complete
- All logs are retained in memory and accessible via the admin endpoints
- The game server runs on the port specified by Railway's PORT environment variable
- Logs are formatted with timestamps and component tags for easy filtering
