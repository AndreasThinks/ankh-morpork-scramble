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
   Handoff:  {"action_type":"quick_pass","player_id":"...","target_receiver_id":"..."}
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


def _describe_valid_actions(valid_actions: dict, state: dict, team_id: str) -> str:
     """Convert the /valid-actions JSON into human-readable sentences the LLM can reason about."""
     players = state.get("players") or {}
     pitch = state.get("pitch") or {}
     player_positions = pitch.get("player_positions") or {}

     lines = ["WHAT YOU CAN DO THIS ACTION:"]

     # Per-player move opportunities
     movable = valid_actions.get("movable_players") or []
     if movable:
         lines.append("")
         lines.append("Players who can still MOVE (have MA remaining, not yet acted):")
         for pid in movable:
             p = players.get(pid) or {}
             pos = player_positions.get(pid) or {}
             position_data = p.get("position") or {}
             role = position_data.get("role", pid)
             ma_total = position_data.get("ma", "?")
             movement_used = p.get("movement_used", 0)
             if isinstance(ma_total, int):
                 ma_remaining = max(0, ma_total - movement_used)
                 ma_note = f"{ma_remaining} squares remaining (used {movement_used}/{ma_total})"
             else:
                 ma_note = f"MA{ma_total}"
             x, y = pos.get("x", "?"), pos.get("y", "?")
             lines.append(f"  - [{pid}] {role} at ({x},{y}): {ma_note}")
     else:
         lines.append("  No players can move (all have acted or exhausted MA).")

     # Block/scuffle opportunities
     blockable = valid_actions.get("blockable_targets") or {}
     if blockable:
         lines.append("")
         lines.append("Players who can BLOCK (scuffle) — already adjacent to an opponent:")
         for attacker_pid, target_pids in blockable.items():
             p = players.get(attacker_pid) or {}
             pos = player_positions.get(attacker_pid) or {}
             position_data = p.get("position") or {}
             role = position_data.get("role", attacker_pid)
             x, y = pos.get("x", "?"), pos.get("y", "?")
             target_descs = []
             for tpid in target_pids:
                 tp = players.get(tpid) or {}
                 tpos = player_positions.get(tpid) or {}
                 trole = (tp.get("position") or {}).get("role", tpid)
                 tx, ty = tpos.get("x", "?"), tpos.get("y", "?")
                 target_descs.append(f"[{tpid}] {trole} at ({tx},{ty})")
             lines.append(f"  - [{attacker_pid}] {role} at ({x},{y}) can scuffle: {'; '.join(target_descs)}")

     # One-per-turn special actions
     specials = []
     if valid_actions.get("can_charge"):
         specials.append("CHARGE (move + block in one action) — not yet used this turn")
     else:
         specials.append("CHARGE — already used this turn (only once allowed)")
     if valid_actions.get("can_hurl"):
         specials.append("HURL (pass the ball) — not yet used this turn")
     else:
         specials.append("HURL — already used this turn")
     if valid_actions.get("can_quick_pass"):
         specials.append("QUICK PASS (hand-off to adjacent teammate) — not yet used this turn")
     else:
         specials.append("QUICK PASS — already used this turn")

     lines.append("")
     lines.append("One-per-turn special actions:")
     for s in specials:
         lines.append(f"  - {s}")

     # Ball state
     ball_carrier = valid_actions.get("ball_carrier")
     ball_on_ground = valid_actions.get("ball_on_ground", False)
     ball_pos = valid_actions.get("ball_position")
     lines.append("")
     if ball_carrier:
         bc = players.get(ball_carrier) or {}
         bc_team = bc.get("team_id", "?")
         bc_role = (bc.get("position") or {}).get("role", ball_carrier)
         ownership = "YOUR player" if bc_team == team_id else "OPPONENT'S player"
         bpos = player_positions.get(ball_carrier) or {}
         bx, by = bpos.get("x", "?"), bpos.get("y", "?")
         lines.append(f"Ball: carried by {ownership} [{ball_carrier}] {bc_role} at ({bx},{by})")
     elif ball_on_ground and ball_pos:
         lines.append(f"Ball: loose on ground at ({ball_pos.get('x','?')},{ball_pos.get('y','?')}) — move a player there to pick it up")
     else:
         lines.append("Ball: not yet in play")

     lines.append("")
     lines.append("You may also return action=null to end your turn voluntarily.")

     return "\n".join(lines)


def _build_failure_note(last_failure: str, last_action: dict | None, state: dict, team_id: str) -> str:
     """Build a rich, contextual failure message for the LLM retry prompt."""
     if not last_failure:
         return ""

     lines = ["PREVIOUS ACTION FAILED — choose a different valid action."]
     lines.append(f"  Error: {last_failure}")

     if last_action:
         action_type = last_action.get("action_type", "unknown")
         player_id = last_action.get("player_id")
         lines.append(f"  Failed action: {action_type}" + (f" by player [{player_id}]" if player_id else ""))

         if player_id:
             players = state.get("players") or {}
             pitch = state.get("pitch") or {}
             player_positions = pitch.get("player_positions") or {}
             p = players.get(player_id) or {}
             pos = player_positions.get(player_id) or {}
             position_data = p.get("position") or {}
             role = position_data.get("role", player_id)
             ma_total = position_data.get("ma", "?")
             movement_used = p.get("movement_used", 0)
             has_acted = p.get("has_acted", False)
             state_val = p.get("state", "standing")
             x, y = pos.get("x", "?"), pos.get("y", "?")

             if isinstance(ma_total, int):
                 ma_remaining = max(0, ma_total - movement_used)
                 ma_note = f"{ma_remaining}/{ma_total} remaining"
             else:
                 ma_note = f"MA{ma_total}"

             lines.append(f"  Player [{player_id}] {role} stats:")
             lines.append(f"    Position: ({x},{y})  State: {state_val}  MA: {ma_note}  Already acted: {has_acted}")

             if has_acted:
                 lines.append("    -> This player has already acted this turn. Pick a different player.")
             if isinstance(ma_total, int) and ma_total - movement_used <= 0:
                 lines.append("    -> This player has no MA remaining. Pick a different player or end turn.")
             if state_val in ("knocked_out", "casualty"):
                 lines.append("    -> This player is off the pitch and cannot act.")
             if state_val == "stunned":
                 lines.append("    -> This player is stunned and cannot act.")

         # If it was a move, note path length constraint
         if action_type == "move":
             path = last_action.get("path") or []
             lines.append(f"  Path you tried had {len(path)} steps.")
             if player_id:
                 players = state.get("players") or {}
                 p = players.get(player_id) or {}
                 position_data = p.get("position") or {}
                 ma_total = position_data.get("ma", "?")
                 movement_used = p.get("movement_used", 0)
                 if isinstance(ma_total, int):
                     ma_remaining = max(0, ma_total - movement_used)
                     lines.append(f"  Player can move at most {ma_remaining} squares (+ up to 2 rush squares with dice).")
                     lines.append(f"  Path must be exactly the squares you want to traverse — don't include starting square.")

     lines.append("")
     return "\n".join(lines)


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
    last_action: dict | None = None

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

        summary, players_unacted = summarize_for_player(state, team_id)
        valid_r = requests.get(f"{base_url}/game/{game_id}/valid-actions", timeout=5)
        valid_actions = valid_r.json() if valid_r.status_code == 200 else {}

        valid_actions_prose = _describe_valid_actions(valid_actions, state, team_id)

        if players_unacted == 0:
            turn_status = "TURN STATUS: All your players have acted — consider ending your turn (return action=null)."
        elif players_unacted == 1:
            turn_status = "TURN STATUS: 1 player has not yet acted this turn."
        else:
            turn_status = f"TURN STATUS: {players_unacted} players have not yet acted this turn."

        failure_note = _build_failure_note(last_failure, last_action, state, team_id)
        user_msg = (
            f"{summary}\n\n"
            f"{turn_status}\n\n"
            f"{valid_actions_prose}\n"
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
                    last_action = None
                    actions_taken += 1
                    break
                else:
                    last_failure = msg
                    last_action = action
                    if attempt < MAX_RETRIES_PER_ACTION - 1:
                        # Ask LLM for a different action on next loop iteration
                        break
            except Exception as e:
                last_failure = str(e)
                last_action = action
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
