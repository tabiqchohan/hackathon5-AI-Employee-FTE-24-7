"""
FlowSync Customer Success AI Agent -- Conversation Memory (Exercise 1.3)
========================================================================
In-memory conversation storage with multi-turn context, sentiment tracking,
and cross-channel conversation resolution.

This module provides:
  - ConversationStore: central registry of all customer conversations
  - Conversation: single conversation thread with metadata
  - Message: individual message in a thread
  - SentimentTrend: tracks sentiment direction over time
"""

from datetime import datetime
from typing import Optional


# ──────────────────────────────────────────────────────────────
# DATA MODELS
# ──────────────────────────────────────────────────────────────

class Message:
    """A single message in a conversation thread."""

    def __init__(
        self,
        role: str,          # "customer" or "agent"
        content: str,
        channel: str,
        timestamp: Optional[str] = None,
        intent: Optional[str] = None,
        sentiment: Optional[str] = None,
        escalation: bool = False,
    ):
        self.role = role
        self.content = content
        self.channel = channel
        self.timestamp = timestamp or datetime.now().isoformat()
        self.intent = intent
        self.sentiment = sentiment
        self.escalation = escalation

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content[:200],  # Truncate for display
            "channel": self.channel,
            "timestamp": self.timestamp,
            "intent": self.intent,
            "sentiment": self.sentiment,
            "escalation": self.escalation,
        }

    def __repr__(self):
        return f"Message({self.role}, {self.channel}, {self.timestamp[:19]})"


class SentimentTrend:
    """Tracks sentiment direction over time for a conversation."""

    def __init__(self):
        self.history: list[str] = []  # Ordered list of sentiment values

    def add(self, sentiment: str, role: str = "customer"):
        """Add a sentiment value. Only track customer sentiment for trend analysis."""
        if role == "customer":
            self.history.append(sentiment)

    @property
    def current(self) -> str:
        return self.history[-1] if self.history else "neutral"

    @property
    def direction(self) -> str:
        """Determine if sentiment is improving, worsening, or stable."""
        if len(self.history) < 2:
            return "stable"

        # Map sentiments to numeric scores
        scores = {
            "positive": 2,
            "neutral": 0,
            "negative": -1,
            "very_negative": -2,
        }

        recent = scores.get(self.history[-1], 0)
        previous = scores.get(self.history[-2], 0)

        if recent > previous:
            return "improving"
        elif recent < previous:
            return "worsening"
        else:
            return "stable"

    @property
    def summary(self) -> str:
        if len(self.history) < 2:
            return f"Current: {self.current}"
        return f"Current: {self.current} | Trend: {self.direction}"

    def to_list(self) -> list[str]:
        return list(self.history)


class Conversation:
    """A single conversation thread with full metadata."""

    def __init__(self, conversation_id: str, customer_key: str):
        self.conversation_id = conversation_id
        self.customer_key = customer_key  # email or phone
        self.messages: list[Message] = []
        self.sentiment_trend = SentimentTrend()
        self.topics: list[str] = []
        self.resolution_status = "open"  # open, in_progress, resolved, escalated
        self.last_channel_used = ""
        self.message_count = 0
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.escalation_history: list[dict] = []

    def add_message(self, message: Message):
        """Add a message and update metadata."""
        self.messages.append(message)
        self.message_count = len(self.messages)
        self.last_channel_used = message.channel
        self.updated_at = datetime.now().isoformat()

        # Update sentiment (only track customer messages for trend)
        if message.sentiment:
            self.sentiment_trend.add(message.sentiment, role=message.role)

        # Track topics from intent
        if message.intent and message.role == "customer":
            topic = message.intent.lower().replace(" / ", "_").replace(" ", "_")
            if topic not in self.topics:
                self.topics.append(topic)

        # Track escalations
        if message.escalation:
            self.resolution_status = "escalated"
            self.escalation_history.append({
                "timestamp": message.timestamp,
                "channel": message.channel,
                "reason": "Escalation triggered on message",
            })

    def get_recent_messages(self, n: int = 5) -> list[Message]:
        """Get the last N messages for context."""
        return self.messages[-n:]

    def get_context_summary(self) -> str:
        """Generate a context summary for the agent to use in response generation."""
        if not self.messages:
            return "No previous conversation history."

        parts = []
        parts.append(f"Conversation ID: {self.conversation_id}")
        parts.append(f"Messages exchanged: {self.message_count}")
        parts.append(f"Topics discussed: {', '.join(self.topics) if self.topics else 'None yet'}")
        parts.append(f"Sentiment trend: {self.sentiment_trend.summary}")
        parts.append(f"Resolution status: {self.resolution_status}")
        parts.append(f"Last channel: {self.last_channel_used}")

        # Add recent message context
        recent = self.get_recent_messages(5)
        if recent:
            parts.append("\nRecent messages:")
            for msg in recent:
                role_label = "Customer" if msg.role == "customer" else "Agent"
                preview = msg.content[:150]
                parts.append(f"  [{role_label}] ({msg.channel}): {preview}")

        return "\n".join(parts)

    def get_channel_switch_notice(self, current_channel: str) -> str:
        """Notice when customer switches channels."""
        if self.last_channel_used and self.last_channel_used != current_channel:
            return (
                f"NOTE: Customer switched from {self.last_channel_used} to {current_channel}. "
                f"Acknowledge this naturally if relevant."
            )
        return ""

    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "customer_key": self.customer_key,
            "message_count": self.message_count,
            "resolution_status": self.resolution_status,
            "last_channel_used": self.last_channel_used,
            "topics": self.topics,
            "sentiment_trend": self.sentiment_trend.to_list(),
            "sentiment_direction": self.sentiment_trend.direction,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.messages],
        }


# ──────────────────────────────────────────────────────────────
# CONVERSATION STORE
# ──────────────────────────────────────────────────────────────

class ConversationStore:
    """
    Central registry for all conversations.
    Maps customer identifiers (email/phone) to Conversation objects.
    Supports cross-channel resolution: same customer via email + phone
    resolves to the same conversation if keys match.
    """

    def __init__(self):
        # Primary key: customer email or phone -> Conversation
        self._conversations: dict[str, Conversation] = {}
        # Cross-reference: alternate keys -> primary key
        self._key_map: dict[str, str] = {}
        self._counter = 0

    def _generate_conversation_id(self) -> str:
        self._counter += 1
        return f"CONV-{self._counter:04d}"

    def _resolve_customer_key(self, email: Optional[str], phone: Optional[str]) -> str:
        """
        Resolve customer identity. Priority: email > phone.
        If email exists, use it as primary key.
        """
        if email:
            return email.lower().strip()
        if phone:
            return phone.strip()
        return "anonymous"

    def get_or_create(self, email: Optional[str] = None, phone: Optional[str] = None) -> Conversation:
        """
        Get existing conversation for this customer, or create a new one.
        Handles cross-channel resolution: if customer was seen before
        via email, and now contacts via phone (with matching email stored),
        return the same conversation.
        """
        primary_key = self._resolve_customer_key(email, phone)

        # Check if we already have this key
        if primary_key in self._conversations:
            return self._conversations[primary_key]

        # Check if this key maps to an existing conversation
        if primary_key in self._key_map:
            mapped_key = self._key_map[primary_key]
            return self._conversations[mapped_key]

        # Create new conversation
        conv_id = self._generate_conversation_id()
        conversation = Conversation(conv_id, primary_key)
        self._conversations[primary_key] = conversation

        # If both email and phone provided, create cross-reference
        if email and phone:
            alt_key = phone.strip()
            if alt_key != primary_key:
                self._key_map[alt_key] = primary_key

        return conversation

    def get(self, email: Optional[str] = None, phone: Optional[str] = None) -> Optional[Conversation]:
        """Get existing conversation without creating a new one."""
        key = self._resolve_customer_key(email, phone)
        if key in self._conversations:
            return self._conversations[key]
        if key in self._key_map:
            return self._conversations[self._key_map[key]]
        return None

    def get_all(self) -> list[Conversation]:
        """Return all conversations."""
        return list(self._conversations.values())

    def get_active(self) -> list[Conversation]:
        """Return conversations that are not resolved."""
        return [c for c in self._conversations.values() if c.resolution_status != "resolved"]

    def get_escalated(self) -> list[Conversation]:
        """Return all escalated conversations."""
        return [c for c in self._conversations.values() if c.resolution_status == "escalated"]

    def update_status(self, email: Optional[str], phone: Optional[str], status: str):
        """Update resolution status for a conversation."""
        conv = self.get(email, phone)
        if conv:
            conv.resolution_status = status
            conv.updated_at = datetime.now().isoformat()

    def display_all(self):
        """Print all conversations summary."""
        print("\n" + "=" * 70)
        print("  CONVERSATION STORE -- All Conversations")
        print("=" * 70)
        for conv in self._conversations.values():
            print(f"\n  [{conv.conversation_id}] Customer: {conv.customer_key}")
            print(f"    Status: {conv.resolution_status} | Messages: {conv.message_count}")
            print(f"    Topics: {', '.join(conv.topics) if conv.topics else 'None'}")
            print(f"    Sentiment: {conv.sentiment_trend.summary}")
            print(f"    Last Channel: {conv.last_channel_used}")
        print("\n" + "=" * 70)
        print()


# ──────────────────────────────────────────────────────────────
# CONTEXT BUILDER
# ──────────────────────────────────────────────────────────────

def build_context_for_agent(
    conversation: Conversation,
    current_channel: str,
    current_content: str,
) -> str:
    """
    Build a context string to inject into the response generation prompt.
    Includes conversation history, sentiment trend, and channel switch notice.
    """
    parts = []

    # Channel switch notice
    channel_notice = conversation.get_channel_switch_notice(current_channel)
    if channel_notice:
        parts.append(channel_notice)

    # Conversation summary
    parts.append(conversation.get_context_summary())

    # Sentiment-based guidance
    if conversation.sentiment_trend.direction == "worsening":
        parts.append(
            "\nWARNING: Customer sentiment is worsening. "
            "Be empathetic and consider escalation if the next interaction is also negative."
        )
    elif conversation.sentiment_trend.direction == "improving":
        parts.append(
            "\nNOTE: Customer sentiment is improving. Continue providing helpful responses."
        )

    # Escalation history warning
    if conversation.escalation_history:
        parts.append(
            f"\nNOTE: This conversation has been escalated {len(conversation.escalation_history)} time(s) before."
        )

    return "\n".join(parts)
