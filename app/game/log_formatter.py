"""
Markdown log formatter for game events.

This module provides formatters to convert structured game events
into beautiful, human-readable markdown format.
"""

from typing import Optional
from datetime import datetime
from app.models.events import (
    GameEvent,
    EventType,
    EventResult,
    GameStatistics,
)
from app.models.actions import DiceRoll


class MarkdownLogFormatter:
    """
    Formats game events as markdown.

    Produces a beautiful, human-readable markdown log with emojis,
    dice results, and organized by half/turn structure.
    """

    # Emoji mappings
    RESULT_EMOJI = {
        EventResult.SUCCESS: "✅",
        EventResult.FAILURE: "❌",
        EventResult.PARTIAL: "⚠️",
        EventResult.TURNOVER: "🔄",
        EventResult.NEUTRAL: "ℹ️",
    }

    DICE_FACES = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]  # 1-6

    def __init__(self, verbose: bool = True):
        """
        Initialize formatter.

        Args:
            verbose: Include full dice roll details
        """
        self.verbose = verbose

    def format_game_log(
        self,
        events: list[GameEvent],
        game_id: str,
        team1_name: str,
        team2_name: str,
        statistics: Optional[GameStatistics] = None,
    ) -> str:
        """
        Format complete game log as markdown.

        Args:
            events: List of game events
            game_id: Game identifier
            team1_name: Name of team 1
            team2_name: Name of team 2
            statistics: Optional game statistics

        Returns:
            Markdown formatted game log
        """
        lines = []

        # Header
        lines.append("# 🏈 Ankh-Morpork Scramble - Game Log")
        lines.append("")
        lines.append(f"**Game ID:** `{game_id}`")
        lines.append(f"**Teams:** {team1_name} vs {team2_name}")

        # Find game start time
        if events:
            start_time = events[0].timestamp
            lines.append(f"**Started:** {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Group events by half and turn
        current_half = 0
        current_turn = -1
        current_team = ""

        for event in events:
            # Check for half change
            if event.half != current_half:
                current_half = event.half
                lines.append(f"## 📊 Half {current_half}")
                lines.append("")
                current_turn = -1

            # Check for turn change or use TURN_START event
            if event.event_type == EventType.TURN_START:
                current_turn = event.turn_number
                current_team = event.details.get("team_name", "")
                lines.append(f"### Turn {current_turn} - {current_team}")
                lines.append("")
            elif event.turn_number != current_turn and event.event_type not in [
                EventType.GAME_START,
                EventType.GAME_END,
                EventType.HALF_START,
                EventType.HALF_END,
            ]:
                # Implicit turn change (for backward compatibility)
                current_turn = event.turn_number
                if current_turn > 0:
                    lines.append(f"### Turn {current_turn}")
                    lines.append("")

            # Format the event
            event_text = self._format_event(event)
            if event_text:
                lines.append(event_text)
                lines.append("")

        # Add statistics if provided
        if statistics:
            lines.append("---")
            lines.append("")
            lines.append(self._format_statistics(statistics))

        return "\n".join(lines)

    def _format_event(self, event: GameEvent) -> str:
        """
        Format a single event.

        Args:
            event: Event to format

        Returns:
            Formatted event text
        """
        # Special handling for certain event types
        if event.event_type == EventType.GAME_START:
            return f"# 🏈 {event.description.replace('# 🏈 Game Start: ', '')}"

        if event.event_type == EventType.GAME_END:
            return f"## {event.description}"

        if event.event_type == EventType.HALF_START:
            return ""  # Handled separately

        if event.event_type == EventType.HALF_END:
            return f"**{event.description}**"

        if event.event_type == EventType.TURN_START:
            return ""  # Handled separately

        if event.event_type == EventType.TURN_END:
            return f"*{event.description}*"

        # Regular events
        lines = []

        # Event title with icon
        icon = self._get_event_icon(event.event_type)
        title = f"**{icon} {self._get_event_title(event.event_type)}**"

        if event.player_name:
            title += f" - {event.player_name}"
            if event.target_player_name:
                title += f" → {event.target_player_name}"

        lines.append(title)

        # Description
        lines.append(f"- {event.description}")

        # Dice rolls (if verbose)
        if self.verbose and event.dice_rolls:
            for dice_roll in event.dice_rolls:
                lines.append(f"  - {self._format_dice_roll(dice_roll)}")

        # Position changes
        if event.from_position and event.to_position:
            lines.append(f"  - Moved: {event.from_position} → {event.to_position}")
        elif event.to_position:
            lines.append(f"  - Position: {event.to_position}")

        return "\n".join(lines)

    def _format_dice_roll(self, dice_roll: DiceRoll) -> str:
        """
        Format a dice roll.

        Args:
            dice_roll: Dice roll to format

        Returns:
            Formatted dice roll text
        """
        # Show dice face emoji for d6 rolls
        if 1 <= dice_roll.result <= 6:
            dice_emoji = self.DICE_FACES[dice_roll.result - 1]
        else:
            dice_emoji = "🎲"

        parts = [f"{dice_emoji} **{dice_roll.type.upper()}**:"]

        # Roll result
        if dice_roll.target:
            result_text = f"Rolled **{dice_roll.result}** (needed {dice_roll.target}+)"
        else:
            result_text = f"Rolled **{dice_roll.result}**"

        # Modifiers
        if dice_roll.modifiers:
            mods = ", ".join([f"{k}: {v:+d}" for k, v in dice_roll.modifiers.items()])
            result_text += f" [{mods}]"

        parts.append(result_text)

        # Success/failure
        if dice_roll.target:
            if dice_roll.success:
                parts.append("✅ **SUCCESS**")
            else:
                parts.append("❌ **FAILED**")

        return " ".join(parts)

    def _get_event_icon(self, event_type: EventType) -> str:
        """Get emoji icon for event type."""
        icons = {
            EventType.MOVE: "🏃",
            EventType.DODGE: "💨",
            EventType.RUSH: "⚡",
            EventType.STAND_UP: "⬆️",
            EventType.PICKUP: "⬆️",
            EventType.DROP: "⬇️",
            EventType.PASS: "🏈",
            EventType.CATCH: "🤲",
            EventType.SCATTER: "💫",
            EventType.HANDOFF: "🤝",
            EventType.BLOCK: "💥",
            EventType.KNOCKDOWN: "💫",
            EventType.ARMOR_BREAK: "🛡️",
            EventType.INJURY: "🚑",
            EventType.CASUALTY: "☠️",
            EventType.FOUL: "👢",
            EventType.KICKOFF: "⚡",
            EventType.TOUCHDOWN: "🏆",
            EventType.TURNOVER: "🔄",
            EventType.REROLL: "🔄",
        }
        return icons.get(event_type, "📝")

    def _get_event_title(self, event_type: EventType) -> str:
        """Get display title for event type."""
        titles = {
            EventType.MOVE: "Movement",
            EventType.DODGE: "Dodge",
            EventType.RUSH: "Rush (GFI)",
            EventType.STAND_UP: "Stand Up",
            EventType.PICKUP: "Pickup",
            EventType.DROP: "Ball Drop",
            EventType.PASS: "Pass",
            EventType.CATCH: "Catch",
            EventType.SCATTER: "Ball Scatter",
            EventType.HANDOFF: "Handoff",
            EventType.BLOCK: "Block",
            EventType.KNOCKDOWN: "Knockdown",
            EventType.ARMOR_BREAK: "Armor Check",
            EventType.INJURY: "Injury",
            EventType.CASUALTY: "Casualty",
            EventType.FOUL: "Foul",
            EventType.KICKOFF: "Kickoff",
            EventType.TOUCHDOWN: "TOUCHDOWN",
            EventType.TURNOVER: "TURNOVER",
            EventType.REROLL: "Reroll",
        }
        return titles.get(event_type, event_type.value.title())

    def _format_statistics(self, stats: GameStatistics) -> str:
        """
        Format game statistics.

        Args:
            stats: Game statistics

        Returns:
            Formatted statistics markdown
        """
        lines = ["## 📈 Game Statistics", ""]

        # Team stats
        for team_id, team_stats in stats.team_stats.items():
            lines.append(f"### {team_stats.team_name}")
            lines.append("")
            lines.append("**Offensive Stats:**")
            lines.append(f"- Touchdowns: {team_stats.touchdowns}")
            lines.append(
                f"- Passes: {team_stats.passes_completed}/{team_stats.passes_attempted} "
                f"({self._percentage(team_stats.passes_completed, team_stats.passes_attempted)})"
            )
            lines.append(
                f"- Pickups: {team_stats.pickups_succeeded}/{team_stats.pickups_attempted} "
                f"({self._percentage(team_stats.pickups_succeeded, team_stats.pickups_attempted)})"
            )
            lines.append(f"- Handoffs: {team_stats.handoffs}")
            lines.append("")

            lines.append("**Defensive Stats:**")
            lines.append(f"- Blocks: {team_stats.blocks_thrown}")
            lines.append(f"- Knockdowns: {team_stats.knockdowns}")
            lines.append(f"- Armor Breaks: {team_stats.armor_breaks}")
            lines.append(f"- Casualties Caused: {team_stats.casualties_caused}")
            lines.append("")

            lines.append("**Other:**")
            lines.append(f"- Turnovers: {team_stats.turnovers}")
            lines.append(f"- Failed Dodges: {team_stats.failed_dodges}")
            lines.append(f"- Players Injured: {team_stats.players_injured}")
            lines.append("")

        # Dice statistics
        lines.append("### 🎲 Dice Statistics")
        lines.append("")
        lines.append(f"- Total Rolls: {stats.total_dice_rolls}")
        lines.append("")

        if stats.dice_by_type:
            lines.append("**Rolls by Type:**")
            for roll_type, count in sorted(stats.dice_by_type.items()):
                success_count = stats.success_by_type.get(roll_type, 0)
                percentage = self._percentage(success_count, count)
                lines.append(f"- {roll_type.title()}: {success_count}/{count} ({percentage})")
            lines.append("")

        # Turnover analysis
        if stats.turnovers_by_reason:
            lines.append("### 🔄 Turnover Analysis")
            lines.append("")
            for reason, count in sorted(
                stats.turnovers_by_reason.items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"- {reason.replace('_', ' ').title()}: {count}")
            lines.append("")

        return "\n".join(lines)

    def _percentage(self, success: int, total: int) -> str:
        """Calculate and format percentage."""
        if total == 0:
            return "0%"
        return f"{(success / total * 100):.1f}%"


class PlainTextLogFormatter:
    """
    Formats game events as plain text (no markdown).

    Simpler format for logs that need to be displayed in
    environments that don't support markdown.
    """

    def format_game_log(
        self,
        events: list[GameEvent],
        game_id: str,
        team1_name: str,
        team2_name: str,
    ) -> str:
        """
        Format complete game log as plain text.

        Args:
            events: List of game events
            game_id: Game identifier
            team1_name: Name of team 1
            team2_name: Name of team 2

        Returns:
            Plain text formatted game log
        """
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("ANKH-MORPORK SCRAMBLE - GAME LOG")
        lines.append("=" * 60)
        lines.append(f"Game ID: {game_id}")
        lines.append(f"Teams: {team1_name} vs {team2_name}")

        if events:
            start_time = events[0].timestamp
            lines.append(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        lines.append("=" * 60)
        lines.append("")

        # Events
        current_half = 0
        current_turn = -1

        for event in events:
            # Half header
            if event.half != current_half:
                current_half = event.half
                lines.append("")
                lines.append(f"{'=' * 20} HALF {current_half} {'=' * 20}")
                lines.append("")
                current_turn = -1

            # Turn header
            if event.event_type == EventType.TURN_START:
                current_turn = event.turn_number
                team_name = event.details.get("team_name", "")
                lines.append(f"--- Turn {current_turn} - {team_name} ---")
                continue

            # Event
            timestamp = event.timestamp.strftime("%H:%M:%S")
            lines.append(f"[{timestamp}] {event.description}")

            # Dice rolls
            for dice_roll in event.dice_rolls:
                if dice_roll.target:
                    lines.append(
                        f"  └─ Rolled {dice_roll.result} (needed {dice_roll.target}+) "
                        f"- {'SUCCESS' if dice_roll.success else 'FAILED'}"
                    )
                else:
                    lines.append(f"  └─ Rolled {dice_roll.result}")

        return "\n".join(lines)
