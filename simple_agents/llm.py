"""Thin OpenRouter wrapper."""
import os
from pathlib import Path

import requests

DEFAULT_MODEL = "qwen/qwen3.6-plus:free"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"


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


def call_llm(system_prompt: str, user_message: str, model: str = DEFAULT_MODEL) -> str:
    r = requests.post(
        f"{OPENROUTER_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {_get_api_key()}", "Content-Type": "application/json"},
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
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
