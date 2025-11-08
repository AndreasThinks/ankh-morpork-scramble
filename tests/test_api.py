"""Tests for FastAPI endpoints"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.enums import TeamType, ActionType


client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Ankh-Morpork Scramble API"
    assert data["status"] == "running"


def test_create_game():
    """Test game creation"""
    response = client.post("/game")
    assert response.status_code == 200
    
    data = response.json()
    assert "game_id" in data
    assert data["phase"] == "setup"
    assert "team1" in data
    assert "team2" in data


def test_get_game():
    """Test getting game state"""
    # Create game
    create_response = client.post("/game")
    game_id = create_response.json()["game_id"]
    
    # Get game
    response = client.get(f"/game/{game_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["game_id"] == game_id


def test_get_nonexistent_game():
    """Test getting non-existent game"""
    response = client.get("/game/nonexistent")
    assert response.status_code == 404


def test_setup_team():
    """Test team setup"""
    # Create game
    create_response = client.post("/game")
    game_id = create_response.json()["game_id"]
    
    # Setup team
    response = client.post(
        f"/game/{game_id}/setup-team",
        params={
            "team_id": "team1",
            "team_type": "city_watch"
        },
        json={
            "constable": "5",
            "clerk_runner": "1",
            "fleet_recruit": "2",
            "watch_sergeant": "3"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check players were created
    assert len(data["players"]) == 11


def test_full_game_flow():
    """Test a complete game flow"""
    # 1. Create game
    create_response = client.post("/game")
    assert create_response.status_code == 200
    game_id = create_response.json()["game_id"]
    
    # 2. Setup team 1
    response = client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team1", "team_type": "city_watch"},
        json={"constable": "3"}
    )
    assert response.status_code == 200
    
    # 3. Setup team 2
    response = client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team2", "team_type": "unseen_university"},
        json={"apprentice_wizard": "3"}
    )
    assert response.status_code == 200
    
    # 4. Join teams (required before starting)
    client.post(f"/game/{game_id}/join", params={"team_id": "team1"})
    client.post(f"/game/{game_id}/join", params={"team_id": "team2"})
    
    # 5. Place players
    response = client.post(
        f"/game/{game_id}/place-players",
        json={
            "team_id": "team1",
            "positions": {
                "team1_player_0": {"x": 5, "y": 7},
                "team1_player_1": {"x": 6, "y": 6},
                "team1_player_2": {"x": 6, "y": 8}
            }
        }
    )
    assert response.status_code == 200
    
    response = client.post(
        f"/game/{game_id}/place-players",
        json={
            "team_id": "team2",
            "positions": {
                "team2_player_0": {"x": 20, "y": 7},
                "team2_player_1": {"x": 19, "y": 6},
                "team2_player_2": {"x": 19, "y": 8}
            }
        }
    )
    assert response.status_code == 200
    
    # 5. Start game
    response = client.post(f"/game/{game_id}/start")
    assert response.status_code == 200
    data = response.json()
    assert data["phase"] == "kickoff"
    assert data["turn"] is not None
    
    # 6. Get valid actions
    response = client.get(f"/game/{game_id}/valid-actions")
    assert response.status_code == 200
    data = response.json()
    assert "movable_players" in data
    assert data["can_charge"] == True
    
    # 7. Execute a move action
    response = client.post(
        f"/game/{game_id}/action",
        json={
            "action_type": "move",
            "player_id": "team1_player_0",
            "path": [{"x": 6, "y": 7}, {"x": 7, "y": 7}]
        }
    )
    assert response.status_code == 200
    result = response.json()
    assert result["success"] == True
    
    # 8. End turn
    response = client.post(f"/game/{game_id}/end-turn")
    assert response.status_code == 200
    
    # 9. Get history
    response = client.get(f"/game/{game_id}/history")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert len(data["events"]) > 0


def test_invalid_action():
    """Test that invalid actions are rejected"""
    # Create and setup minimal game
    create_response = client.post("/game")
    game_id = create_response.json()["game_id"]
    
    # Try to execute action before game started
    response = client.post(
        f"/game/{game_id}/action",
        json={
            "action_type": "move",
            "player_id": "nonexistent",
            "path": [{"x": 6, "y": 7}]
        }
    )
    assert response.status_code == 400
