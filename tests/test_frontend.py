import re

from fastapi.testclient import TestClient

from app.main import app
from app.setup.default_game import DEFAULT_GAME_ID


def test_ui_dashboard_renders_default_game_id():
    """Test that UI dashboard renders with default game ID"""
    client = TestClient(app)
    response = client.get("/ui")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert re.search(rf"data-game-id=\"{DEFAULT_GAME_ID}\"", response.text)
    assert "Recent Events" in response.text


def test_ui_dashboard_with_custom_game_id():
    """Test that UI dashboard accepts custom game_id parameter"""
    client = TestClient(app)
    custom_id = "custom-game-123"
    response = client.get(f"/ui?game_id={custom_id}")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert re.search(rf"data-game-id=\"{custom_id}\"", response.text)


def test_ui_endpoint_headers():
    """Test that UI endpoint returns correct content-type"""
    client = TestClient(app)
    response = client.get("/ui")

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "text/html" in content_type
    assert "charset" in content_type.lower()


def test_ui_renders_core_components():
    """Test that all major UI components are present"""
    client = TestClient(app)
    response = client.get("/ui")

    assert response.status_code == 200
    html = response.text

    # Check for essential UI elements
    assert "Ankh-Morpork Scramble" in html
    assert "Pitch Overview" in html
    assert "Recent Events" in html
    assert "Players on the Pitch" in html
    assert "pitch-canvas" in html
    assert "roster-body" in html
    assert "team1-thoughts" in html
    assert "team2-thoughts" in html


def test_ui_includes_javascript():
    """Test that UI includes necessary JavaScript"""
    client = TestClient(app)
    response = client.get("/ui")

    assert response.status_code == 200
    html = response.text

    # Check for essential JavaScript functions
    assert "fetchState" in html
    assert "renderPitch" in html
    assert "updateScoreboard" in html
    assert "initPitchGrid" in html
    assert "setInterval(fetchState" in html


def test_ui_includes_styling():
    """Test that UI includes CSS styling"""
    client = TestClient(app)
    response = client.get("/ui")

    assert response.status_code == 200
    html = response.text

    # Check for CSS custom properties and styling
    assert "<style>" in html
    assert "--bg:" in html
    assert "--accent-blue:" in html
    assert "--accent-orange:" in html
    assert "--accent-gold:" in html
    assert "Cinzel" in html  # Custom font


def test_ui_has_accessibility_features():
    """Test that UI includes basic accessibility features"""
    client = TestClient(app)
    response = client.get("/ui")

    assert response.status_code == 200
    html = response.text

    # Check for accessibility attributes
    assert 'role="img"' in html
    assert 'aria-labelledby="pitch-title"' in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html


def test_ui_renders_with_special_characters_in_game_id():
    """Test that UI handles game IDs with special characters safely"""
    client = TestClient(app)
    # Test with URL-safe characters
    game_id = "game-with-dashes-123"
    response = client.get(f"/ui?game_id={game_id}")

    assert response.status_code == 200
    assert game_id in response.text
