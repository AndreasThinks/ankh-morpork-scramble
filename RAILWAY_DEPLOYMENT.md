# Railway Deployment Guide

This guide explains how to deploy Ankh-Morpork Scramble to Railway using Railpack.

## About This Deployment

This project uses **Railpack** for Railway deployment, which automatically:
- Detects the Python project via `pyproject.toml` and `uv.lock`
- Uses **UV** (ultra-fast Python package manager) for dependency installation
- Configures Python 3.12.7 (from `.python-version`)
- Sets up optimal Python runtime environment variables
- Installs all dependencies from `pyproject.toml`

## Prerequisites

- A [Railway](https://railway.app) account
- This repository pushed to GitHub

## Quick Start

1. **Create a new Railway project**
   - Go to [Railway](https://railway.app)
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Select this repository
   - Railway will automatically detect and use Railpack

2. **Configure Environment Variables**

   In Railway's dashboard, add the following environment variables:

   ### Required Variables
   ```
   ADMIN_API_KEY=<generate-a-secure-random-key>
   OPENROUTER_API_KEY=<your-openrouter-api-key>
   ```

   ### Optional Variables (with defaults)
   ```
   DEFAULT_GAME_ID=demo-game
   INTERACTIVE_GAME_ID=interactive-game
   DEMO_MODE=true
   CORS_ORIGINS=*
   APP_LOG_LEVEL=INFO
   MCP_LOG_LEVEL=INFO
   LOG_DIR=logs
   ```

3. **Deploy**
   - Railpack will automatically detect your Python project
   - UV will install dependencies from `pyproject.toml` and `uv.lock`
   - The deployment will start automatically using the `Procfile`
   - Wait for the build and deployment to complete

4. **Access Your Application**
   - Railway will provide a public URL (e.g., `https://your-app.railway.app`)
   - Visit the URL to see your application
   - Health check endpoint: `https://your-app.railway.app/health`
   - Web dashboard: `https://your-app.railway.app/ui`

## Admin Log Access

View logs remotely using the admin API:

### List all available logs
```bash
curl -H "X-Admin-Key: your-admin-api-key" \
  https://your-app.railway.app/admin/logs
```

### View a specific log file
```bash
# Full log
curl -H "X-Admin-Key: your-admin-api-key" \
  https://your-app.railway.app/admin/logs/api.log

# Last 100 lines
curl -H "X-Admin-Key: your-admin-api-key" \
  https://your-app.railway.app/admin/logs/api.log?tail=100

# First 50 lines
curl -H "X-Admin-Key: your-admin-api-key" \
  https://your-app.railway.app/admin/logs/mcp.log?head=50
```

### Available log files
- `api.log` - FastAPI server logs
- `mcp.log` - MCP server logs
- `team1.log` - Team 1 agent logs
- `team2.log` - Team 2 agent logs
- `referee.log` - Referee commentary logs
- `server.log` - Uvicorn server logs

## Configuration Details

### Railpack Build Process
Railpack automatically handles the build using:
1. **Python Version**: 3.12.7 (from `.python-version`)
2. **Package Manager**: UV (detected from `uv.lock`)
3. **Dependencies**: Installed from `pyproject.toml`
4. **Start Command**: From `Procfile` - `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`

### Environment Variables Set by Railpack
Railpack automatically configures these for optimal Python performance:
```
PYTHONFAULTHANDLER=1
PYTHONUNBUFFERED=1
PYTHONHASHSEED=random
PYTHONDONTWRITEBYTECODE=1
PIP_DISABLE_PIP_VERSION_CHECK=1
PIP_DEFAULT_TIMEOUT=100
```

### Port Configuration
Railway automatically sets the `PORT` environment variable. The application will use this port automatically.

### Health Checks
You can monitor the `/health` endpoint to ensure the application is running correctly. The health check returns:
```json
{
  "status": "healthy",
  "active_games": 1
}
```

### CORS Configuration
By default, CORS is set to allow all origins (`*`). For production, you should restrict this:

```
CORS_ORIGINS=https://your-frontend.com,https://another-allowed-origin.com
```

### Logging
Logs are stored in the `logs/` directory and are also sent to stdout for Railway's log aggregation.

## Troubleshooting

### Application won't start
1. Check Railway logs for errors
2. Verify all required environment variables are set
3. Ensure `OPENROUTER_API_KEY` is valid

### Can't access admin logs
1. Verify `ADMIN_API_KEY` is set in Railway environment variables
2. Check that you're passing the correct key in the `X-Admin-Key` header
3. Ensure the log directory exists and has proper permissions

### Health check failing
1. Check that the application is binding to the correct `PORT`
2. Verify the `/health` endpoint is responding
3. Check Railway logs for startup errors

## Why UV?

This project uses **UV** as the package manager for several benefits:
- **10-100x faster** than pip for dependency resolution and installation
- **Reproducible builds** with `uv.lock` ensuring identical dependencies
- **Lower memory usage** during installation
- **Better caching** for faster subsequent deployments
- **Native to Railpack** - automatically detected and optimized

## Production Recommendations

1. **Security**
   - Generate a strong random key for `ADMIN_API_KEY`
   - Restrict CORS origins to only trusted domains
   - Keep `OPENROUTER_API_KEY` secure

2. **Monitoring**
   - Regularly check the `/health` endpoint
   - Monitor log files for errors using the admin API
   - Set up Railway alerts for downtime

3. **Performance**
   - Consider upgrading Railway plan for more resources
   - Monitor memory and CPU usage in Railway dashboard
   - Adjust log rotation settings if logs grow too large

## Additional Resources

- [Railway Documentation](https://docs.railway.app)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Application Documentation](./README.md)
