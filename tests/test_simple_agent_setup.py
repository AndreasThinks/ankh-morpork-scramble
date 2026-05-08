from types import SimpleNamespace

import simple_agents.player as player


def _response(payload=None, status_code=200, text="OK"):
    return SimpleNamespace(
        status_code=status_code,
        text=text,
        json=lambda: payload if payload is not None else {},
    )


def test_setup_team_bounds_roster_llm_retries_and_timeout(monkeypatch):
    """Roster selection is optional; if OpenRouter stalls, setup must fall back fast."""
    calls = []

    def fake_call_llm(system_prompt, user_message, model, *, max_retries, timeout):
        calls.append({"max_retries": max_retries, "timeout": timeout})
        return '{"players": ["constable"], "rerolls": 0}'

    def fake_get(url, *args, **kwargs):
        if url.endswith("/budget"):
            return _response({"budget_remaining": 1_000_000})
        if url.endswith("/available-positions"):
            return _response(
                {
                    "reroll_cost": 60_000,
                    "rerolls_max": 8,
                    "positions": [
                        {
                            "position_key": "constable",
                            "role": "Constable",
                            "cost": 50_000,
                            "quantity_limit": 16,
                            "stats": {"ma": 6, "st": 3, "ag": 3, "pa": 4, "av": 9, "skills": []},
                        }
                    ],
                }
            )
        return _response({"team1": {"player_ids": ["p1"]}, "team2": {"player_ids": []}})

    posts = []

    def fake_post(url, *args, **kwargs):
        posts.append((url, kwargs))
        return _response({})

    monkeypatch.setattr(player, "call_llm", fake_call_llm)
    monkeypatch.setattr(player.requests, "get", fake_get)
    monkeypatch.setattr(player.requests, "post", fake_post)

    player.setup_team("the-match", "team1", "City Watch Constables", model="test-model")

    assert calls == [{"max_retries": 0, "timeout": 20}]
    assert any(url.endswith("/buy-player") for url, _ in posts)
    assert any(url.endswith("/place-players") for url, _ in posts)
    assert any(url.endswith("/join") for url, _ in posts)
