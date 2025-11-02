"""Entry point for Dockerised LLM agents controlling the MCP tools."""
from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from typing import Deque, Iterable

import httpx
from fastmcp.client import Client
from langchain_mcp import MCPToolkit
from langchain_openai import ChatOpenAI

from app.agents.config import AgentConfig
from app.agents.langgraph_agent import AgentStepResult, LangGraphMCPAgent


logger = logging.getLogger("app.agents")


class AgentMemory:
    """Bounded log of the agent's recent reasoning."""

    def __init__(self, capacity: int) -> None:
        self._entries: Deque[str] = deque(maxlen=capacity)

    def add(self, *entries: str) -> None:
        for entry in entries:
            clean = entry.strip()
            if clean:
                self._entries.append(clean)

    def render(self) -> str:
        if not self._entries:
            return "No previous turns recorded."

        numbered: Iterable[str] = (
            f"{idx + 1}. {value}"
            for idx, value in enumerate(self._entries)
        )
        return "\n".join(numbered)


def _build_system_prompt(config: AgentConfig) -> str:
    direction = (
        "increase the x coordinate by 1"
        if config.team_direction == 1
        else "decrease the x coordinate by 1"
    )

    return (
        "You are an autonomous coach for Ankh-Morpork Scramble. Your team id is "
        f"{config.team_id} and the current game id is {config.game_id}.\n"
        "Use the provided MCP tools to control your players.\n"
        "Workflow:\n"
        "1. If you have not yet joined, call join_game with the correct IDs.\n"
        "2. Every loop call get_game_state to understand the board and whose turn it is.\n"
        "3. When it is your turn, call get_valid_actions, pick the first movable "
        "player, and move them one square toward the opponent (" + direction + ").\n"
        "   Use execute_action with action_type='MOVE' and a target_position JSON object.\n"
        "4. Immediately call end_turn after a successful action.\n"
        "5. When it is not your turn, simply acknowledge `STATUS: WAITING`.\n"
        "Respond with a short status line such as `STATUS: ACTION_TAKEN` followed by "
        "a justification."
    )


async def _wait_for_server(base_url: str, timeout: float) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    async with httpx.AsyncClient() as client:
        while True:
            try:
                response = await client.get(base_url, timeout=5)
                if response.status_code < 500:
                    logger.info("Server at %s is ready", base_url)
                    return
            except Exception:
                pass

            if asyncio.get_event_loop().time() > deadline:
                raise RuntimeError(f"Server at {base_url} did not become ready in time")

            await asyncio.sleep(1)


def _summarize_game_state(state: dict, team_id: str) -> str:
    """Compress the HTTP game payload into a concise text summary."""

    phase = state.get("phase", "?")
    turn = state.get("turn") or {}
    half = turn.get("half", "-")
    turn_number = turn.get("team_turn", "-")
    active_team_id = turn.get("active_team_id")
    if active_team_id == team_id:
        active_team = f"{active_team_id} (our turn)"
    else:
        active_team = active_team_id or "none"

    pitch = state.get("pitch", {})
    ball_carrier = pitch.get("ball_carrier")
    ball_position = pitch.get("ball_position")
    if ball_carrier:
        ball_summary = f"ball carried by {ball_carrier}"
    elif ball_position:
        x, y = ball_position.get("x"), ball_position.get("y")
        ball_summary = f"ball on ground at ({x}, {y})"
    else:
        ball_summary = "ball off pitch"

    team1 = state.get("team1", {})
    team2 = state.get("team2", {})
    score_line = (
        f"{team1.get('name', 'team1')} {team1.get('score', 0)}"
        f" - {team2.get('score', 0)} {team2.get('name', 'team2')}"
    )

    events = state.get("event_log", [])
    recent_events = "; ".join(events[-3:]) if events else "no events yet"

    return (
        f"Phase={phase}; Half={half}; Turn={turn_number}; Active={active_team}; "
        f"Score={score_line}; {ball_summary}. Recent events: {recent_events}."
    )


def _compose_instruction(
    config: AgentConfig,
    joined: bool,
    state_summary: str,
    memory_text: str,
    require_action: bool,
    awaiting_end_turn: bool,
) -> str:
    base = [
        f"Game ID: {config.game_id}",
        f"Team ID: {config.team_id}",
        "Context from the referee:",
        state_summary,
        "Recent memory:",
        memory_text,
        "Always cite the tools you use when describing the result.",
    ]

    if not joined:
        base.append(
            "You have not joined yet. Call join_game exactly once, then confirm via "
            "get_game_state that your team_joined flag is true."
        )
    else:
        base.append(
            "Before anything else, call get_game_state to refresh the board and "
            "identify the active team."
        )
        if require_action:
            base.extend(
                [
                    "It is YOUR turn. Use get_valid_actions to inspect movable_players, "
                    "then move the first available player one square forward (x "
                    f"{'+' if config.team_direction == 1 else '-'} 1).",
                    "Submit the MOVE via execute_action and immediately end the turn "
                    "with end_turn.",
                ]
            )
        else:
            base.append(
                "If the active team is not yours, acknowledge STATUS: WAITING after "
                "confirming the turn information. Do not execute actions while waiting."
            )

    if awaiting_end_turn:
        base.append(
            "You already moved this turn. Call end_turn now so the opponent can play."
        )

    base.append("Summarise the outcome and include `STATUS:` in your reply.")
    return "\n".join(base)


def _log_step(result: AgentStepResult) -> None:
    if result.ai_message:
        logger.info("Assistant: %r", result.ai_message.content)
        if getattr(result.ai_message, "additional_kwargs", None):
            logger.info("Assistant metadata: %s", result.ai_message.additional_kwargs)
    if result.tool_calls:
        logger.info("Tools used: %s", ", ".join(result.tool_calls))
    for msg in result.new_messages:
        logger.debug("New message %s", msg)


async def _fetch_state(client: httpx.AsyncClient, config: AgentConfig) -> dict:
    response = await client.get(f"{config.http_base_url}/game/{config.game_id}", timeout=10)
    response.raise_for_status()
    return response.json()


async def run() -> None:
    log_level = os.getenv("AGENT_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
    config = AgentConfig.from_env()

    await _wait_for_server(config.http_base_url, config.startup_timeout)

    llm = ChatOpenAI(
        model=config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=0.2,
        default_headers={
            "HTTP-Referer": config.http_referer,
            "X-Title": config.app_title,
        },
    )

    async with httpx.AsyncClient() as http_client, Client(config.mcp_server_url) as client:
        toolkit = MCPToolkit(session=client.session)
        await toolkit.initialize()

        system_prompt = _build_system_prompt(config)
        agent = LangGraphMCPAgent(llm, toolkit.get_tools(), system_prompt=system_prompt)

        joined = False
        awaiting_end_turn = False
        memory = AgentMemory(config.memory_window)

        for step in range(config.max_steps):
            state = await _fetch_state(http_client, config)
            state_summary = _summarize_game_state(state, config.team_id)
            require_action = bool(
                joined
                and state.get("turn")
                and state["turn"].get("active_team_id") == config.team_id
            )

            instruction = _compose_instruction(
                config,
                joined,
                state_summary,
                memory.render(),
                require_action,
                awaiting_end_turn,
            )
            logger.info("Step %s instruction: %s", step + 1, instruction)
            result = await agent.step(instruction)
            _log_step(result)

            if result.ai_message:
                memory.add(result.ai_message.content)
            if result.tool_calls:
                memory.add("Tools used: " + ", ".join(result.tool_calls))

            if "join_game" in result.tool_calls:
                joined = True

            if "execute_action" in result.tool_calls:
                awaiting_end_turn = True

            if "end_turn" in result.tool_calls:
                awaiting_end_turn = False

            await asyncio.sleep(
                config.post_turn_delay if "end_turn" in result.tool_calls else config.poll_interval
            )


if __name__ == "__main__":
    asyncio.run(run())
