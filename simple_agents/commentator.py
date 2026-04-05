"""Commentator agent: fires after every team turn and on turnovers."""
import logging
from typing import Optional

import requests

from .llm import call_llm, DEFAULT_MODEL, LLMPermanentError
from . import model_picker
from .state_summary import summarize_for_commentator

logger = logging.getLogger(__name__)

# Current commentator model + already-tried set for this process. Mutated by
# set_commentator_model() at match start and by internal fallback logic below.
_current_commentator_model: str = DEFAULT_MODEL
_tried_commentator_models: set[str] = set()


def set_commentator_model(model: str) -> None:
    """Set the current commentator model, resetting the tried-models set."""
    global _current_commentator_model, _tried_commentator_models
    _current_commentator_model = model
    _tried_commentator_models = {model}


def get_commentator_model() -> str:
    return _current_commentator_model


def _try_swap_commentator(failed_model: str, reason: str) -> Optional[str]:
    """Mark ``failed_model`` dead and swap in a fallback. Returns the new model or None."""
    global _current_commentator_model
    model_picker.mark_model_dead(failed_model, reason)
    new_model = model_picker.get_fallback_model(_tried_commentator_models)
    if new_model is None:
        logger.error("[Dibbler] No untried commentator model left; giving up.")
        return None
    logger.warning(
        "[Dibbler] Commentator swap %s → %s (%s)", failed_model, new_model, reason
    )
    _current_commentator_model = new_model
    _tried_commentator_models.add(new_model)
    return new_model


def _call_with_fallback(system_prompt: str, user_msg: str, model: Optional[str]) -> Optional[str]:
    """Call the LLM, swapping models on a permanent error. Returns the text or None."""
    global _current_commentator_model
    # Prefer the module-level model once a swap has happened — the caller is
    # likely still passing the original (now dead) model each turn.
    current = _current_commentator_model or model or DEFAULT_MODEL
    _current_commentator_model = current
    _tried_commentator_models.add(current)
    try:
        return call_llm(system_prompt, user_msg, current)
    except LLMPermanentError as e:
        reason = "out_of_credits" if e.out_of_credits else "unavailable"
        logger.warning("[Dibbler] Commentary permanent error on %s: %s", current, e)
        if e.out_of_credits:
            # Global condition — no swap will help.
            model_picker.mark_model_dead(current, "out_of_credits")
            return None
        new_model = _try_swap_commentator(current, reason)
        if new_model is None:
            return None
        try:
            return call_llm(system_prompt, user_msg, new_model)
        except Exception as e2:
            logger.warning("[Dibbler] Commentary retry on %s failed: %s", new_model, e2)
            return None
    except Exception as e:
        logger.warning("[Dibbler] Commentary failed: %s", e)
        return None

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
    response = _call_with_fallback(SYSTEM_PROMPT, summary, model)
    if response:
        line = response.strip()
        if line:
            _post(game_id, line, base_url)


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
    response = _call_with_fallback(SYSTEM_PROMPT, prompt, model)
    if response:
        line = response.strip()
        if line:
            _post(game_id, line, base_url)


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
