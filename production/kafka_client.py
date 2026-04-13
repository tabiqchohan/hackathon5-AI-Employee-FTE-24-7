"""
FlowSync Customer Success -- Kafka Client
==========================================
Production Kafka producer and consumer using aiokafka.

Topics:
  fte.tickets.incoming    -- Incoming messages from all channels
  fte.tickets.responses   -- AI-generated responses to customers
  fte.tickets.escalations -- Tickets escalated to human agents
  fte.events.customer     -- Customer lifecycle events (created, switched channel)
  fte.events.conversation -- Conversation lifecycle events
  fte.metrics.agent       -- Agent performance metrics (resolution rate, sentiment)
  fte.metrics.channel     -- Channel-level metrics (volume, response time)

Architecture:
  ┌─────────────┐     fte.tickets.incoming     ┌─────────────────────┐
  │  Web Form   │ ───────────────────────────►  │  Message Processor  │
  │  Gmail      │ ───────────────────────────►  │  (worker)           │
  │  WhatsApp   │ ───────────────────────────►  │                     │
  └─────────────┘                              └─────────┬───────────┘
                              fte.tickets.responses       │
                              fte.tickets.escalations     │
                              fte.events.*                │
                              fte.metrics.*               │
                                                          ▼
                                                  ┌───────────────┐
                                                  │  PostgreSQL   │
                                                  └───────────────┘

Usage:
    from kafka_client import FTEKafkaProducer, FTEKafkaConsumer, TOPICS

    # Producer
    producer = FTEKafkaProducer(bootstrap_servers=["localhost:9092"])
    await producer.start()
    await producer.send("fte.tickets.incoming", {"customer_email": "user@test.com", ...})
    await producer.stop()

    # Consumer
    consumer = FTEKafkaConsumer(
        bootstrap_servers=["localhost:9092"],
        group_id="message-processor",
        topics=[TOPICS.TICKETS_INCOMING],
    )
    await consumer.start()
    async for message in consumer:
        await process_message(message)
    await consumer.stop()

Environment Variables:
  KAFKA_BOOTSTRAP_SERVERS  -- Comma-separated Kafka broker addresses
                              (default: "localhost:9092")
  KAFKA_CONSUMER_GROUP     -- Consumer group ID
                              (default: "flowsync-message-processor")
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger("flowsync.kafka")


# ──────────────────────────────────────────────────────────────
# TOPIC DEFINITIONS
# ──────────────────────────────────────────────────────────────

class Topics(Enum):
    """All Kafka topics used by the FlowSync system."""

    # Incoming messages from channels (web, gmail, whatsapp)
    TICKETS_INCOMING = "fte.tickets.incoming"

    # AI-generated responses ready to send to customers
    TICKETS_RESPONSES = "fte.tickets.responses"

    # Tickets that have been escalated to human agents
    TICKETS_ESCALATIONS = "fte.tickets.escalations"

    # Customer lifecycle events
    EVENTS_CUSTOMER = "fte.events.customer"

    # Conversation lifecycle events
    EVENTS_CONVERSATION = "fte.events.conversation"

    # Agent performance metrics
    METRICS_AGENT = "fte.metrics.agent"

    # Channel-level metrics
    METRICS_CHANNEL = "fte.metrics.channel"


# Module-level constant for easy import
TOPICS = Topics


# ──────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────

@dataclass
class KafkaConfig:
    """Kafka configuration from environment or defaults."""

    bootstrap_servers: list[str] = field(default_factory=lambda: [
        os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    ])
    consumer_group: str = field(default_factory=lambda:
        os.environ.get("KAFKA_CONSUMER_GROUP", "flowsync-message-processor")
    )
    # Serialization
    value_serializer: callable = field(default=lambda v: json.dumps(v).encode("utf-8"))
    value_deserializer: callable = field(default=lambda v: json.loads(v.decode("utf-8")))
    # Producer settings
    acks: str = "all"
    retries: int = 3
    # Consumer settings
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = True
    auto_commit_interval_ms: int = 5000
    max_poll_records: int = 100
    # Topic settings
    num_partitions: int = 3
    replication_factor: int = 1

    @classmethod
    def from_env(cls) -> "KafkaConfig":
        """Create config from environment variables."""
        servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        return cls(
            bootstrap_servers=[s.strip() for s in servers.split(",")],
            consumer_group=os.environ.get("KAFKA_CONSUMER_GROUP", "flowsync-message-processor"),
        )


# ──────────────────────────────────────────────────────────────
# MESSAGE SCHEMAS
# ──────────────────────────────────────────────────────────────

@dataclass
class IncomingMessage:
    """
    Schema for messages published to fte.tickets.incoming.

    This is the unified message format that all channels should
    produce. The message processor consumes these regardless of
    the original channel.
    """
    # Required
    customer_identifier: str          # email or phone
    channel: str                      # "email", "whatsapp", "web_form"
    content: str                      # Message text

    # Optional but recommended
    customer_name: Optional[str] = None
    subject: Optional[str] = None
    category: Optional[str] = None    # "bug", "integration", "billing", etc.
    priority: Optional[str] = None    # "low", "medium", "high", "critical"
    company_name: Optional[str] = None
    media_urls: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dict for Kafka."""
        return {
            "customer_identifier": self.customer_identifier,
            "channel": self.channel,
            "content": self.content,
            "customer_name": self.customer_name,
            "subject": self.subject,
            "category": self.category,
            "priority": self.priority,
            "company_name": self.company_name,
            "media_urls": self.media_urls,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IncomingMessage":
        """Deserialize from dict (Kafka message value)."""
        return cls(
            customer_identifier=data["customer_identifier"],
            channel=data["channel"],
            content=data["content"],
            customer_name=data.get("customer_name"),
            subject=data.get("subject"),
            category=data.get("category"),
            priority=data.get("priority"),
            company_name=data.get("company_name"),
            media_urls=data.get("media_urls", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AgentResponse:
    """
    Schema for messages published to fte.tickets.responses.

    Published by the message processor after the AI agent generates
    a response.
    """
    ticket_id: str
    customer_identifier: str
    channel: str
    response_text: str
    sentiment: str
    intent: str
    was_escalated: bool = False
    escalation_reason: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticket_id": self.ticket_id,
            "customer_identifier": self.customer_identifier,
            "channel": self.channel,
            "response_text": self.response_text,
            "sentiment": self.sentiment,
            "intent": self.intent,
            "was_escalated": self.was_escalated,
            "escalation_reason": self.escalation_reason,
            "metadata": self.metadata,
        }


@dataclass
class EscalationEvent:
    """
    Schema for messages published to fte.tickets.escalations.
    """
    ticket_id: str
    customer_identifier: str
    reason: str
    urgency: str                    # "immediate", "high", "standard"
    triggered_by: str               # "ai_agent" or human name
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticket_id": self.ticket_id,
            "customer_identifier": self.customer_identifier,
            "reason": self.reason,
            "urgency": self.urgency,
            "triggered_by": self.triggered_by,
            "metadata": self.metadata,
        }


# ──────────────────────────────────────────────────────────────
# PRODUCER
# ──────────────────────────────────────────────────────────────

class FTEKafkaProducer:
    """
    Async Kafka producer for FlowSync messages.

    Thread-safe, supports multiple concurrent send operations.
    Automatically handles serialization to JSON.

    Usage:
        producer = FTEKafkaProducer(bootstrap_servers=["localhost:9092"])
        await producer.start()
        await producer.send_event(
            topic=Topics.TICKETS_INCOMING,
            key="user@test.com",
            value=IncomingMessage(...).to_dict(),
        )
        await producer.stop()
    """

    def __init__(
        self,
        bootstrap_servers: Optional[list[str]] = None,
        config: Optional[KafkaConfig] = None,
    ):
        self.config = config or KafkaConfig.from_env()
        if bootstrap_servers:
            self.config.bootstrap_servers = bootstrap_servers

        self._producer = None
        self._started = False

    async def start(self):
        """Initialize and start the producer."""
        if self._started:
            return

        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.config.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks=self.config.acks,
                retries=self.config.retries,
            )
            await self._producer.start()
            self._started = True
            logger.info(
                "Kafka producer started: brokers=%s",
                self.config.bootstrap_servers,
            )
        except ImportError:
            logger.warning(
                "aiokafka not installed. Producer running in dry-run mode. "
                "Install with: pip install aiokafka"
            )
            self._started = True  # Mark as started in dry-run mode
        except Exception as e:
            logger.error("Failed to start Kafka producer: %s", e)
            raise

    async def stop(self):
        """Stop the producer gracefully."""
        if self._producer and self._started:
            await self._producer.stop()
            self._started = False
            logger.info("Kafka producer stopped")

    async def send_event(
        self,
        topic: Topics | str,
        value: dict,
        key: Optional[str] = None,
    ) -> bool:
        """
        Send a JSON event to a Kafka topic.

        Args:
            topic: Target topic (Topics enum or string).
            value: Event payload (will be JSON-serialized).
            key: Optional partition key (e.g. customer email).

        Returns:
            True if sent successfully, False in dry-run mode.
        """
        if not self._started:
            await self.start()

        topic_name = topic.value if isinstance(topic, Topics) else topic

        # Dry-run mode: aiokafka not available
        if self._producer is None:
            logger.debug(
                "[DRY-RUN] Would send to %s (key=%s): %s",
                topic_name, key, str(value)[:200],
            )
            return False

        try:
            await self._producer.send_and_wait(
                topic=topic_name,
                value=value,
                key=key,
            )
            logger.debug("Sent to %s (key=%s)", topic_name, key)
            return True
        except Exception as e:
            logger.error("Failed to send to %s: %s", topic_name, e)
            raise

    async def send_incoming_message(self, msg: IncomingMessage) -> bool:
        """Send an incoming customer message to the tickets.incoming topic."""
        return await self.send_event(
            topic=Topics.TICKETS_INCOMING,
            value=msg.to_dict(),
            key=msg.customer_identifier,
        )

    async def send_response(self, response: AgentResponse) -> bool:
        """Send an AI-generated response to the tickets.responses topic."""
        return await self.send_event(
            topic=Topics.TICKETS_RESPONSES,
            value=response.to_dict(),
            key=response.ticket_id,
        )

    async def send_escalation(self, escalation: EscalationEvent) -> bool:
        """Send an escalation event to the tickets.escalations topic."""
        return await self.send_event(
            topic=Topics.TICKETS_ESCALATIONS,
            value=escalation.to_dict(),
            key=escalation.ticket_id,
        )

    async def send_metric(self, topic: Topics, value: dict) -> bool:
        """Send a metric event to the specified metrics topic."""
        return await self.send_event(
            topic=topic,
            value=value,
            key=value.get("window_start", "unknown"),
        )


# ──────────────────────────────────────────────────────────────
# CONSUMER
# ──────────────────────────────────────────────────────────────

class FTEKafkaConsumer:
    """
    Async Kafka consumer for FlowSync messages.

    Subscribes to one or more topics and yields messages via
    async iteration. Handles JSON deserialization automatically.

    Usage:
        consumer = FTEKafkaConsumer(
            bootstrap_servers=["localhost:9092"],
            group_id="message-processor",
            topics=[Topics.TICKETS_INCOMING],
        )
        await consumer.start()
        async for msg in consumer:
            await process_message(msg)
        await consumer.stop()
    """

    def __init__(
        self,
        topics: list[Topics | str],
        group_id: Optional[str] = None,
        bootstrap_servers: Optional[list[str]] = None,
        config: Optional[KafkaConfig] = None,
    ):
        self.config = config or KafkaConfig.from_env()
        if bootstrap_servers:
            self.config.bootstrap_servers = bootstrap_servers
        if group_id:
            self.config.consumer_group = group_id

        self.topics = [
            t.value if isinstance(t, Topics) else t for t in topics
        ]

        self._consumer = None
        self._started = False

    async def start(self):
        """Initialize and start the consumer."""
        if self._started:
            return

        try:
            from aiokafka import AIOKafkaConsumer
            self._consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self.config.bootstrap_servers,
                group_id=self.config.consumer_group,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
                auto_offset_reset=self.config.auto_offset_reset,
                enable_auto_commit=self.config.enable_auto_commit,
                auto_commit_interval_ms=self.config.auto_commit_interval_ms,
                max_poll_records=self.config.max_poll_records,
            )
            await self._consumer.start()
            self._started = True
            logger.info(
                "Kafka consumer started: group=%s, topics=%s",
                self.config.consumer_group, self.topics,
            )
        except ImportError:
            logger.warning(
                "aiokafka not installed. Consumer running in dry-run mode. "
                "Install with: pip install aiokafka"
            )
            self._started = True
        except Exception as e:
            logger.error("Failed to start Kafka consumer: %s", e)
            raise

    async def stop(self):
        """Stop the consumer gracefully."""
        if self._consumer and self._started:
            await self._consumer.stop()
            self._started = False
            logger.info("Kafka consumer stopped")

    async def __aiter__(self) -> AsyncIterator[dict]:
        """
        Async iterator over consumed messages.

        Yields:
            dict with keys: key, value, topic, partition, offset, timestamp
        """
        if not self._started:
            await self.start()

        if self._consumer is None:
            # Dry-run mode: simulate no messages (nothing to iterate)
            return
            yield  # Make it an async generator

        try:
            async for msg in self._consumer:
                yield {
                    "key": msg.key,
                    "value": msg.value,
                    "topic": msg.topic,
                    "partition": msg.partition,
                    "offset": msg.offset,
                    "timestamp": msg.timestamp,
                }
        except Exception as e:
            logger.error("Consumer error: %s", e)
            raise

    async def get_one(self, timeout_ms: int = 5000) -> Optional[dict]:
        """
        Poll for a single message with timeout.

        Args:
            timeout_ms: Maximum time to wait for a message.

        Returns:
            Message dict or None if timeout.
        """
        if not self._started:
            await self.start()

        if self._consumer is None:
            return None

        record = await self._consumer.getone()
        if record is None:
            return None

        return {
            "key": record.key,
            "value": record.value,
            "topic": record.topic,
            "partition": record.partition,
            "offset": record.offset,
            "timestamp": record.timestamp,
        }


# ──────────────────────────────────────────────────────────────
# TOPIC ADMIN (create topics programmatically)
# ──────────────────────────────────────────────────────────────

async def create_topics(
    bootstrap_servers: Optional[list[str]] = None,
    num_partitions: int = 3,
    replication_factor: int = 1,
) -> list[str]:
    """
    Create all FlowSync Kafka topics if they don't exist.

    Called during application startup to ensure topics exist.

    Args:
        bootstrap_servers: Kafka broker addresses.
        num_partitions: Number of partitions per topic.
        replication_factor: Replication factor.

    Returns:
        List of created topic names.
    """
    from aiokafka.admin import AIOKafkaAdminClient, NewTopic

    servers = bootstrap_servers or [
        os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    ]

    admin = AIOKafkaAdminClient(bootstrap_servers=servers)
    await admin.start()

    try:
        existing = await admin.list_topics()
        topics_to_create = []

        for topic in Topics:
            if topic.value not in existing:
                topics_to_create.append(
                    NewTopic(
                        name=topic.value,
                        num_partitions=num_partitions,
                        replication_factor=replication_factor,
                    )
                )

        if topics_to_create:
            await admin.create_topics(topics_to_create)
            created = [t.name for t in topics_to_create]
            logger.info("Created Kafka topics: %s", created)
            return created
        else:
            logger.info("All Kafka topics already exist")
            return []

    finally:
        await admin.stop()
