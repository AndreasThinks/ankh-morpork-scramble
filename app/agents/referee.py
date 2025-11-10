"""Referee agent that provides live commentary on the game."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx


@dataclass
class RefereeConfig:
    """Configuration for the referee commentator agent."""

    game_id: str
    api_base_url: str
    commentary_interval: float  # seconds between commentary updates
    model: str
    api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    http_referer: str = "https://github.com/AndreasThinks/ankh-morpork-scramble"
    app_title: str = "Ankh-Morpork Scramble Referee"
    custom_prompt: Optional[str] = None

    @classmethod
    def from_env(cls) -> "RefereeConfig":
        """Load referee configuration from environment variables."""
        game_id = os.getenv("INTERACTIVE_GAME_ID", "interactive-game")
        api_base_url = os.getenv("REFEREE_API_BASE_URL", "http://localhost:8000")
        commentary_interval = float(os.getenv("REFEREE_COMMENTARY_INTERVAL", "30"))
        model = os.getenv("REFEREE_MODEL", "anthropic/claude-3.5-haiku")
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("openrouter_api_key")

        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY environment variable is required for referee")

        custom_prompt = os.getenv("REFEREE_PROMPT")

        return cls(
            game_id=game_id,
            api_base_url=api_base_url,
            commentary_interval=commentary_interval,
            model=model,
            api_key=api_key,
            custom_prompt=custom_prompt,
        )

    @property
    def default_prompt(self) -> str:
        """Get the default referee prompt."""
        return """You are the referee and commentator for an Ankh-Morpork Scramble match - a chaotic,
Blood Bowl-inspired sports game set in Terry Pratchett's Discworld.

Your role is to provide entertaining, character-driven commentary on the match as it unfolds.
You should:

1. **Observe the action**: Review the game state and recent events
2. **Stay in character**: You're a gruff, seen-it-all Ankh-Morpork sports referee who's witnessed
   countless street brawls masquerading as sport
3. **Be colorful**: Use Discworld humor, reference the absurdity of the situation, and don't be
   afraid to express opinions about the teams' tactics
4. **Keep it concise**: Your commentary should be 2-3 sentences, punchy and memorable
5. **Comment on drama**: Highlight exciting plays, brutal hits, impressive moves, or tactical blunders
6. **Acknowledge the setting**: Reference Ankh-Morpork locations, customs, and the general chaos

Examples of your style:
- "And the Watch sergeant just flattened that wizard like a troll sitting on a cream puff!
   That's gonna leave a mark, and possibly require a spell or two..."
- "The Unseen University lads are playing keepaway with the ball like it's a hot pie and they're
   scared it'll burn their fingers. Show some backbone, wizards!"
- "Well, that was about as subtle as a brick through a window at the Thieves' Guild.
   The crowd loves it though!"

Now, provide your commentary based on the current game state and recent events."""

    def get_prompt(self) -> str:
        """Get the prompt to use (custom or default)."""
        return self.custom_prompt if self.custom_prompt else self.default_prompt


class RefereeAgent:
    """Agent that provides live commentary on the game."""

    def __init__(self, config: RefereeConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.last_turn = -1
        self.last_event_count = 0

    async def run(self) -> None:
        """Run the referee agent in a continuous loop."""
        self.logger.info("Referee agent starting (interval: %.1fs)", self.config.commentary_interval)
        self.logger.info("Using model: %s", self.config.model)

        while True:
            try:
                await asyncio.sleep(self.config.commentary_interval)
                await self._generate_commentary()
            except asyncio.CancelledError:
                self.logger.info("Referee agent shutting down")
                break
            except Exception as e:
                self.logger.error("Error generating commentary: %s", e, exc_info=True)
                # Continue running even if one commentary fails
                await asyncio.sleep(5)

    async def _get_game_state(self) -> dict:
        """Fetch current game state from API."""
        url = f"{self.config.api_base_url}/game/{self.config.game_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            return response.json()

    async def _get_recent_history(self, limit: int = 5) -> dict:
        """Fetch recent game history."""
        url = f"{self.config.api_base_url}/game/{self.config.game_id}/history"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"limit": limit}, timeout=10)
            response.raise_for_status()
            return response.json()

    async def _post_commentary(self, commentary: str) -> None:
        """Post commentary as a referee message."""
        url = f"{self.config.api_base_url}/game/{self.config.game_id}/message"
        data = {
            "sender_id": "referee",
            "sender_name": "Referee",
            "content": commentary,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, timeout=10)
            response.raise_for_status()

    async def _generate_commentary(self) -> None:
        """Generate and post commentary based on current game state."""
        try:
            # Fetch game state and history
            game_state = await self._get_game_state()
            history = await self._get_recent_history(limit=10)

            # Check if there's anything new to comment on
            current_turn = game_state.get("turn", 0)
            events = history.get("events", [])
            current_event_count = len(events)

            if current_turn == self.last_turn and current_event_count == self.last_event_count:
                self.logger.debug("No new events, skipping commentary")
                return

            self.last_turn = current_turn
            self.last_event_count = current_event_count

            # Build context for the LLM
            context = self._build_context(game_state, history)

            # Generate commentary using OpenRouter
            commentary = await self._call_llm(context)

            if commentary:
                # Post commentary to the game
                await self._post_commentary(commentary)
                self.logger.info("Posted commentary: %s", commentary)

        except httpx.HTTPError as e:
            self.logger.warning("HTTP error fetching game state: %s", e)
        except Exception as e:
            self.logger.error("Error in commentary generation: %s", e, exc_info=True)

    def _build_context(self, game_state: dict, history: dict) -> str:
        """Build context string for the LLM."""
        phase = game_state.get("phase", "UNKNOWN")
        turn = game_state.get("turn", 0)
        active_team = game_state.get("active_team", "unknown")
        score = game_state.get("score", {})

        context_parts = [
            f"Current Turn: {turn}",
            f"Phase: {phase}",
            f"Active Team: {active_team}",
            f"Score: Team 1 ({score.get('team1', 0)}) - Team 2 ({score.get('team2', 0)})",
            "",
            "Recent Events:",
        ]

        # Add recent history - events are strings from event_log
        events = history.get("events", [])
        for event in events[-5:]:  # Last 5 events
            context_parts.append(f"- {event}")

        return "\n".join(context_parts)

    async def _call_llm(self, context: str) -> Optional[str]:
        """Call OpenRouter LLM to generate commentary."""
        prompt = self.config.get_prompt()
        full_prompt = f"{prompt}\n\n{context}\n\nYour commentary (2-3 sentences):"

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "HTTP-Referer": self.config.http_referer,
            "X-Title": self.config.app_title,
            "Content-Type": "application/json",
        }

        data = {
            "model": self.config.model,
            "messages": [
                {"role": "user", "content": full_prompt}
            ],
            "max_tokens": 200,
            "temperature": 0.8,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.config.openrouter_base_url}/chat/completions",
                    headers=headers,
                    json=data,
                )
                response.raise_for_status()
                result = response.json()

                commentary = result["choices"][0]["message"]["content"].strip()
                return commentary

        except Exception as e:
            self.logger.error("Error calling LLM: %s", e)
            return None


async def run_referee() -> None:
    """Main entry point for referee agent."""
    config = RefereeConfig.from_env()

    # Set up logging
    logger = logging.getLogger("app.agents.referee")
    logger.setLevel(os.getenv("REFEREE_LOG_LEVEL", "INFO"))

    # Add console handler
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[referee] %(levelname)s: %(message)s")
    )
    logger.addHandler(handler)

    # Add file handler if log directory exists
    log_dir = Path("logs")
    if log_dir.exists():
        file_handler = logging.FileHandler(log_dir / "referee.log", mode="w")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)

    referee = RefereeAgent(config, logger)
    await referee.run()


if __name__ == "__main__":
    asyncio.run(run_referee())
