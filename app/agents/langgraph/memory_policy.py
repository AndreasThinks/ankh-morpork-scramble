"""
Memory management policy for Scramble agents.

Handles intelligent message trimming when approaching token limits.
Adapted from ai-at-risk's RiskMemoryPolicy.
"""

from typing import List
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.messages.utils import trim_messages

try:
    from langchain_core.messages.utils import count_tokens_approximately
except ImportError:
    # Fallback for older versions
    def count_tokens_approximately(messages: List[BaseMessage]) -> int:
        """Rough token count estimation (4 chars ≈ 1 token)"""
        total_chars = sum(len(str(m.content)) for m in messages)
        return total_chars // 4


class ScrambleMemoryPolicy:
    """
    Memory management for Scramble agents.

    This class implements intelligent conversation trimming to prevent
    token limit exhaustion while preserving critical game context.

    Key features:
    - Automatic trimming when approaching token limits
    - Preservation of system messages
    - Retention of critical game events
    - Recent-first strategy for non-critical messages
    """

    def __init__(self, max_tokens: int = 150000, keep_recent_exchanges: int = 5):
        """
        Initialize memory policy.

        Args:
            max_tokens: Maximum tokens before trimming (Claude has ~200k context)
            keep_recent_exchanges: Number of recent exchanges to always keep
        """
        self.max_tokens = max_tokens
        self.keep_recent_exchanges = keep_recent_exchanges
        # Trigger compression at 70% of max
        self.compression_threshold = int(max_tokens * 0.7)

    def should_trim_memory(self, messages: List[BaseMessage]) -> bool:
        """
        Check if conversation history needs trimming.

        Args:
            messages: Current message history

        Returns:
            True if messages should be trimmed
        """
        token_count = count_tokens_approximately(messages)
        return token_count > self.compression_threshold

    def trim_conversation(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Trim conversation while preserving critical context.

        Strategy:
        1. Always keep system messages
        2. Identify and keep critical game event messages
        3. Trim older non-critical messages
        4. Keep recent exchanges

        Args:
            messages: Full message history

        Returns:
            Trimmed message list
        """
        # Separate message types
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        other_messages = [m for m in messages if not isinstance(m, SystemMessage)]

        # Identify critical messages to preserve
        critical_messages = []
        non_critical_messages = []

        for msg in other_messages:
            if self._is_critical_message(msg):
                critical_messages.append(msg)
            else:
                non_critical_messages.append(msg)

        try:
            # Use LangChain's trim_messages for non-critical messages
            # Strategy: Keep recent messages (last-in priority)
            trimmed_non_critical = trim_messages(
                non_critical_messages,
                max_tokens=self.max_tokens - self._estimate_tokens(system_messages + critical_messages),
                strategy="last",  # Keep most recent
                token_counter=count_tokens_approximately,
                start_on="human",
                end_on=("human", "ai"),
            )

            # Combine: system + critical + trimmed recent
            result = system_messages + critical_messages + trimmed_non_critical

            # Log reduction
            old_tokens = count_tokens_approximately(messages)
            new_tokens = count_tokens_approximately(result)
            reduction_pct = 100 * (old_tokens - new_tokens) / old_tokens if old_tokens > 0 else 0

            print(
                f"[Memory] Trimmed: {old_tokens} → {new_tokens} tokens "
                f"({reduction_pct:.1f}% reduction)"
            )

            return result

        except Exception as e:
            print(f"[Memory] Error trimming messages: {e}")
            # Fallback: keep system + last N messages
            fallback_count = 10
            return system_messages + other_messages[-fallback_count:]

    def _is_critical_message(self, message: BaseMessage) -> bool:
        """
        Check if message contains critical game events that should be preserved.

        Critical events include:
        - Scores/touchdowns
        - Major injuries/casualties
        - Turnovers
        - Phase transitions
        - Reroll usage
        - Game end conditions

        Args:
            message: Message to check

        Returns:
            True if message is critical
        """
        # Keywords indicating critical game events
        critical_keywords = [
            "TOUCHDOWN",
            "SCORE",
            "SCRATCH",
            "INJURY",
            "CASUALTY",
            "KO",
            "KNOCKOUT",
            "TURNOVER",
            "FUMBLE",
            "KICKOFF",
            "HALF",
            "HALFTIME",
            "END",
            "COMPLETE",
            "REROLL USED",
            "ELIMINATED",
            "WINNER",
            "🎯",  # Score emoji
            "💥",  # Injury emoji
        ]

        content = str(message.content).upper()
        return any(keyword in content for keyword in critical_keywords)

    def _estimate_tokens(self, messages: List[BaseMessage]) -> int:
        """Estimate token count for a list of messages"""
        return count_tokens_approximately(messages)

    def get_compression_status(self, messages: List[BaseMessage]) -> dict:
        """
        Get current memory status.

        Args:
            messages: Current message history

        Returns:
            Dict with token counts and status
        """
        current_tokens = count_tokens_approximately(messages)
        usage_pct = (current_tokens / self.max_tokens) * 100

        return {
            "current_tokens": current_tokens,
            "max_tokens": self.max_tokens,
            "compression_threshold": self.compression_threshold,
            "usage_percent": usage_pct,
            "needs_trimming": current_tokens > self.compression_threshold,
            "message_count": len(messages),
        }
