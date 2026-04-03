"""Player agent: setup and turn execution via direct LLM calls."""
import json
import logging
import re

import requests

from .llm import call_llm, DEFAULT_MODEL
from .state_summary import summarize_for_player

logger = logging.getLogger(__name__)

# ── system prompts ─────────────────────────────────────────────────────────

_BASE_RULES = """
GAME RULES:
- Score by carrying the ball to x={my_end_zone} (your end zone). Opponent scores at x={opp_end_zone}.
- Move each player up to their MA squares per turn. You can only move each player ONCE per turn.
- Leaving a square adjacent to a standing opponent requires a dodge roll. Failure = TURNOVER (turn ends immediately).
- Rush moves (extra squares beyond MA, max 2) also need dice rolls. Failure = TURNOVER.
- Do safe moves FIRST, risky ones LAST. A turnover wastes whatever you had left.
- Block: 'scuffle' if already adjacent. 'charge' to move AND block in one action (once per turn).
- Knocking down the ball carrier causes a turnover for THEM — top priority target.
- Move a player onto the ball square to pick it up (automatic if you have Sure Hands, rolled otherwise).

Each turn you will be called once per action. Return ONE action at a time as a JSON object with this exact shape:
  {"thought": "brief in-character reasoning (1-2 sentences)", "action": <action object or null to end turn>}

Action formats for the "action" field:
  Move:     {"action_type":"move","player_id":"...","path":[{"x":N,"y":N},...]}
  Block:    {"action_type":"scuffle","player_id":"...","target_player_id":"..."}
  Charge:   {"action_type":"charge","player_id":"...","target_player_id":"...","target_position":{"x":N,"y":N}}
  Pass:     {"action_type":"hurl","player_id":"...","target_position":{"x":N,"y":N}}
  Handoff:  {"action_type":"quick_pass","player_id":"...","target_player_id":"..."}
  Standup:  {"action_type":"stand_up","player_id":"..."}
  End turn: null

Return ONLY the JSON object. No markdown, no explanation outside the "thought" field.
"""

DEFAULT_SYSTEM_PROMPTS = {
    "team1": (
        "You are coaching the City Watch Constables in Ankh-Morpork Scramble, a Blood Bowl-inspired "
        "sports game set in Terry Pratchett's Discworld. You are Captain Carrot: pragmatic, principled, "
        "and quietly terrifying. You play clean but you play hard."
        + _BASE_RULES
    ),
    "team2": (
        "You are coaching the Unseen University Adepts in Ankh-Morpork Scramble, a Blood Bowl-inspired "
        "sports game set in Terry Pratchett's Discworld. You are Archchancellor Ridcully: loud, decisive, "
        "and convinced that the best magical solution is also the most direct one."
        + _BASE_RULES
    ),
}

DEFAULT_MODELS = {
    "team1": DEFAULT_MODEL,
    "team2": DEFAULT_MODEL,
}

# ── formation helpers ──────────────────────────────────────────────────────

def _build_formation(player_ids: list, team_id: str) -> dict:
    """Sensible spread formation for each side of the pitch."""
    if team_id == "team1":
        slots = [(5,7),(6,6),(6,8),(7,7),(4,6),(4,8),(5,5),(5,9),(7,5),(7,9),(8,7)]
    else:
        slots = [(20,7),(19,6),(19,8),(18,7),(21,6),(21,8),(20,5),(20,9),(18,5),(18,9),(17,7)]
    return {
        pid: {"x": slots[i][0], "y": slots[i][1]}
        for i, pid in enumerate(player_ids)
        if i < len(slots)
    }

# ── setup ──────────────────────────────────────────────────────────────────

def setup_team(game_id: str, team_id: str, team_name: str,
               model: str = None, base_url: str = "http://localhost:8000") -> None:
    """Buy roster, auto-place, mark ready."""
    model = model or DEFAULT_MODELS.get(team_id, DEFAULT_MODEL)
    logger.info(f"[{team_name}] Setup starting...")

    budget_data = requests.get(f"{base_url}/game/{game_id}/team/{team_id}/budget").json()
    positions_data = requests.get(f"{base_url}/game/{game_id}/team/{team_id}/available-positions").json()

    budget = budget_data.get("budget_remaining", 1_000_000)
    available = positions_data.get("positions") or []

    roster_prompt = (
        f"You are building a roster for {team_name} in Ankh-Morpork Scramble.\n"
        f"Budget: {budget} gold.\n"
        f"Available positions (key: cost, limit):\n"
        + "\n".join(f"  {p['position_key']}: {p.get('cost',0)}g, max {p.get('quantity_limit','?')}" for p in available)
        + "\n\nChoose 7-11 players and 1-3 rerolls that fit within budget. Aim for a balanced mix."
        + '\n\nReturn ONLY a JSON object: {"players": ["key","key",...], "rerolls": N}'
    )

    try:
        resp = call_llm("You are a Blood Bowl coach. Return only valid JSON.", roster_prompt, model)
        match = re.search(r'\{.*\}', resp, re.DOTALL)
        roster = json.loads(match.group()) if match else {}
    except Exception as e:
        logger.warning(f"[{team_name}] Roster LLM failed ({e}), using fallback.")
        roster = {}

    if not roster.get("players"):
        if team_id == "team1":
            roster = {"players": ["constable"]*5 + ["fleet_recruit"]*2 + ["watch_sergeant"], "rerolls": 2}
        else:
            roster = {"players": ["apprentice_wizard"]*6 + ["haste_mage"]*2, "rerolls": 2}

    # Buy players
    for position_key in roster.get("players", []):
        r = requests.post(f"{base_url}/game/{game_id}/team/{team_id}/buy-player",
                          params={"position_key": position_key})
        if r.status_code == 200:
            logger.info(f"[{team_name}] Bought {position_key}")
        else:
            logger.warning(f"[{team_name}] Failed to buy {position_key}: {r.text[:80]}")

    # Buy rerolls
    for _ in range(roster.get("rerolls", 0)):
        r = requests.post(f"{base_url}/game/{game_id}/team/{team_id}/buy-reroll")
        if r.status_code == 200:
            logger.info(f"[{team_name}] Bought reroll")

    # Refresh to get player IDs, then place
    state = requests.get(f"{base_url}/game/{game_id}").json()
    team_data = state["team1"] if team_id == "team1" else state["team2"]
    player_ids = team_data.get("player_ids") or []

    positions = _build_formation(player_ids, team_id)
    r = requests.post(f"{base_url}/game/{game_id}/place-players",
                      json={"team_id": team_id, "positions": positions})
    if r.status_code == 200:
        logger.info(f"[{team_name}] Players placed.")
    else:
        logger.error(f"[{team_name}] Placement failed: {r.text[:200]}")

    # Mark ready
    requests.post(f"{base_url}/game/{game_id}/join", params={"team_id": team_id})
    logger.info(f"[{team_name}] Ready.")

# ── turn execution ─────────────────────────────────────────────────────────

COACH_NAMES = {
    "team1": "Captain Carrot",
    "team2": "Archchancellor Ridcully",
}

MAX_ACTIONS_PER_TURN = 20   # hard cap to prevent infinite loops
MAX_RETRIES_PER_ACTION = 3  # retries on rejection before giving up


def _post_message(base_url: str, game_id: str, team_id: str, team_name: str, content: str) -> None:
    """Post a coach message to the game chat."""
    coach_name = COACH_NAMES.get(team_id, team_name)
    try:
        requests.post(
            f"{base_url}/game/{game_id}/message",
            params={"sender_id": team_id, "sender_name": coach_name, "content": content},
            timeout=5,
        )
    except Exception:
        pass  # non-critical


def _parse_step(text: str) -> tuple[str, dict | None]:
    """Parse a single-action LLM response into (thought, action).

    Returns (thought, None) to signal end-of-turn.
    """
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group())
            thought = obj.get("thought", "")
            action = obj.get("action")  # None means end turn
            return thought, action
        except json.JSONDecodeError:
            pass
    return "", None


def play_turn(game_id: str, team_id: str, team_name: str, state: dict,
              model: str = None, system_prompt: str = None,
              base_url: str = "http://localhost:8000") -> None:
    """Execute one full turn: one LLM call per action, with retry on failure."""
    model = model or DEFAULT_MODELS.get(team_id, DEFAULT_MODEL)

    my_end_zone = 25 if team_id == "team1" else 0
    opp_end_zone = 0 if team_id == "team1" else 25

    sys_prompt = (system_prompt or DEFAULT_SYSTEM_PROMPTS.get(team_id, DEFAULT_SYSTEM_PROMPTS["team1"]))
    sys_prompt = sys_prompt.replace("{my_end_zone}", str(my_end_zone)).replace("{opp_end_zone}", str(opp_end_zone))

    actions_taken = 0
    last_failure: str | None = None

    while actions_taken < MAX_ACTIONS_PER_TURN:
        # Refresh state before each action
        try:
            state = requests.get(f"{base_url}/game/{game_id}", timeout=5).json()
        except Exception:
            break

        # Check if turn is still ours
        turn = state.get("turn") or {}
        if turn.get("active_team_id") != team_id:
            logger.info(f"[{team_name}] Turn passed (turnover or phase change).")
            return

        summary = summarize_for_player(state, team_id)
        valid_r = requests.get(f"{base_url}/game/{game_id}/valid-actions", timeout=5)
        valid_actions = valid_r.json() if valid_r.status_code == 200 else {}

        failure_note = f"\nPREVIOUS ACTION FAILED: {last_failure}\nChoose a different valid action.\n" if last_failure else ""
        user_msg = (
            f"{summary}\n\n"
            f"VALID ACTIONS:\n{json.dumps(valid_actions, indent=2)}\n"
            f"{failure_note}\n"
            "What is your next single action? Return one JSON object with 'thought' and 'action'."
        )

        try:
            response = call_llm(sys_prompt, user_msg, model)
            thought, action = _parse_step(response)
        except Exception as e:
            logger.error(f"[{team_name}] LLM error: {e}")
            break

        # Post thought as coach message if present
        if thought:
            logger.info(f"[{team_name}] 💬 {thought}")
            _post_message(base_url, game_id, team_id, team_name, thought)

        # End turn if action is null
        if action is None:
            logger.info(f"[{team_name}] Coach called end of turn.")
            break

        # Execute the action, retry up to MAX_RETRIES_PER_ACTION on failure
        for attempt in range(MAX_RETRIES_PER_ACTION):
            try:
                r = requests.post(f"{base_url}/game/{game_id}/action", json=action, timeout=10)
                result = r.json() if r.content else {}
                ok = result.get("success", False)
                msg = result.get("message", "")[:120]
                logger.info(f"[{team_name}] {action.get('action_type')} → {'OK' if ok else 'FAIL'} {msg}")

                if result.get("turnover"):
                    logger.info(f"[{team_name}] Turnover — server ended turn.")
                    return

                if ok:
                    last_failure = None
                    actions_taken += 1
                    break
                else:
                    last_failure = msg
                    if attempt < MAX_RETRIES_PER_ACTION - 1:
                        # Ask LLM for a different action on next loop iteration
                        break
            except Exception as e:
                last_failure = str(e)
                logger.warning(f"[{team_name}] Action error: {e}")
                break

    # End turn explicitly
    r = requests.post(f"{base_url}/game/{game_id}/end-turn", params={"team_id": team_id}, timeout=5)
    logger.info(f"[{team_name}] Turn ended (status {r.status_code}).")


def _parse_actions(text: str) -> list:
    """Extract a JSON action array from LLM output, tolerating markdown fences."""
    text = re.sub(r'```(?:json)?\s*', '', text).strip().rstrip('`').strip()
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    try:
        result = json.loads(text)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []
