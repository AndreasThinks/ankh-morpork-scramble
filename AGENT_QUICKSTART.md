# Agent Quickstart Guide

## Testing LangGraph Agents

The easiest way to test two AI agents playing against each other!

### Prerequisites

1. **API Key**: You need an OpenRouter API key
2. **Configuration**: Set it in your `.env` file:
   ```bash
   OPENROUTER_API_KEY=sk-or-v1-your-key-here
   OPENROUTER_MODEL=moonshotai/kimi-k2-thinking
   ```

### Quick Start

Just run the script:

```bash
./run_agents.sh
```

That's it! The script will:
- ✅ Load your `.env` configuration
- ✅ Start the game server (if not running)
- ✅ Create a new game
- ✅ Launch both AI agents
- ✅ Show you where to watch the match

### Custom Game ID

Want to run multiple games? Use a custom game ID:

```bash
./run_agents.sh my_awesome_match
```

### Watch the Game

Open your browser to:
```
http://localhost:8000/ui
```

You'll see:
- 📊 Live game board
- 💰 Roster building decisions
- ⚔️ Combat and movement actions
- 📝 Agent strategic messages
- 🏆 Real-time score updates

### What Happens?

**Phase 1: DEPLOYMENT (Roster Building)**
- Each team gets 1,000,000 gold
- Agents buy players (need minimum 3)
- Agents can buy rerolls (expensive but powerful)
- Agents place players on their half of the pitch
- Both teams mark ready when complete

**Phase 2: OPENING_SCRAMBLE (Kickoff)**
- Ball is placed
- Game transitions to active play

**Phase 3: ACTIVE_PLAY (The Match)**
- Agents take turns
- Move players, block opponents, advance the ball
- First to score wins!

### Stopping the Game

Press `CTRL+C` to gracefully stop the agents.

The game server will keep running (you can restart agents anytime).

### Troubleshooting

**"OPENROUTER_API_KEY not set"**
- Check your `.env` file has the API key
- Make sure there are no spaces around the `=`

**"Server failed to start"**
- Check `/tmp/game_server_demo_game.log` for errors
- Make sure port 8000 is not in use

**"Game already exists"**
- Use a different game ID: `./run_agents.sh game2`
- Or delete the existing game via API

**Agents seem stuck**
- Check the model is responding (OpenRouter might be slow/down)
- Watch the agent output for errors
- Check the web UI to see current game state

### Logs

Game logs are saved to:
```
logs/games/<game_id>/
  ├── game_log.md      # Human-readable markdown
  └── events.json      # Machine-readable JSON
```

### Advanced Usage

**Different Model:**
```bash
# Edit .env
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# Run
./run_agents.sh
```

**Manual Control:**
```bash
# Start server only
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Create game manually
curl -X POST "http://localhost:8000/game?game_id=test"

# Launch agents manually
export OPENROUTER_API_KEY=your_key
uv run python -m app.agents.langgraph.launch --game-id test
```

### Next Steps

- Read `LANGGRAPH_AGENTS.md` for implementation details
- Check `rules.md` for game mechanics
- Explore the web UI at `/docs` for API documentation
- Try tournament mode: `python -m app.agents.langgraph.launch --tournament --num-games 5`

## Success Indicators

✅ **MCP Integration Test Passed**
- All 16 tools loaded successfully
- Transport: `streamable_http` (with underscore)
- Model configuration from `.env` working

✅ **Fixes Applied**
- Transport type corrected (was hyphen, now underscore)
- Model reads from `OPENROUTER_MODEL` environment variable
- Launch script handles all setup automatically

✅ **Ready to Play**
- Game server running
- Agents can connect to MCP
- Interactive roster building enabled

Enjoy watching the AI agents battle it out! 🏈⚔️
