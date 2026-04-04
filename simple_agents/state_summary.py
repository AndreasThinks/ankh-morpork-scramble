"""Convert raw game state JSON into compact readable summaries for LLM prompts."""


def summarize_for_player(state: dict, my_team_id: str) -> tuple[str, int]:
    team1 = state["team1"]
    team2 = state["team2"]
    my_team = team1 if team1["id"] == my_team_id else team2
    opp_team = team2 if team1["id"] == my_team_id else team1

    turn = state.get("turn") or {}
    half = turn.get("half", 1)
    team_turn = turn.get("team_turn", 0)

    pitch = state.get("pitch") or {}
    ball_pos = pitch.get("ball_position")
    ball_carrier_id = pitch.get("ball_carrier")
    player_positions = pitch.get("player_positions") or {}
    players = state.get("players") or {}

    my_end_zone = 25 if my_team_id == "team1" else 0
    opp_end_zone = 0 if my_team_id == "team1" else 25

    lines = [
        "=== GAME STATE ===",
        f"Half {half}, Turn {team_turn}  |  Score: {team1['name']} {team1['score']} - {team2['score']} {team2['name']}",
    ]

    # Ball
    if ball_carrier_id:
        carrier = players.get(ball_carrier_id) or {}
        pos = player_positions.get(ball_carrier_id) or {}
        who = "YOUR" if carrier.get("team_id") == my_team_id else "OPPONENT'S"
        lines.append(f"Ball: carried by {who} {carrier.get('position','?')} [{ball_carrier_id}] at ({pos.get('x','?')},{pos.get('y','?')})")
    elif ball_pos:
        lines.append(f"Ball: loose at ({ball_pos.get('x','?')},{ball_pos.get('y','?')})")
    else:
        lines.append("Ball: not yet in play")

    lines.append(f"End zones: YOURS x={my_end_zone}  |  OPPONENT x={opp_end_zone}")
    lines.append("")

    # My squad
    my_players_unacted = 0
    lines.append("YOUR SQUAD:")
    for pid in my_team.get("player_ids") or []:
        p = players.get(pid) or {}
        pos = player_positions.get(pid) or {}
        x, y = pos.get("x", "?"), pos.get("y", "?")

        state_val = p.get("state", "standing")
        has_acted = p.get("has_acted", False)
        movement_used = p.get("movement_used", 0)

        # Compute MA values
        position_data = p.get("position") or {}
        ma_total = p.get("ma") or position_data.get("ma") or "?"
        if isinstance(ma_total, int):
            ma_remaining = max(0, ma_total - movement_used)
            ma_str = f"MA{ma_remaining}/{ma_total}"
        else:
            ma_str = f"MA{ma_total}"

        flags = []
        if state_val in ("knocked_out", "casualty"):
            flags.append("OFF PITCH")
        elif state_val == "stunned":
            flags.append("STUNNED")
        elif state_val == "prone":
            flags.append("PRONE")
        if has_acted:
            flags.append("ACTED")
        else:
            # Only count players who are physically able to act this turn
            if state_val in ("standing", "prone"):
                my_players_unacted += 1
        if pid == ball_carrier_id:
            flags.append("BALL")

        skills = p.get("skills") or []
        skill_str = f" [{','.join(skills[:3])}]" if skills else ""
        flag_str = f" | {', '.join(flags)}" if flags else ""
        lines.append(
            f"  [{pid}] {str(position_data.get('role','?')):<22} ({x:>2},{y:>2})"
            f"  {ma_str} ST{p.get('st') or position_data.get('st','?')} AG{p.get('ag') or position_data.get('ag','?')}"
            f"{skill_str}{flag_str}"
        )

    lines.append("")
    lines.append("OPPONENT SQUAD:")
    for pid in opp_team.get("player_ids") or []:
        p = players.get(pid) or {}
        pos = player_positions.get(pid) or {}
        x, y = pos.get("x", "?"), pos.get("y", "?")
        state_val = p.get("state", "standing")
        flags = []
        if state_val in ("knocked_out", "casualty"):
            flags.append("OFF PITCH")
        elif state_val == "stunned":
            flags.append("STUNNED")
        elif state_val == "prone":
            flags.append("PRONE")
        if pid == ball_carrier_id:
            flags.append("BALL")
        flag_str = f" | {', '.join(flags)}" if flags else ""
        position_data = p.get("position") or {}
        lines.append(
            f"  [{pid}] {str(position_data.get('role','?')):<22} ({x:>2},{y:>2})"
            f"  ST{p.get('st') or position_data.get('st','?')}{flag_str}"
        )

    # Recent events
    events = state.get("events") or []
    if events:
        lines.append("")
        lines.append("RECENT EVENTS (last 8):")
        for e in events[-8:]:
            desc = e.get("description", e.get("event_type", str(e))) if isinstance(e, dict) else str(e)
            lines.append(f"  - {desc}")

    return "\n".join(lines), my_players_unacted


def summarize_for_commentator(
    state: dict, new_events: list, had_turnover: bool = False
) -> str:
    """Build a structured prompt for C.M.O.T. Dibbler.

    Prioritises the single most significant event so the commentator
    leads with something concrete rather than atmosphere.
    """
    team1, team2 = state["team1"], state["team2"]
    turn = state.get("turn") or {}
    pitch = state.get("pitch") or {}
    players = state.get("players") or {}

    # Score and situation
    score_line = (
        f"{team1['name']} {team1['score']} — {team2['score']} {team2['name']}"
    )
    situation = f"Half {turn.get('half', 1)}, Turn {turn.get('team_turn', 0)}"

    # Ball context
    carrier_id = pitch.get("ball_carrier")
    if carrier_id:
        carrier = players.get(carrier_id) or {}
        carrier_team = team1 if carrier.get("team_id") == team1["id"] else team2
        role = (carrier.get("position") or {}).get("role", "player")
        ball_context = f"Ball carried by {carrier_team['name']} {role}"
    elif pitch.get("ball_position"):
        bp = pitch["ball_position"]
        ball_context = f"Ball loose at ({bp['x']}, {bp['y']})"
    else:
        ball_context = "Ball off pitch"

    # Find the headline event (highest tier wins)
    _PRIORITY = {
        "touchdown": 0, "turnover": 1, "casualty": 2, "injury": 3,
        "knockdown": 4, "block": 5, "foul": 6,
        "pass": 7, "catch": 7, "pickup": 7, "drop": 8,
    }
    headline = None
    best_priority = 999
    for e in new_events:
        if not isinstance(e, dict):
            continue
        p = _PRIORITY.get(e.get("event_type", ""), 50)
        if p < best_priority:
            best_priority = p
            headline = e

    lines = [
        f"SCORE: {score_line}",
        f"SITUATION: {situation}",
        f"BALL: {ball_context}",
        "",
    ]

    if had_turnover:
        lines.append("NOTE: THIS TURN ENDED IN A TURNOVER — the active team lost possession.")
        lines.append("")

    if headline:
        etype = headline.get("event_type", "event").upper()
        result = headline.get("result", "")
        desc = headline.get("description") or etype
        lines.append(f"HEADLINE EVENT ({etype}{', ' + result if result else ''}):")
        lines.append(f"  {desc}")
        # Other events as secondary context
        others = [e for e in new_events if isinstance(e, dict) and e is not headline]
        if others:
            lines.append("")
            lines.append("OTHER EVENTS THIS TURN:")
            for e in others[:6]:
                d = e.get("description") or e.get("event_type", "")
                lines.append(f"  - {d}")
    else:
        lines.append("No significant events this turn.")

    return "\n".join(lines)
