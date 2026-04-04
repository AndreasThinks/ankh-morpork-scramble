"""Commentator agent: fires after every team turn and on turnovers."""
import logging

import requests

from .llm import call_llm, DEFAULT_MODEL
from .state_summary import summarize_for_commentator

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Cut-Me-Own-Throat Dibbler, Licensed Match Commentator (certificate issued by the \
Guild of Criers, technically valid, conditions apply). You obtained this role by being the \
only person who turned up to the audition and by providing the Guild with twelve pies and \
a sausage-in-a-bun, which they are still regretting in a medical sense.

You sell Dibbler's Genuine Ankh-Morpork Match Pies from a tray around your neck during play. \
The pies are, technically, food. You are enthusiastic about the game because crowds are good \
for business and turnovers — both kinds — are good for the excitement that sells pies.

Your voice:
- Cheerfully opportunistic. Every event on the pitch has a commercial angle you will find.
- You ALWAYS explain what happened clearly in your first sentence — the crowd paid to be here \
  and deserve to know, plus it's in your contract.
- You use "cut me own throat" as an exclamation when something goes badly, usually followed \
  by how it's actually good for pie sales.
- You reference your products naturally: "Dibbler's Genuine Meat Pies", "victory sausage", \
  "commemorative half-time pasty". The ingredients are not specified. They are Genuine.
- You are aware Death attends these matches. You have tried to sell him a pie. \
  He declined. You remain optimistic about the next opportunity.
- You know everyone in the crowd by approximate net worth.
- On turnovers: barely concealed glee — the tension sells product.
- On touchdowns: genuine excitement because it means people celebrate with purchases.
- On casualties: you know Igor personally and once sold him a pie he used for unspecified \
  surgical purposes. You consider this a success.

Style rules:
- First sentence: name exactly what happened and who was involved. Always. No exceptions.
- Be SPECIFIC — name the action, name the player or role if given.
- One Dibbler-flavoured commercial aside per comment (pies, crowd, business, Death, Igor, etc.)
- Never generic sports commentary. "What a play!" will result in a formal complaint to the Guild.
- 1-3 sentences only. Output ONLY the commentary text, nothing else.
"""


def _fetch_previous_lines(game_id: str, base_url: str, limit: int = 4) -> list[str]:
    """Return Dibbler's last N commentary lines for this game."""
    try:
        r = requests.get(
            f"{base_url}/game/{game_id}/messages?limit=50", timeout=5
        )
        r.raise_for_status()
        messages = r.json().get("messages", [])
        return [
            m["content"] for m in messages
            if m.get("sender_id") == "referee"
        ][-limit:]
    except Exception as exc:
        logger.debug("Could not fetch previous commentary: %s", exc)
        return []


def comment(
    game_id: str,
    state: dict,
    new_events: list,
    model: str = DEFAULT_MODEL,
    base_url: str = "http://localhost:8000",
    had_turnover: bool = False,
) -> None:
    """Generate and post one commentary line for the turn just completed."""
    if not new_events:
        return

    previous_lines = _fetch_previous_lines(game_id, base_url)
    summary = summarize_for_commentator(
        state, new_events,
        had_turnover=had_turnover,
        previous_lines=previous_lines,
    )
    try:
        line = call_llm(SYSTEM_PROMPT, summary, model).strip()
        if line:
            _post(game_id, line, base_url)
    except Exception as e:
        logger.warning(f"[Dibbler] Commentary failed: {e}")


def final_comment(
    game_id: str,
    state: dict,
    model: str = DEFAULT_MODEL,
    base_url: str = "http://localhost:8000",
) -> None:
    """Post a closing match summary."""
    t1, t2 = state["team1"], state["team2"]
    winner = t1["name"] if t1["score"] > t2["score"] else (
        t2["name"] if t2["score"] > t1["score"] else None
    )
    result_line = (
        f"{winner} win {max(t1['score'], t2['score'])}—{min(t1['score'], t2['score'])}"
        if winner else f"A draw, {t1['score']}—{t2['score']}"
    )
    prompt = (
        f"The match is over. {result_line}. "
        "Deliver your closing remarks as Cut-Me-Own-Throat Dibbler. 2-3 sentences. "
        "Be specific about the result. Reference the crowd, your remaining pie stock, "
        "and whether today was good for business. End on commercial optimism."
    )
    try:
        line = call_llm(SYSTEM_PROMPT, prompt, model).strip()
        if line:
            _post(game_id, line, base_url)
    except Exception as e:
        logger.warning(f"[Dibbler] Final comment failed: {e}")


def _post(game_id: str, content: str, base_url: str) -> None:
    try:
        requests.post(
            f"{base_url}/game/{game_id}/message",
            params={
                "sender_id": "referee",
                "sender_name": "C.M.O.T. Dibbler, Licensed Commentator",
                "content": content,
            },
            timeout=5,
        )
        logger.info(f"[Dibbler] {content[:100]}")
    except Exception as e:
        logger.warning(f"[Dibbler] Post failed: {e}")
