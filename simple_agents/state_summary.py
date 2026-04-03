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


def summarize_for_commentator(state: dict, new_events: list) -> str:
    team1, team2 = state["team1"], state["team2"]
    turn = state.get("turn") or {}
    lines = [
        f"Match: {team1['name']} {team1['score']} - {team2['score']} {team2['name']}",
        f"Half {turn.get('half', 1)}, Turn {turn.get('team_turn', 0)}",
        "",
        "EVENTS THIS ROUND:",
    ]
    for e in new_events:
        desc = e.get("description", e.get("event_type", str(e))) if isinstance(e, dict) else str(e)
        lines.append(f"  - {desc}")
    return "\n".join(lines)
