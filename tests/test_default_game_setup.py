from app.setup.default_game import bootstrap_default_game
from app.state.game_manager import GameManager


def test_bootstrap_creates_players():
    manager = GameManager()
    state = bootstrap_default_game(manager, game_id="demo-test")

    assert state.game_id == "demo-test"
    assert len(state.players) == 8
    assert state.team1_joined is False
    assert state.team2_joined is False
    assert state.pitch.player_positions


def test_bootstrap_idempotent():
    manager = GameManager()
    first = bootstrap_default_game(manager, game_id="demo-test")
    second = bootstrap_default_game(manager, game_id="demo-test")

    assert first is second
