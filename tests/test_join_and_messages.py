"""Tests for join status and messaging features"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_join_workflow():
    """Test team join workflow"""
    # Create game
    response = client.post("/game")
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    
    # Verify initial join status
    response = client.get(f"/game/{game_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["team1_joined"] == False
    assert data["team2_joined"] == False
    assert data["game_started"] == False
    
    # Team 1 joins
    response = client.post(
        f"/game/{game_id}/join",
        params={"team_id": "team1"}
    )
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert response.json()["players_ready"] == False
    
    # Verify team1 joined
    response = client.get(f"/game/{game_id}")
    data = response.json()
    assert data["team1_joined"] == True
    assert data["team2_joined"] == False
    
    # Team 2 joins
    response = client.post(
        f"/game/{game_id}/join",
        params={"team_id": "team2"}
    )
    assert response.status_code == 200
    assert response.json()["players_ready"] == True
    
    # Verify both joined
    response = client.get(f"/game/{game_id}")
    data = response.json()
    assert data["team1_joined"] == True
    assert data["team2_joined"] == True


def test_cannot_start_without_both_teams():
    """Test that game cannot start without both teams joined"""
    # Create game
    response = client.post("/game")
    game_id = response.json()["game_id"]
    
    # Setup teams
    client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team1", "team_type": "city_watch"},
        json={"constable": "3"}
    )
    client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team2", "team_type": "unseen_university"},
        json={"apprentice_wizard": "3"}
    )
    
    # Try to start without joins (should fail)
    response = client.post(f"/game/{game_id}/start")
    assert response.status_code == 400
    assert "must join" in response.json()["detail"].lower()
    
    # Join both teams
    client.post(f"/game/{game_id}/join", params={"team_id": "team1"})
    client.post(f"/game/{game_id}/join", params={"team_id": "team2"})
    
    # Now it should work (but still needs player placement)
    response = client.post(f"/game/{game_id}/start")
    # May fail for other reasons (player placement) but not for join status
    if response.status_code == 400:
        assert "must join" not in response.json()["detail"].lower()


def test_send_and_receive_messages():
    """Test sending and receiving messages"""
    # Create game
    response = client.post("/game")
    game_id = response.json()["game_id"]
    
    # Send a message
    response = client.post(
        f"/game/{game_id}/message",
        params={
            "sender_id": "player1",
            "sender_name": "Alice",
            "content": "Hello, ready to play?"
        }
    )
    assert response.status_code == 200
    assert response.json()["success"] == True
    message = response.json()["message"]
    assert message["sender_id"] == "player1"
    assert message["sender_name"] == "Alice"
    assert message["content"] == "Hello, ready to play?"
    assert message["game_phase"] == "setup"
    
    # Send another message
    response = client.post(
        f"/game/{game_id}/message",
        params={
            "sender_id": "player2",
            "sender_name": "Bob",
            "content": "Let's go!"
        }
    )
    assert response.status_code == 200
    
    # Get all messages
    response = client.get(f"/game/{game_id}/messages")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert len(data["messages"]) == 2
    assert data["messages"][0]["sender_name"] == "Alice"
    assert data["messages"][1]["sender_name"] == "Bob"


def test_messages_with_limit():
    """Test message retrieval with limit"""
    # Create game
    response = client.post("/game")
    game_id = response.json()["game_id"]
    
    # Send 5 messages
    for i in range(5):
        client.post(
            f"/game/{game_id}/message",
            params={
                "sender_id": f"player{i}",
                "sender_name": f"Player{i}",
                "content": f"Message {i}"
            }
        )
    
    # Get last 3 messages
    response = client.get(f"/game/{game_id}/messages", params={"limit": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    assert data["messages"][0]["content"] == "Message 2"
    assert data["messages"][2]["content"] == "Message 4"


def test_messages_with_turn_filter():
    """Test filtering messages by turn number"""
    # Create and setup game
    response = client.post("/game")
    game_id = response.json()["game_id"]
    
    # Setup teams
    client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team1", "team_type": "city_watch"},
        json={"constable": "3"}
    )
    client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team2", "team_type": "unseen_university"},
        json={"apprentice_wizard": "3"}
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
                "team1_player_1": {"x": 6, "y": 6},
                "team1_player_2": {"x": 6, "y": 8}
            }
        }
    )
    client.post(
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
    
    # Start game
    client.post(f"/game/{game_id}/start")
    
    # Send message during game (turn 0)
    client.post(
        f"/game/{game_id}/message",
        params={
            "sender_id": "team1",
            "sender_name": "Team 1",
            "content": "Turn 0 message"
        }
    )
    
    # Get messages for turn 0
    response = client.get(f"/game/{game_id}/messages", params={"turn_number": 0})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    assert any(m["content"] == "Turn 0 message" for m in data["messages"])


def test_reset_game():
    """Test resetting game to setup phase"""
    # Create and setup game
    response = client.post("/game")
    game_id = response.json()["game_id"]
    
    # Setup teams
    client.post(
        f"/game/{game_id}/setup-team",
        params={"team_id": "team1", "team_type": "city_watch"},
        json={"constable": "3"}
    )
    
    # Join teams
    client.post(f"/game/{game_id}/join", params={"team_id": "team1"})
    client.post(f"/game/{game_id}/join", params={"team_id": "team2"})
    
    # Send a message
    client.post(
        f"/game/{game_id}/message",
        params={
            "sender_id": "test",
            "sender_name": "Tester",
            "content": "Before reset"
        }
    )
    
    # Place players
    response = client.post(
        f"/game/{game_id}/place-players",
        json={
            "team_id": "team1",
            "positions": {
                "team1_player_0": {"x": 5, "y": 7}
            }
        }
    )
    
    # Verify game has players
    response = client.get(f"/game/{game_id}")
    data = response.json()
    assert len(data["players"]) > 0
    
    # Reset game
    response = client.post(f"/game/{game_id}/reset")
    assert response.status_code == 200
    data = response.json()
    
    # Verify reset state
    assert data["phase"] == "setup"
    assert data["game_started"] == False
    assert data["turn"] is None
    assert len(data["players"]) == 0
    
    # Verify join status preserved
    assert data["team1_joined"] == True
    assert data["team2_joined"] == True
    
    # Verify messages preserved
    response = client.get(f"/game/{game_id}/messages")
    messages_data = response.json()
    assert messages_data["count"] >= 1
    assert any(m["content"] == "Before reset" for m in messages_data["messages"])


def test_invalid_team_join():
    """Test joining with invalid team ID"""
    response = client.post("/game")
    game_id = response.json()["game_id"]
    
    response = client.post(
        f"/game/{game_id}/join",
        params={"team_id": "invalid_team"}
    )
    assert response.status_code == 400
