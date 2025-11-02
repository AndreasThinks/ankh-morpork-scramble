"""LangGraph-powered agent that drives MCP tool usage."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, TypedDict, Annotated

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


@dataclass(slots=True)
class AgentStepResult:
    """Summary of a single LangGraph invocation."""

    ai_message: AIMessage | None
    tool_calls: List[str]
    new_messages: List[BaseMessage]


class ConversationState(TypedDict):
    """Graph state definition for LangGraph."""

    messages: Annotated[List[BaseMessage], add_messages]


class LangGraphMCPAgent:
    """Utility wrapper that keeps conversation state across steps."""

    def __init__(
        self,
        llm,
        tools: Sequence[BaseTool],
        *,
        system_prompt: str,
    ) -> None:
        self._llm = llm.bind_tools(tools)
        self._tool_node = ToolNode(tools)
        self._system_message = SystemMessage(content=system_prompt)
        self._graph = self._build_graph()
        self._state: ConversationState = {"messages": [self._system_message]}

    def _build_graph(self):
        """Create the LangGraph state machine that handles tool routing."""

        builder = StateGraph(ConversationState)

        async def call_model(state: ConversationState):
            response = await self._llm.ainvoke(state["messages"])
            return {"messages": [response]}

        builder.add_node("agent", call_model)
        builder.add_node("tools", self._tool_node)
        builder.add_edge("tools", "agent")
        builder.add_conditional_edges(
            "agent",
            tools_condition,
            {"tools": "tools", "__end__": END},
        )
        builder.set_entry_point("agent")
        return builder.compile()

    def reset(self) -> None:
        """Reset conversation history while retaining the system prompt."""

        self._state = {"messages": [self._system_message]}

    async def step(self, instruction: str) -> AgentStepResult:
        """Append a human instruction and execute the LangGraph."""

        previous_length = len(self._state["messages"])
        self._state["messages"].append(HumanMessage(content=instruction))

        new_state = await self._graph.ainvoke(self._state)
        self._state["messages"] = new_state["messages"]
        new_messages = self._state["messages"][previous_length:]

        tool_calls = [
            msg.name for msg in new_messages if isinstance(msg, ToolMessage)
        ]
        ai_message = next(
            (msg for msg in reversed(new_messages) if isinstance(msg, AIMessage)),
            None,
        )

        return AgentStepResult(
            ai_message=ai_message,
            tool_calls=list(tool_calls),
            new_messages=list(new_messages),
        )

    @property
    def transcript(self) -> Iterable[BaseMessage]:
        """Expose the accumulated message history for logging or debugging."""

        return tuple(self._state["messages"])
