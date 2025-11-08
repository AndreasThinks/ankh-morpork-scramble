"""Tests for setup phase with budget management"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.state.game_manager import GameManager
from app.models.enums import TeamType, GamePhase
from app.models.team import Team, TEAM_ROSTERS


client = TestClient(app)


# ============================================================================
# Team Model Budget Tests
# ============================================================================

def test_team_initial_budget():
    """Test team starts with correct initial budget"""
    team = Team(id="test", name="Test Team", team_type=TeamType.CITY_WATCH)

    assert team.budget_initial == 1_000_000
    assert team.budget_spent == 0
    assert team.budget_remaining == 1_000_000
    assert len(team.purchase_history) == 0


def test_team_can_afford():
    """Test can_afford method"""
    team = Team(id="test", name="Test Team", team_type=TeamType.CITY_WATCH)

    assert team.can_afford(50000) is True
    assert team.can_afford(1_000_000) is True
    assert team.can_afford(1_000_001) is False


def test_team_purchase_player():
    """Test purchasing a player updates budget correctly"""
    team = Team(id="test", name="Test Team", team_type=TeamType.CITY_WATCH)

    team.purchase_player("Constable", 50000)

    assert team.budget_spent == 50000
    assert team.budget_remaining == 950_000
    assert len(team.purchase_history) == 1
    assert "Player: Constable" in team.purchase_history[0]
    assert "50000g" in team.purchase_history[0]


def test_team_purchase_multiple_items():
    """Test purchasing multiple items accumulates correctly"""
    team = Team(id="test", name="Test Team", team_type=TeamType.CITY_WATCH)

    team.purchase_player("Constable", 50000)
    team.purchase_player("Constable", 50000)
    team.purchase_reroll(50000)

    assert team.budget_spent == 150_000
    assert team.budget_remaining == 850_000
    assert len(team.purchase_history) == 3
    assert team.rerolls_total == 1


def test_team_purchase_exceeds_budget():
    """Test purchasing when insufficient funds raises error"""
    team = Team(id="test", name="Test Team", team_type=TeamType.CITY_WATCH)
    team.budget_spent = 950_000  # Only 50k left

    with pytest.raises(ValueError, match="Insufficient funds"):
        team.purchase_player("Clerk-Runner", 80000)


def test_team_purchase_reroll_limit():
    """Test purchasing rerolls enforces maximum limit"""
    team = Team(id="test", name="Test Team", team_type=TeamType.CITY_WATCH)

    # Buy 8 rerolls (the maximum)
    for i in range(8):
        team.purchase_reroll(50000)

    assert team.rerolls_total == 8

    # Try to buy 9th reroll
    with pytest.raises(ValueError, match="Cannot exceed maximum"):
        team.purchase_reroll(50000)


def test_team_purchase_history_tracking():
    """Test purchase history is tracked correctly"""
    team = Team(id="test", name="Test Team", team_type=TeamType.CITY_WATCH)

    team.purchase_player("Constable", 50000)
    team.purchase_player("Clerk-Runner", 80000)
    team.purchase_reroll(50000)

    assert len(team.purchase_history) == 3
    assert "Player: Constable (50000g)" in team.purchase_history
    assert "Player: Clerk-Runner (80000g)" in team.purchase_history
    assert "Team Reroll (50000g)" in team.purchase_history


# ============================================================================
# GameManager Budget and Purchase Tests
# ============================================================================

def test_get_budget_status():
    """Test getting budget status for a team"""
    manager = GameManager()
    game = manager.create_game("test_game")

    budget = manager.get_budget_status("test_game", "team1")

    assert budget.initial == 1_000_000
    assert budget.spent == 0
    assert budget.remaining == 1_000_000
    assert len(budget.purchases) == 0


def test_get_available_positions_city_watch():
    """Test getting available positions for City Watch"""
    manager = GameManager()
    game = manager.create_game("test_game")

    available = manager.get_available_positions("test_game", "team1")

    assert available.team_id == "team1"
    assert available.team_type == "city_watch"
    assert len(available.positions) == 9  # 9 City Watch positions

    # Check constable details
    constable = next(p for p in available.positions if p.position_key == "constable")
    assert constable.role == "Constable"
    assert constable.cost == 50000
    assert constable.quantity_limit == 16
    assert constable.quantity_owned == 0
    assert constable.can_afford is True

    # Check reroll info
    assert available.reroll_cost == 50000
    assert available.rerolls_max == 8
    assert available.can_afford_reroll is True


def test_get_available_positions_unseen_university():
    """Test getting available positions for Unseen University"""
    manager = GameManager()
    game = manager.create_game("test_game")
    game.team2.team_type = TeamType.UNSEEN_UNIVERSITY

    available = manager.get_available_positions("test_game", "team2")

    assert available.team_type == "unseen_university"
    assert len(available.positions) == 9  # 9 UU positions

    # Check gargoyle details
    gargoyle = next(p for p in available.positions if p.position_key == "animated_gargoyle")
    assert gargoyle.role == "Animated Gargoyle"
    assert gargoyle.cost == 115000
    assert gargoyle.quantity_limit == 1  # Only 1 allowed

    # Check reroll cost is higher for UU
    assert available.reroll_cost == 60000


def test_buy_player_success():
    """Test successfully buying a player"""
    manager = GameManager()
    game = manager.create_game("test_game")

    result = manager.buy_player("test_game", "team1", "constable")

    assert result.success is True
    assert result.cost == 50000
    assert result.budget_status.spent == 50000
    assert result.budget_status.remaining == 950_000
    assert "Constable" in result.item_purchased

    # Check player was created
    assert len(game.team1.player_ids) == 1
    player_id = game.team1.player_ids[0]
    assert player_id in game.players
    assert game.players[player_id].position.role == "Constable"


def test_buy_multiple_players():
    """Test buying multiple players"""
    manager = GameManager()
    game = manager.create_game("test_game")

    # Buy 5 constables
    for i in range(5):
        result = manager.buy_player("test_game", "team1", "constable")
        assert result.success is True

    assert len(game.team1.player_ids) == 5
    assert game.team1.budget_spent == 250_000
    assert game.team1.budget_remaining == 750_000


def test_buy_different_player_types():
    """Test buying different types of players"""
    manager = GameManager()
    game = manager.create_game("test_game")

    manager.buy_player("test_game", "team1", "constable")
    manager.buy_player("test_game", "team1", "clerk_runner")
    manager.buy_player("test_game", "team1", "fleet_recruit")

    assert len(game.team1.player_ids) == 3

    # Check different player types were created
    players = [game.players[pid] for pid in game.team1.player_ids]
    roles = [p.position.role for p in players]
    assert "Constable" in roles
    assert "Clerk-Runner" in roles
    assert "Fleet Recruit" in roles


def test_buy_player_exceeds_position_limit():
    """Test buying more than position limit fails"""
    manager = GameManager()
    game = manager.create_game("test_game")

    # Clerk-Runner limit is 2
    manager.buy_player("test_game", "team1", "clerk_runner")
    manager.buy_player("test_game", "team1", "clerk_runner")

    # Try to buy 3rd
    with pytest.raises(ValueError, match="Cannot exceed limit"):
        manager.buy_player("test_game", "team1", "clerk_runner")


def test_buy_player_exceeds_budget():
    """Test buying player when insufficient funds fails"""
    manager = GameManager()
    game = manager.create_game("test_game")

    # Buy mix of players to drain budget without hitting position limits
    # 16 constables (max) + 2 clerks (max) + 1 gargoyle... wait, wrong team
    # Let's use: 16 constables + 2 clerk-runners + 4 fleet recruits + 4 sergeants
    # That's 26 players * ~65k average = way over budget

    # Actually, let's just buy 10 watch sergeants (10 * 85k = 850k)
    # Leaves 150k, then try to buy animated gargoyle (115k) which is wrong team type
    # Better: buy expensive players to drain budget
    for i in range(11):  # 11 * 85k = 935k
        manager.buy_player("test_game", "team1", "watch_sergeant")  # 85k each, max 4
        if i >= 3:  # After 4th sergeant, switch to clerk-runners
            break

    # After 4 sergeants (340k), buy clerk-runners
    for i in range(2):  # 2 * 80k = 160k (total 500k)
        manager.buy_player("test_game", "team1", "clerk_runner")

    # Buy fleet recruits
    for i in range(4):  # 4 * 65k = 260k (total 760k)
        manager.buy_player("test_game", "team1", "fleet_recruit")

    # Buy constables to get close to budget limit
    for i in range(4):  # 4 * 50k = 200k (total 960k)
        manager.buy_player("test_game", "team1", "constable")

    # Now only 40k left, can't afford 50k constable
    with pytest.raises(ValueError, match="Insufficient funds"):
        manager.buy_player("test_game", "team1", "constable")


def test_buy_player_invalid_position():
    """Test buying invalid position fails"""
    manager = GameManager()
    game = manager.create_game("test_game")

    with pytest.raises(ValueError, match="Invalid position"):
        manager.buy_player("test_game", "team1", "invalid_position")


def test_buy_player_wrong_team_position():
    """Test buying position from wrong team fails"""
    manager = GameManager()
    game = manager.create_game("test_game")
    game.team1.team_type = TeamType.CITY_WATCH

    with pytest.raises(ValueError, match="Invalid position"):
        manager.buy_player("test_game", "team1", "apprentice_wizard")


def test_buy_player_only_in_setup_phase():
    """Test buying players only allowed in setup phase"""
    manager = GameManager()
    game = manager.create_game("test_game")

    # Move to different phase
    game.phase = GamePhase.ACTIVE_PLAY

    with pytest.raises(ValueError, match="only purchase players during deployment"):
        manager.buy_player("test_game", "team1", "constable")


def test_buy_reroll_success():
    """Test successfully buying a reroll"""
    manager = GameManager()
    game = manager.create_game("test_game")

    result = manager.buy_reroll("test_game", "team1")

    assert result.success is True
    assert result.cost == 50000  # City Watch reroll cost
    assert result.budget_status.spent == 50000
    assert result.budget_status.remaining == 950_000
    assert game.team1.rerolls_total == 1


def test_buy_multiple_rerolls():
    """Test buying multiple rerolls"""
    manager = GameManager()
    game = manager.create_game("test_game")

    for i in range(3):
        result = manager.buy_reroll("test_game", "team1")
        assert result.success is True

    assert game.team1.rerolls_total == 3
    assert game.team1.budget_spent == 150_000


def test_buy_reroll_different_team_costs():
    """Test reroll costs differ by team type"""
    manager = GameManager()
    game = manager.create_game("test_game")

    # City Watch rerolls cost 50k
    result1 = manager.buy_reroll("test_game", "team1")
    assert result1.cost == 50000

    # Unseen University rerolls cost 60k
    game.team2.team_type = TeamType.UNSEEN_UNIVERSITY
    result2 = manager.buy_reroll("test_game", "team2")
    assert result2.cost == 60000


def test_buy_reroll_exceeds_limit():
    """Test buying more than 8 rerolls fails"""
    manager = GameManager()
    game = manager.create_game("test_game")

    # Buy maximum 8
    for i in range(8):
        manager.buy_reroll("test_game", "team1")

    # Try to buy 9th
    with pytest.raises(ValueError, match="Cannot exceed maximum"):
        manager.buy_reroll("test_game", "team1")


def test_buy_reroll_only_in_setup_phase():
    """Test buying rerolls only allowed in setup phase"""
    manager = GameManager()
    game = manager.create_game("test_game")
    game.phase = GamePhase.ACTIVE_PLAY

    with pytest.raises(ValueError, match="only purchase rerolls during deployment"):
        manager.buy_reroll("test_game", "team1")


def test_complete_roster_purchase():
    """Test purchasing a complete roster"""
    manager = GameManager()
    game = manager.create_game("test_game")

    # Buy a full team
    for i in range(5):
        manager.buy_player("test_game", "team1", "constable")
    manager.buy_player("test_game", "team1", "clerk_runner")
    for i in range(2):
        manager.buy_player("test_game", "team1", "fleet_recruit")
    for i in range(3):
        manager.buy_player("test_game", "team1", "watch_sergeant")

    # Buy rerolls
    for i in range(3):
        manager.buy_reroll("test_game", "team1")

    # Check final state
    assert len(game.team1.player_ids) == 11
    assert game.team1.rerolls_total == 3

    # Calculate expected cost
    expected_cost = (5 * 50000) + 80000 + (2 * 65000) + (3 * 85000) + (3 * 50000)
    assert game.team1.budget_spent == expected_cost
    assert game.team1.budget_remaining == 1_000_000 - expected_cost


# ============================================================================
# REST API Endpoint Tests
# ============================================================================

def test_api_get_team_budget():
    """Test GET /game/{game_id}/team/{team_id}/budget"""
    # Create game
    response = client.post("/game")
    game_id = response.json()["game_id"]

    # Get budget
    response = client.get(f"/game/{game_id}/team/team1/budget")
    assert response.status_code == 200

    data = response.json()
    assert data["initial"] == 1_000_000
    assert data["spent"] == 0
    assert data["remaining"] == 1_000_000
    assert data["purchases"] == []


def test_api_get_available_positions():
    """Test GET /game/{game_id}/team/{team_id}/available-positions"""
    # Create game
    response = client.post("/game")
    game_id = response.json()["game_id"]

    # Get available positions
    response = client.get(f"/game/{game_id}/team/team1/available-positions")
    assert response.status_code == 200

    data = response.json()
    assert data["team_id"] == "team1"
    assert data["team_type"] == "city_watch"
    assert len(data["positions"]) == 9
    assert data["reroll_cost"] == 50000
    assert data["can_afford_reroll"] is True


def test_api_buy_player():
    """Test POST /game/{game_id}/team/{team_id}/buy-player"""
    # Create game
    response = client.post("/game")
    game_id = response.json()["game_id"]

    # Buy player
    response = client.post(
        f"/game/{game_id}/team/team1/buy-player",
        params={"position_key": "constable"}
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["cost"] == 50000
    assert "Constable" in data["item_purchased"]
    assert data["budget_status"]["spent"] == 50000
    assert data["budget_status"]["remaining"] == 950_000


def test_api_buy_player_invalid_position():
    """Test buying invalid position returns error"""
    response = client.post("/game")
    game_id = response.json()["game_id"]

    response = client.post(
        f"/game/{game_id}/team/team1/buy-player",
        params={"position_key": "invalid"}
    )
    assert response.status_code == 400


def test_api_buy_reroll():
    """Test POST /game/{game_id}/team/{team_id}/buy-reroll"""
    # Create game
    response = client.post("/game")
    game_id = response.json()["game_id"]

    # Buy reroll
    response = client.post(f"/game/{game_id}/team/team1/buy-reroll")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["cost"] == 50000
    assert "Team Reroll" in data["item_purchased"]
    assert data["budget_status"]["spent"] == 50000


def test_api_full_team_purchase_flow():
    """Test complete team purchase workflow via API"""
    # Create game
    response = client.post("/game")
    game_id = response.json()["game_id"]

    # Check initial budget
    response = client.get(f"/game/{game_id}/team/team1/budget")
    initial_budget = response.json()
    assert initial_budget["remaining"] == 1_000_000
    assert initial_budget["spent"] == 0

    # Buy several players
    positions_to_buy = [
        "constable",
        "constable",
        "constable",
        "clerk_runner",
        "fleet_recruit",
    ]

    for position in positions_to_buy:
        response = client.post(
            f"/game/{game_id}/team/team1/buy-player",
            params={"position_key": position}
        )
        assert response.status_code == 200

    # Buy rerolls
    for i in range(2):
        response = client.post(f"/game/{game_id}/team/team1/buy-reroll")
        assert response.status_code == 200

    # Check final budget
    response = client.get(f"/game/{game_id}/team/team1/budget")
    final_budget = response.json()

    # Calculate expected cost: 3 constables + 1 clerk-runner + 1 fleet recruit + 2 rerolls
    expected_cost = (3 * 50000) + 80000 + 65000 + (2 * 50000)
    assert final_budget["spent"] == expected_cost
    assert final_budget["remaining"] == 1_000_000 - expected_cost
    assert len(final_budget["purchases"]) == 7

    # Check game state - players and rerolls should be correctly created
    response = client.get(f"/game/{game_id}")
    game_state = response.json()
    assert len(game_state["team1"]["player_ids"]) == 5  # 5 players purchased
    # Teams start with 0 rerolls, we purchased 2
    assert game_state["team1"]["rerolls_total"] == 2


def test_api_available_positions_updates_after_purchase():
    """Test available positions reflects purchases"""
    response = client.post("/game")
    game_id = response.json()["game_id"]

    # Check initial state
    response = client.get(f"/game/{game_id}/team/team1/available-positions")
    positions_before = response.json()
    constable_before = next(p for p in positions_before["positions"] if p["position_key"] == "constable")
    assert constable_before["quantity_owned"] == 0

    # Buy a constable
    client.post(f"/game/{game_id}/team/team1/buy-player", params={"position_key": "constable"})

    # Check updated state
    response = client.get(f"/game/{game_id}/team/team1/available-positions")
    positions_after = response.json()
    constable_after = next(p for p in positions_after["positions"] if p["position_key"] == "constable")
    assert constable_after["quantity_owned"] == 1
    assert positions_after["budget_status"]["spent"] == 50000


def test_api_budget_enforcement():
    """Test API enforces budget constraints"""
    response = client.post("/game")
    game_id = response.json()["game_id"]

    # Buy mix of players to drain budget: 4 sergeants + 2 clerks + 4 fleet + 4 constables
    # 4*85k + 2*80k + 4*65k + 4*50k = 340 + 160 + 260 + 200 = 960k spent

    for i in range(4):
        response = client.post(
            f"/game/{game_id}/team/team1/buy-player",
            params={"position_key": "watch_sergeant"}
        )
        assert response.status_code == 200

    for i in range(2):
        response = client.post(
            f"/game/{game_id}/team/team1/buy-player",
            params={"position_key": "clerk_runner"}
        )
        assert response.status_code == 200

    for i in range(4):
        response = client.post(
            f"/game/{game_id}/team/team1/buy-player",
            params={"position_key": "fleet_recruit"}
        )
        assert response.status_code == 200

    for i in range(4):
        response = client.post(
            f"/game/{game_id}/team/team1/buy-player",
            params={"position_key": "constable"}
        )
        assert response.status_code == 200

    # Now only 40k left, can't afford 50k constable
    response = client.post(
        f"/game/{game_id}/team/team1/buy-player",
        params={"position_key": "constable"}
    )
    assert response.status_code == 400
    assert "Insufficient funds" in response.json()["detail"]
