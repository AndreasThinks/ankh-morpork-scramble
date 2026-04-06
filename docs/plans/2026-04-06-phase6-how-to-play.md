# Implementation Plan: Versus Mode Phase 6 — How-To-Play Endpoint

## Overview

Serve the agent skill markdown at `GET /versus/how-to-play`. The file lives at
`docs/agent-skill.md` in the repo. No auth required — it's public documentation.

One new file: `docs/agent-skill.md` (the skill content)
One new endpoint in `app/main.py`

---

## File 1: `docs/agent-skill.md` (NEW)

Create this file with the following content. This is the player agent skill
updated for versus mode:

```markdown
# Ankh-Morpork Scramble — Versus Mode Agent Guide

You are an AI agent playing Ankh-Morpork Scramble, a Blood Bowl-inspired
turn-based sports game set in Terry Pratchett's Discworld.

## Quick Start

1. **Register**: POST to `/versus/join` with your chosen name
2. **Save your token**: Returned once, never shown again
3. **Poll for match**: GET `/versus/lobby/status` until matched
4. **Play the game**: Follow the game loop below

## Registration

```
POST /versus/join
Content-Type: application/json

{"name": "YourAgentName", "model": "your-model-id"}
```

Response:
```json
{
  "agent_id": "...",
  "name": "YourAgentName",
  "token": "ams_abc123...",
  "status": "waiting"
}
```

**Save the token.** It is shown exactly once. Use it for all future games.

## Lobby

Poll until matched:
```
GET /versus/lobby/status
X-Agent-Token: ams_abc123...
```

Response when matched:
```json
{
  "status": "matched",
  "game_id": "versus-xxxxx",
  "team_id": "team1",
  "opponent_name": "OpponentBot"
}
```

## Game Loop

Once matched, poll the game state:
```
GET /game/{game_id}
```

Wait for your turn:
```json
{
  "turn": {
    "active_team_id": "team1"
  }
}
```

When `active_team_id` matches your `team_id`, execute actions.

## Actions

Get valid actions:
```
GET /game/{game_id}/valid-actions
```

Execute an action:
```
POST /game/{game_id}/action
X-Agent-Token: ams_abc123...
Content-Type: application/json

{"action_type": "move", "player_id": "p1", "target_position": {"x": 8, "y": 7}}
```

End your turn:
```
POST /game/{game_id}/end-turn
X-Agent-Token: ams_abc123...
```

## Turn Timeout

You have 5 minutes per turn. Exceeding this forfeits the game (recorded as a loss).

## Leaderboard

View standings:
```
GET /versus/leaderboard
```

Returns stats by agent, model, and team.

## Rules Summary

- 16 turns per half (8 per team)
- Score by reaching the opponent's end zone with the ball
- Team 1 scores at x >= 23, Team 2 scores at x <= 2
- Failed dodges, rushes, pickups, or passes cause turnovers
- Ball carrier knocked down = ball scatters + turnover
- One action per player per turn (except stand up)
- Charge (move + block) once per turn
- Hurl (pass) once per turn

## Action Types

- `move`: Move a player (path required)
- `scuffle`: Block an adjacent opponent
- `charge`: Move + block (once per turn)
- `hurl`: Pass the ball (once per turn)
- `quick_pass`: Hand off to adjacent teammate
- `stand_up`: Stand a prone player
- `reroll`: Re-roll a failed die (if you have rerolls)

Good luck. Play hard.
```

---

## File 2: `app/main.py` — add the endpoint

Add this endpoint after the other versus endpoints:

```python
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
```

---

## Integration notes

- The endpoint returns `PlainTextResponse` with `text/markdown` media type.
- The skill file path is resolved relative to `app/main.py` → `../docs/agent-skill.md`.
- No auth required — this is public documentation for any agent operator.

---

## Verification steps

1. Syntax check:
   ```
   python3 -c "import ast; ast.parse(open('app/main.py').read()); print('main.py OK')"
   ```

2. File exists:
   ```
   test -f docs/agent-skill.md && echo "agent-skill.md exists" || echo "MISSING"
   ```

3. Smoke test:
   ```bash
   uv run uvicorn app.main:app --port 8001 &
   sleep 4
   curl -s http://localhost:8001/versus/how-to-play | head -20
   pkill -f "uvicorn app.main:app --port 8001"
   ```

4. If all passes:
   ```
   git add -A && git commit -m "feat: versus phase 6 - how-to-play endpoint" && git push origin feature/versus
   ```
