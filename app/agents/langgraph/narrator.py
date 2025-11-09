"""
Game state narrator for Scramble agents.

Converts raw game state into concise narratives by tracking changes between turns.
Adapted from ai-at-risk's GameNarrator pattern - reduces token usage by 60-80%.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple


@dataclass
class GameStateChange:
    """Represents a detected change in game state"""

    category: str  # "movement", "combat", "ball", "score", "rerolls", "phase"
    description: str  # Human-readable description
    details: Dict[str, Any]  # Additional structured data


class ScrambleNarrator:
    """
    Converts game state deltas to concise narratives.

    This class tracks previous game states and generates narrative updates
    by detecting only what changed, significantly reducing token usage.
    """

    def __init__(self):
        # Store previous states keyed by "game_id_team_id"
        self.previous_states: Dict[str, Dict] = {}

    def generate_turn_update(
        self,
        game_id: str,
        team_id: str,
        current_state: Dict,
        last_action: Optional[Dict] = None,
    ) -> str:
        """
        Generate narrative from state changes.

        Args:
            game_id: Game identifier
            team_id: Team identifier
            current_state: Current game state
            last_action: Most recent action taken

        Returns:
            Concise narrative describing changes
        """
        state_key = f"{game_id}_{team_id}"
        prev_state = self.previous_states.get(state_key)

        if not prev_state:
            # First turn - provide full context
            narrative = self._generate_game_start_update(current_state, team_id)
        else:
            # Detect and narrate changes only
            changes = self._detect_changes(prev_state, current_state, team_id)
            narrative = self._format_turn_update(changes, current_state, last_action)

        # Store for next comparison
        self.previous_states[state_key] = self._deep_copy_state(current_state)

        return narrative

    def _generate_game_start_update(self, state: Dict, team_id: str) -> str:
        """Generate initial game context"""
        phase = state.get("phase", "UNKNOWN")
        turn = state.get("turn", 0)

        # Get team info
        teams = state.get("teams", {})
        my_team = teams.get(team_id, {})
        team_name = my_team.get("name", "Unknown")

        # Get score
        score = state.get("score", {})
        my_score = score.get(team_id, 0)

        # Get opponent info
        opponent_id = [tid for tid in teams.keys() if tid != team_id]
        opponent_score = 0
        if opponent_id:
            opponent_score = score.get(opponent_id[0], 0)

        narrative = f"""
🎮 **Game Start - {team_name}**

**Phase:** {phase}
**Turn:** {turn}
**Score:** {my_score} - {opponent_score}

You are playing Ankh-Morpork Scramble. Assess the current situation and plan your move.
        """.strip()

        return narrative

    def _detect_changes(
        self, prev_state: Dict, current_state: Dict, team_id: str
    ) -> List[GameStateChange]:
        """Detect what changed between states"""
        changes = []

        # Check phase changes
        changes.extend(self._detect_phase_changes(prev_state, current_state))

        # Check player positions and movements
        changes.extend(self._detect_movement_changes(prev_state, current_state, team_id))

        # Check player status (KO, injured, standing)
        changes.extend(self._detect_status_changes(prev_state, current_state, team_id))

        # Check ball position
        changes.extend(self._detect_ball_changes(prev_state, current_state))

        # Check score
        changes.extend(self._detect_score_changes(prev_state, current_state, team_id))

        # Check rerolls
        changes.extend(self._detect_reroll_changes(prev_state, current_state, team_id))

        return changes

    def _detect_phase_changes(
        self, prev_state: Dict, current_state: Dict
    ) -> List[GameStateChange]:
        """Detect phase transitions"""
        changes = []

        prev_phase = prev_state.get("phase")
        curr_phase = current_state.get("phase")

        if prev_phase != curr_phase:
            changes.append(
                GameStateChange(
                    category="phase",
                    description=f"Phase changed: {prev_phase} → {curr_phase}",
                    details={"old_phase": prev_phase, "new_phase": curr_phase},
                )
            )

        return changes

    def _detect_movement_changes(
        self, prev_state: Dict, current_state: Dict, team_id: str
    ) -> List[GameStateChange]:
        """Detect player movements"""
        changes = []

        prev_players = self._get_team_players(prev_state, team_id)
        curr_players = self._get_team_players(current_state, team_id)

        for player_id, curr_player in curr_players.items():
            prev_player = prev_players.get(player_id)
            if not prev_player:
                continue

            prev_pos = prev_player.get("position")
            curr_pos = curr_player.get("position")

            if prev_pos and curr_pos and prev_pos != curr_pos:
                player_name = curr_player.get("name", player_id)
                changes.append(
                    GameStateChange(
                        category="movement",
                        description=f"{player_name} moved {self._format_pos(prev_pos)} → {self._format_pos(curr_pos)}",
                        details={
                            "player_id": player_id,
                            "from": prev_pos,
                            "to": curr_pos,
                        },
                    )
                )

        return changes

    def _detect_status_changes(
        self, prev_state: Dict, current_state: Dict, team_id: str
    ) -> List[GameStateChange]:
        """Detect player status changes (KO, injury, etc.)"""
        changes = []

        prev_players = self._get_team_players(prev_state, team_id)
        curr_players = self._get_team_players(current_state, team_id)

        # Also check opponent players for combat results
        prev_opp_players = self._get_opponent_players(prev_state, team_id)
        curr_opp_players = self._get_opponent_players(current_state, team_id)

        # Check own team
        for player_id, curr_player in curr_players.items():
            prev_player = prev_players.get(player_id)
            if not prev_player:
                continue

            prev_status = prev_player.get("status", "ACTIVE")
            curr_status = curr_player.get("status", "ACTIVE")

            if prev_status != curr_status:
                player_name = curr_player.get("name", player_id)
                changes.append(
                    GameStateChange(
                        category="combat",
                        description=f"💥 {player_name} is now {curr_status}",
                        details={
                            "player_id": player_id,
                            "old_status": prev_status,
                            "new_status": curr_status,
                        },
                    )
                )

        # Check opponent team
        for player_id, curr_player in curr_opp_players.items():
            prev_player = prev_opp_players.get(player_id)
            if not prev_player:
                continue

            prev_status = prev_player.get("status", "ACTIVE")
            curr_status = curr_player.get("status", "ACTIVE")

            if prev_status != curr_status:
                player_name = curr_player.get("name", player_id)
                changes.append(
                    GameStateChange(
                        category="combat",
                        description=f"⚔️ Opponent {player_name} is now {curr_status}",
                        details={
                            "player_id": player_id,
                            "old_status": prev_status,
                            "new_status": curr_status,
                        },
                    )
                )

        return changes

    def _detect_ball_changes(
        self, prev_state: Dict, current_state: Dict
    ) -> List[GameStateChange]:
        """Detect ball position/carrier changes"""
        changes = []

        prev_ball = prev_state.get("ball", {})
        curr_ball = current_state.get("ball", {})

        prev_carrier = prev_ball.get("carrier_id")
        curr_carrier = curr_ball.get("carrier_id")

        prev_pos = prev_ball.get("position")
        curr_pos = curr_ball.get("position")

        # Ball carrier changed
        if prev_carrier != curr_carrier:
            if curr_carrier:
                changes.append(
                    GameStateChange(
                        category="ball",
                        description=f"🏈 Ball picked up by player {curr_carrier}",
                        details={"carrier_id": curr_carrier},
                    )
                )
            elif prev_carrier:
                changes.append(
                    GameStateChange(
                        category="ball",
                        description="🏈 Ball dropped/fumbled",
                        details={"previous_carrier": prev_carrier},
                    )
                )

        # Ball position changed (on ground)
        elif not curr_carrier and prev_pos and curr_pos and prev_pos != curr_pos:
            changes.append(
                GameStateChange(
                    category="ball",
                    description=f"🏈 Ball scattered {self._format_pos(prev_pos)} → {self._format_pos(curr_pos)}",
                    details={"from": prev_pos, "to": curr_pos},
                )
            )

        return changes

    def _detect_score_changes(
        self, prev_state: Dict, current_state: Dict, team_id: str
    ) -> List[GameStateChange]:
        """Detect score changes"""
        changes = []

        prev_score = prev_state.get("score", {})
        curr_score = current_state.get("score", {})

        prev_my_score = prev_score.get(team_id, 0)
        curr_my_score = curr_score.get(team_id, 0)

        if curr_my_score > prev_my_score:
            changes.append(
                GameStateChange(
                    category="score",
                    description=f"🎯 TOUCHDOWN! Score: {curr_my_score}",
                    details={"old_score": prev_my_score, "new_score": curr_my_score},
                )
            )

        # Check opponent score
        opponent_id = [tid for tid in curr_score.keys() if tid != team_id]
        if opponent_id:
            opp_id = opponent_id[0]
            prev_opp_score = prev_score.get(opp_id, 0)
            curr_opp_score = curr_score.get(opp_id, 0)

            if curr_opp_score > prev_opp_score:
                changes.append(
                    GameStateChange(
                        category="score",
                        description=f"⚠️ Opponent scored! Their score: {curr_opp_score}",
                        details={
                            "old_score": prev_opp_score,
                            "new_score": curr_opp_score,
                        },
                    )
                )

        return changes

    def _detect_reroll_changes(
        self, prev_state: Dict, current_state: Dict, team_id: str
    ) -> List[GameStateChange]:
        """Detect team reroll usage"""
        changes = []

        prev_teams = prev_state.get("teams", {})
        curr_teams = current_state.get("teams", {})

        prev_team = prev_teams.get(team_id, {})
        curr_team = curr_teams.get(team_id, {})

        prev_rerolls = prev_team.get("rerolls", 0)
        curr_rerolls = curr_team.get("rerolls", 0)

        if curr_rerolls < prev_rerolls:
            changes.append(
                GameStateChange(
                    category="rerolls",
                    description=f"🎲 Team reroll used ({curr_rerolls} remaining)",
                    details={"remaining": curr_rerolls},
                )
            )

        return changes

    def _format_turn_update(
        self,
        changes: List[GameStateChange],
        current_state: Dict,
        last_action: Optional[Dict],
    ) -> str:
        """Format changes as concise narrative"""

        if not changes:
            return "No significant changes this turn. Assess the board and make your next move."

        # Group by category
        by_category: Dict[str, List[str]] = {}
        for change in changes:
            category = change.category
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(change.description)

        # Build narrative sections
        sections = []

        if "phase" in by_category:
            sections.append("📋 " + "\n".join(by_category["phase"]))

        if "score" in by_category:
            sections.append("\n".join(by_category["score"]))

        if "ball" in by_category:
            sections.append("\n".join(by_category["ball"]))

        if "movement" in by_category:
            # Limit movement details to avoid spam
            movements = by_category["movement"]
            if len(movements) > 5:
                sections.append(f"🏃 {len(movements)} players moved")
            else:
                sections.append("🏃 " + "\n   ".join(movements))

        if "combat" in by_category:
            sections.append("⚔️ " + "\n   ".join(by_category["combat"]))

        if "rerolls" in by_category:
            sections.append("\n".join(by_category["rerolls"]))

        narrative = "\n\n".join(sections)

        # Add current turn context
        turn = current_state.get("turn", "?")
        phase = current_state.get("phase", "?")
        narrative = f"**Turn {turn} - {phase}**\n\n{narrative}"

        return narrative

    def _get_team_players(self, state: Dict, team_id: str) -> Dict[str, Dict]:
        """Extract this team's players from state"""
        teams = state.get("teams", {})
        team = teams.get(team_id, {})
        players = team.get("players", {})
        return players

    def _get_opponent_players(self, state: Dict, team_id: str) -> Dict[str, Dict]:
        """Extract opponent team's players from state"""
        teams = state.get("teams", {})
        opponent_id = [tid for tid in teams.keys() if tid != team_id]
        if not opponent_id:
            return {}

        opponent_team = teams.get(opponent_id[0], {})
        return opponent_team.get("players", {})

    def _format_pos(self, pos: Any) -> str:
        """Format position coordinates"""
        if isinstance(pos, dict):
            x = pos.get("x", "?")
            y = pos.get("y", "?")
            return f"({x},{y})"
        elif isinstance(pos, (list, tuple)) and len(pos) >= 2:
            return f"({pos[0]},{pos[1]})"
        return str(pos)

    def _deep_copy_state(self, state: Dict) -> Dict:
        """Create a deep copy of state for comparison"""
        import copy

        return copy.deepcopy(state)
