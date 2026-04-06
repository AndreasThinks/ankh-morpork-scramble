"""Weighted random model selection for the tournament pool.

Each game, two distinct models are picked from MODEL_POOL.
Models with fewer recorded games get higher weight (1 / (games + 1)),
so the leaderboard fills in evenly over time.

Override the pool with OPENROUTER_MODELS env var (comma-separated model IDs).
"""
import concurrent.futures
import logging
import os
import random
from typing import Optional

import requests

from .llm import validate_model

logger = logging.getLogger(__name__)

# Module-level cache, populated by validate_pool()
_validated_pool: Optional[list[str]] = None
_dead_models: set[str] = set()
_service_status: str = "ok"  # one of: "ok", "out_of_credits", "no_models"

MODEL_POOL = [
    "google/gemma-3-12b-it:free",
    "google/gemma-3-27b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-14b:free",
    "qwen/qwen3-8b:free",
    "meta-llama/llama-3.1-8b-instruct:free",
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


def _active_pool() -> list[str]:
    """Return the validated pool if we have one, else the full pool.

    Dead models discovered at runtime are always filtered out.
    """
    base = _validated_pool if _validated_pool is not None else _get_pool()
    return [m for m in base if m not in _dead_models]


def get_fallback_model(exclude: set[str]) -> Optional[str]:
    """Return a random model from the (validated) pool not in ``exclude``.

    Used to swap out a team's model when it keeps erroring. Returns None
    if every pool entry has already been tried (caller should stop
    swapping in that case).
    """
    candidates = [m for m in _active_pool() if m not in exclude]
    if not candidates:
        return None
    return random.choice(candidates)


def get_service_status() -> str:
    return _service_status


def mark_model_dead(model: str, reason: str = "unavailable") -> None:
    """Mark ``model`` as unusable for the rest of this process.

    If ``reason`` is ``"out_of_credits"`` the whole service flips to that state.
    """
    global _service_status
    if reason == "out_of_credits":
        _service_status = "out_of_credits"
        logger.error("mark_model_dead: out-of-credits detected while using %s", model)
        return

    if model in _dead_models:
        return
    _dead_models.add(model)
    logger.warning("mark_model_dead: banning %s (%s)", model, reason)
    if not _active_pool():
        _service_status = "no_models"
        logger.error("mark_model_dead: no usable models left in pool")


def validate_pool(force: bool = False) -> list[str]:
    """Probe every model in the pool in parallel and cache the live ones.

    If any probe reports out-of-credits, sets the service status to
    ``"out_of_credits"`` and returns an empty list immediately (the condition
    is global — no point continuing).

    Permanent/unavailable models are dropped. Models that 5xx/time-out are kept
    (benefit of the doubt). If the validated pool ends up empty, the service
    status flips to ``"no_models"``.
    """
    global _validated_pool, _service_status
    if _validated_pool is not None and not force:
        return list(_validated_pool)

    pool = _get_pool()
    logger.info("validate_pool: probing %d model(s)...", len(pool))
    alive: list[str] = []
    out_of_credits = False

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(validate_model, m): m for m in pool}
        for future in concurrent.futures.as_completed(futures):
            model = futures[future]
            try:
                ok, reason = future.result()
            except Exception as exc:
                logger.warning("validate_pool: %s raised %s — keeping", model, exc)
                alive.append(model)
                continue
            if reason == "out_of_credits":
                out_of_credits = True
            if ok:
                alive.append(model)

    if out_of_credits:
        _service_status = "out_of_credits"
        _validated_pool = []
        logger.error("validate_pool: OpenRouter reports no credits — service unavailable")
        return []

    # Preserve original pool order for determinism
    alive_set = set(alive)
    _validated_pool = [m for m in pool if m in alive_set]
    dropped = [m for m in pool if m not in alive_set]
    logger.info(
        "validate_pool: %d alive, %d dropped. alive=%s dropped=%s",
        len(_validated_pool), len(dropped), _validated_pool, dropped,
    )
    if not _validated_pool:
        _service_status = "no_models"
        logger.error("validate_pool: no usable models")
    else:
        _service_status = "ok"
    return list(_validated_pool)


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
    pool = _active_pool()
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
