"""Tests for FastAPI endpoints"""
import pytest
from fastapi.testclient import TestClient
from app.main import app, demo_mode, default_demo_game_id
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


def test_create_game_with_custom_id():
    """Test creating game with custom ID"""
    response = client.post("/game", params={"game_id": "custom-test-game"})
    assert response.status_code == 200

    data = response.json()
    assert data["game_id"] == "custom-test-game"


def test_setup_team_invalid_game():
    """Test setting up team for non-existent game"""
    response = client.post(
        "/game/nonexistent-game/setup-team",
        params={"team_id": "team1", "team_type": "city_watch"},
        json={"constable": "3"}
    )
    assert response.status_code == 400


def test_place_players_invalid_game():
    """Test placing players for non-existent game"""
    response = client.post(
        "/game/nonexistent-game/place-players",
        json={
            "team_id": "team1",
            "positions": {"player1": {"x": 5, "y": 7}}
        }
    )
    assert response.status_code == 400


def test_start_game_invalid_game():
    """Test starting non-existent game"""
    response = client.post("/game/nonexistent-game/start")
    assert response.status_code == 400


def test_end_turn_invalid_game():
    """Test ending turn for non-existent game"""
    response = client.post("/game/nonexistent-game/end-turn")
    assert response.status_code == 400


def test_action_on_nonexistent_game():
    """Test executing action on non-existent game"""
    response = client.post(
        "/game/nonexistent/action",
        json={
            "action_type": "move",
            "player_id": "player1",
            "path": [{"x": 6, "y": 7}]
        }
    )
    assert response.status_code == 404


def test_action_wrong_team_turn():
    """Test executing action when it's not the team's turn"""
    # Create and setup game
    create_response = client.post("/game")
    game_id = create_response.json()["game_id"]

    # Setup both teams
    client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team1", "team_type": "city_watch"},
        json={"constable": "2"}
    )
    client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team2", "team_type": "unseen_university"},
        json={"apprentice_wizard": "2"}
    )

    # Join teams
    client.post(f"/game/{game_id}/join", params={"team_id": "team1"})
    client.post(f"/game/{game_id}/join", params={"team_id": "team2"})

    # Place players
    client.post(
        f"/game/{game_id}/place-players",
        json={
            "team_id": "team1",
            "positions": {
                "team1_player_0": {"x": 5, "y": 7},
                "team1_player_1": {"x": 6, "y": 7}
            }
        }
    )
    client.post(
        f"/game/{game_id}/place-players",
        json={
            "team_id": "team2",
            "positions": {
                "team2_player_0": {"x": 20, "y": 7},
                "team2_player_1": {"x": 19, "y": 7}
            }
        }
    )

    # Start game
    client.post(f"/game/{game_id}/start")

    # Get game state to see which team is active
    game_state = client.get(f"/game/{game_id}").json()
    active_team = game_state["turn"]["active_team_id"]
    wrong_team = "team2" if active_team == "team1" else "team1"

    # Try to move wrong team's player
    response = client.post(
        f"/game/{game_id}/action",
        json={
            "action_type": "move",
            "player_id": f"{wrong_team}_player_0",
            "path": [{"x": 6, "y": 7}]
        }
    )
    assert response.status_code == 400
    assert "Not this team's turn" in response.json()["detail"]


def test_get_budget_status():
    """Test getting budget status for a team"""
    # Create game
    create_response = client.post("/game")
    game_id = create_response.json()["game_id"]

    # Setup team
    client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team1", "team_type": "city_watch"},
        json={"constable": "3"}
    )

    # Get budget
    response = client.get(f"/game/{game_id}/team/team1/budget")
    assert response.status_code == 200

    data = response.json()
    assert "spent" in data
    assert "remaining" in data
    assert "initial" in data


def test_get_budget_status_invalid_game():
    """Test getting budget for non-existent game"""
    response = client.get("/game/nonexistent/team/team1/budget")
    assert response.status_code == 400


def test_get_available_positions():
    """Test getting available positions"""
    # Create game
    create_response = client.post("/game")
    game_id = create_response.json()["game_id"]

    # Setup team
    client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team1", "team_type": "city_watch"},
        json={"constable": "1"}
    )

    # Get available positions
    response = client.get(f"/game/{game_id}/team/team1/available-positions")
    assert response.status_code == 200

    data = response.json()
    assert "positions" in data
    assert "reroll_cost" in data


def test_get_available_positions_invalid_game():
    """Test getting available positions for non-existent game"""
    response = client.get("/game/nonexistent/team/team1/available-positions")
    assert response.status_code == 400


def test_buy_player():
    """Test buying a player"""
    # Create game
    create_response = client.post("/game")
    game_id = create_response.json()["game_id"]

    # Setup team
    client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team1", "team_type": "city_watch"},
        json={}
    )

    # Buy player
    response = client.post(
        f"/game/{game_id}/team/team1/buy-player",
        params={"position_key": "constable"}
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] == True
    assert "budget_status" in data


def test_buy_player_invalid_game():
    """Test buying player for non-existent game"""
    response = client.post(
        "/game/nonexistent/team/team1/buy-player",
        params={"position_key": "constable"}
    )
    assert response.status_code == 400


def test_buy_reroll():
    """Test buying a reroll"""
    # Create game
    create_response = client.post("/game")
    game_id = create_response.json()["game_id"]

    # Setup team
    client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team1", "team_type": "city_watch"},
        json={"constable": "3"}
    )

    # Buy reroll
    response = client.post(f"/game/{game_id}/team/team1/buy-reroll")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] == True
    assert "budget_status" in data


def test_buy_reroll_invalid_game():
    """Test buying reroll for non-existent game"""
    response = client.post("/game/nonexistent/team/team1/buy-reroll")
    assert response.status_code == 400


def test_valid_actions_endpoint():
    """Test the valid actions endpoint"""
    # Create and setup game
    create_response = client.post("/game")
    game_id = create_response.json()["game_id"]

    # Setup teams
    client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team1", "team_type": "city_watch"},
        json={"constable": "2"}
    )
    client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team2", "team_type": "unseen_university"},
        json={"apprentice_wizard": "2"}
    )

    # Join teams
    client.post(f"/game/{game_id}/join", params={"team_id": "team1"})
    client.post(f"/game/{game_id}/join", params={"team_id": "team2"})

    # Place players
    client.post(
        f"/game/{game_id}/place-players",
        json={
            "team_id": "team1",
            "positions": {
                "team1_player_0": {"x": 5, "y": 7},
                "team1_player_1": {"x": 6, "y": 7}
            }
        }
    )
    client.post(
        f"/game/{game_id}/place-players",
        json={
            "team_id": "team2",
            "positions": {
                "team2_player_0": {"x": 20, "y": 7},
                "team2_player_1": {"x": 19, "y": 7}
            }
        }
    )

    # Start game
    client.post(f"/game/{game_id}/start")

    # Get valid actions
    response = client.get(f"/game/{game_id}/valid-actions")
    assert response.status_code == 200

    data = response.json()
    assert "movable_players" in data
    assert "can_blitz" in data
    assert "can_pass" in data


def test_valid_actions_invalid_game():
    """Test valid actions for non-existent game"""
    response = client.get("/game/nonexistent/valid-actions")
    assert response.status_code == 404


def test_statistics_endpoint_returns_data():
    """Statistics endpoint should respond with structured aggregates."""
    if demo_mode and default_demo_game_id:
        game_id = default_demo_game_id
    else:
        game_id = client.post("/game").json()["game_id"]

    response = client.get(f"/game/{game_id}/statistics")
    assert response.status_code == 200

    data = response.json()
    assert data["game_id"] == game_id
    assert "team_stats" in data
    assert "player_stats" in data


def test_rematch_endpoint_starts_or_resets_game():
    """Rematch endpoint should provide a fresh match state."""
    if demo_mode and default_demo_game_id:
        game_id = default_demo_game_id
    else:
        game_id = client.post("/game").json()["game_id"]

    response = client.post(f"/game/{game_id}/rematch")
    assert response.status_code == 200

    new_state = response.json()
    assert new_state["game_id"] == game_id

    if demo_mode and default_demo_game_id:
        assert new_state["phase"] == "kickoff"
        assert new_state["game_started"] is True
    else:
        assert new_state["phase"] == "setup"
