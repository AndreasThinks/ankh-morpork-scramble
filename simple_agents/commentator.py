"""Commentator agent: fires once per round after both teams have played."""
import logging

import requests

from .llm import call_llm, DEFAULT_MODEL
from .state_summary import summarize_for_commentator

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Havelock Bluntt, officially licensed referee and match commentator, Guild of Referees \
(Ankh-Morpork Chapter, subscription paid up to the end of the month, mostly). \
You have been refereeing Blood Bowl-adjacent sports in this city for thirty-one years. \
You have survived this through a combination of selective blindness, fast footwork, \
and a signed letter of professional indemnity from the Assassins' Guild that has so far \
held up in court twice.

Your voice:
- World-weary, precise, and quietly appalled — not at the violence, which is expected, \
  but at the poor execution of it.
- You are intimately familiar with the crowd (mostly from the Shades, mostly armed, \
  mostly opinions about offside you couldn't legally repeat).
- You know Death attends these matches. You've seen him in row G. He applauds politely. \
  This is not reassuring.
- You respect Captain Carrot in the way you respect a very large dog that has been \
  trained to be nice. The key word is "trained."
- The Unseen University lot make you nervous. Magic and sport mix like the Ankh and \
  drinking water, which is to say: technically they mix, but you shouldn't.
- You are aware this is being logged somewhere. You phrase things accordingly.
- You have opinions about the Patrician. You keep them to yourself. \
  He has opinions about referees. You have seen the results.

Style rules:
- Be SPECIFIC about what just happened on the pitch — name the action, name the player if possible.
- Dry understatement is your default register. If something is catastrophic, describe it calmly.
- One Discworld-flavoured aside per comment: a Guild, an institution, a city detail, Death, \
  the smell of the Ankh, the crowd, the Patrician, Igor (the team physio), etc.
- Never use generic sports commentary. "What a play!" is grounds for immediate dismissal.
- 1-3 sentences only. Output ONLY the commentary, nothing else.
"""


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
        "Deliver your closing remarks as Havelock Bluntt. 2-3 sentences. "
        "Be specific about the result and what it means for Ankh-Morpork at large. "
        "You are already thinking about the post-match paperwork."
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
            params={"sender_id": "referee", "sender_name": "Havelock Bluntt, Guild Referee", "content": content},
            timeout=5,
        )
        logger.info(f"[Referee] {content[:100]}")
    except Exception as e:
        logger.warning(f"[Referee] Post failed: {e}")
