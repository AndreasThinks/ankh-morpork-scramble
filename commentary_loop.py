import requests, time, json

GAME_URL = "http://localhost:8000"
GAME_ID = "the-match"
SENDER_ID = "referee"
SENDER_NAME = "Referee Quirke"

last_event_count = 0
last_turn = None
commentary_interval = 30

def post_commentary(game_id, content):
    try:
        requests.post(
            f"{GAME_URL}/game/{game_id}/message",
            params={
                "sender_id": SENDER_ID,
                "sender_name": SENDER_NAME,
                "content": content
            },
            timeout=5
        )
        print(f"[{time.strftime('%H:%M')}] Posted: {content[:60]}...")
    except Exception as e:
        print(f"Commentary post failed: {e}")

def generate_comment(state, new_events):
    phase = state["phase"]
    score = state["score"]
    turn = state.get("turn", {})
    half = turn.get("half", "?")
    team_turn = turn.get("team_turn", "?")
    active_id = turn.get("active_team_id", "?")
    events_str = "\n".join(new_events)
    
    team1 = state.get("team1", {})
    team2 = state.get("team2", {})
    
    team1_name = team1.get("name", "Team One")
    team2_name = team2.get("name", "Team Two")
    
    # Find active team name
    if active_id == team1.get("id"):
        active_name = team1_name
    else:
        active_name = team2_name
    
    comment_parts = []
    
    # Turn commentary
    comment_parts.append(f"Half {half}, turn {team_turn}. {active_name} have the ball.")
    
    # Event commentary
    for event in new_events:
        event_lower = event.lower()
        
        if "score" in event_lower or "goal" in event_lower:
            if team1_name in event or team1.get("name") in event:
                comment_parts.append(f"{team1_name} score! The guild's finest haven't seen that coming.")
            elif team2_name in event or team2.get("name") in event:
                comment_parts.append(f"{team2_name} get the points. The Watch are taking notes.")
        elif "turnover" in event_lower:
            comment_parts.append(f"Turnover! Someone made a choice the dice didn't approve of.")
        elif "injured" in event_lower or "knocked" in event_lower or "ko" in event_lower:
            comment_parts.append(f"Someone's down. In Ankh-Morpork sports, this is basically entertainment.")
        elif "dodge" in event_lower or "tackle" in event_lower:
            comment_parts.append(f"That {event_lower} went better for one team than the other.")
        else:
            # Generic commentary for other events
            comment_parts.append(f"Action report: {event.strip()}.")
    
    # Join with semicolons for Discworld flow
    return " ".join(comment_parts)

def generate_final_comment(state):
    team1 = state.get("team1", {})
    team2 = state.get("team2", {})
    team1_name = team1.get("name", "Team One")
    team2_name = team2.get("name", "Team Two")
    score = state["score"]
    team1_score = score.get("team1", 0)
    team2_score = score.get("team2", 0)
    events = state.get("events", [])
    
    ending_parts = []
    ending_parts.append(f"Final score: {team1_name} {team1_score} - {team2_score} {team2_name}.")
    
    if team1_score > team2_score:
        winner = team1_name
        ending_parts.append(f"{winner} take the match. They played it, didn't just wave at it.")
    elif team2_score > team1_score:
        winner = team2_name
        ending_parts.append(f"{winner} win the day. The dice weren't as unkind this time.")
    else:
        ending_parts.append("A draw. Neither side proved superior. The Guild accepts this outcome reluctantly.")
    
    # Mention key events
    significant_events = [e for e in events if any(kw in e.lower() for kw in ["score", "turnover", "injured", "ko", "goal"])]
    if significant_events:
        ending_parts.append(f"The script: {', '.join(significant_events[-3:])}.")
    
    ending_parts.append("Referee Quirke signs off. The guild files this under 'another one'.")
    
    return " ".join(ending_parts)

def check_phase_change(state):
    # Detect phase transitions
    turn = state.get("turn", {})
    half = turn.get("half")
    team_turn = turn.get("team_turn")
    current_turn = (half, team_turn)
    
    # Phase-specific commentary
    if half == 2 and team_turn == 1:
        return "Half time break is over. Both sides have had coffee. Some of it was decaf."
    elif half == 1 and team_turn == 1:
        return "Kick-off. The ball rolls. History begins."
    elif half == 2 and team_turn == 10:
        return "Late game. Everyone's tired. Everyone's still dangerous."
    
    # Turn boundary detection
    if last_turn is not None and current_turn != last_turn:
        return f"New half/turn cycle. The score stands. The tension does not."
    
    return None

print(f"[*] Starting commentary for game {GAME_ID}")
print(f"[*] Server: {GAME_URL}")

last_event_count = 0
last_turn = None

while True:
    try:
        # Fetch game state
        resp = requests.get(f"{GAME_URL}/game/{GAME_ID}", timeout=5)
        state = resp.json()
        
        phase = state["phase"]
        print(f"[*] Phase: {phase}")
        
        # CONCLUDED - final commentary
        if phase == "CONCLUDED":
            print("[!] Game concluded!")
            final = generate_final_comment(state)
            post_commentary(GAME_ID, final)
            print("[*] Final commentary posted. Exiting.")
            break
        
        # SETUP - wait
        if phase == "SETUP":
            print("[*] In SETUP. Waiting for play to begin...")
            time.sleep(5)
            continue
        
        # Check for new events
        events = state.get("events", [])
        new_events = events[last_event_count:]
        last_event_count = len(events)
        
        turn = state.get("turn", {})
        current_turn = (turn.get("half"), turn.get("team_turn"))
        
        # Phase change commentary
        phase_comment = check_phase_change(state)
        if phase_comment:
            post_commentary(GAME_ID, phase_comment)
            last_turn = current_turn
        
        # New events commentary
        if new_events:
            comment = generate_comment(state, new_events)
            if comment:
                post_commentary(GAME_ID, comment)
            last_turn = current_turn
        
        time.sleep(commentary_interval)
        
    except requests.exceptions.RequestException as e:
        print(f"[!] Server error: {e}")
        time.sleep(10)
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
        time.sleep(10)
