import re

from fastapi.testclient import TestClient

from app.main import app
from app.setup.default_game import DEFAULT_GAME_ID


def test_ui_dashboard_renders_default_game_id():
    client = TestClient(app)
    response = client.get("/ui")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert re.search(rf"data-game-id=\"{DEFAULT_GAME_ID}\"", response.text)
    assert "Recent Events" in response.text
