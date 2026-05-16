"""Tests for tournament model selection."""

from simple_agents import model_picker


def test_pick_models_revalidates_when_cached_pool_is_empty(monkeypatch):
    """An exhausted runtime pool should re-probe before giving up.

    Regression: when all models were marked dead or the validated pool became [],
    pick_models() raised immediately. The runner caught that and retried every 3s,
    leaving the live match stuck in setup with zero players.
    """
    model_picker._validated_pool = []
    model_picker._dead_models = set()
    model_picker._service_status = "no_models"

    monkeypatch.setattr(model_picker, "_fetch_free_models", lambda: ["model/a", "model/b"])
    monkeypatch.setattr(model_picker, "validate_model", lambda model: (True, None))
    monkeypatch.setattr(model_picker, "_fetch_games_per_model", lambda _url: {})

    first, second = model_picker.pick_models("http://testserver")

    assert {first, second} == {"model/a", "model/b"}
    assert model_picker.get_service_status() == "ok"
