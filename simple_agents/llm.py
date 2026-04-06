"""Thin OpenRouter wrapper with retry / back-off."""
import logging
import os
import random
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "google/gemma-3-12b-it:free"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Transient HTTP status codes worth retrying
_RETRYABLE = {429, 500, 502, 503, 504}
# Non-retryable client errors: bad model id, auth failure, insufficient credits, etc.
_PERMANENT = {400, 401, 402, 403, 404}
# Substrings in an error body that indicate we've run out of credits on OpenRouter.
_CREDIT_MARKERS = ("insufficient", "credit", "quota", "payment", "balance")


class LLMPermanentError(Exception):
    """Non-retryable failure: bad model id, auth failure, insufficient credits."""

    def __init__(self, status: int, message: str, *, out_of_credits: bool = False):
        self.status = status
        self.message = message
        self.out_of_credits = out_of_credits
        super().__init__(f"HTTP {status}: {message}" + (" [out_of_credits]" if out_of_credits else ""))


def _extract_error_text(response) -> str:
    """Best-effort pull of an error description from an OpenRouter response."""
    try:
        body = response.json()
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                return str(err.get("message") or err)
            if err:
                return str(err)
            if body.get("message"):
                return str(body["message"])
        return str(body)[:300]
    except Exception:
        return (response.text or "")[:300]


def _looks_like_out_of_credits(status: int, err_text: str) -> bool:
    if status == 402:
        return True
    lowered = (err_text or "").lower()
    return any(marker in lowered for marker in _CREDIT_MARKERS)


def _get_api_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        env_file = Path.home() / ".hermes" / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip("\"'")
                    break
    if not key:
        raise ValueError("OPENROUTER_API_KEY not set and not found in ~/.hermes/.env")
    return key


def _backoff(attempt: int, status: int, headers: dict) -> float:
    """Return seconds to wait before the next attempt.

    For 429 responses, honour the Retry-After (or x-ratelimit-reset-requests)
    header when present.  Otherwise use capped exponential back-off with jitter.
    """
    if status == 429:
        for header in ("Retry-After", "x-ratelimit-reset-requests", "X-RateLimit-Reset"):
            val = headers.get(header)
            if val:
                try:
                    return max(1.0, float(val))
                except ValueError:
                    pass
        # No header — exponential: 5, 10, 20, 40 s + up to 2 s jitter
        return min(60.0, 5.0 * (2 ** attempt)) + random.uniform(0, 2)
    # 5xx — shorter back-off: 2, 4, 8, 16 s + jitter
    return min(30.0, 2.0 * (2 ** attempt)) + random.uniform(0, 1)


def call_llm(
    system_prompt: str,
    user_message: str,
    model: str = DEFAULT_MODEL,
    max_retries: int = 4,
) -> str:
    """Call the OpenRouter chat completions endpoint.

    Retries automatically on 429 (rate limit) and transient 5xx errors, using
    exponential back-off.  Respects the Retry-After header when provided.
    Raises on the final attempt or on non-retryable errors.
    """
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            r = requests.post(
                f"{OPENROUTER_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {_get_api_key()}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.7,
                },
                timeout=60,
            )
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = 5.0 * (attempt + 1)
                logger.warning(
                    "call_llm timeout on attempt %d/%d — retrying in %.0fs",
                    attempt + 1, max_retries + 1, wait,
                )
                time.sleep(wait)
                continue
            raise

        if r.status_code in _RETRYABLE and attempt < max_retries:
            wait = _backoff(attempt, r.status_code, dict(r.headers))
            logger.warning(
                "call_llm HTTP %d on attempt %d/%d — retrying in %.1fs (model=%s)",
                r.status_code, attempt + 1, max_retries + 1, wait, model,
            )
            time.sleep(wait)
            continue

        if r.status_code in _PERMANENT:
            err_text = _extract_error_text(r)
            out_of_credits = _looks_like_out_of_credits(r.status_code, err_text)
            raise LLMPermanentError(r.status_code, err_text, out_of_credits=out_of_credits)

        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    # Should only reach here if max_retries is 0 and we got a timeout
    if last_exc:
        raise last_exc
    raise RuntimeError("call_llm: exhausted retries without result")


def validate_model(model: str, timeout: float = 15.0) -> tuple[bool, str | None]:
    """Probe OpenRouter with a tiny request to check whether ``model`` is usable.

    Returns ``(True, None)`` on success OR on transient (5xx/timeout/network)
    failures — we give the model the benefit of the doubt for blips.
    Returns ``(False, "out_of_credits")`` if the account has run out of credits
    (402 or a matching error body) — this is a *global* condition.
    Returns ``(False, "unavailable")`` for permanent client errors (400/401/403/404)
    which indicate a bad model id or account-level access problem for that model.
    """
    try:
        r = requests.post(
            f"{OPENROUTER_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {_get_api_key()}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 1,
                "temperature": 0.0,
            },
            timeout=timeout,
        )
    except requests.exceptions.RequestException as exc:
        logger.warning("validate_model(%s): network error, treating as transient: %s", model, exc)
        return True, None

    if r.status_code == 200:
        return True, None

    if r.status_code in _PERMANENT:
        err_text = _extract_error_text(r)
        if _looks_like_out_of_credits(r.status_code, err_text):
            logger.error(
                "validate_model(%s): HTTP %d — out of credits (%s)",
                model, r.status_code, err_text[:200],
            )
            return False, "out_of_credits"
        logger.warning(
            "validate_model(%s): HTTP %d — unavailable (%s)",
            model, r.status_code, err_text[:200],
        )
        return False, "unavailable"

    # 5xx or 429 — transient, keep the model
    logger.info(
        "validate_model(%s): HTTP %d — transient, keeping model", model, r.status_code
    )
    return True, None
