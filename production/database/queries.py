"""
FlowSync Customer Success AI Agent -- Database Queries
=======================================================
Async database query functions using asyncpg for the PostgreSQL backend.
Provides the data access layer for the production agent.

Usage:
    from database.queries import get_db_pool, create_or_get_customer, ...
    pool = await get_db_pool()
    result = await create_or_get_customer(pool, "test@example.com", "email")
"""

from __future__ import annotations

import os
from typing import Optional

import asyncpg


# ──────────────────────────────────────────────────────────────
# CONNECTION
# ──────────────────────────────────────────────────────────────

_db_pool: Optional[asyncpg.Pool] = None


async def get_db_pool(
    dsn: Optional[str] = None,
    min_size: int = 5,
    max_size: int = 20,
) -> asyncpg.Pool:
    """
    Get or create the asyncpg connection pool.

    Args:
        dsn: PostgreSQL connection string. If None, reads from DATABASE_URL env var.
            Format: postgresql://user:password@host:port/database
        min_size: Minimum number of connections in the pool.
        max_size: Maximum number of connections in the pool.

    Returns:
        asyncpg.Pool instance.

    Example:
        pool = await get_db_pool("postgresql://flowsync:pass@localhost:5432/flowsync")
    """
    global _db_pool

    if _db_pool is not None:
        return _db_pool

    connection_string = dsn or os.environ.get("DATABASE_URL")
    if not connection_string:
        raise ValueError(
            "DATABASE_URL environment variable not set. "
            "Provide a DSN argument or set DATABASE_URL. "
            "Example: postgresql://user:password@localhost:5432/flowsync"
        )

    _db_pool = await asyncpg.create_pool(
        dsn=connection_string,
        min_size=min_size,
        max_size=max_size,
        command_timeout=30,
    )

    return _db_pool


async def close_db_pool():
    """Close the connection pool. Call on application shutdown."""
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None


# ──────────────────────────────────────────────────────────────
# CUSTOMER QUERIES
# ──────────────────────────────────────────────────────────────

async def create_or_get_customer(
    pool: asyncpg.Pool,
    identifier: str,
    channel: str,
    display_name: Optional[str] = None,
    company_name: Optional[str] = None,
) -> dict:
    """
    Create a new customer or return existing one.

    Resolves customer identity by identifier (email or phone).
    If the identifier already exists, returns the existing customer.
    If not, creates a new customer record and adds the identifier.

    Args:
        pool: asyncpg connection pool.
        identifier: Customer email or phone number.
        channel: Communication channel ('email', 'whatsapp', 'web_form').
        display_name: Optional customer display name.
        company_name: Optional company name.

    Returns:
        dict with keys: customer_id, is_new, display_name, current_sentiment,
        sentiment_trend, total_tickets, first_contact_at, last_contact_at.

    Example:
        result = await create_or_get_customer(pool, "ahmed@startup.io", "email")
        # {'customer_id': UUID, 'is_new': True, 'display_name': None, ...}
    """
    identifier_type = "email" if "@" in identifier else "phone"
    identifier_value = identifier.lower().strip() if identifier_type == "email" else identifier.strip()

    async with pool.acquire() as conn:
        # Try to find existing identifier
        existing = await conn.fetchrow(
            """
            SELECT c.id AS customer_id, c.display_name, c.company_name,
                   c.current_sentiment, c.sentiment_trend,
                   c.total_tickets, c.first_contact_at, c.last_contact_at
            FROM customer_identifiers ci
            JOIN customers c ON c.id = ci.customer_id
            WHERE ci.identifier_type = $1
              AND ci.identifier_value = $2
              AND c.is_deleted = FALSE
            """,
            identifier_type,
            identifier_value,
        )

        if existing:
            # Update last_contact_at
            await conn.execute(
                """
                UPDATE customers
                SET last_contact_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                """,
                existing["customer_id"],
            )
            return {
                "customer_id": existing["customer_id"],
                "is_new": False,
                "display_name": existing["display_name"],
                "company_name": existing["company_name"],
                "current_sentiment": existing["current_sentiment"],
                "sentiment_trend": existing["sentiment_trend"],
                "total_tickets": existing["total_tickets"],
                "first_contact_at": existing["first_contact_at"],
                "last_contact_at": existing["last_contact_at"],
            }

        # Create new customer
        customer = await conn.fetchrow(
            """
            INSERT INTO customers (display_name, company_name, first_contact_at, last_contact_at)
            VALUES ($1, $2, NOW(), NOW())
            RETURNING id, display_name, company_name, current_sentiment, sentiment_trend,
                      total_tickets, first_contact_at, last_contact_at
            """,
            display_name,
            company_name,
        )

        # Add identifier
        await conn.execute(
            """
            INSERT INTO customer_identifiers
                (customer_id, identifier_type, identifier_value, preferred_channel)
            VALUES ($1, $2, $3, $4::channel_type)
            """,
            customer["id"],
            identifier_type,
            identifier_value,
            channel,
        )

        return {
            "customer_id": customer["id"],
            "is_new": True,
            "display_name": customer["display_name"],
            "company_name": customer["company_name"],
            "current_sentiment": customer["current_sentiment"],
            "sentiment_trend": customer["sentiment_trend"],
            "total_tickets": customer["total_tickets"],
            "first_contact_at": customer["first_contact_at"],
            "last_contact_at": customer["last_contact_at"],
        }


async def get_customer_by_id(
    pool: asyncpg.Pool,
    customer_id: str,
) -> Optional[dict]:
    """
    Get customer details by UUID.

    Args:
        pool: asyncpg connection pool.
        customer_id: Customer UUID string.

    Returns:
        dict with customer details or None if not found.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, display_name, company_name, flowsync_plan,
                   total_tickets, escalated_tickets,
                   current_sentiment, sentiment_trend,
                   first_contact_at, last_contact_at
            FROM customers
            WHERE id = $1 AND is_deleted = FALSE
            """,
            customer_id,
        )
        return dict(row) if row else None


async def get_customer_identifiers(
    pool: asyncpg.Pool,
    customer_id: str,
) -> list[dict]:
    """
    Get all identifiers (email, phone, etc.) for a customer.

    Args:
        pool: asyncpg connection pool.
        customer_id: Customer UUID string.

    Returns:
        List of dicts with identifier_type, identifier_value, preferred_channel.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT identifier_type, identifier_value, preferred_channel, is_verified
            FROM customer_identifiers
            WHERE customer_id = $1
            ORDER BY created_at
            """,
            customer_id,
        )
        return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────
# TICKET QUERIES
# ──────────────────────────────────────────────────────────────

async def create_ticket(
    pool: asyncpg.Pool,
    customer_id: str,
    description: str,
    channel: str,
    subject: Optional[str] = None,
    priority: str = "medium",
    conversation_id: Optional[str] = None,
    sla_deadline: Optional[str] = None,
) -> dict:
    """
    Create a new support ticket.

    Args:
        pool: asyncpg connection pool.
        customer_id: Customer UUID string.
        description: Detailed description of the issue.
        channel: Communication channel ('email', 'whatsapp', 'web_form').
        subject: Optional ticket subject line.
        priority: Priority level ('low', 'medium', 'high', 'critical').
        conversation_id: Optional linked conversation UUID.
        sla_deadline: Optional SLA deadline timestamp.

    Returns:
        dict with ticket_id, ticket_number, status, created_at.

    Example:
        ticket = await create_ticket(
            pool,
            customer_id="uuid-here",
            description="Slack integration not syncing tasks",
            channel="email",
            priority="high",
        )
        # {'ticket_id': UUID, 'ticket_number': 'TKT-00001', 'status': 'open', ...}
    """
    async with pool.acquire() as conn:
        ticket = await conn.fetchrow(
            """
            INSERT INTO tickets
                (customer_id, conversation_id, subject, description,
                 priority, channel, sla_deadline)
            VALUES ($1, $2, $3, $4, $5::ticket_priority, $6::channel_type, $7)
            RETURNING id, ticket_number, status, priority, channel, created_at
            """,
            customer_id,
            conversation_id,
            subject,
            description,
            priority,
            channel,
            sla_deadline,
        )

        # Increment customer ticket count
        await conn.execute(
            """
            UPDATE customers
            SET total_tickets = total_tickets + 1,
                updated_at = NOW()
            WHERE id = $1
            """,
            customer_id,
        )

        return dict(ticket)


async def escalate_ticket(
    pool: asyncpg.Pool,
    ticket_id: str,
    reason: str,
    escalated_by: str = "ai_agent",
) -> dict:
    """
    Escalate a ticket to a human agent.

    Args:
        pool: asyncpg connection pool.
        ticket_id: Ticket UUID string.
        reason: Reason for escalation.
        escalated_by: Who escalated ('ai_agent' or human name).

    Returns:
        dict with ticket_id, status, escalated_at.
    """
    async with pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            UPDATE tickets
            SET is_escalated = TRUE,
                status = 'escalated',
                escalation_reason = $2,
                escalated_at = NOW(),
                escalated_by = $3,
                updated_at = NOW()
            WHERE id = $1
            RETURNING id, ticket_number, status, escalated_at
            """,
            ticket_id,
            reason,
            escalated_by,
        )

        if result:
            # Increment customer escalated count
            await conn.execute(
                """
                UPDATE customers
                SET escalated_tickets = escalated_tickets + 1,
                    updated_at = NOW()
                WHERE id = (SELECT customer_id FROM tickets WHERE id = $1)
                """,
                ticket_id,
            )

        return dict(result) if result else None


async def get_ticket(
    pool: asyncpg.Pool,
    ticket_id: str,
) -> Optional[dict]:
    """
    Get a ticket by ID (UUID or ticket_number).

    Args:
        pool: asyncpg connection pool.
        ticket_id: Ticket UUID string or ticket_number (e.g., 'TKT-00001').

    Returns:
        dict with ticket details or None.
    """
    async with pool.acquire() as conn:
        # Try UUID first, then ticket_number
        row = await conn.fetchrow(
            """
            SELECT t.*, c.display_name AS customer_name
            FROM tickets t
            LEFT JOIN customers c ON c.id = t.customer_id
            WHERE t.id = $1 OR t.ticket_number = $1
            """,
            ticket_id,
        )
        return dict(row) if row else None


async def get_customer_tickets(
    pool: asyncpg.Pool,
    customer_id: str,
    limit: int = 20,
) -> list[dict]:
    """
    Get all tickets for a customer, most recent first.

    Args:
        pool: asyncpg connection pool.
        customer_id: Customer UUID string.
        limit: Maximum number of tickets to return.

    Returns:
        List of ticket dicts.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, ticket_number, subject, description, priority, status,
                   channel, is_escalated, created_at, updated_at
            FROM tickets
            WHERE customer_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            customer_id,
            limit,
        )
        return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────
# CONVERSATION QUERIES
# ──────────────────────────────────────────────────────────────

async def get_customer_history(
    pool: asyncpg.Pool,
    customer_id: str,
    max_messages: int = 20,
) -> dict:
    """
    Get full conversation history for a customer across all channels.

    Returns conversation metadata plus the most recent messages.

    Args:
        pool: asyncpg connection pool.
        customer_id: Customer UUID string.
        max_messages: Maximum number of recent messages to return.

    Returns:
        dict with conversations list and recent messages.
    """
    async with pool.acquire() as conn:
        # Get conversations
        conversations = await conn.fetch(
            """
            SELECT id, topic_summary, topics, status, message_count,
                   initial_sentiment, current_sentiment, sentiment_trend,
                   last_channel_used, escalation_count,
                   started_at, resolved_at, updated_at
            FROM conversations
            WHERE customer_id = $1
            ORDER BY updated_at DESC
            LIMIT 10
            """,
            customer_id,
        )

        # Get recent messages across all conversations
        messages = await conn.fetch(
            """
            SELECT m.id, m.role, m.content, m.channel, m.intent, m.sentiment,
                   m.is_escalation, m.created_at, c.id AS conversation_id
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.customer_id = $1
            ORDER BY m.created_at DESC
            LIMIT $2
            """,
            customer_id,
            max_messages,
        )

        return {
            "customer_id": customer_id,
            "conversations": [dict(c) for c in conversations],
            "recent_messages": [dict(m) for m in messages],
            "total_conversations": len(conversations),
            "total_messages_returned": len(messages),
        }


async def create_conversation(
    pool: asyncpg.Pool,
    customer_id: str,
    topic_summary: Optional[str] = None,
    topics: Optional[list[str]] = None,
) -> dict:
    """
    Create a new conversation thread.

    Args:
        pool: asyncpg connection pool.
        customer_id: Customer UUID string.
        topic_summary: Optional one-line summary of conversation topic.
        topics: Optional list of topic tags.

    Returns:
        dict with conversation_id and created_at.
    """
    async with pool.acquire() as conn:
        conv = await conn.fetchrow(
            """
            INSERT INTO conversations (customer_id, topic_summary, topics)
            VALUES ($1, $2, $3)
            RETURNING id, started_at
            """,
            customer_id,
            topic_summary,
            topics,
        )
        return dict(conv)


async def update_conversation_sentiment(
    pool: asyncpg.Pool,
    conversation_id: str,
    sentiment: str,
    trend: str,
) -> None:
    """
    Update conversation sentiment tracking.

    Args:
        pool: asyncpg connection pool.
        conversation_id: Conversation UUID string.
        sentiment: Current sentiment level.
        trend: Sentiment trend direction.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE conversations
            SET current_sentiment = $2::sentiment_level,
                sentiment_trend = $3::sentiment_trend,
                updated_at = NOW()
            WHERE id = $1
            """,
            conversation_id,
            sentiment,
            trend,
        )


# ──────────────────────────────────────────────────────────────
# MESSAGE QUERIES
# ──────────────────────────────────────────────────────────────

async def store_message(
    pool: asyncpg.Pool,
    conversation_id: str,
    role: str,
    content: str,
    channel: str,
    intent: Optional[str] = None,
    sentiment: Optional[str] = None,
    is_escalation: bool = False,
    escalation_reason: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """
    Store a message in the database.

    Args:
        pool: asyncpg connection pool.
        conversation_id: Conversation UUID string.
        role: Message role ('customer', 'agent', 'system').
        content: Message text content.
        channel: Communication channel.
        intent: Classified intent type.
        sentiment: Analyzed sentiment level.
        is_escalation: Whether this message triggered escalation.
        escalation_reason: Reason for escalation if applicable.
        metadata: Optional JSONB metadata (attachments, tool results, etc.).

    Returns:
        dict with message_id and created_at.

    Example:
        msg = await store_message(
            pool,
            conversation_id="conv-uuid",
            role="customer",
            content="Slack not syncing",
            channel="whatsapp",
            intent="integration_issue",
            sentiment="neutral",
        )
    """
    import json

    async with pool.acquire() as conn:
        message = await conn.fetchrow(
            """
            INSERT INTO messages
                (conversation_id, role, content, channel, intent, sentiment,
                 is_escalation, escalation_reason, metadata)
            VALUES ($1, $2::message_role, $3, $4::channel_type, $5::intent_type,
                    $6::sentiment_level, $7, $8, $9::jsonb)
            RETURNING id, created_at
            """,
            conversation_id,
            role,
            content,
            channel,
            intent,
            sentiment,
            is_escalation,
            escalation_reason,
            json.dumps(metadata) if metadata else "{}",
        )

        # Update conversation last_channel_used
        await conn.execute(
            """
            UPDATE conversations
            SET last_channel_used = $2::channel_type,
                updated_at = NOW()
            WHERE id = $1
            """,
            conversation_id,
            channel,
        )

        return dict(message)


async def get_conversation_messages(
    pool: asyncpg.Pool,
    conversation_id: str,
    limit: int = 10,
    offset: int = 0,
) -> list[dict]:
    """
    Get messages from a specific conversation.

    Args:
        pool: asyncpg connection pool.
        conversation_id: Conversation UUID string.
        limit: Maximum messages to return.
        offset: Number of messages to skip (for pagination).

    Returns:
        List of message dicts, newest first.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, role, content, channel, intent, sentiment,
                   is_escalation, escalation_reason, metadata, created_at
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            conversation_id,
            limit,
            offset,
        )
        return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────
# KNOWLEDGE BASE QUERIES (Vector Search)
# ──────────────────────────────────────────────────────────────

async def search_knowledge_base_vector(
    pool: asyncpg.Pool,
    query_embedding: list[float],
    limit: int = 3,
    category: Optional[str] = None,
    min_confidence: float = 0.0,
) -> list[dict]:
    """
    Search knowledge base using vector similarity (cosine distance).

    Uses pgvector's HNSW index for fast approximate nearest neighbor search.

    Args:
        pool: asyncpg connection pool.
        query_embedding: 384-dimensional query vector (from embedding model).
        limit: Maximum number of results to return.
        category: Optional filter by KB category.
        min_confidence: Minimum similarity threshold (0.0 to 1.0).
            1 - cosine_distance = similarity.

    Returns:
        List of KB article dicts with similarity score, ordered by relevance.

    Example:
        results = await search_knowledge_base_vector(
            pool,
            query_embedding=[0.1, 0.2, ..., 0.05],  # 384 dims
            limit=3,
            category="integrations",
        )
    """
    async with pool.acquire() as conn:
        # Build query with optional category filter
        if category:
            rows = await conn.fetch(
                """
                SELECT id, title, content, category, tags, source_url,
                       1 - (embedding <=> $1) AS similarity
                FROM knowledge_base
                WHERE is_active = TRUE
                  AND category = $2
                  AND embedding IS NOT NULL
                  AND 1 - (embedding <=> $1) >= $3
                ORDER BY embedding <=> $1
                LIMIT $4
                """,
                query_embedding,
                category,
                min_confidence,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, title, content, category, tags, source_url,
                       1 - (embedding <=> $1) AS similarity
                FROM knowledge_base
                WHERE is_active = TRUE
                  AND embedding IS NOT NULL
                  AND 1 - (embedding <=> $1) >= $2
                ORDER BY embedding <=> $1
                LIMIT $3
                """,
                query_embedding,
                min_confidence,
                limit,
            )

        results = [dict(r) for r in rows]

        # Increment search count for returned articles
        if results:
            ids = [r["id"] for r in results]
            await conn.execute(
                """
                UPDATE knowledge_base
                SET search_count = search_count + 1
                WHERE id = ANY($1)
                """,
                ids,
            )

        return results


async def search_knowledge_base_text(
    pool: asyncpg.Pool,
    query: str,
    limit: int = 3,
    category: Optional[str] = None,
) -> list[dict]:
    """
    Search knowledge base using full-text search (PostgreSQL tsvector).

    Fallback when vector embeddings are not available.

    Args:
        pool: asyncpg connection pool.
        query: Search query string.
        limit: Maximum results to return.
        category: Optional category filter.

    Returns:
        List of KB article dicts with relevance rank.
    """
    async with pool.acquire() as conn:
        if category:
            rows = await conn.fetch(
                """
                SELECT id, title, content, category, tags, source_url,
                       ts_rank(
                           to_tsvector('english', title || ' ' || content),
                           plainto_tsquery('english', $1)
                       ) AS rank
                FROM knowledge_base
                WHERE is_active = TRUE
                  AND category = $2
                  AND to_tsvector('english', title || ' ' || content)
                      @@ plainto_tsquery('english', $1)
                ORDER BY rank DESC
                LIMIT $3
                """,
                query,
                category,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, title, content, category, tags, source_url,
                       ts_rank(
                           to_tsvector('english', title || ' ' || content),
                           plainto_tsquery('english', $1)
                       ) AS rank
                FROM knowledge_base
                WHERE is_active = TRUE
                  AND to_tsvector('english', title || ' ' || content)
                      @@ plainto_tsquery('english', $1)
                ORDER BY rank DESC
                LIMIT $2
                """,
                query,
                limit,
            )

        results = [dict(r) for r in rows]

        # Increment search count
        if results:
            ids = [r["id"] for r in results]
            await conn.execute(
                """
                UPDATE knowledge_base
                SET search_count = search_count + 1
                WHERE id = ANY($1)
                """,
                ids,
            )

        return results


async def get_knowledge_base_article(
    pool: asyncpg.Pool,
    article_id: str,
) -> Optional[dict]:
    """
    Get a single knowledge base article by ID.

    Args:
        pool: asyncpg connection pool.
        article_id: Article UUID string.

    Returns:
        dict with article content or None.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, title, content, content_html, category, tags,
                   source_url, version, search_count, helpful_count
            FROM knowledge_base
            WHERE id = $1 AND is_active = TRUE
            """,
            article_id,
        )
        return dict(row) if row else None


# ──────────────────────────────────────────────────────────────
# METRICS QUERIES
# ──────────────────────────────────────────────────────────────

async def record_agent_metrics(
    pool: asyncpg.Pool,
    window_start: str,
    window_end: str,
    metrics: dict,
) -> dict:
    """
    Record agent performance metrics for a time window.

    Args:
        pool: asyncpg connection pool.
        window_start: ISO timestamp of window start.
        window_end: ISO timestamp of window end.
        metrics: Dict with metric values (total_messages, resolved_count, etc.).

    Returns:
        dict with the recorded metrics.
    """
    import json

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO agent_metrics
                (window_start, window_end,
                 total_messages, total_tickets, total_conversations,
                 resolved_count, escalated_count,
                 resolution_rate, escalation_rate,
                 avg_response_time_ms, p50_response_time_ms,
                 p95_response_time_ms, p99_response_time_ms,
                 avg_sentiment_score,
                 sentiment_improving_count, sentiment_worsening_count,
                 intent_distribution, channel_distribution,
                 kb_hit_rate, avg_kb_confidence)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                    $14, $15, $16, $17::jsonb, $18::jsonb, $19, $20)
            RETURNING id, window_start, window_end, resolution_rate, escalation_rate
            """,
            window_start,
            window_end,
            metrics.get("total_messages", 0),
            metrics.get("total_tickets", 0),
            metrics.get("total_conversations", 0),
            metrics.get("resolved_count", 0),
            metrics.get("escalated_count", 0),
            metrics.get("resolution_rate"),
            metrics.get("escalation_rate"),
            metrics.get("avg_response_time_ms"),
            metrics.get("p50_response_time_ms"),
            metrics.get("p95_response_time_ms"),
            metrics.get("p99_response_time_ms"),
            metrics.get("avg_sentiment_score"),
            metrics.get("sentiment_improving_count", 0),
            metrics.get("sentiment_worsening_count", 0),
            json.dumps(metrics.get("intent_distribution", {})),
            json.dumps(metrics.get("channel_distribution", {})),
            metrics.get("kb_hit_rate"),
            metrics.get("avg_kb_confidence"),
        )
        return dict(row)


async def get_recent_metrics(
    pool: asyncpg.Pool,
    limit: int = 24,
) -> list[dict]:
    """
    Get recent agent performance metrics (hourly windows).

    Args:
        pool: asyncpg connection pool.
        limit: Number of recent time windows to return.

    Returns:
        List of metric dicts, most recent first.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT window_start, window_end,
                   total_messages, total_tickets, resolved_count, escalated_count,
                   resolution_rate, escalation_rate,
                   avg_response_time_ms, p95_response_time_ms,
                   avg_sentiment_score, kb_hit_rate
            FROM agent_metrics
            ORDER BY window_start DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]
