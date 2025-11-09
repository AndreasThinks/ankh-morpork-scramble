"""
Agent state definition for Scramble agents.

Adapted from ai-at-risk's agent_state.py with Scramble-specific fields.
"""

from typing import TypedDict, List, Optional, Dict, Any, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ScrambleAgentState(TypedDict):
    """
    State structure for LangGraph-based Scramble agents.

    This TypedDict defines all the state that flows through the agent's
    execution graph. The messages field uses the add_messages reducer to
    properly handle message accumulation.
    """

    # Conversation history with automatic message accumulation
    messages: Annotated[List[BaseMessage], add_messages]

    # Game identifiers
    game_id: str
    team_id: str

    # Game progress tracking
    current_turn: int
    current_phase: str  # "SETUP", "KICKOFF", "PLAYING", "HALFTIME", "COMPLETE"

    # Context and memory
    context: Dict[str, Any]  # Additional context data
    last_action: Optional[Dict[str, Any]]  # Most recent action taken
    game_state_snapshot: Optional[Dict[str, Any]]  # Full game state for comparison

    # Scramble-specific game state
    ball_carrier_id: Optional[str]  # Player ID carrying the ball
    team_score: int  # This team's score
    opponent_score: int  # Opponent's score
    rerolls_remaining: int  # Team rerolls left
    players_on_pitch: int  # Active players count

    # Memory management
    total_tokens: Optional[int]  # Estimated token count
    needs_compression: Optional[bool]  # Flag for memory trimming
