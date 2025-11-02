import pytest
from fastmcp.client import Client
import pytest
from fastmcp.client import Client
from langchain_mcp import MCPToolkit
from langchain_core.messages import AIMessage, ToolCall

from app.agents.config import AgentConfig
from app.agents.langgraph_agent import LangGraphMCPAgent
from app.agents.run_agent import AgentMemory, _compose_instruction, _summarize_game_state
from app.mcp_server import mcp
from app.setup.default_game import bootstrap_default_game


class DummyLLM:
    def __init__(self, responses):
        self.responses = responses
        self.index = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages, **kwargs):  # pragma: no cover - signature compat
        response = self.responses[self.index]
        self.index += 1
        return response


@pytest.fixture
def clean_manager():
    from app.main import game_manager

    game_manager.games.clear()
    return game_manager


@pytest.mark.asyncio
async def test_langgraph_agent_joins_game(clean_manager):
    bootstrap_default_game(clean_manager, game_id="agent-test")

    async with Client(mcp) as client:
        toolkit = MCPToolkit(session=client.session)
        await toolkit.initialize()
        tools = toolkit.get_tools()

        join_call = ToolCall(
            name="join_game",
            args={"game_id": "agent-test", "team_id": "team1"},
            id="call-1",
        )

        responses = [
            AIMessage(content="joining", tool_calls=[join_call]),
            AIMessage(content="STATUS: WAITING"),
        ]

        agent = LangGraphMCPAgent(DummyLLM(responses), tools, system_prompt="test")
        result = await agent.step("Join the match")

        assert "join_game" in result.tool_calls
        assert clean_manager.get_game("agent-test").team1_joined is True


def test_agent_memory_tracks_recent_entries():
    memory = AgentMemory(capacity=2)
    memory.add("First", "Second")
    memory.add("Third")

    rendered = memory.render()

    assert "1. Second" in rendered
    assert "2. Third" in rendered
    assert "First" not in rendered


def test_summarize_game_state_highlights_active_team():
    state = {
        "phase": "PLAYING",
        "turn": {"half": 1, "team_turn": 4, "active_team_id": "team2"},
        "pitch": {"ball_carrier": None, "ball_position": {"x": 13, "y": 5}},
        "team1": {"name": "Watch", "score": 1},
        "team2": {"name": "Wizards", "score": 0},
        "event_log": ["Kick-off", "team1 scored"],
    }

    summary = _summarize_game_state(state, team_id="team1")

    assert "PLAYING" in summary
    assert "Turn=4" in summary
    assert "Active=team2" in summary
    assert "ball on ground at (13, 5)" in summary
    assert "Watch 1 - 0 Wizards" in summary


def test_compose_instruction_requires_action_for_active_team():
    config = AgentConfig(
        team_id="team1",
        team_name="Watch",
        game_id="demo",
        mcp_server_url="http://localhost:8000/mcp",
        model="openrouter/test",
        api_key="fake",
        base_url="https://example.com",
        http_referer="https://example.com",
        app_title="Test",
        join_retry_delay=1.0,
        poll_interval=1.0,
        post_turn_delay=1.0,
        startup_timeout=10.0,
        max_steps=1,
        memory_window=3,
    )

    instruction = _compose_instruction(
        config,
        joined=True,
        state_summary="Phase=PLAYING",
        memory_text="1. Did something",
        require_action=True,
        awaiting_end_turn=False,
    )

    assert "It is YOUR turn" in instruction
    assert "get_valid_actions" in instruction
    assert "execute_action" in instruction
    assert "end_turn" in instruction
