"""Weighted random model selection for the tournament pool.

Each game, two distinct models are picked from MODEL_POOL.
Models with fewer recorded games get higher weight (1 / (games + 1)),
so the leaderboard fills in evenly over time.

Override the pool with OPENROUTER_MODELS env var (comma-separated model IDs).
"""
import logging
import os
import random
from typing import Optional

import requests

logger = logging.getLogger(__name__)

MODEL_POOL = [
    "qwen/qwen3-8b:free",
    "qwen/qwen3-14b:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3-27b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-nemo:free",
    "microsoft/phi-4:free",
    "deepseek/deepseek-r1-0528:free",
    "deepseek/deepseek-chat-v3-5:free",
]


def _get_pool() -> list[str]:
    override = os.getenv("OPENROUTER_MODELS", "").strip()
    if override:
        return [m.strip() for m in override.split(",") if m.strip()]
    return list(MODEL_POOL)


def _fetch_games_per_model(leaderboard_url: str) -> dict[str, int]:
    """Return {model_id: games_played} from the leaderboard API."""
    try:
        r = requests.get(f"{leaderboard_url}/leaderboard", timeout=5)
        r.raise_for_status()
        data = r.json()
        return {entry["model_id"]: entry["games"] for entry in data.get("by_model", [])}
    except Exception as exc:
        logger.warning("Could not fetch leaderboard for model weighting: %s", exc)
        return {}


def pick_models(leaderboard_url: str = "http://localhost:8000") -> tuple[str, str]:
    """Pick two distinct models weighted toward least-played.

    Falls back to uniform random if the pool has fewer than 2 models or
    if weighting fails for any reason.
    """
    pool = _get_pool()
    if len(pool) < 2:
        raise ValueError(f"MODEL_POOL must have at least 2 models, got: {pool}")

    games_map = _fetch_games_per_model(leaderboard_url)

    # Weight = 1 / (games + 1): models with 0 games get weight 1.0,
    # models with 9 games get weight 0.1, etc.
    weights = [1.0 / (games_map.get(m, 0) + 1) for m in pool]

    # Pick first model
    model1 = random.choices(pool, weights=weights, k=1)[0]

    # Pick second model, excluding model1
    remaining = [(m, w) for m, w in zip(pool, weights) if m != model1]
    if not remaining:
        # Pool has only one unique model — shouldn't happen but handle gracefully
        model2 = model1
    else:
        r_models, r_weights = zip(*remaining)
        model2 = random.choices(list(r_models), weights=list(r_weights), k=1)[0]

    logger.info("Model pick: team1=%s  team2=%s", model1, model2)
    return model1, model2
