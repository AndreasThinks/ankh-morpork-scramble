"""
Log saver for persisting game logs to disk.

This module handles saving game logs in various formats (markdown, JSON)
to the filesystem for persistence and later retrieval.
"""

import json
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from app.models.game_state import GameState
from app.models.events import GameEvent, GameStatistics
from app.game.log_formatter import MarkdownLogFormatter
from app.game.statistics import StatisticsAggregator


class LogSaver:
    """
    Saves game logs to disk.

    Handles persistence of game logs in multiple formats:
    - Markdown for human-readable viewing
    - JSON for structured data and replay
    - Statistics as JSON
    """

    def __init__(self, base_dir: str = "logs/games"):
        """
        Initialize log saver.

        Args:
            base_dir: Base directory for saving logs
        """
        self.base_dir = base_dir

    def save_game_log(
        self,
        game_state: GameState,
        save_markdown: bool = True,
        save_json: bool = True,
        save_stats: bool = True,
    ) -> dict[str, str]:
        """
        Save game log to disk.

        Args:
            game_state: Game state with events to save
            save_markdown: Save markdown formatted log
            save_json: Save JSON events data
            save_stats: Save statistics

        Returns:
            Dictionary of saved file paths
        """
        # Create game directory
        game_dir = self._get_game_dir(game_state.game_id)
        game_dir.mkdir(parents=True, exist_ok=True)

        saved_files = {}

        # Save markdown log
        if save_markdown:
            markdown_path = game_dir / "game_log.md"
            self._save_markdown_log(game_state, markdown_path)
            saved_files["markdown"] = str(markdown_path)

        # Save JSON events
        if save_json:
            json_path = game_dir / "events.json"
            self._save_json_events(game_state, json_path)
            saved_files["json"] = str(json_path)

        # Save statistics
        if save_stats and game_state.events:
            stats_path = game_dir / "statistics.json"
            self._save_statistics(game_state, stats_path)
            saved_files["statistics"] = str(stats_path)

        return saved_files

    def _get_game_dir(self, game_id: str) -> Path:
        """Get directory path for a game."""
        return Path(self.base_dir) / game_id

    def _save_markdown_log(self, game_state: GameState, file_path: Path) -> None:
        """Save markdown formatted log."""
        formatter = MarkdownLogFormatter(verbose=True)

        markdown = formatter.format_game_log(
            events=game_state.events,
            game_id=game_state.game_id,
            team1_name=game_state.team1.name,
            team2_name=game_state.team2.name,
        )

        # Add statistics if available
        if game_state.events:
            aggregator = StatisticsAggregator(game_state)
            stats = aggregator.aggregate()
            markdown += "\n\n" + formatter._format_statistics(stats)

        file_path.write_text(markdown, encoding="utf-8")

    def _save_json_events(self, game_state: GameState, file_path: Path) -> None:
        """Save events as JSON."""
        events_data = {
            "game_id": game_state.game_id,
            "team1": {
                "id": game_state.team1.id,
                "name": game_state.team1.name,
                "score": game_state.team1.score,
            },
            "team2": {
                "id": game_state.team2.id,
                "name": game_state.team2.name,
                "score": game_state.team2.score,
            },
            "phase": game_state.phase.value,
            "events": [event.model_dump(mode="json") for event in game_state.events],
        }

        file_path.write_text(json.dumps(events_data, indent=2), encoding="utf-8")

    def _save_statistics(self, game_state: GameState, file_path: Path) -> None:
        """Save statistics as JSON."""
        aggregator = StatisticsAggregator(game_state)
        stats = aggregator.aggregate()

        stats_data = stats.model_dump(mode="json")

        file_path.write_text(json.dumps(stats_data, indent=2), encoding="utf-8")

    def load_events(self, game_id: str) -> Optional[list[dict]]:
        """
        Load events from JSON file.

        Args:
            game_id: Game ID to load

        Returns:
            List of event dictionaries or None if not found
        """
        game_dir = self._get_game_dir(game_id)
        json_path = game_dir / "events.json"

        if not json_path.exists():
            return None

        data = json.loads(json_path.read_text(encoding="utf-8"))
        return data.get("events", [])

    def get_markdown_log(self, game_id: str) -> Optional[str]:
        """
        Get markdown log content.

        Args:
            game_id: Game ID to retrieve

        Returns:
            Markdown log content or None if not found
        """
        game_dir = self._get_game_dir(game_id)
        markdown_path = game_dir / "game_log.md"

        if not markdown_path.exists():
            return None

        return markdown_path.read_text(encoding="utf-8")

    def list_saved_games(self) -> list[str]:
        """
        List all game IDs with saved logs.

        Returns:
            List of game IDs
        """
        base_path = Path(self.base_dir)

        if not base_path.exists():
            return []

        return [
            d.name
            for d in base_path.iterdir()
            if d.is_dir() and (d / "game_log.md").exists()
        ]
