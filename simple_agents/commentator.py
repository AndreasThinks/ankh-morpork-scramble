"""Commentator agent: fires once per round after both teams have played."""
import logging

import requests

from .llm import call_llm, DEFAULT_MODEL
from .state_summary import summarize_for_commentator

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are Referee Quirke, official commentator for the Guild of Referees, Ankh-Morpork. "
    "Thirty years on the pitch. You've seen everything twice, and the second time wasn't better. "
    "Your commentary is dry, specific, and darkly funny in Terry Pratchett's voice. "
    "Reference Ankh-Morpork institutions, the Watch, Unseen University, the river, the Guilds. "
    "Be specific about what actually happened. Never be generic. Never use sports clichés. "
    "Write ONE commentary remark: 1-3 sentences. Output only that, nothing else."
)


def comment(game_id: str, state: dict, new_events: list,
            model: str = DEFAULT_MODEL, base_url: str = "http://localhost:8000") -> None:
    """Generate and post one commentary line for the round just played."""
    if not new_events:
        return

    summary = summarize_for_commentator(state, new_events)
    try:
        line = call_llm(SYSTEM_PROMPT, summary, model).strip()
        if line:
            _post(game_id, line, base_url)
    except Exception as e:
        logger.warning(f"[Referee] Commentary failed: {e}")


def final_comment(game_id: str, state: dict,
                  model: str = DEFAULT_MODEL, base_url: str = "http://localhost:8000") -> None:
    """Post a closing match summary."""
    t1, t2 = state["team1"], state["team2"]
    prompt = (
        f"The match is over. Final score: {t1['name']} {t1['score']} — {t2['score']} {t2['name']}. "
        "Write a brief Discworld-flavoured closing remark. 2-3 sentences. Be specific about the result."
    )
    try:
        line = call_llm(SYSTEM_PROMPT, prompt, model).strip()
        if line:
            _post(game_id, line, base_url)
    except Exception as e:
        logger.warning(f"[Referee] Final comment failed: {e}")


def _post(game_id: str, content: str, base_url: str) -> None:
    try:
        requests.post(
            f"{base_url}/game/{game_id}/message",
            params={"sender_id": "referee", "sender_name": "Referee Quirke", "content": content},
            timeout=5,
        )
        logger.info(f"[Referee] {content[:100]}")
    except Exception as e:
        logger.warning(f"[Referee] Post failed: {e}")
