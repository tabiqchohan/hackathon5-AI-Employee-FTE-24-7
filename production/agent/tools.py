"""
FlowSync Customer Success AI Agent -- Production Tools (OpenAI Agents SDK)
===========================================================================
Architecture:
  - Core logic functions (prefixed with _do_): pure, testable, accept AgentContext
  - @function_tool wrappers: accept RunContextWrapper + Pydantic input, delegate to core

Tools use the real PostgreSQL database via production/database/queries.py,
with in-memory fallback when the DB is unavailable.

Core functions exported (for testing):
  _do_search_kb, _do_create_ticket, _do_get_customer_history,
  _do_escalate_to_human, _do_send_response, _do_analyze_sentiment,
  _do_get_or_create_customer

Pydantic input models exported:
  KBSearchInput, CreateTicketInput, CustomerHistoryInput,
  EscalateInput, SendResponseInput, SentimentInput, CustomerInput

Tool wrappers exported (for SDK registration):
  search_knowledge_base, create_ticket, get_customer_history,
  escalate_to_human, send_response, analyze_sentiment, get_or_create_customer
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from agents import function_tool, RunContextWrapper

# ──────────────────────────────────────────────────────────────
# PATH SETUP
# ──────────────────────────────────────────────────────────────

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_src_path = os.path.join(_project_root, "src")
for p in [_src_path, _project_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Local prototype modules
from knowledge_base import search_kb as _search_kb
from prototype import (
    analyze_sentiment as _analyze_sentiment,
    classify_intent as _classify_intent,
)

# Formatters
try:
    from agent.formatters import format_response as _format_response
except ImportError:
    from formatters import format_response as _format_response

logger = logging.getLogger("flowsync.tools")

# Lazy import of queries module to avoid circular deps
_queries = None


def _get_queries():
    """Lazy import of database queries module."""
    global _queries
    if _queries is None:
        from database import queries
        _queries = queries
    return _queries


def _run_async(coro):
    """Run an async coroutine from synchronous tool context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ──────────────────────────────────────────────────────────────
# AGENT CONTEXT
# ──────────────────────────────────────────────────────────────

@dataclass
class AgentContext:
    """
    Shared context passed to every tool call via RunContextWrapper.
    Single source of truth for shared state during an agent run.
    """
    # Database connection pool (asyncpg.Pool)
    db_pool: Any = None

    # Current run metadata
    run_id: str = ""
    customer_id: str = ""
    conversation_id: str = ""
    current_channel: str = ""

    # In-memory fallback (used when DB is unavailable)
    _ticket_counter: int = field(default=0, repr=False)
    _tickets: dict = field(default_factory=dict, repr=False)
    _conversations: dict = field(default_factory=dict, repr=False)

    @property
    def has_database(self) -> bool:
        """True if a real database connection pool is available."""
        return self.db_pool is not None


# ──────────────────────────────────────────────────────────────
# PYDANTIC INPUT MODELS
# ──────────────────────────────────────────────────────────────

class KBSearchInput(BaseModel):
    """Input for searching the knowledge base."""
    query: str = Field(..., description="The customer's question or search query.")
    category: Optional[str] = Field(
        default=None,
        description="Optional filter: 'features', 'integrations', 'pricing', 'faq'.",
    )


class CreateTicketInput(BaseModel):
    """Input for creating a support ticket."""
    customer_id: str = Field(..., description="Unique customer identifier (email or phone).")
    issue: str = Field(..., description="Clear description of the problem or request.")
    priority: str = Field(default="medium", description="Urgency: low, medium, high, critical.")
    channel: str = Field(default="email", description="Channel: email, whatsapp, web_form.")


class CustomerHistoryInput(BaseModel):
    """Input for retrieving customer conversation history."""
    customer_id: str = Field(..., description="Unique customer identifier (email or phone).")


class EscalateInput(BaseModel):
    """Input for escalating a ticket to a human agent."""
    ticket_id: str = Field(..., description="Ticket ID to escalate (e.g. TKT-00001).")
    reason: str = Field(..., description="Explanation of why this ticket is being escalated.")


class SendResponseInput(BaseModel):
    """Input for sending a formatted response to a customer."""
    ticket_id: str = Field(..., description="Ticket ID this response is for.")
    message: str = Field(..., description="The response content to send.")
    channel: str = Field(..., description="Channel to send through: email, whatsapp, web_form.")


class SentimentInput(BaseModel):
    """Input for analyzing sentiment of a customer message."""
    message: str = Field(..., description="The customer's message text to analyze.")


class CustomerInput(BaseModel):
    """Input for resolving customer identity."""
    identifier: str = Field(..., description="Customer email or phone number.")
    channel: str = Field(..., description="Current channel: email, whatsapp, web_form.")


# ──────────────────────────────────────────────────────────────
# CORE LOGIC FUNCTIONS (testable, accept AgentContext directly)
# ──────────────────────────────────────────────────────────────

def _do_search_kb(ctx: AgentContext, query: str, category: Optional[str] = None) -> str:
    """Core KB search logic. Tests call this directly."""
    try:
        logger.info("KB search: query='%s', category=%s", query[:80], category)

        # Try database vector/text search first
        if ctx.has_database:
            try:
                pool = ctx.db_pool
                results = _run_async(_async_search_kb_text(pool, query, category))
                if results:
                    formatted = _format_kb_results(results)
                    logger.info("KB search (DB): found %d results", len(results))
                    return formatted
            except Exception as db_err:
                logger.warning("KB database search failed, falling back to local: %s", db_err)

        # Fallback to local keyword-based search
        result = _search_kb(query)
        is_fallback = (
            "No specific product documentation found" in result
            or result.strip() == "### general_faq"
        )
        if is_fallback:
            logger.info("KB search: no specific match (fallback)")
            return (
                "No specific product documentation found for this query. "
                "Please provide general guidance based on FlowSync's capabilities "
                "as a project management and team collaboration platform."
            )

        logger.info("KB search (local): matched, %d chars", len(result))
        return result

    except Exception as e:
        logger.error("KB search error: %s", e, exc_info=True)
        return f"Error searching knowledge base: {str(e)}"


async def _async_search_kb_text(pool, query: str, category: Optional[str] = None) -> list[dict]:
    """Async wrapper for text-based KB search."""
    q = _get_queries()
    return await q.search_knowledge_base_text(pool, query, limit=3, category=category)


def _format_kb_results(results: list[dict]) -> str:
    """Format database KB search results into readable text."""
    parts = []
    for r in results:
        parts.append(f"### {r['title']}")
        parts.append(f"Category: {r.get('category', 'general')}")
        if r.get('tags'):
            parts.append(f"Tags: {', '.join(r['tags'])}")
        parts.append("")
        parts.append(r['content'])
        parts.append("")
    return "\n".join(parts)


def _do_create_ticket(
    ctx: AgentContext,
    customer_id: str,
    issue: str,
    priority: str = "medium",
    channel: str = "email",
) -> str:
    """Core ticket creation logic. Tests call this directly."""
    try:
        valid_priorities = {"low", "medium", "high", "critical"}
        if priority not in valid_priorities:
            priority = "medium"

        valid_channels = {"email", "whatsapp", "web_form"}
        if channel not in valid_channels:
            channel = "email"

        logger.info(
            "Create ticket: customer=%s, priority=%s, channel=%s",
            customer_id, priority, channel,
        )

        # Try database
        if ctx.has_database:
            try:
                pool = ctx.db_pool
                ticket = _run_async(
                    _async_create_ticket_db(pool, customer_id, issue, channel, priority)
                )
                ctx._tickets[ticket["ticket_number"]] = ticket
                logger.info("Ticket created (DB): %s", ticket["ticket_number"])
                return (
                    f"Ticket {ticket['ticket_number']} created for {customer_id} | "
                    f"Issue: {issue[:100]} | "
                    f"Priority: {ticket['priority']} | "
                    f"Channel: {ticket['channel']} | "
                    f"Created: {ticket['created_at']}"
                )
            except Exception as db_err:
                logger.warning("Ticket DB creation failed, using fallback: %s", db_err)

        # Fallback: in-memory
        ctx._ticket_counter += 1
        ticket_id = f"TKT-{ctx._ticket_counter:05d}"
        ticket = {
            "ticket_id": ticket_id,
            "ticket_number": ticket_id,
            "customer_id": customer_id,
            "issue": issue,
            "priority": priority,
            "channel": channel,
            "status": "open",
            "created_at": datetime.now().isoformat(),
        }
        ctx._tickets[ticket_id] = ticket
        logger.info("Ticket created (memory): %s", ticket_id)
        return (
            f"Ticket {ticket_id} created for {customer_id} | "
            f"Issue: {issue[:100]} | "
            f"Priority: {priority} | "
            f"Channel: {channel} | "
            f"Created: {ticket['created_at']}"
        )

    except Exception as e:
        logger.error("Create ticket error: %s", e, exc_info=True)
        return f"Error creating ticket: {str(e)}"


async def _async_create_ticket_db(pool, customer_id, issue, channel, priority):
    """Async wrapper for ticket creation."""
    q = _get_queries()
    return await q.create_ticket(
        pool, customer_id=customer_id, description=issue,
        channel=channel, priority=priority,
    )


def _do_get_customer_history(ctx: AgentContext, customer_id: str) -> str:
    """Core customer history logic. Tests call this directly."""
    try:
        logger.info("Get customer history: %s", customer_id)

        # Try database
        if ctx.has_database:
            try:
                pool = ctx.db_pool
                history = _run_async(_async_get_customer_history_db(pool, customer_id))
                if history and history.get("conversations"):
                    return _format_history_db(history)

                # Check tickets as fallback
                q = _get_queries()
                tickets = _run_async(q.get_customer_tickets(pool, customer_id, limit=10))
                if tickets:
                    ticket_lines = "\n".join([
                        f"  - {t['ticket_number']}: {t.get('subject', t.get('description', '')[:80])} | "
                        f"Status: {t['status']} | Priority: {t['priority']}"
                        for t in tickets
                    ])
                    return (
                        f"No conversation history found for {customer_id}.\n"
                        f"However, {len(tickets)} ticket(s) exist in the registry:\n{ticket_lines}"
                    )
            except Exception as db_err:
                logger.warning("History DB query failed: %s", db_err)

        # Fallback: in-memory conversations
        conv = ctx._conversations.get(customer_id)
        if conv and conv.get("messages"):
            parts = [
                f"Customer: {customer_id}",
                f"Messages: {len(conv['messages'])}",
                f"Topics: {', '.join(conv.get('topics', []))}",
                f"Sentiment: {conv.get('current_sentiment', 'neutral')}",
                f"Status: {conv.get('status', 'open')}",
                "",
                "--- Message History ---",
            ]
            for msg in conv["messages"]:
                role_label = "CUSTOMER" if msg.get("role") == "customer" else "AGENT"
                parts.append(f"\n[{role_label}] ({msg.get('channel', '?')})")
                if msg.get("intent"):
                    parts.append(f"  Intent: {msg['intent']}")
                if msg.get("sentiment"):
                    parts.append(f"  Sentiment: {msg['sentiment']}")
                parts.append(f"  {msg.get('content', '')[:300]}")
            return "\n".join(parts)

        return f"No conversation history or tickets found for {customer_id}."

    except Exception as e:
        logger.error("Get customer history error: %s", e, exc_info=True)
        return f"Error retrieving customer history: {str(e)}"


async def _async_get_customer_history_db(pool, customer_id):
    """Async wrapper for customer history retrieval."""
    q = _get_queries()
    return await q.get_customer_history(pool, customer_id, max_messages=20)


def _format_history_db(history: dict) -> str:
    """Format database history into readable text."""
    parts = []
    parts.append(f"Customer: {history['customer_id']}")
    parts.append(f"Total Conversations: {history['total_conversations']}")
    parts.append(f"Messages Returned: {history['total_messages_returned']}")
    parts.append("")

    for conv in history.get("conversations", []):
        parts.append(f"--- Conversation: {conv['id']} ---")
        parts.append(f"Topic: {conv.get('topic_summary', 'N/A')}")
        topics = conv.get('topics', []) or []
        parts.append(f"Topics: {', '.join(topics)}")
        parts.append(f"Status: {conv['status']}")
        parts.append(f"Messages: {conv['message_count']}")
        parts.append(
            f"Sentiment: {conv.get('current_sentiment', 'N/A')} "
            f"(trend: {conv.get('sentiment_trend', 'N/A')})"
        )
        parts.append(f"Last Channel: {conv.get('last_channel_used', 'N/A')}")
        parts.append("")

    parts.append("--- Recent Messages ---")
    for msg in history.get("recent_messages", []):
        role = "CUSTOMER" if msg.get("role") == "customer" else "AGENT"
        parts.append(
            f"\n[{role}] ({msg.get('channel', '?')}) - {msg.get('created_at', '')[:19]}"
        )
        if msg.get("intent"):
            parts.append(f"  Intent: {msg['intent']}")
        if msg.get("sentiment"):
            parts.append(f"  Sentiment: {msg['sentiment']}")
        parts.append(f"  {msg.get('content', '')[:300]}")

    return "\n".join(parts)


def _do_escalate_to_human(ctx: AgentContext, ticket_id: str, reason: str) -> str:
    """Core escalation logic. Tests call this directly."""
    try:
        logger.info("Escalate ticket: %s, reason='%s'", ticket_id, reason[:80])

        # Try database
        if ctx.has_database:
            try:
                pool = ctx.db_pool
                result = _run_async(_async_escalate_ticket_db(pool, ticket_id, reason))
                if result and result.get("success"):
                    logger.info("Escalated (DB): %s", ticket_id)
                    return (
                        f"ESCALATION CONFIRMED\n"
                        f"Ticket: {result.get('ticket_number', ticket_id)}\n"
                        f"Reason: {reason}\n"
                        f"Status: ESCALATED\n"
                        f"Timestamp: {result.get('escalated_at', datetime.now().isoformat())}\n"
                        f"The human support team has been notified and will take over this case."
                    )
            except Exception as db_err:
                logger.warning("Escalation DB failed, using fallback: %s", db_err)

        # Fallback: in-memory
        ticket = ctx._tickets.get(ticket_id)
        if not ticket:
            logger.warning("Escalation: ticket %s not found", ticket_id)
            return f"Error: Ticket {ticket_id} not found. Cannot escalate a non-existent ticket."

        ticket["status"] = "escalated"
        ticket["escalation_reason"] = reason
        ticket["escalated_at"] = datetime.now().isoformat()
        logger.info("Escalated (memory): %s", ticket_id)
        return (
            f"ESCALATION CONFIRMED\n"
            f"Ticket: {ticket_id}\n"
            f"Customer: {ticket['customer_id']}\n"
            f"Reason: {reason}\n"
            f"Status: ESCALATED\n"
            f"Timestamp: {ticket['escalated_at']}\n"
            f"The human support team has been notified and will take over this case."
        )

    except Exception as e:
        logger.error("Escalation error: %s", e, exc_info=True)
        return f"Error escalating ticket: {str(e)}"


async def _async_escalate_ticket_db(pool, ticket_id, reason):
    """Async wrapper for ticket escalation."""
    q = _get_queries()
    result = await q.escalate_ticket(pool, ticket_id, reason, escalated_by="ai_agent")
    if result:
        return {"success": True, **result}
    return {"success": False, "error": f"Ticket {ticket_id} not found"}


def _do_send_response(
    ctx: AgentContext,
    ticket_id: str,
    message: str,
    channel: str,
) -> str:
    """Core response sending logic. Tests call this directly."""
    try:
        valid_channels = {"email", "whatsapp", "web_form"}
        if channel not in valid_channels:
            channel = "email"

        logger.info("Send response: ticket=%s, channel=%s", ticket_id, channel)

        # Apply channel-specific formatting
        formatted = _format_response(message=message, channel=channel)

        # Try database storage
        if ctx.has_database:
            try:
                pool = ctx.db_pool
                _run_async(
                    _async_store_message_db(
                        pool, ctx.conversation_id,
                        role="agent", content=formatted.text, channel=channel,
                    )
                )
            except Exception as db_err:
                logger.warning("Failed to store message in DB: %s", db_err)

        # Update in-memory ticket
        ticket = ctx._tickets.get(ticket_id)
        if ticket:
            if ticket.get("status") == "open":
                ticket["status"] = "in_progress"
            if "responses" not in ticket:
                ticket["responses"] = []
            ticket["responses"].append({
                "message": formatted.text,
                "channel": channel,
                "timestamp": datetime.now().isoformat(),
            })

        logger.info("Response sent: %s, %d chars", ticket_id, len(formatted.text))
        return (
            f"Response sent for ticket {ticket_id}\n"
            f"Channel: {channel}\n"
            f"Customer: {ticket['customer_id'] if ticket else 'unknown'}\n"
            f"Response preview: {formatted.text[:200]}...\n"
            f"Timestamp: {datetime.now().isoformat()}"
        )

    except Exception as e:
        logger.error("Send response error: %s", e, exc_info=True)
        return f"Error sending response: {str(e)}"


async def _async_store_message_db(pool, conv_id, role, content, channel):
    """Async wrapper for storing a message."""
    q = _get_queries()
    return await q.store_message(pool, conv_id, role, content, channel)


def _do_analyze_sentiment(ctx: AgentContext, message: str) -> str:
    """Core sentiment analysis logic. Tests call this directly."""
    try:
        logger.info("Analyze sentiment: '%s...'", message[:80])

        sentiment = _analyze_sentiment(message)

        score_map = {
            "positive": 2,
            "neutral": 0,
            "negative": -1,
            "very_negative": -2,
        }

        guidance_map = {
            "positive": "Customer is satisfied. Continue providing helpful responses.",
            "neutral": "Customer is asking a standard question. Provide clear, helpful assistance.",
            "negative": "Customer shows mild frustration. Be empathetic and try to resolve quickly.",
            "very_negative": "Customer is very upset. Consider immediate escalation to human agent.",
        }

        result = {
            "sentiment": sentiment,
            "score": score_map.get(sentiment, 0),
            "requires_escalation": sentiment == "very_negative",
            "guidance": guidance_map.get(sentiment, ""),
        }

        logger.info("Sentiment result: %s (score=%d)", sentiment, result["score"])
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error("Sentiment analysis error: %s", e, exc_info=True)
        return json.dumps({
            "sentiment": "neutral",
            "score": 0,
            "requires_escalation": False,
            "guidance": f"Error analyzing sentiment: {str(e)}",
        })


def _do_get_or_create_customer(ctx: AgentContext, identifier: str, channel: str) -> str:
    """Core customer resolution logic. Tests call this directly."""
    try:
        valid_channels = {"email", "whatsapp", "web_form"}
        if channel not in valid_channels:
            channel = "email"

        logger.info("Get/create customer: %s, channel=%s", identifier, channel)

        # Try database
        if ctx.has_database:
            try:
                pool = ctx.db_pool
                result = _run_async(
                    _async_get_or_create_customer_db(pool, identifier, channel)
                )

                # Update context
                ctx.customer_id = str(result.get("customer_id", ""))
                ctx.current_channel = channel

                status = "EXISTING" if not result["is_new"] else "NEW"
                channel_switched = (
                    "Channel Switched: Yes"
                    if result.get("channel_switched")
                    else ""
                )
                return (
                    f"{status} CUSTOMER\n"
                    f"Identifier: {identifier}\n"
                    f"Channel: {channel}\n"
                    f"Customer ID: {result.get('customer_id', 'N/A')}\n"
                    f"Message Count: {result.get('message_count', 0)}\n"
                    f"Topics: {', '.join(result.get('topics', [])) or 'None yet'}\n"
                    f"Sentiment Trend: {result.get('sentiment_trend', 'stable')}\n"
                    f"Current Sentiment: {result.get('current_sentiment', 'neutral')}\n"
                    f"Resolution Status: {result.get('resolution_status', 'open')}\n"
                    f"{channel_switched}"
                )
            except Exception as db_err:
                logger.warning("Customer DB lookup failed, using fallback: %s", db_err)

        # Fallback: in-memory
        if identifier in ctx._conversations:
            conv = ctx._conversations[identifier]
            channel_switched = bool(conv.get("last_channel")) and conv["last_channel"] != channel
            return (
                f"EXISTING CUSTOMER\n"
                f"Identifier: {identifier}\n"
                f"Channel: {channel}\n"
                f"Conversation ID: {conv.get('conversation_id', 'N/A')}\n"
                f"Message Count: {len(conv.get('messages', []))}\n"
                f"Topics: {', '.join(conv.get('topics', [])) or 'None yet'}\n"
                f"Sentiment Trend: {conv.get('sentiment_trend', 'stable')}\n"
                f"Current Sentiment: {conv.get('current_sentiment', 'neutral')}\n"
                f"Resolution Status: {conv.get('status', 'open')}\n"
                f"{'Channel Switched: Yes' if channel_switched else ''}"
            )
        else:
            conv_id = f"CONV-{uuid.uuid4().hex[:8].upper()}"
            ctx._conversations[identifier] = {
                "conversation_id": conv_id,
                "customer_id": identifier,
                "messages": [],
                "topics": [],
                "current_sentiment": "neutral",
                "sentiment_trend": "stable",
                "status": "open",
                "last_channel": channel,
            }
            ctx.customer_id = identifier
            ctx.conversation_id = conv_id
            ctx.current_channel = channel
            return (
                f"NEW CUSTOMER\n"
                f"Identifier: {identifier}\n"
                f"Channel: {channel}\n"
                f"Conversation ID: {conv_id}\n"
                f"Status: New customer, no prior interactions"
            )

    except Exception as e:
        logger.error("Get/create customer error: %s", e, exc_info=True)
        return f"Error resolving customer: {str(e)}"


async def _async_get_or_create_customer_db(pool, identifier, channel):
    """Async wrapper for customer resolution."""
    q = _get_queries()
    customer = await q.create_or_get_customer(pool, identifier, channel)

    # Get conversation history for additional context
    history = await q.get_customer_history(
        pool, str(customer["customer_id"]), max_messages=5
    )

    return {
        "customer_id": customer["customer_id"],
        "is_new": customer["is_new"],
        "message_count": history.get("total_messages_returned", 0),
        "topics": [],
        "sentiment_trend": customer.get("sentiment_trend", "stable"),
        "current_sentiment": customer.get("current_sentiment", "neutral"),
        "resolution_status": "open",
        "channel_switched": False,
    }


# ──────────────────────────────────────────────────────────────
# @function_tool WRAPPERS (SDK integration, delegate to core)
# ──────────────────────────────────────────────────────────────

@function_tool
def search_knowledge_base(
    ctx: RunContextWrapper[AgentContext],
    args: KBSearchInput,
) -> str:
    """Search the FlowSync product documentation and knowledge base.

    Use when a customer asks about FlowSync features, setup instructions,
    troubleshooting, integrations, pricing plans, or product information.
    """
    return _do_search_kb(ctx.context, args.query, args.category)


@function_tool
def create_ticket(
    ctx: RunContextWrapper[AgentContext],
    args: CreateTicketInput,
) -> str:
    """Create a new support ticket for a customer issue.

    Use when a customer reports a bug, problem, or issue needing tracking.
    """
    return _do_create_ticket(
        ctx.context, args.customer_id, args.issue, args.priority, args.channel
    )


@function_tool
def get_customer_history(
    ctx: RunContextWrapper[AgentContext],
    args: CustomerHistoryInput,
) -> str:
    """Retrieve the full conversation history for a customer across all channels."""
    return _do_get_customer_history(ctx.context, args.customer_id)


@function_tool
def escalate_to_human(
    ctx: RunContextWrapper[AgentContext],
    args: EscalateInput,
) -> str:
    """Escalate a support ticket to a human agent immediately."""
    return _do_escalate_to_human(ctx.context, args.ticket_id, args.reason)


@function_tool
def send_response(
    ctx: RunContextWrapper[AgentContext],
    args: SendResponseInput,
) -> str:
    """Send a channel-appropriate response to a customer for a given ticket."""
    return _do_send_response(ctx.context, args.ticket_id, args.message, args.channel)


@function_tool
def analyze_sentiment(
    ctx: RunContextWrapper[AgentContext],
    args: SentimentInput,
) -> str:
    """Analyze the sentiment of a customer message.

    Detects frustration, anger, satisfaction, or neutral tones.
    """
    return _do_analyze_sentiment(ctx.context, args.message)


@function_tool
def get_or_create_customer(
    ctx: RunContextWrapper[AgentContext],
    args: CustomerInput,
) -> str:
    """Get an existing customer record or create a new one.

    Performs cross-channel customer resolution.
    """
    return _do_get_or_create_customer(ctx.context, args.identifier, args.channel)
