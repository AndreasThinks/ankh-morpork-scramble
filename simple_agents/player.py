"""Player agent: setup and turn execution via direct LLM calls."""
import json
import logging
import re

import requests

from .llm import call_llm, DEFAULT_MODEL, LLMPermanentError
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
            The LAST element of path must be one of the "Safe destinations" listed
            in VALID ACTIONS. Each step must be adjacent (1 square) to the previous.
  Block:    {"action_type":"scuffle","player_id":"...","target_player_id":"..."}
  Charge:   {"action_type":"charge","player_id":"...","target_player_id":"...","path":[{"x":N,"y":N},...],"target_position":{"x":N,"y":N}}
            path is the movement route to reach target_position (same rules as Move — last step must be target_position).
            target_position must be exactly 1 square away (adjacent) to target_player_id's position.
            Only charge targets listed under CHARGEABLE TARGETS in VALID ACTIONS are reachable.
   Pass:     {"action_type":"hurl","player_id":"...","target_position":{"x":N,"y":N}}
   Handoff:  {"action_type":"quick_pass","player_id":"...","target_receiver_id":"..."}
   Standup:  {"action_type":"stand_up","player_id":"..."}
  End turn: null

Return ONLY the JSON object. No markdown, no explanation outside the "thought" field.
"""

DEFAULT_SYSTEM_PROMPTS = {
    "team1": (
        "You are coaching the City Watch Constables in Ankh-Morpork Scramble, a Blood Bowl-inspired "
        "sports game set in Terry Pratchett's Discworld. You are Commander Sam Vimes, watching from "
        "the sideline while Captain Carrot actually plays. You are a cynical, streetwise copper who "
        "has learned the hard way that the direct route is usually the one with the trap. Coach like "
        "a Watchman on a double shift: read the play, call the safe move first, protect your ball "
        "carrier like he's the last witness, and when something goes wrong mutter about it being a "
        "\"bloody organised\" sort of mess. You respect Carrot but you don't trust the dice. Voice: "
        "dry, tired, tactically sharp, occasional grumbled asides about boots, bosses, or bastards. "
        "Be clear and concrete about what the action accomplishes — no speeches, just orders."
        + _BASE_RULES
    ),
    "team2": (
        "You are coaching the Unseen University Adepts in Ankh-Morpork Scramble, a Blood Bowl-inspired "
        "sports game set in Terry Pratchett's Discworld. You are Ponder Stibbons, Head of Inadvisably "
        "Applied Magic, coaching from the bench while the Archchancellor handles the physical side of things. "
        "You have run the numbers through Hex; the numbers say this will probably not work, but probably "
        "is a range. Coach like an overworked academic: identify the highest-probability play, hedge "
        "against turnovers, explain your reasoning as if presenting to the faculty, and sigh internally "
        "when Ridcully ignores the plan. Voice: polite, slightly fretful, fond of phrases like "
        "\"statistically speaking\", \"all things being equal\", and \"oh, dear\". "
        "Be clear and concrete about what the action accomplishes — state the move, then the reasoning."
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

# ── skill translation ───────────────────────────────────────────────────────
# Maps Discworld-flavoured skill keys → Blood Bowl mechanic names so the LLM
# understands what each skill actually does during roster selection.
_SKILL_MECHANICS: dict[str, str] = {
    # City Watch
    "drill_hardened":       "Block",
    "pigeon_post":          "Pass",
    "chain_of_custody":     "Sure Hands",
    "quick_grab":           "Catch",
    "sidestep_shuffle":     "Dodge",
    # Wizard base
    "blink":                "Dodge",
    "small_and_sneaky":     "Stunty",
    "portable":             "Right Stuff",
    "pointy_hat_padding":   "Thick Skull",
    "reroll_the_thesis":    "Brawler",
    "grappling_cantrip":    "Grab",
    # Gargoyle
    "bound_spirit":         "Loner (3+)",
    "stone_thick":          "Mighty Blow (+1)",
    "pigeon_proof":         "Projectile Vomit",
    "mindless_masonry":     "Really Stupid",
    "weathered":            "Regeneration",
    "lob_the_lackey":       "Throw Team-Mate",
    "occasional_bite_mark": "Always Hungry",
    # Troll
    "thick_as_a_brick":     "Thick Skull",
    "rock_solid":           "Stand Firm",
    "really_thick":         "Bone Head",
    "cooling_helmet":       "Bone Head (2+)",
    "crossbow_training":    "Mighty Blow (+1)",
    "break_heads":          "Break Tackle",
    # Street Veteran
    "street_fighting":      "Dirty Player (+1)",
    "slippery":             "Dodge",
    # Watchdog
    "lupine_speed":         "Sure Feet",
    "keen_senses":          "Catch",
    "regenerative":         "Regeneration",
    # Captain Carrot
    "true_king":            "Leader",
    "kingly_presence":      "Guard",
    "honest_fighter":       "Block",
    "will_not_back_down":   "Dauntless",
    "diplomatic_immunity":  "Fend",
    "trusted_by_all":       "Inspiring Presence",
    # UU — combat
    "combat_evocation":     "Block",
    "arcane_strike":        "Mighty Blow (+1)",
    "battle_hardened":      "Thick Skull",
    "aggressive_casting":   "Juggernaut",
    # UU — speed
    "haste_spell":          "Sprint",
    "blink_dodge":          "Dodge",
    "fleet_footed":         "Sure Feet",
    # UU — tech / ball-handling
    "hex_assisted":         "Sure Hands",
    "calculated_trajectory": "Pass",
    "safe_pair_of_hands":   "Safe Pass",
    "dump_off_spell":       "Dump-Off",
    # The Librarian
    "prehensile_everything": "Extra Arms",
    "library_swinging":     "Leap",
    "protective_instinct":  "Guard",
    "bibliophile_rage":     "Frenzy",
    "terrifying_glare":     "Disturbing Presence",
    # Ridcully
    "archchancellor":       "Leader",
    "robust_physique":      "Block",
    "booming_voice":        "Guard",
    "arcane_mastery":       "Pass",
    "headology_expert":     "Hypnotic Gaze",
    "stubborn":             "Stand Firm",
    # Transformed Wizard
    "simian_agility":       "Leap",
    "four_limbs":           "Extra Arms",
    "independent":          "Loner (4+)",
}

_SKILL_GUIDE = (
    "Skill guide — "
    "Block: block without falling; "
    "Sure Hands: reroll failed pickups; "
    "Dodge: reroll failed dodges; "
    "Catch: reroll failed catches; "
    "Pass: reroll failed throws; "
    "Safe Pass: ball never scatters on fumble; "
    "Sprint: +1 rush square (3 total); "
    "Sure Feet: reroll failed rush; "
    "Guard: assists even when outnumbered; "
    "Mighty Blow (+1): +1 on armour/injury rolls; "
    "Leader: grants one free team reroll per half; "
    "Frenzy: must follow up and block again; "
    "Leap: jump over adjacent players; "
    "Extra Arms: reroll failed catches and pickups; "
    "Loner: only benefits from team rerolls on a 4+; "
    "Stunty: smaller target but easier to injure; "
    "Really Stupid/Bone Head: may refuse to act."
)


def _format_position_for_llm(p: dict) -> str:
    """Format one position entry for the roster selection prompt."""
    stats = p.get("stats", {})
    skills_raw = stats.get("skills", [])
    skills_str = (
        ", ".join(_SKILL_MECHANICS.get(s, s) for s in skills_raw)
        if skills_raw else "—"
    )
    star = " ★" if p.get("quantity_limit", 99) == 1 else ""
    return (
        f"  {p['position_key']} ({p.get('role', p['position_key'])}){star}  "
        f"{p.get('cost', 0):,}g  max {p.get('quantity_limit', '?')}  "
        f"MA{stats.get('ma','?')} ST{stats.get('st','?')} "
        f"AG{stats.get('ag','?')} PA{stats.get('pa','?')} AV{stats.get('av','?')}  "
        f"[{skills_str}]"
    )


# ── setup ──────────────────────────────────────────────────────────────────

# Mapping of generic Blood Bowl terms to team-specific position keys.
# LLMs often hallucinate standard BB position names instead of using the
# Discworld-flavoured keys, so we remap the most common ones.
_GENERIC_KEY_MAP = {
    "team1": {
        "lineman": "constable", "linemen": "constable",
        "thrower": "clerk_runner", "passer": "clerk_runner",
        "runner": "fleet_recruit", "catcher": "fleet_recruit",
        "blitzer": "watch_sergeant", "blocker": "watch_sergeant",
        "sergeant": "watch_sergeant",
        "big_guy": "troll_constable", "troll": "troll_constable",
        "captain": "captain_carrot",
    },
    "team2": {
        "lineman": "apprentice_wizard", "linemen": "apprentice_wizard",
        "thrower": "divination_wizard", "passer": "divination_wizard",
        "runner": "haste_mage", "catcher": "haste_mage",
        "blitzer": "senior_wizard", "blocker": "senior_wizard",
        "big_guy": "animated_gargoyle", "wizard": "apprentice_wizard",
    },
}


def setup_team(game_id: str, team_id: str, team_name: str,
               model: str = None, base_url: str = "http://localhost:8000") -> None:
    """Buy roster, auto-place, mark ready."""
    model = model or DEFAULT_MODELS.get(team_id, DEFAULT_MODEL)
    logger.info(f"[{team_name}] Setup starting...")

    budget_data = requests.get(f"{base_url}/game/{game_id}/team/{team_id}/budget").json()
    positions_data = requests.get(f"{base_url}/game/{game_id}/team/{team_id}/available-positions").json()

    budget = budget_data.get("budget_remaining", 1_000_000)
    available = positions_data.get("positions") or []

    valid_keys = [p["position_key"] for p in available]
    valid_keys_str = ", ".join(valid_keys)

    roster_prompt = (
        f"You are building a roster for {team_name} in Ankh-Morpork Scramble (Blood Bowl rules).\n"
        f"Budget: {budget:,}g.  Rerolls cost {positions_data.get('reroll_cost', 60000):,}g each (max {positions_data.get('rerolls_max', 8)}).\n\n"
        f"Available positions (key | name | cost | max | MA ST AG PA AV | [skills]):\n"
        + "\n".join(_format_position_for_llm(p) for p in available)
        + f"\n\n{_SKILL_GUIDE}\n\n"
        + "Build a balanced squad of 7-11 players plus 1-3 rerolls within budget.\n"
        + "Aim for: a core of cheap linemen, 1-2 fast runners (high MA) for ball carrying, "
        + "1 dedicated passer/ball-handler (good PA or Sure Hands), and 1-2 strong blockers (high ST).\n"
        + "★ = star player (unique, max 1, expensive — only buy if budget allows after filling the core).\n\n"
        + f"IMPORTANT: You MUST use ONLY these exact position keys in the 'players' array: {valid_keys_str}\n"
        + "Do NOT use generic Blood Bowl names like 'lineman' or 'thrower' — they will be rejected.\n\n"
        + 'Return ONLY a JSON object: {"players": ["key","key",...], "rerolls": N}'
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
            roster = {
                "players": (
                    ["apprentice_wizard"] * 4
                    + ["haste_mage"] * 2
                    + ["divination_wizard"] * 2
                    + ["senior_wizard"] * 1
                ),
                "rerolls": 2,
            }

    # Remap generic Blood Bowl terms to valid team-specific keys
    key_map = _GENERIC_KEY_MAP.get(team_id, {})
    valid_key_set = set(valid_keys)
    remapped_players = []
    for pk in roster.get("players", []):
        pk_lower = pk.lower().strip()
        if pk_lower in valid_key_set:
            remapped_players.append(pk_lower)
        elif pk_lower in key_map:
            mapped = key_map[pk_lower]
            logger.info(f"[{team_name}] Remapped generic key '{pk}' → '{mapped}'")
            remapped_players.append(mapped)
        else:
            logger.warning(f"[{team_name}] Unknown position key '{pk}', skipping.")
    roster["players"] = remapped_players

    # Buy players
    bought_count = 0
    for position_key in roster.get("players", []):
        r = requests.post(f"{base_url}/game/{game_id}/team/{team_id}/buy-player",
                          params={"position_key": position_key})
        if r.status_code == 200:
            bought_count += 1
            logger.info(f"[{team_name}] Bought {position_key}")
        else:
            logger.warning(f"[{team_name}] Failed to buy {position_key}: {r.text[:80]}")

    # If no players were successfully purchased, use the fallback roster
    if bought_count == 0:
        logger.warning(f"[{team_name}] Zero players purchased — falling back to default roster.")
        if team_id == "team1":
            fallback = ["constable"]*5 + ["fleet_recruit"]*2 + ["watch_sergeant"]
        else:
            fallback = ["apprentice_wizard"]*4 + ["haste_mage"]*2 + ["divination_wizard"]*2 + ["senior_wizard"]
        for position_key in fallback:
            r = requests.post(f"{base_url}/game/{game_id}/team/{team_id}/buy-player",
                              params={"position_key": position_key})
            if r.status_code == 200:
                logger.info(f"[{team_name}] Fallback bought {position_key}")

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
    "team1": "Commander Vimes",
    "team2": "Ponder Stibbons",
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


# Sentinel returned by _parse_step when the LLM output is not valid JSON,
# distinct from action=None which means "intentionally end turn".
_PARSE_FAILED = object()


def _parse_step(text: str) -> tuple[str, dict | None | object]:
    """Parse a single-action LLM response into (thought, action).

    Returns:
      (thought, action_dict) — a valid action to execute.
      (thought, None)        — model intentionally ended its turn.
      ("", _PARSE_FAILED)    — response could not be parsed as JSON.
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
            logger.warning("JSON decode failed on extracted object: %s", match.group()[:200])
    else:
        logger.warning("No JSON object found in LLM response: %s", text[:200])
    return "", _PARSE_FAILED


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
         reachable_map = valid_actions.get("reachable_squares") or {}
         for pid in movable:
             p = players.get(pid) or {}
             pos = player_positions.get(pid) or {}
             position_data = p.get("position") or {}
             role = position_data.get("role", pid)
             ma_total = position_data.get("ma", "?")
             movement_used = p.get("movement_used", 0)
             ma_remaining = max(0, ma_total - movement_used) if isinstance(ma_total, int) else "?"
             x, y = pos.get("x", "?"), pos.get("y", "?")

             squares = reachable_map.get(pid) or []
             safe = [(s["x"], s["y"]) for s in squares if not s.get("rush")]
             rush_sq = [(s["x"], s["y"]) for s in squares if s.get("rush")]

             if safe:
                 sample = safe[:12]
                 safe_str = ", ".join(f"({sx},{sy})" for sx, sy in sample)
                 more = f" (+{len(safe)-12} more)" if len(safe) > 12 else ""
                 lines.append(
                     f"  - [{pid}] {role} at ({x},{y}) — {ma_remaining} free squares. "
                     f"Safe destinations: {safe_str}{more}"
                 )
             else:
                 lines.append(
                     f"  - [{pid}] {role} at ({x},{y}) — {ma_remaining} squares free "
                     f"(no safe destinations)"
                 )
             if rush_sq:
                 rush_str = ", ".join(f"({rx},{ry})" for rx, ry in rush_sq[:6])
                 lines.append(f"    Rush (dice, risky — do last): {rush_str}")
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

     # Charge: enumerate reachable targets so the LLM doesn't guess
     lines.append("")
     if valid_actions.get("can_charge"):
         lines.append("CHARGE (move + block in one action) — not yet used this turn.")
         lines.append("  To charge: move your player to a square adjacent to the target, then block.")
         lines.append("  target_position must be exactly 1 square away from target_player_id.")
         lines.append("  CHARGEABLE TARGETS (only these are reachable this action):")

         # Build opponent position lookup
         opp_positions = {}
         for pid, pdata in players.items():
             if pdata.get("team_id") != team_id:
                 ppos = player_positions.get(pid) or {}
                 if ppos:
                     opp_positions[pid] = ppos

         has_any_charge = False
         for pid in movable:
             p = players.get(pid) or {}
             pos = player_positions.get(pid) or {}
             if p.get("has_acted"):
                 continue
             position_data = p.get("position") or {}
             role = position_data.get("role", pid)
             x, y = pos.get("x", "?"), pos.get("y", "?")

             reachable = reachable_map.get(pid) or []
             reachable_set = {(s["x"], s["y"]) for s in reachable}

             charge_opts = []
             for opp_pid, opp_pos in opp_positions.items():
                 ox, oy = opp_pos.get("x"), opp_pos.get("y")
                 if ox is None or oy is None:
                     continue
                 opp_pdata = players.get(opp_pid) or {}
                 opp_role = (opp_pdata.get("position") or {}).get("role", opp_pid)
                 adj = [(ox + dx, oy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                        if (dx, dy) != (0, 0) and (ox + dx, oy + dy) in reachable_set]
                 if adj:
                     pos_str = ", ".join(f"({ax},{ay})" for ax, ay in adj[:3])
                     charge_opts.append(f"[{opp_pid}] {opp_role} at ({ox},{oy}) — move to {pos_str}")

             if charge_opts:
                 has_any_charge = True
                 lines.append(f"  - [{pid}] {role} at ({x},{y}):")
                 for opt in charge_opts:
                     lines.append(f"      {opt}")
             else:
                 lines.append(f"  - [{pid}] {role} at ({x},{y}): no opponents within charge range")

         if not has_any_charge:
             lines.append("  (No player can reach any opponent this turn for a charge.)")
     else:
         lines.append("CHARGE — already used this turn (only once allowed).")

     # Other one-per-turn special actions
     specials = []
     if valid_actions.get("can_hurl"):
         specials.append("HURL (pass the ball) — not yet used this turn")
     else:
         specials.append("HURL — already used this turn")
     if valid_actions.get("can_quick_pass"):
         specials.append("QUICK PASS (hand-off to adjacent teammate) — not yet used this turn")
     else:
         specials.append("QUICK PASS — already used this turn")

     lines.append("")
     lines.append("Other one-per-turn special actions:")
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
         bx, by = ball_pos.get('x', '?'), ball_pos.get('y', '?')
         # Check if the ball square is blocked by a prone player
         blocking_pid = None
         blocking_team = None
         for pid, pdata in players.items():
             ppos = player_positions.get(pid) or {}
             if ppos.get('x') == ball_pos.get('x') and ppos.get('y') == ball_pos.get('y'):
                 if pdata.get('state') == 'prone':
                     blocking_pid = pid
                     blocking_team = pdata.get('team_id')
                     break
         if blocking_pid:
             owner = "YOUR" if blocking_team == team_id else "OPPONENT'S"
             action_hint = (
                 "Stand them up first (stand_up action, costs 3 MA)."
                 if blocking_team == team_id else
                 "Block/scuffle them off that square first, then move onto the ball."
             )
             lines.append(
                 f"Ball: loose on ground at ({bx},{by}) — WARNING: {owner} player [{blocking_pid}] "
                 f"is PRONE on that square. You CANNOT move there yet. {action_hint}"
             )
         else:
             lines.append(f"Ball: loose on ground at ({bx},{by}) — move a player there to pick it up")
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
             if state_val in ("knocked_out", "casualty", "sent_off"):
                 lines.append("    -> This player is off the pitch and cannot act.")
             if state_val == "stunned":
                 lines.append("    -> This player is stunned and cannot act.")

         # If it was a charge or scuffle, note adjacency constraint
         if action_type in ("charge", "scuffle"):
             target_id = last_action.get("target_player_id")
             if target_id:
                 tpos = player_positions.get(target_id) or {}
                 tx, ty = tpos.get("x"), tpos.get("y")
                 if tx is not None:
                     lines.append(f"  -> For charge/scuffle, your player must be in a square")
                     lines.append(f"     directly adjacent (1 square) to [{target_id}] at ({tx},{ty}).")
                     lines.append(f"     For charge: check CHARGEABLE TARGETS above — only listed targets are reachable.")
             if action_type == "charge":
                 lines.append(f"  -> target_position must be a square adjacent to target_player_id, not the target's own square.")

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
              base_url: str = "http://localhost:8000") -> dict:
    """Execute one full turn: one LLM call per action, with retry on failure.

    Returns a stats dict: {"actions_taken": int, "llm_failed": bool}. Callers
    can use ``llm_failed`` to detect turns where the model never produced a
    usable response (e.g. 404s, rate-limit exhaustion) and swap models.
    """
    model = model or DEFAULT_MODELS.get(team_id, DEFAULT_MODEL)

    my_end_zone = 25 if team_id == "team1" else 0
    opp_end_zone = 0 if team_id == "team1" else 25

    sys_prompt = (system_prompt or DEFAULT_SYSTEM_PROMPTS.get(team_id, DEFAULT_SYSTEM_PROMPTS["team1"]))
    sys_prompt = sys_prompt.replace("{my_end_zone}", str(my_end_zone)).replace("{opp_end_zone}", str(opp_end_zone))

    actions_taken = 0
    total_iterations = 0
    parse_failures = 0
    consecutive_failures = 0
    last_failed_sig: str | None = None
    consecutive_same_failures = 0
    last_failure: str | None = None
    last_action: dict | None = None
    llm_ever_succeeded = False
    permanent_failure = False
    failure_reason: str | None = None

    MAX_TOTAL_ITERATIONS = 30   # absolute cap including failures
    MAX_PARSE_FAILURES = 3      # consecutive parse failures before giving up
    MAX_CONSECUTIVE_FAILURES = 5  # any consecutive failures → force end turn
    MAX_SAME_ACTION_FAILURES = 3  # same action failing repeatedly → force end turn

    while actions_taken < MAX_ACTIONS_PER_TURN and total_iterations < MAX_TOTAL_ITERATIONS:
        total_iterations += 1

        # Refresh state before each action
        try:
            state = requests.get(f"{base_url}/game/{game_id}", timeout=5).json()
        except Exception:
            break

        # Check if turn is still ours
        turn = state.get("turn") or {}
        if turn.get("active_team_id") != team_id:
            logger.info(f"[{team_name}] Turn passed (turnover or phase change).")
            return {"actions_taken": actions_taken, "llm_failed": False}

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
            llm_ever_succeeded = True
        except LLMPermanentError as e:
            logger.error(f"[{team_name}] LLM permanent error ({model}): {e}")
            permanent_failure = True
            failure_reason = "out_of_credits" if e.out_of_credits else "unavailable"
            break
        except Exception as e:
            logger.error(f"[{team_name}] LLM error: {e}")
            break

        # Handle JSON parse failures — retry with feedback instead of ending turn
        if action is _PARSE_FAILED:
            parse_failures += 1
            logger.warning(f"[{team_name}] Parse failure {parse_failures}/{MAX_PARSE_FAILURES}")
            if parse_failures >= MAX_PARSE_FAILURES:
                logger.warning(f"[{team_name}] {MAX_PARSE_FAILURES} consecutive parse failures — ending turn.")
                break
            last_failure = (
                "Your response was not valid JSON. You MUST return a JSON object like: "
                '{\"thought\": \"...\", \"action\": {...}} or {\"thought\": \"...\", \"action\": null} to end turn.'
            )
            last_action = None
            continue

        # Reset parse failure counter on successful parse
        parse_failures = 0

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
                    return {"actions_taken": actions_taken, "llm_failed": False}

                if result.get("details", {}).get("turn_ended"):
                    logger.info(f"[{team_name}] Touchdown — server ended turn.")
                    return {"actions_taken": actions_taken, "llm_failed": False}

                if ok:
                    last_failure = None
                    last_action = None
                    actions_taken += 1
                    consecutive_failures = 0
                    last_failed_sig = None
                    consecutive_same_failures = 0
                    break
                else:
                    last_failure = msg
                    last_action = action
                    consecutive_failures += 1

                    # Track repeated identical failures
                    sig = f"{action.get('action_type')}|{action.get('player_id')}|{action.get('target_player_id')}"
                    if sig == last_failed_sig:
                        consecutive_same_failures += 1
                    else:
                        last_failed_sig = sig
                        consecutive_same_failures = 1

                    if attempt < MAX_RETRIES_PER_ACTION - 1:
                        # Ask LLM for a different action on next loop iteration
                        break
            except Exception as e:
                last_failure = str(e)
                last_action = action
                consecutive_failures += 1
                logger.warning(f"[{team_name}] Action error: {e}")
                break

        # Check repetition guards
        if consecutive_same_failures >= MAX_SAME_ACTION_FAILURES:
            logger.warning(f"[{team_name}] Same action failed {consecutive_same_failures} times — forcing end turn.")
            break
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.warning(f"[{team_name}] {consecutive_failures} consecutive failures — forcing end turn.")
            break

    # End turn explicitly
    r = requests.post(f"{base_url}/game/{game_id}/end-turn", params={"team_id": team_id}, timeout=5)
    logger.info(f"[{team_name}] Turn ended (status {r.status_code}).")
    return {
        "actions_taken": actions_taken,
        "llm_failed": not llm_ever_succeeded,
        "permanent_failure": permanent_failure,
        "failure_reason": failure_reason,
    }


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
