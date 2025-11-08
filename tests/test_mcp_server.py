"""Tests for MCP server integration"""
import logging
import pytest
from fastmcp.client import Client
from fastmcp.exceptions import ToolError
from app.mcp_server import mcp, use_reroll
from app.models.team import TeamType
from app.models.enums import ActionType
from app.models.pitch import Position


@pytest.fixture
def clean_manager():
    """Clean game manager before each test"""
    from app.main import game_manager
    game_manager.games.clear()
    return game_manager


@pytest.mark.asyncio
async def test_mcp_tools_are_registered():
    """Test that all expected MCP tools are registered"""
    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]

        # Verify all expected tools are present (10 original + 6 setup phase tools)
        expected_tools = [
            # Gameplay tools
            "join_game",
            "get_game_state",
            "get_valid_actions",
            "execute_action",
            "end_turn",
            "use_reroll",
            "get_history",
            "send_message",
            "get_messages",
            "suggest_path",
            # Setup phase tools
            "get_team_budget",
            "get_available_positions",
            "buy_player",
            "buy_reroll",
            "place_players",
            "ready_to_play"
        ]

        for tool in expected_tools:
            assert tool in tool_names, f"Tool '{tool}' not found in MCP server"

        assert len(tool_names) == len(expected_tools), \
            f"Expected {len(expected_tools)} tools, found {len(tool_names)}: {tool_names}"


@pytest.mark.asyncio
async def test_join_game_flow(clean_manager):
    """Test joining a game through MCP"""
    # Create a game first (coordinator action)
    game = clean_manager.create_game("test_game")
    
    # Set up teams (coordinator action)
    clean_manager.setup_team(
        "test_game",
        "team1",
        TeamType.CITY_WATCH,
        {"constable": "2"}
    )
    clean_manager.setup_team(
        "test_game",
        "team2",
        TeamType.CITY_WATCH,
        {"constable": "2"}
    )
    
    async with Client(mcp) as client:
        # Team 1 joins
        result = await client.call_tool(
            "join_game",
            {"game_id": "test_game", "team_id": "team1"}
        )
        
        assert result.data["success"] is True
        assert result.data["team_id"] == "team1"
        assert result.data["players_ready"] is False
        
        # Team 2 joins
        result = await client.call_tool(
            "join_game",
            {"game_id": "test_game", "team_id": "team2"}
        )
        
        # Both teams should now be ready
        game_state = clean_manager.get_game("test_game")
        assert game_state.players_ready is True


@pytest.mark.asyncio
async def test_join_game_starts_match(clean_manager):
    """Joining both teams should automatically start the game."""
    clean_manager.create_game("auto_game")
    clean_manager.setup_team("auto_game", "team1", TeamType.CITY_WATCH, {"constable": "2"})
    clean_manager.setup_team("auto_game", "team2", TeamType.CITY_WATCH, {"constable": "2"})

    clean_manager.place_players("auto_game", "team1", {
        "team1_player_0": Position(x=5, y=5),
        "team1_player_1": Position(x=6, y=5),
    })
    clean_manager.place_players("auto_game", "team2", {
        "team2_player_0": Position(x=10, y=10),
        "team2_player_1": Position(x=11, y=10),
    })

    async with Client(mcp) as client:
        await client.call_tool("join_game", {"game_id": "auto_game", "team_id": "team1"})
        await client.call_tool("join_game", {"game_id": "auto_game", "team_id": "team2"})

    game_state = clean_manager.get_game("auto_game")
    assert game_state.game_started is True
    assert game_state.turn is not None


@pytest.mark.asyncio
async def test_join_game_invalid_game_id(clean_manager):
    """Test joining a non-existent game"""
    async with Client(mcp) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool(
                "join_game",
                {"game_id": "nonexistent", "team_id": "team1"}
            )
        
        assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_join_game_invalid_team_id(clean_manager):
    """Test joining with invalid team ID"""
    clean_manager.create_game("test_game")
    
    async with Client(mcp) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool(
                "join_game",
                {"game_id": "test_game", "team_id": "invalid_team"}
            )
        
        assert "invalid" in str(exc_info.value).lower()


def test_use_reroll_logs_stack_trace(clean_manager, caplog):
    """`use_reroll` should log a stack trace when reroll usage fails."""
    clean_manager.create_game("log_game")

    with caplog.at_level(logging.ERROR, logger="app.mcp_server"):
        with pytest.raises(ToolError) as exc_info:
            use_reroll.fn("log_game", "team1")

    assert "Failed to use reroll" in str(exc_info.value)
    log_messages = [record.getMessage() for record in caplog.records]
    assert any("Failed to use reroll" in message for message in log_messages)
    assert any(record.exc_info for record in caplog.records)


@pytest.mark.asyncio
async def test_get_game_state(clean_manager):
    """Test retrieving game state through MCP"""
    game = clean_manager.create_game("test_game")
    
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_game_state",
            {"game_id": "test_game"}
        )
        
        # Result should contain GameState data
        state = result.data
        assert state["game_id"] == "test_game"
        assert "team1" in state
        assert "team2" in state
        assert "pitch" in state


@pytest.mark.asyncio
async def test_get_valid_actions_before_game_starts(clean_manager):
    """Test that valid_actions fails before game starts"""
    clean_manager.create_game("test_game")
    
    async with Client(mcp) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool(
                "get_valid_actions",
                {"game_id": "test_game"}
            )
        
        assert "not started" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_valid_actions_during_game(clean_manager):
    """Test retrieving valid actions during active game"""
    # Set up and start a game
    game = clean_manager.create_game("test_game")
    clean_manager.setup_team("test_game", "team1", TeamType.CITY_WATCH, {"constable": "2"})
    clean_manager.setup_team("test_game", "team2", TeamType.CITY_WATCH, {"constable": "2"})
    
    # Mark teams as joined
    game = clean_manager.get_game("test_game")
    game.team1_joined = True
    game.team2_joined = True
    
    # Mark teams as joined
    game.team1_joined = True
    game.team2_joined = True
    
    # Place players
    clean_manager.place_players("test_game", "team1", {
        "team1_player_0": Position(x=5, y=5),
        "team1_player_1": Position(x=6, y=5)
    })
    clean_manager.place_players("test_game", "team2", {
        "team2_player_0": Position(x=10, y=10),
        "team2_player_1": Position(x=11, y=10)
    })
    
    clean_manager.start_game("test_game")
    
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_valid_actions",
            {"game_id": "test_game"}
        )
        
        # Access data using attributes (Root object from MCP)
        actions = result.data
        assert hasattr(actions, "current_team")
        assert hasattr(actions, "movable_players")
        assert actions.can_charge is True  # First turn, everything available
        assert actions.can_hurl is True


@pytest.mark.asyncio
async def test_execute_action_not_your_turn(clean_manager):
    """Test that execute_action prevents acting out of turn"""
    # Set up and start a game
    clean_manager.create_game("test_game")
    clean_manager.setup_team("test_game", "team1", TeamType.CITY_WATCH, {"constable": "1"})
    clean_manager.setup_team("test_game", "team2", TeamType.CITY_WATCH, {"constable": "1"})
    
    # Mark teams as joined
    game = clean_manager.get_game("test_game")
    game.team1_joined = True
    game.team2_joined = True
    
    clean_manager.place_players("test_game", "team1", {
        "team1_player_0": Position(x=5, y=5)
    })
    clean_manager.place_players("test_game", "team2", {
        "team2_player_0": Position(x=10, y=10)
    })
    
    game = clean_manager.start_game("test_game")
    
    # Determine which team is NOT active
    active_team_id = game.get_active_team().id
    inactive_player = "team2_player_0" if active_team_id == "team1" else "team1_player_0"
    
    async with Client(mcp) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool(
                "execute_action",
                {
                    "game_id": "test_game",
                    "action_type": ActionType.MOVE.value,
                    "player_id": inactive_player,
                    "target_position": {"x": 6, "y": 6}
                }
            )
        
        assert "not your turn" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_execute_move_action(clean_manager):
    """Test executing a move action through MCP"""
    # Set up and start a game
    clean_manager.create_game("test_game")
    clean_manager.setup_team("test_game", "team1", TeamType.CITY_WATCH, {"constable": "1"})
    clean_manager.setup_team("test_game", "team2", TeamType.CITY_WATCH, {"constable": "1"})
    
    # Mark teams as joined
    game = clean_manager.get_game("test_game")
    game.team1_joined = True
    game.team2_joined = True
    
    clean_manager.place_players("test_game", "team1", {
        "team1_player_0": Position(x=5, y=5)
    })
    clean_manager.place_players("test_game", "team2", {
        "team2_player_0": Position(x=10, y=10)
    })
    
    game = clean_manager.start_game("test_game")
    active_team_id = game.get_active_team().id
    active_player = f"{active_team_id}_player_0"
    
    async with Client(mcp) as client:
        result = await client.call_tool(
            "execute_action",
            {
                "game_id": "test_game",
                "action_type": ActionType.MOVE.value,
                "player_id": active_player,
                "target_position": {"x": 6, "y": 5},
                "path": [{"x": 6, "y": 5}]  # Movement requires path
            }
        )
        
        # Access data using attributes (Root object from MCP)
        action_result = result.data
        assert action_result.success is True
        assert action_result.player_moved == active_player


@pytest.mark.asyncio
async def test_end_turn(clean_manager):
    """Test ending a turn through MCP"""
    # Set up and start a game
    clean_manager.create_game("test_game")
    clean_manager.setup_team("test_game", "team1", TeamType.CITY_WATCH, {"constable": "1"})
    clean_manager.setup_team("test_game", "team2", TeamType.CITY_WATCH, {"constable": "1"})
    
    # Mark teams as joined
    game = clean_manager.get_game("test_game")
    game.team1_joined = True
    game.team2_joined = True
    
    clean_manager.place_players("test_game", "team1", {
        "team1_player_0": Position(x=5, y=5)
    })
    clean_manager.place_players("test_game", "team2", {
        "team2_player_0": Position(x=10, y=10)
    })
    
    game = clean_manager.start_game("test_game")
    initial_active_team = game.get_active_team().id
    
    async with Client(mcp) as client:
        result = await client.call_tool(
            "end_turn",
            {
                "game_id": "test_game",
                "team_id": initial_active_team
            }
        )
        
        assert result.data["success"] is True
        assert result.data["turn_ended"] == initial_active_team
        assert result.data["new_active_team"] != initial_active_team


@pytest.mark.asyncio
async def test_end_turn_not_your_turn(clean_manager):
    """Test that you can't end another team's turn"""
    # Set up and start a game
    clean_manager.create_game("test_game")
    clean_manager.setup_team("test_game", "team1", TeamType.CITY_WATCH, {"constable": "1"})
    clean_manager.setup_team("test_game", "team2", TeamType.CITY_WATCH, {"constable": "1"})
    
    # Mark teams as joined
    game = clean_manager.get_game("test_game")
    game.team1_joined = True
    game.team2_joined = True
    
    clean_manager.place_players("test_game", "team1", {
        "team1_player_0": Position(x=5, y=5)
    })
    clean_manager.place_players("test_game", "team2", {
        "team2_player_0": Position(x=10, y=10)
    })
    
    game = clean_manager.start_game("test_game")
    active_team_id = game.get_active_team().id
    inactive_team_id = "team2" if active_team_id == "team1" else "team1"
    
    async with Client(mcp) as client:
        with pytest.raises(Exception) as exc_info:
            await client.call_tool(
                "end_turn",
                {
                    "game_id": "test_game",
                    "team_id": inactive_team_id
                }
            )
        
        assert "not your turn" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_send_and_get_messages(clean_manager):
    """Test sending and retrieving messages through MCP"""
    clean_manager.create_game("test_game")
    
    async with Client(mcp) as client:
        # Send a message
        result = await client.call_tool(
            "send_message",
            {
                "game_id": "test_game",
                "sender_id": "team1",
                "sender_name": "Watch Commander",
                "content": "Good luck!"
            }
        )
        
        assert result.data["success"] is True
        assert "message" in result.data
        
        # Get messages
        result = await client.call_tool(
            "get_messages",
            {"game_id": "test_game"}
        )
        
        messages = result.data
        assert messages["count"] == 1
        assert len(messages["messages"]) == 1
        assert messages["messages"][0]["content"] == "Good luck!"
        assert messages["messages"][0]["sender_name"] == "Watch Commander"


@pytest.mark.asyncio
async def test_get_messages_with_limit(clean_manager):
    """Test getting messages with limit"""
    clean_manager.create_game("test_game")
    game = clean_manager.get_game("test_game")
    
    # Add multiple messages
    for i in range(5):
        game.add_message("team1", "Player", f"Message {i}")
    
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_messages",
            {"game_id": "test_game", "limit": 3}
        )
        
        messages = result.data
        assert messages["count"] == 3
        assert len(messages["messages"]) == 3
        # Should get the last 3 messages
        assert messages["messages"][0]["content"] == "Message 2"
        assert messages["messages"][2]["content"] == "Message 4"


@pytest.mark.asyncio
async def test_get_history(clean_manager):
    """Test getting game history through MCP"""
    # Create and set up a game
    clean_manager.create_game("test_game")
    clean_manager.setup_team("test_game", "team1", TeamType.CITY_WATCH, {"constable": "1"})
    
    game = clean_manager.get_game("test_game")
    game.add_event("Test event 1")
    game.add_event("Test event 2")
    
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_history",
            {"game_id": "test_game", "limit": 10}
        )
        
        history = result.data
        assert "events" in history
        assert "total_events" in history
        assert len(history["events"]) > 0
        # Our custom events should be in there
        assert "Test event 1" in history["events"]
        assert "Test event 2" in history["events"]


@pytest.mark.asyncio
async def test_use_reroll(clean_manager):
    """Test using a reroll through MCP"""
    clean_manager.create_game("test_game")
    clean_manager.setup_team("test_game", "team1", TeamType.CITY_WATCH, {"constable": "1"})

    # Buy a reroll first (teams start with 0 rerolls now)
    clean_manager.buy_reroll("test_game", "team1")

    game = clean_manager.get_game("test_game")
    initial_rerolls = game.team1.rerolls_remaining
    assert initial_rerolls == 1  # Should have 1 reroll after purchase

    async with Client(mcp) as client:
        result = await client.call_tool(
            "use_reroll",
            {"game_id": "test_game", "team_id": "team1"}
        )

        assert result.data["success"] is True
        assert result.data["rerolls_remaining"] == initial_rerolls - 1


@pytest.mark.asyncio
async def test_integration_two_llm_agents_playing(clean_manager):
    """Integration test: simulate two LLM agents playing"""
    # Coordinator sets up the game
    clean_manager.create_game("test_game")
    clean_manager.setup_team("test_game", "team1", TeamType.CITY_WATCH, {"constable": "1"})
    clean_manager.setup_team("test_game", "team2", TeamType.CITY_WATCH, {"constable": "1"})
    
    # Mark teams as joined
    game = clean_manager.get_game("test_game")
    game.team1_joined = True
    game.team2_joined = True
    
    clean_manager.place_players("test_game", "team1", {
        "team1_player_0": Position(x=5, y=5)
    })
    clean_manager.place_players("test_game", "team2", {
        "team2_player_0": Position(x=10, y=10)
    })
    
    clean_manager.start_game("test_game")
    
    # Simulate LLM agents connecting and playing
    async with Client(mcp) as client1, Client(mcp) as client2:
        # Both agents join
        await client1.call_tool("join_game", {"game_id": "test_game", "team_id": "team1"})
        await client2.call_tool("join_game", {"game_id": "test_game", "team_id": "team2"})
        
        # Get game state
        state_result = await client1.call_tool("get_game_state", {"game_id": "test_game"})
        state = state_result.data
        assert state["team1_joined"] is True
        assert state["team2_joined"] is True
        
        # Active team checks valid actions
        active_team = state["turn"]["active_team_id"]
        active_client = client1 if active_team == "team1" else client2
        active_player = f"{active_team}_player_0"
        
        actions_result = await active_client.call_tool(
            "get_valid_actions",
            {"game_id": "test_game"}
        )
        # Access data using attributes (Root object from MCP)
        actions = actions_result.data
        assert active_player in actions.movable_players
        
        # Active team sends a message
        await active_client.call_tool(
            "send_message",
            {
                "game_id": "test_game",
                "sender_id": active_team,
                "sender_name": f"{active_team} Agent",
                "content": "Let's play!"
            }
        )
        
        # Other team can read the message
        inactive_client = client2 if active_team == "team1" else client1
        messages_result = await inactive_client.call_tool(
            "get_messages",
            {"game_id": "test_game"}
        )
        assert messages_result.data["count"] > 0
        
        # Active team makes a move
        move_result = await active_client.call_tool(
            "execute_action",
            {
                "game_id": "test_game",
                "action_type": ActionType.MOVE.value,
                "player_id": active_player,
                "target_position": {"x": 6, "y": 5},
                "path": [{"x": 6, "y": 5}]  # Movement requires path
            }
        )
        assert move_result.data.success is True
        
        # Active team ends turn
        end_result = await active_client.call_tool(
            "end_turn",
            {"game_id": "test_game", "team_id": active_team}
        )
        assert end_result.data["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
