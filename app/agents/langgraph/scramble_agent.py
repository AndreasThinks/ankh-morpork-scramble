"""
React-based agent for playing Ankh-Morpork Scramble.

Uses LangChain's create_react_agent pattern with MCP tools.
Adapted from ai-at-risk's RiskAgent implementation.
"""

import os
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

from .narrator import ScrambleNarrator
from .memory_policy import ScrambleMemoryPolicy
from .state import ScrambleAgentState


class ScrambleAgent:
    """
    React-based agent for playing Ankh-Morpork Scramble.

    This agent uses:
    - LangChain's React pattern for tool-calling loops
    - Game state narrator for token-efficient context
    - Memory policy for intelligent conversation trimming
    - MCP tools for game actions
    """

    def __init__(
        self,
        game_id: str,
        team_id: str,
        team_name: str,
        mcp_url: str = "http://localhost:8000/mcp",
        model: str = "claude-sonnet-4-5-20250929",
        api_key: Optional[str] = None,
        max_tokens: int = 150000,
    ):
        """
        Initialize Scramble agent.

        Args:
            game_id: Game identifier
            team_id: Team identifier (e.g., "team1")
            team_name: Human-readable team name
            mcp_url: MCP server URL
            model: LLM model to use
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            max_tokens: Maximum context tokens before compression
        """
        self.game_id = game_id
        self.team_id = team_id
        self.team_name = team_name
        self.mcp_url = mcp_url
        self.model = model

        # Initialize LLM
        self.llm = ChatAnthropic(
            model=model,
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
            temperature=0.7,
            max_tokens=4096,
        )

        # Initialize components
        self.narrator = ScrambleNarrator()
        self.memory_policy = ScrambleMemoryPolicy(max_tokens=max_tokens)

        # Initialize MCP client (following ai-at-risk pattern)
        self.mcp_client = MultiServerMCPClient({
            "scramble": {
                "transport": "sse",
                "url": mcp_url
            }
        })

        # Tools will be loaded during initialize()
        self.tools = []
        self.agent = None

        # Track conversation history
        self.messages: List = []

        print(f"[Agent] {team_name} initialized (model: {model})")

    async def initialize(self):
        """
        Connect to MCP server and initialize agent with tools.

        This must be called before using the agent (following ai-at-risk pattern).
        """
        print(f"[Agent] {self.team_name} connecting to MCP server at {self.mcp_url}...")

        try:
            # Get tools from MCP server
            self.tools = await self.mcp_client.get_tools()
            print(f"[Agent] Loaded {len(self.tools)} MCP tools")

            # Build React agent with MCP tools
            self.agent = create_react_agent(
                self.llm,
                self.tools,
                state_modifier=self._get_system_message()
            )

            print(f"[Agent] {self.team_name} ready to play!")

        except Exception as e:
            print(f"[Agent] Error initializing {self.team_name}: {e}")
            raise

    def _create_mcp_tools_OLD(self) -> List[Tool]:
        """
        Create LangChain tools from MCP endpoints.

        Returns:
            List of LangChain Tool objects
        """

        async def call_mcp_tool(tool_name: str, **kwargs) -> Dict:
            """Make MCP tool call via HTTP"""
            try:
                # Prepare request
                request_data = {
                    "game_id": self.game_id,
                    "team_id": self.team_id,
                    **kwargs,
                }

                # Remove None values
                request_data = {k: v for k, v in request_data.items() if v is not None}

                async with httpx.AsyncClient(timeout=30.0) as client:
                    # Note: Actual MCP endpoint structure may vary
                    # Adjust URL pattern based on your mcp_server.py implementation
                    response = await client.post(
                        f"{self.mcp_url}/call/{tool_name}", json=request_data
                    )
                    response.raise_for_status()
                    return response.json()

            except Exception as e:
                return {"error": str(e), "tool": tool_name}

        # Define all MCP tools as LangChain Tools
        tools = [
            Tool(
                name="get_game_state",
                description="Get complete current game state including pitch, players, ball position, phase, score",
                func=lambda: None,  # Placeholder for sync
                coroutine=lambda: call_mcp_tool("get_game_state"),
            ),
            Tool(
                name="get_valid_actions",
                description="Get all valid actions available right now. Returns list of possible moves, scuffles, charges, passes, etc.",
                func=lambda: None,
                coroutine=lambda: call_mcp_tool("get_valid_actions"),
            ),
            Tool(
                name="execute_action",
                description="Execute a game action. Required params: action_type (MOVE/SCUFFLE/CHARGE/HURL/QUICK_PASS/BOOT), player_id. Optional: target_position, target_player_id",
                func=lambda **kwargs: None,
                coroutine=lambda **kwargs: call_mcp_tool("execute_action", **kwargs),
            ),
            Tool(
                name="end_turn",
                description="End your current turn. Call this when you've completed your desired actions for this turn.",
                func=lambda: None,
                coroutine=lambda: call_mcp_tool("end_turn"),
            ),
            Tool(
                name="use_reroll",
                description="Use a team reroll to reroll a failed dice roll. Limited supply!",
                func=lambda: None,
                coroutine=lambda: call_mcp_tool("use_reroll"),
            ),
            Tool(
                name="send_message",
                description="Send a message to your opponent. Use for strategic communication or trash talk.",
                func=lambda message: None,
                coroutine=lambda message: call_mcp_tool("send_message", message=message),
            ),
            Tool(
                name="get_messages",
                description="Get recent messages from opponent",
                func=lambda: None,
                coroutine=lambda: call_mcp_tool("get_messages"),
            ),
            Tool(
                name="suggest_path",
                description="Get suggested movement path with risk assessment. Params: player_id, target_position",
                func=lambda **kwargs: None,
                coroutine=lambda **kwargs: call_mcp_tool("suggest_path", **kwargs),
            ),
            # SETUP phase tools
            Tool(
                name="get_team_budget",
                description="Check remaining budget and purchase history during setup phase",
                func=lambda: None,
                coroutine=lambda: call_mcp_tool("get_team_budget"),
            ),
            Tool(
                name="get_available_positions",
                description="View purchasable player positions and rerolls during setup",
                func=lambda: None,
                coroutine=lambda: call_mcp_tool("get_available_positions"),
            ),
            Tool(
                name="buy_player",
                description="Purchase a player position during setup. Params: position_name",
                func=lambda position_name: None,
                coroutine=lambda position_name: call_mcp_tool(
                    "buy_player", position_name=position_name
                ),
            ),
            Tool(
                name="buy_reroll",
                description="Purchase a team reroll during setup (expensive but valuable!)",
                func=lambda: None,
                coroutine=lambda: call_mcp_tool("buy_reroll"),
            ),
            Tool(
                name="place_players",
                description="Position players on pitch after purchasing. Params: placements (dict of player_id: position)",
                func=lambda placements: None,
                coroutine=lambda placements: call_mcp_tool(
                    "place_players", placements=placements
                ),
            ),
            Tool(
                name="ready_to_play",
                description="Mark team as ready after completing setup phase",
                func=lambda: None,
                coroutine=lambda: call_mcp_tool("ready_to_play"),
            ),
        ]

        return tools

    def _get_system_message(self) -> SystemMessage:
        """
        Build strategic system prompt for the agent.

        Returns:
            SystemMessage with game instructions
        """
        return SystemMessage(
            content=f"""
You are an AI agent playing Ankh-Morpork Scramble as **{self.team_name}**.

## GAME OBJECTIVE
Score "Scratches" by carrying the ball into the opponent's end zone (like American football/rugby).

## YOUR STRATEGIC APPROACH

### During SETUP Phase:
1. Check budget with get_team_budget
2. View options with get_available_positions
3. Build balanced roster:
   - Mix of strong blockers and agile runners
   - Consider 2-3 rerolls (expensive but crucial)
   - Spend most of your 1M gold budget
4. Place players strategically
5. Call ready_to_play when done

### During PLAY Phase:
1. **ALWAYS** start by calling get_game_state
2. Call get_valid_actions to see your options
3. Analyze situation:
   - Where is the ball?
   - Who has possession?
   - What's the score?
   - Which players are active vs KO'd?

4. Execute strategic actions:
   - **Ball Control**: Priority #1 - secure and advance the ball
   - **MOVE**: Reposition players (watch for tackle zones - may need dodge rolls)
   - **SCUFFLE**: Block opponents to create openings
   - **CHARGE**: Aggressive move+scuffle combo (1 action, high impact)
   - **HURL**: Throw ball to teammate (risky but fast)
   - **QUICK_PASS**: Hand off to adjacent player (safer)
   - **BOOT**: Foul downed opponents (dirty but effective)

5. **Tactical Principles**:
   - Form protective cage around ball carrier
   - Control center field for positional advantage
   - Remove key opponent blockers with SCUFFLE/CHARGE
   - Use suggest_path to find safe routes
   - Conserve rerolls for critical moments
   - Don't over-extend - know when to end turn

6. Call end_turn when you've made your key moves

## KEY MECHANICS
- **Tackle Zones**: Adjacent opponents force dodge rolls
- **Turnovers**: Failed actions end your turn immediately
- **Injuries**: Players can be KO'd or worse
- **Rerolls**: Limited but powerful - use wisely
- **Actions per turn**: Usually 3-11 depending on roster size

## COMMUNICATION
- Be concise in your reasoning
- Explain key decisions briefly
- Use send_message for strategic communication with opponent

## IMPORTANT
- Always verify it's your turn before acting
- Check valid actions before executing
- One action at a time - verify results
- Adapt to injuries and turnovers
- Don't waste actions on low-value moves

Play smart, be aggressive when ahead, and protect the ball at all costs!
        """.strip()
        )

    async def play_turn(self, current_state: Dict) -> Dict:
        """
        Execute one game turn.

        Args:
            current_state: Current game state from server

        Returns:
            Agent's response with actions taken
        """
        turn_start = datetime.now()

        # Generate narrative context from state changes
        narrative = self.narrator.generate_turn_update(
            self.game_id, self.team_id, current_state
        )

        print(f"\n[Agent] {self.team_name} - Turn {current_state.get('turn', '?')}")
        print(f"[Context] {narrative[:200]}...")  # Preview

        # Build state
        state: ScrambleAgentState = {
            "messages": self.messages + [HumanMessage(content=narrative)],
            "game_id": self.game_id,
            "team_id": self.team_id,
            "current_turn": current_state.get("turn", 0),
            "current_phase": current_state.get("phase", "PLAYING"),
            "context": {"narrative": narrative, "timestamp": turn_start.isoformat()},
            "last_action": None,
            "game_state_snapshot": current_state,
            "ball_carrier_id": self._extract_ball_carrier(current_state),
            "team_score": self._extract_team_score(current_state, self.team_id),
            "opponent_score": self._extract_opponent_score(current_state, self.team_id),
            "rerolls_remaining": self._extract_rerolls(current_state, self.team_id),
            "players_on_pitch": self._count_active_players(current_state, self.team_id),
            "total_tokens": None,
            "needs_compression": None,
        }

        # Check if memory needs trimming
        if self.memory_policy.should_trim_memory(state["messages"]):
            print("[Memory] Trimming conversation history...")
            state["messages"] = self.memory_policy.trim_conversation(state["messages"])

        try:
            # Invoke React agent - it will loop with tools until done
            response = await self.agent.ainvoke(state)

            # Update conversation history
            self.messages = response.get("messages", [])

            # Track completion
            turn_duration = (datetime.now() - turn_start).total_seconds()
            print(f"[Agent] Turn completed in {turn_duration:.1f}s")

            return response

        except Exception as e:
            print(f"[Agent] Error during turn: {e}")
            import traceback

            traceback.print_exc()
            return {"error": str(e), "messages": state["messages"]}

    def _extract_ball_carrier(self, state: Dict) -> Optional[str]:
        """Extract ball carrier ID from state"""
        ball = state.get("ball", {})
        return ball.get("carrier_id")

    def _extract_team_score(self, state: Dict, team_id: str) -> int:
        """Extract this team's score"""
        score = state.get("score", {})
        return score.get(team_id, 0)

    def _extract_opponent_score(self, state: Dict, team_id: str) -> int:
        """Extract opponent's score"""
        score = state.get("score", {})
        opponent_id = [tid for tid in score.keys() if tid != team_id]
        if opponent_id:
            return score.get(opponent_id[0], 0)
        return 0

    def _extract_rerolls(self, state: Dict, team_id: str) -> int:
        """Extract remaining rerolls"""
        teams = state.get("teams", {})
        team = teams.get(team_id, {})
        return team.get("rerolls", 0)

    def _count_active_players(self, state: Dict, team_id: str) -> int:
        """Count active players on pitch"""
        teams = state.get("teams", {})
        team = teams.get(team_id, {})
        players = team.get("players", {})
        active = sum(
            1 for p in players.values() if p.get("status") == "ACTIVE" and p.get("position")
        )
        return active

    async def join_game(self) -> Dict:
        """Join the game (called once at start)"""
        print(f"[Agent] {self.team_name} joining game {self.game_id}...")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.mcp_url}/call/join_game",
                    json={"game_id": self.game_id, "team_id": self.team_id},
                )
                response.raise_for_status()
                result = response.json()
                print(f"[Agent] Successfully joined game")
                return result

        except Exception as e:
            print(f"[Agent] Error joining game: {e}")
            return {"error": str(e)}
