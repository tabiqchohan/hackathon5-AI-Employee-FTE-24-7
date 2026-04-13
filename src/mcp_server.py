"""
FlowSync Customer Success AI Agent -- MCP Server (Exercise 1.4)
=================================================================
Exposes the agent's capabilities as MCP tools for consumption by
the OpenAI Agents SDK or any MCP-compatible client.

Tools exposed:
  1. search_knowledge_base(query) -> str
  2. create_ticket(customer_id, issue, priority, channel) -> str
  3. get_customer_history(customer_id) -> str
  4. escalate_to_human(ticket_id, reason) -> str
  5. send_response(ticket_id, message, channel) -> str
  6. analyze_sentiment(message) -> dict
  7. get_or_create_customer(identifier, channel) -> str

Run server:  python src/mcp_server.py
Run tests:   python src/mcp_server.py --test
"""

import sys
import io
import json
import asyncio
from enum import Enum
from typing import Optional
from datetime import datetime

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# MCP SDK
from mcp.server.fastmcp import FastMCP

# Reuse existing modules
sys.path.insert(0, ".")
from knowledge_base import search_kb, KNOWLEDGE_BASE
from memory import ConversationStore, Conversation, Message
from prototype import (
    Ticket,
    classify_intent,
    analyze_sentiment as _analyze_sentiment,
    check_escalation,
    generate_response,
    process_ticket,
    store,
    INTENT_CATEGORIES,
)


# ──────────────────────────────────────────────────────────────
# ENUMS & CONSTANTS
# ──────────────────────────────────────────────────────────────

class Channel(str, Enum):
    """Supported communication channels for the FlowSync Customer Success AI."""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class Priority(str, Enum):
    """Ticket priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(str, Enum):
    """Lifecycle states for support tickets."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


# ──────────────────────────────────────────────────────────────
# TICKET REGISTRY (in-memory, separate from conversation store)
# ──────────────────────────────────────────────────────────────

class TicketRegistry:
    """Stores all created tickets with their metadata and responses."""

    def __init__(self):
        self._tickets: dict[str, dict] = {}
        self._counter = 0

    def create(
        self,
        customer_id: str,
        issue: str,
        priority: str,
        channel: str,
    ) -> str:
        """Create a new ticket and return the ticket_id."""
        self._counter += 1
        ticket_id = f"TKT-{self._counter:05d}"
        self._tickets[ticket_id] = {
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "issue": issue,
            "priority": priority,
            "channel": channel,
            "status": TicketStatus.OPEN.value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "responses": [],
            "escalation": None,
        }
        return ticket_id

    def get(self, ticket_id: str) -> Optional[dict]:
        """Get a ticket by ID."""
        return self._tickets.get(ticket_id)

    def add_response(self, ticket_id: str, message: str, channel: str):
        """Add an agent response to a ticket."""
        if ticket_id in self._tickets:
            self._tickets[ticket_id]["responses"].append({
                "message": message,
                "channel": channel,
                "timestamp": datetime.now().isoformat(),
            })
            self._tickets[ticket_id]["updated_at"] = datetime.now().isoformat()

    def escalate(self, ticket_id: str, reason: str):
        """Mark a ticket as escalated."""
        if ticket_id in self._tickets:
            self._tickets[ticket_id]["status"] = TicketStatus.ESCALATED.value
            self._tickets[ticket_id]["escalation"] = {
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
            }
            self._tickets[ticket_id]["updated_at"] = datetime.now().isoformat()

    def get_by_customer(self, customer_id: str) -> list[dict]:
        """Get all tickets for a customer."""
        return [
            t for t in self._tickets.values()
            if t["customer_id"] == customer_id
        ]


# Global registries
ticket_registry = TicketRegistry()

# Initialize FastMCP server
mcp = FastMCP("flowsync-customer-success-agent")


# ──────────────────────────────────────────────────────────────
# MCP TOOLS
# ──────────────────────────────────────────────────────────────

@mcp.tool()
async def search_knowledge_base(query: str) -> str:
    """Search the FlowSync product documentation and knowledge base.

    Use this tool when a customer asks a question about FlowSync features,
    setup instructions, troubleshooting steps, integrations, pricing plans,
    or general product information.

    This searches across all product documentation including:
    - AI Task Suggestions
    - Smart Dashboards
    - Team Collaboration (invites, permissions, roles)
    - Integrations (Slack, Google Drive, GitHub, Figma, Zoom)
    - AI Meeting Summarizer
    - Resource Planner
    - Custom Workflows (no-code)
    - Pricing Plans (Starter, Pro, Enterprise)
    - General FAQ (account, security, mobile, cancellation)

    Args:
        query: The customer's question or search query. Should be a natural
            language string describing what they need help with.
            Examples:
            - "How do I invite team members?"
            - "Slack integration not working"
            - "What features are in the Pro plan?"
            - "AI suggestions not showing recommendations"

    Returns:
        A formatted string containing relevant documentation sections,
        including setup instructions, troubleshooting steps, and feature
        descriptions. Returns a fallback message if no specific documentation
        is found.
    """
    result = search_kb(query)
    return result


@mcp.tool()
async def create_ticket(
    customer_id: str,
    issue: str,
    priority: str = "medium",
    channel: str = "email",
) -> str:
    """Create a new support ticket for a customer issue.

    Use this tool when:
    - A customer reports a bug, problem, or issue that needs tracking
    - A customer requests help with something that requires follow-up
    - You need to formally log a customer's issue for the support team
    - The issue cannot be resolved in a single interaction

    The ticket is created in the central ticket registry and can be referenced
    by the returned ticket_id for future updates, responses, or escalation.

    Args:
        customer_id: The unique identifier for the customer. This should be
            their email address or phone number.
            Examples: "ahmed@startup.io", "+923001234567"
        issue: A clear description of the problem or request the customer
            is reporting. Be specific and include relevant details.
            Examples: "Slack integration not syncing tasks",
                      "Cannot invite more than 10 team members"
        priority: The urgency level of the ticket. Choose from:
            - "low": General inquiry, non-urgent question
            - "medium": Standard issue, feature not working as expected
            - "high": Important feature broken, affecting customer workflow
            - "critical": System outage, data loss, security issue
            Defaults to "medium" if not specified.
        channel: The channel through which the customer reached out.
            Choose from: "email", "whatsapp", "web_form"
            Defaults to "email" if not specified.

    Returns:
        A confirmation string containing the ticket_id, customer_id, issue
        summary, priority, channel, and creation timestamp.
        Example: "Ticket TKT-00001 created for ahmed@startup.io | Issue: Slack sync not working | Priority: high | Channel: whatsapp | Created: 2026-04-08T10:30:00"
    """
    # Validate inputs
    valid_priorities = [p.value for p in Priority]
    if priority not in valid_priorities:
        priority = "medium"

    valid_channels = [c.value for c in Channel]
    if channel not in valid_channels:
        channel = "email"

    ticket_id = ticket_registry.create(
        customer_id=customer_id,
        issue=issue,
        priority=priority,
        channel=channel,
    )

    ticket = ticket_registry.get(ticket_id)
    return (
        f"Ticket {ticket_id} created for {customer_id} | "
        f"Issue: {issue[:100]} | "
        f"Priority: {priority} | "
        f"Channel: {channel} | "
        f"Created: {ticket['created_at']}"
    )


@mcp.tool()
async def get_customer_history(customer_id: str) -> str:
    """Retrieve the full conversation history for a customer across all channels.

    Use this tool when:
    - You need to understand the context of a customer's previous interactions
    - A customer follows up on a previous question
    - You want to check if this customer has contacted support before
    - You need to see the sentiment trend over time
    - You want to review what topics the customer has asked about previously

    This returns the complete conversation history including:
    - All messages exchanged (both customer and agent)
    - Channels used for each message (email, whatsapp, web_form)
    - Intent classification for each customer message
    - Sentiment analysis for each message
    - Overall sentiment trend (improving, worsening, stable)
    - Topics discussed across the conversation
    - Current resolution status
    - Any escalation history

    Args:
        customer_id: The unique identifier for the customer. This should be
            their email address or phone number.
            Examples: "ahmed@startup.io", "+923001234567"

    Returns:
        A formatted string containing the full conversation history including
        conversation ID, message count, topics, sentiment trend, resolution
        status, and all individual messages with timestamps. Returns a message
        indicating no history found if the customer has no prior conversations.
    """
    # Check conversation store
    conversation = store.get(email=customer_id, phone=customer_id)

    if not conversation:
        # Check ticket registry as fallback
        tickets = ticket_registry.get_by_customer(customer_id)
        if tickets:
            ticket_summary = "\n".join([
                f"  - {t['ticket_id']}: {t['issue'][:80]} | Status: {t['status']} | Priority: {t['priority']}"
                for t in tickets
            ])
            return (
                f"No conversation history found for {customer_id}.\n"
                f"However, {len(tickets)} ticket(s) exist in the registry:\n{ticket_summary}"
            )
        return f"No conversation history or tickets found for {customer_id}."

    # Build comprehensive history
    parts = []
    parts.append(f"Conversation ID: {conversation.conversation_id}")
    parts.append(f"Customer: {conversation.customer_key}")
    parts.append(f"Total Messages: {conversation.message_count}")
    parts.append(f"Topics Discussed: {', '.join(conversation.topics) if conversation.topics else 'None'}")
    parts.append(f"Sentiment Trend: {conversation.sentiment_trend.direction}")
    parts.append(f"Current Sentiment: {conversation.sentiment_trend.current}")
    parts.append(f"Resolution Status: {conversation.resolution_status}")
    parts.append(f"Last Channel Used: {conversation.last_channel_used}")
    parts.append(f"Conversation Started: {conversation.created_at}")
    parts.append(f"Last Updated: {conversation.updated_at}")

    if conversation.escalation_history:
        parts.append(f"\nEscalation History: {len(conversation.escalation_history)} escalation(s)")
        for esc in conversation.escalation_history:
            parts.append(f"  - {esc['timestamp']}: {esc['reason']} (via {esc['channel']})")

    parts.append("\n--- Message History ---")
    for msg in conversation.messages:
        role_label = "CUSTOMER" if msg.role == "customer" else "AGENT"
        parts.append(f"\n[{role_label}] ({msg.channel}) - {msg.timestamp[:19]}")
        if msg.intent:
            parts.append(f"  Intent: {msg.intent}")
        if msg.sentiment:
            parts.append(f"  Sentiment: {msg.sentiment}")
        preview = msg.content[:300]
        parts.append(f"  {preview}")

    return "\n".join(parts)


@mcp.tool()
async def escalate_to_human(ticket_id: str, reason: str) -> str:
    """Escalate a support ticket to a human agent immediately.

    Use this tool when:
    - The customer explicitly asks to speak to a human, manager, or real person
    - The customer shows significant anger, frustration, or uses profanity
    - The issue involves pricing, billing, refunds, or contracts
    - The issue involves legal, security, or data loss concerns
    - The agent cannot resolve the issue after multiple attempts
    - The customer's sentiment is worsening across interactions
    - The customer threatens to cancel their subscription or churn

    Escalation is irreversible and marks the ticket as 'escalated' status.
    The human support team will be notified and will take over the conversation.

    Args:
        ticket_id: The ID of the ticket to escalate. This should be a valid
            ticket ID returned from create_ticket or process_ticket.
            Examples: "TKT-00001", "TKT-00042"
        reason: A clear explanation of why this ticket is being escalated.
            Include relevant context so the human agent can pick up quickly.
            Examples:
            - "Customer explicitly requested to speak to a manager"
            - "Pricing inquiry for Enterprise plan - requires sales team"
            - "Customer sentiment worsening after 3 unsuccessful troubleshooting attempts"
            - "Security/compliance question requiring legal team review"

    Returns:
        A confirmation string with the ticket_id, escalation reason, timestamp,
        and confirmation that the human team has been notified.
        Returns an error message if the ticket_id is not found.
    """
    ticket = ticket_registry.get(ticket_id)

    if not ticket:
        return f"Error: Ticket {ticket_id} not found. Cannot escalate a non-existent ticket."

    ticket_registry.escalate(ticket_id, reason)

    return (
        f"ESCALATION CONFIRMED\n"
        f"Ticket: {ticket_id}\n"
        f"Customer: {ticket['customer_id']}\n"
        f"Reason: {reason}\n"
        f"Status: ESCALATED\n"
        f"Timestamp: {datetime.now().isoformat()}\n"
        f"The human support team has been notified and will take over this case."
    )


@mcp.tool()
async def send_response(
    ticket_id: str,
    message: str,
    channel: str,
) -> str:
    """Send a channel-appropriate response to a customer for a given ticket.

    Use this tool when:
    - You have generated a helpful response and need to deliver it to the customer
    - You want to ensure the response is formatted correctly for the channel
    - You need to log the response in the ticket history

    This tool automatically applies the correct brand voice and formatting
    based on the channel:
    - EMAIL: Formal greeting, detailed response, professional sign-off
    - WHATSAPP: Casual, concise, friendly tone (optimized for mobile reading)
    - WEB_FORM: Semi-formal, clear and solution-focused

    Args:
        ticket_id: The ID of the ticket this response is for. Must be a valid
            ticket ID from create_ticket.
            Examples: "TKT-00001", "TKT-00042"
        message: The response content to send to the customer. This should be
            the core answer. The tool will automatically wrap it with
            appropriate channel-specific formatting (greeting, sign-off, etc.).
            Examples: "To invite team members, go to Settings > Team > Invite Members..."
        channel: The channel to send the response through. Must match the
            customer's preferred channel.
            Choose from: "email", "whatsapp", "web_form"

    Returns:
        A confirmation string with the ticket_id, channel, formatted response
        preview, and timestamp. Returns an error message if the ticket_id
        is not found.
    """
    ticket = ticket_registry.get(ticket_id)

    if not ticket:
        return f"Error: Ticket {ticket_id} not found. Cannot send response to a non-existent ticket."

    # Validate channel
    valid_channels = [c.value for c in Channel]
    if channel not in valid_channels:
        channel = "email"

    # Apply channel-specific formatting
    formatted_message = _apply_channel_formatting(message, channel)

    # Log the response
    ticket_registry.add_response(ticket_id, formatted_message, channel)

    # Update ticket status to in_progress if it was open
    if ticket["status"] == TicketStatus.OPEN.value:
        ticket["status"] = TicketStatus.IN_PROGRESS.value

    return (
        f"Response sent for ticket {ticket_id}\n"
        f"Channel: {channel}\n"
        f"Customer: {ticket['customer_id']}\n"
        f"Response preview: {formatted_message[:200]}...\n"
        f"Timestamp: {datetime.now().isoformat()}"
    )


@mcp.tool()
async def analyze_sentiment(message: str) -> dict:
    """Analyze the sentiment of a customer message to detect frustration, anger, or satisfaction.

    Use this tool when:
    - You need to assess the emotional tone of a customer's message
    - You want to determine if a customer is becoming frustrated or angry
    - You need to decide whether escalation is warranted based on sentiment
    - You want to track sentiment trends across a conversation
    - You need to adjust your response tone based on the customer's emotional state

    Sentiment levels:
    - "positive": Customer is happy, satisfied, or expressing gratitude
    - "neutral": Customer is asking a straightforward question without strong emotion
    - "negative": Customer shows mild frustration, disappointment, or annoyance
    - "very_negative": Customer is angry, using profanity, or extremely frustrated

    Args:
        message: The customer's message text to analyze. Should be the raw,
            unmodified text as received from the customer.
            Examples:
            - "Thanks for the help, that worked perfectly!"
            - "How do I reset my password?"
            - "This is still not working, I'm getting frustrated"
            - "This is ridiculous! I want to speak to a manager NOW!"

    Returns:
        A dictionary containing:
        - sentiment: The detected sentiment level (positive, neutral, negative, very_negative)
        - score: A numeric score (-2 to +2) where negative values indicate negative sentiment
        - requires_escalation: Boolean indicating if this sentiment level warrants escalation
        - guidance: A brief recommendation on how to respond based on the sentiment
    """
    sentiment = _analyze_sentiment(message)

    # Map to scores
    score_map = {
        "positive": 2,
        "neutral": 0,
        "negative": -1,
        "very_negative": -2,
    }

    # Escalation guidance
    escalation_map = {
        "positive": False,
        "neutral": False,
        "negative": False,
        "very_negative": True,
    }

    guidance_map = {
        "positive": "Customer is satisfied. Continue providing helpful responses.",
        "neutral": "Customer is asking a standard question. Provide clear, helpful assistance.",
        "negative": "Customer shows mild frustration. Be empathetic and try to resolve quickly.",
        "very_negative": "Customer is very upset. Consider immediate escalation to human agent.",
    }

    return {
        "sentiment": sentiment,
        "score": score_map.get(sentiment, 0),
        "requires_escalation": escalation_map.get(sentiment, False),
        "guidance": guidance_map.get(sentiment, ""),
    }


@mcp.tool()
async def get_or_create_customer(
    identifier: str,
    channel: str,
) -> str:
    """Get an existing customer record or create a new one if they don't exist.

    Use this tool when:
    - A new message arrives and you need to identify the customer
    - You want to check if a customer has contacted support before
    - You need to resolve a customer's identity across channels (email vs phone)
    - You want to create a customer record before creating a ticket
    - You need the customer's conversation history and context

    This tool performs cross-channel customer resolution:
    - If the customer was previously seen via email, and now contacts via
      WhatsApp with the same email, they will be matched to the same record.
    - A new conversation is created only for truly new customers.

    Args:
        identifier: The customer's unique identifier. This should be their
            email address or phone number.
            Examples: "ahmed@startup.io", "+923001234567"
        channel: The channel through which the customer is currently reaching
            out. This helps track which channel they last used.
            Choose from: "email", "whatsapp", "web_form"

    Returns:
        A formatted string containing the customer's information including:
        - Whether this is a new or existing customer
        - Conversation ID (if existing)
        - Message count
        - Topics previously discussed
        - Sentiment trend
        - Resolution status
        - Last channel used
        - When a new customer is created, returns the new conversation ID
          and initial details.
    """
    # Determine if identifier is email or phone
    is_email = "@" in identifier
    email = identifier if is_email else None
    phone = identifier if not is_email else None

    # Validate channel
    valid_channels = [c.value for c in Channel]
    if channel not in valid_channels:
        channel = "email"

    # Check if customer exists
    existing_conv = store.get(email=email, phone=phone)

    if existing_conv:
        return (
            f"EXISTING CUSTOMER FOUND\n"
            f"Identifier: {identifier}\n"
            f"Channel: {channel}\n"
            f"Conversation ID: {existing_conv.conversation_id}\n"
            f"Message Count: {existing_conv.message_count}\n"
            f"Topics: {', '.join(existing_conv.topics) if existing_conv.topics else 'None yet'}\n"
            f"Sentiment Trend: {existing_conv.sentiment_trend.direction}\n"
            f"Current Sentiment: {existing_conv.sentiment_trend.current}\n"
            f"Resolution Status: {existing_conv.resolution_status}\n"
            f"Last Channel Used: {existing_conv.last_channel_used}\n"
            f"Conversation Started: {existing_conv.created_at}"
        )
    else:
        # Create new customer
        conversation = store.get_or_create(email=email, phone=phone)
        return (
            f"NEW CUSTOMER CREATED\n"
            f"Identifier: {identifier}\n"
            f"Channel: {channel}\n"
            f"Conversation ID: {conversation.conversation_id}\n"
            f"Message Count: 0\n"
            f"Status: New customer, no prior interactions\n"
            f"Created: {conversation.created_at}"
        )


# ──────────────────────────────────────────────────────────────
# HELPER: Channel-Aware Response Formatting
# ──────────────────────────────────────────────────────────────

def _apply_channel_formatting(message: str, channel: str) -> str:
    """Apply channel-specific formatting to a response message."""
    if channel == Channel.WHATSAPP.value:
        # Keep it short and casual
        return (
            f"Hey! Here's what you need to know:\n\n"
            f"{message[:500]}\n\n"
            f"Let me know if you need more help!"
        )
    elif channel == Channel.EMAIL.value:
        # Formal and detailed
        return (
            f"Dear Valued Customer,\n\n"
            f"Thank you for reaching out to FlowSync support.\n\n"
            f"{message}\n\n"
            f"If you have any further questions, please don't hesitate to ask.\n\n"
            f"Best regards,\n"
            f"FlowSync Customer Success Team"
        )
    else:  # web_form
        return (
            f"Thanks for your message!\n\n"
            f"{message}\n\n"
            f"Let me know if you need anything else!\n\n"
            f"Best,\n"
            f"FlowSync Support"
        )


# ──────────────────────────────────────────────────────────────
# SERVER ENTRY POINT
# ──────────────────────────────────────────────────────────────

def run_server():
    """Start the MCP server using stdio transport."""
    print("Starting FlowSync Customer Success AI Agent MCP Server...", file=sys.stderr)
    print("Tools available:", file=sys.stderr)
    for tool_name in [
        "search_knowledge_base",
        "create_ticket",
        "get_customer_history",
        "escalate_to_human",
        "send_response",
        "analyze_sentiment",
        "get_or_create_customer",
    ]:
        print(f"  - {tool_name}", file=sys.stderr)
    print("Server ready. Waiting for MCP client connections...", file=sys.stderr)

    mcp.run(transport="stdio")


# ──────────────────────────────────────────────────────────────
# TEST HARNESS
# ──────────────────────────────────────────────────────────────

async def run_tests():
    """Test all MCP tools and display results."""
    print("\n" + "=" * 70)
    print("  FlowSync MCP Server -- Tool Test Suite")
    print("=" * 70)

    # Test 1: search_knowledge_base
    print("\n[TEST 1] search_knowledge_base")
    print("-" * 50)
    result = await search_knowledge_base("How do I invite team members?")
    print(f"Query: 'How do I invite team members?'")
    print(f"Result length: {len(result)} chars")
    print(f"Result preview: {result[:200]}...")

    # Test 2: analyze_sentiment
    print("\n[TEST 2] analyze_sentiment")
    print("-" * 50)
    test_messages = [
        "Thanks for the help, that worked perfectly!",
        "How do I reset my password?",
        "This is still not working, I'm getting frustrated",
        "This is ridiculous! I want to speak to a manager NOW!",
    ]
    for msg in test_messages:
        result = await analyze_sentiment(msg)
        print(f"  Message: '{msg[:60]}...'")
        print(f"  Sentiment: {result['sentiment']} | Score: {result['score']} | Escalation: {result['requires_escalation']}")
        print()

    # Test 3: get_or_create_customer
    print("\n[TEST 3] get_or_create_customer")
    print("-" * 50)
    result = await get_or_create_customer("test@hackathon.com", "email")
    print(result)

    # Test 4: create_ticket
    print("\n[TEST 4] create_ticket")
    print("-" * 50)
    result = await create_ticket(
        customer_id="test@hackathon.com",
        issue="Slack integration not syncing tasks",
        priority="high",
        channel="email",
    )
    print(result)
    # Extract ticket_id from result: "Ticket TKT-00001 created for..."
    ticket_id = result.split()[1]
    print(f"Extracted ticket_id: {ticket_id}")

    # Test 5: send_response
    print("\n[TEST 5] send_response")
    print("-" * 50)
    result = await send_response(
        ticket_id=ticket_id,
        message="To reconnect Slack, go to Settings > Integrations > Slack > Disconnect > Reconnect.",
        channel="email",
    )
    print(result)

    # Test 6: get_customer_history
    print("\n[TEST 6] get_customer_history")
    print("-" * 50)
    result = await get_customer_history("test@hackathon.com")
    print(result[:500])

    # Test 7: escalate_to_human
    print("\n[TEST 7] escalate_to_human")
    print("-" * 50)
    result = await escalate_to_human(
        ticket_id=ticket_id,
        reason="Customer requested to speak to a manager",
    )
    print(result)

    # Test 8: Cross-channel customer creation
    print("\n[TEST 8] Cross-channel customer resolution")
    print("-" * 50)
    result1 = await get_or_create_customer("crosschannel@test.com", "email")
    print("First contact (email):")
    print(result1)
    result2 = await get_or_create_customer("crosschannel@test.com", "whatsapp")
    print("\nSecond contact (whatsapp, same email):")
    print(result2)

    # Test 9: Invalid ticket handling
    print("\n[TEST 9] Invalid ticket handling")
    print("-" * 50)
    result = await escalate_to_human("TKT-99999", "Testing invalid ticket")
    print(result)

    # Summary
    print("\n" + "=" * 70)
    print("  ALL TESTS COMPLETED")
    print("=" * 70)
    print(f"\n  Tools tested: 7/7")
    print(f"  Tickets created: {len(ticket_registry._tickets)}")
    print(f"  Conversations in store: {len(store._conversations)}")
    print()


def main():
    """Entry point: run server or tests based on command-line args."""
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("\nRunning MCP Server tool tests...\n")
        asyncio.run(run_tests())
    else:
        run_server()


if __name__ == "__main__":
    main()
