"""
Statistics aggregation from game events.

This module provides the StatisticsAggregator class which analyzes
game events to produce comprehensive statistics for teams and players.
"""

from collections import defaultdict
from typing import Optional
from app.models.events import (
    GameEvent,
    EventType,
    EventResult,
    GameStatistics,
    TeamStats,
    PlayerStats,
    TurnoverReason,
)
from app.models.game_state import GameState


class StatisticsAggregator:
    """
    Aggregates statistics from game events.

    Analyzes structured game events to produce comprehensive statistics
    for teams, players, dice rolls, and turnovers.
    """

    def __init__(self, game_state: GameState):
        """
        Initialize the statistics aggregator.

        Args:
            game_state: The game state to aggregate statistics for
        """
        self.game_state = game_state

    def aggregate(self, events: Optional[list[GameEvent]] = None) -> GameStatistics:
        """
        Aggregate statistics from events.

        Args:
            events: Events to aggregate (uses game_state.events if None)

        Returns:
            Aggregated game statistics
        """
        if events is None:
            events = self.game_state.events

        stats = GameStatistics(game_id=self.game_state.game_id)

        # Initialize team stats
        stats.team_stats[self.game_state.team1.id] = TeamStats(
            team_id=self.game_state.team1.id,
            team_name=self.game_state.team1.name,
        )
        stats.team_stats[self.game_state.team2.id] = TeamStats(
            team_id=self.game_state.team2.id,
            team_name=self.game_state.team2.name,
        )

        # Initialize player stats
        for player_id, player in self.game_state.players.items():
            stats.player_stats[player_id] = PlayerStats(
                player_id=player_id,
                player_name=f"{player.position_name} #{player.number}",
                team_id=player.team_id,
            )

        # Process events
        for event in events:
            self._process_event(event, stats)

        return stats

    def _process_event(self, event: GameEvent, stats: GameStatistics) -> None:
        """
        Process a single event and update statistics.

        Args:
            event: Event to process
            stats: Statistics object to update
        """
        # Track dice rolls
        for dice_roll in event.dice_rolls:
            stats.total_dice_rolls += 1

            roll_type = dice_roll.type
            stats.dice_by_type[roll_type] = stats.dice_by_type.get(roll_type, 0) + 1

            if dice_roll.success:
                stats.success_by_type[roll_type] = stats.success_by_type.get(roll_type, 0) + 1

        # Get team and player stats
        team_stats = None
        player_stats = None

        if event.active_team_id in stats.team_stats:
            team_stats = stats.team_stats[event.active_team_id]

        if event.player_id and event.player_id in stats.player_stats:
            player_stats = stats.player_stats[event.player_id]

        # Process by event type
        if event.event_type == EventType.MOVE:
            if player_stats:
                player_stats.moves += 1

        elif event.event_type == EventType.DODGE:
            if player_stats:
                player_stats.dodges_attempted += 1
                if event.result == EventResult.SUCCESS:
                    player_stats.dodges_succeeded += 1
                elif event.result == EventResult.FAILURE and team_stats:
                    team_stats.failed_dodges += 1

        elif event.event_type == EventType.PICKUP:
            if player_stats:
                player_stats.pickups_attempted += 1
                if event.result == EventResult.SUCCESS:
                    player_stats.pickups_succeeded += 1

            if team_stats:
                team_stats.pickups_attempted += 1
                if event.result == EventResult.SUCCESS:
                    team_stats.pickups_succeeded += 1

        elif event.event_type == EventType.PASS:
            if player_stats:
                player_stats.passes_attempted += 1
                if event.result == EventResult.SUCCESS:
                    player_stats.passes_completed += 1

            if team_stats:
                team_stats.passes_attempted += 1
                if event.result == EventResult.SUCCESS:
                    team_stats.passes_completed += 1
                elif event.result == EventResult.FAILURE:
                    team_stats.fumbles += 1

        elif event.event_type == EventType.CATCH:
            if player_stats:
                player_stats.catches_attempted += 1
                if event.result == EventResult.SUCCESS:
                    player_stats.catches_succeeded += 1

        elif event.event_type == EventType.HANDOFF:
            if team_stats:
                team_stats.handoffs += 1

        elif event.event_type == EventType.BLOCK:
            if player_stats:
                player_stats.blocks_thrown += 1

            if team_stats:
                team_stats.blocks_thrown += 1

        elif event.event_type == EventType.KNOCKDOWN:
            # Track knockdowns caused
            if event.target_player_id:
                # Someone knocked someone else down
                if event.target_player_id in stats.player_stats:
                    target_stats = stats.player_stats[event.target_player_id]
                    target_stats.times_knocked_down += 1

                    # Find the attacker's team
                    attacker_team = self._get_other_team_id(
                        target_stats.team_id, stats
                    )
                    if attacker_team in stats.team_stats:
                        stats.team_stats[attacker_team].knockdowns += 1

            if player_stats:
                player_stats.knockdowns_caused += 1

        elif event.event_type == EventType.ARMOR_BREAK:
            if event.result == EventResult.FAILURE:  # Armor broken
                if player_stats:
                    player_stats.times_injured += 1

                    # Credit the other team
                    other_team = self._get_other_team_id(player_stats.team_id, stats)
                    if other_team in stats.team_stats:
                        stats.team_stats[other_team].armor_breaks += 1

        elif event.event_type == EventType.INJURY:
            injury_type = event.details.get("injury")

            if player_stats:
                # Track injuries to this player
                if injury_type == "stunned":
                    pass  # Already counted in armor break
                elif injury_type == "ko":
                    if player_stats.team_id in stats.team_stats:
                        stats.team_stats[player_stats.team_id].players_ko += 1
                elif injury_type == "casualty":
                    if player_stats.team_id in stats.team_stats:
                        stats.team_stats[player_stats.team_id].players_casualties += 1

                # Credit casualties to the other team
                if injury_type == "casualty":
                    other_team = self._get_other_team_id(player_stats.team_id, stats)
                    if other_team in stats.team_stats:
                        stats.team_stats[other_team].casualties_caused += 1

                    # Find attacker if present
                    if event.target_player_id and event.target_player_id in stats.player_stats:
                        attacker_stats = stats.player_stats[event.target_player_id]
                        attacker_stats.casualties_caused += 1

        elif event.event_type == EventType.TOUCHDOWN:
            if player_stats:
                player_stats.touchdowns += 1

            # Get the scoring team from the event details
            scoring_team_id = event.details.get("team_id")
            if scoring_team_id and scoring_team_id in stats.team_stats:
                stats.team_stats[scoring_team_id].touchdowns += 1

        elif event.event_type == EventType.TURNOVER:
            if team_stats:
                team_stats.turnovers += 1

            # Track turnover reason
            reason = event.details.get("reason", "unknown")
            stats.turnovers_by_reason[reason] = stats.turnovers_by_reason.get(reason, 0) + 1

        elif event.event_type == EventType.DROP:
            if team_stats:
                team_stats.fumbles += 1

    def _get_other_team_id(self, team_id: str, stats: GameStatistics) -> str:
        """Get the ID of the other team."""
        for tid in stats.team_stats.keys():
            if tid != team_id:
                return tid
        return ""

    def get_player_stats(self, player_id: str, events: Optional[list[GameEvent]] = None) -> PlayerStats:
        """
        Get statistics for a specific player.

        Args:
            player_id: Player ID
            events: Events to aggregate (uses game_state.events if None)

        Returns:
            Player statistics
        """
        stats = self.aggregate(events)
        if player_id in stats.player_stats:
            return stats.player_stats[player_id]

        # Return empty stats if player not found
        player = self.game_state.players.get(player_id)
        if player:
            return PlayerStats(
                player_id=player_id,
                player_name=f"{player.position_name} #{player.number}",
                team_id=player.team_id,
            )

        return PlayerStats(
            player_id=player_id,
            player_name="Unknown",
            team_id="",
        )

    def get_team_stats(self, team_id: str, events: Optional[list[GameEvent]] = None) -> TeamStats:
        """
        Get statistics for a specific team.

        Args:
            team_id: Team ID
            events: Events to aggregate (uses game_state.events if None)

        Returns:
            Team statistics
        """
        stats = self.aggregate(events)
        if team_id in stats.team_stats:
            return stats.team_stats[team_id]

        # Return empty stats if team not found
        team = self.game_state.get_team_by_id(team_id)
        return TeamStats(
            team_id=team_id,
            team_name=team.name if team else "Unknown",
        )

    def get_turnover_summary(self, events: Optional[list[GameEvent]] = None) -> dict[str, int]:
        """
        Get a summary of turnovers by reason.

        Args:
            events: Events to aggregate (uses game_state.events if None)

        Returns:
            Dictionary mapping turnover reasons to counts
        """
        stats = self.aggregate(events)
        return dict(stats.turnovers_by_reason)

    def get_dice_summary(self, events: Optional[list[GameEvent]] = None) -> dict[str, dict[str, int]]:
        """
        Get a summary of dice rolls.

        Args:
            events: Events to aggregate (uses game_state.events if None)

        Returns:
            Dictionary with dice statistics by type
        """
        stats = self.aggregate(events)

        summary = {}
        for roll_type in stats.dice_by_type.keys():
            total = stats.dice_by_type[roll_type]
            success = stats.success_by_type.get(roll_type, 0)
            summary[roll_type] = {
                "total": total,
                "success": success,
                "failure": total - success,
                "success_rate": (success / total * 100) if total > 0 else 0,
            }

        return summary
