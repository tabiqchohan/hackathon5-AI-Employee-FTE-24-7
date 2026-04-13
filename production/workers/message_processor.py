"""
FlowSync Customer Success -- Unified Message Processor
=======================================================
Background worker that consumes messages from Kafka, processes them
through the AI agent pipeline, and stores results in PostgreSQL.

Processing Pipeline:
  ┌─────────────────────────────────────────────────────────┐
  │  1. RECEIVE  (from Kafka fte.tickets.incoming)          │
  │       ↓                                                  │
  │  2. IDENTIFY  (resolve customer from email/phone)        │
  │       ↓                                                  │
  │  3. CONVERSATION  (get/create conversation thread)       │
  │       ↓                                                  │
  │  4. STORE MSG  (store customer message in DB)            │
  │       ↓                                                  │
  │  5. ANALYZE  (sentiment + intent classification)         │
  │       ↓                                                  │
  │  6. RUN AGENT  (OpenAI Agents SDK with tools)            │
  │       ↓                                                  │
  │  7. DECIDE  (escalate or respond)                        │
  │       ↓                                                  │
  │  8a. ESCALATE  → publish to fte.tickets.escalations     │
  │  8b. RESPOND   → publish to fte.tickets.responses       │
  │       ↓                                                  │
  │  9. METRICS  → publish to fte.metrics.agent              │
  └─────────────────────────────────────────────────────────┘

Usage:
    # As a standalone worker:
    python -m workers.message_processor

    # As a module:
    from workers.message_processor import UnifiedMessageProcessor
    processor = UnifiedMessageProcessor()
    await processor.start()
    # Consumes and processes messages forever...

    # Process a single message directly:
    result = await processor.process_message(incoming_msg_dict)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("flowsync.worker")

# ──────────────────────────────────────────────────────────────
# PATH SETUP
# ──────────────────────────────────────────────────────────────

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_src_path = os.path.join(_project_root, "..", "src")
for p in [_src_path, _project_root]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ──────────────────────────────────────────────────────────────
# PROCESSING RESULT
# ──────────────────────────────────────────────────────────────

@dataclass
class ProcessingResult:
    """Result of processing a single message."""

    success: bool
    customer_id: str = ""
    ticket_id: str = ""
    conversation_id: str = ""
    was_escalated: bool = False
    escalation_reason: Optional[str] = None
    response_text: Optional[str] = None
    sentiment: str = "neutral"
    intent: str = "general"
    processing_time_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "customer_id": self.customer_id,
            "ticket_id": self.ticket_id,
            "conversation_id": self.conversation_id,
            "was_escalated": self.was_escalated,
            "escalation_reason": self.escalation_reason,
            "response_text": self.response_text,
            "sentiment": self.sentiment,
            "intent": self.intent,
            "processing_time_ms": self.processing_time_ms,
            "error": self.error,
        }


# ──────────────────────────────────────────────────────────────
# UNIFIED MESSAGE PROCESSOR
# ──────────────────────────────────────────────────────────────

class UnifiedMessageProcessor:
    """
    Processes incoming customer messages end-to-end.

    Pipeline:
      1. Resolve customer identity (create if new)
      2. Get/create conversation thread
      3. Store the customer's message
      4. Analyze sentiment and classify intent
      5. Run the AI agent with the message
      6. Decide: escalate or respond
      7. Publish results to Kafka
      8. Record metrics

    Usage:
        processor = UnifiedMessageProcessor()
        await processor.start()

        # Process one message:
        result = await processor.process_message({
            "customer_identifier": "user@test.com",
            "channel": "web_form",
            "content": "Slack integration not working",
        })

        # Or run the consumer loop:
        await processor.run_consumer()
    """

    def __init__(
        self,
        db_pool=None,
        producer=None,
        model: str = "gpt-4o",
    ):
        """
        Initialize the message processor.

        Args:
            db_pool: Optional asyncpg.Pool for database access.
                     If None, will try to connect on start().
            producer: Optional FTEKafkaProducer. If None, will create one.
            model: OpenAI model to use for the AI agent.
        """
        self._db_pool = db_pool
        self._producer = producer
        self._model = model
        self._agent = None
        self._running = False

        # Metrics counters
        self._stats = {
            "messages_processed": 0,
            "escalations": 0,
            "responses_sent": 0,
            "errors": 0,
            "total_processing_time_ms": 0.0,
        }

    # ── Lifecycle ─────────────────────────────────────────

    async def start(self):
        """Initialize database pool and Kafka producer."""
        logger.info("Starting UnifiedMessageProcessor...")

        # Database
        if self._db_pool is None:
            try:
                from database import queries
                self._db_pool = await queries.get_db_pool()
                logger.info("Database pool connected")
            except Exception as e:
                logger.warning("Database unavailable, using in-memory mode: %s", e)
                self._db_pool = "fallback"

        # Kafka producer
        if self._producer is None:
            try:
                from kafka_client import FTEKafkaProducer
                self._producer = FTEKafkaProducer()
                await self._producer.start()
                logger.info("Kafka producer connected")
            except Exception as e:
                logger.warning("Kafka unavailable, operating in direct mode: %s", e)
                self._producer = None  # Will use direct DB fallback

        # AI agent (lazy init)
        logger.info("Message processor ready (model=%s)", self._model)

    async def stop(self):
        """Stop the processor and print stats."""
        self._running = False

        if self._producer:
            await self._producer.stop()

        try:
            from database import queries
            await queries.close_db_pool()
        except Exception:
            pass

        self._print_stats()
        logger.info("Message processor stopped")

    async def run_consumer(self):
        """
        Run the Kafka consumer loop forever.

        Consumes from fte.tickets.incoming, processes each message,
        and publishes results to appropriate topics.
        """
        from kafka_client import FTEKafkaConsumer, Topics

        logger.info("Starting Kafka consumer loop...")

        consumer = FTEKafkaConsumer(
            topics=[Topics.TICKETS_INCOMING],
        )
        await consumer.start()

        self._running = True
        try:
            async for msg in consumer:
                if not self._running:
                    break

                value = msg.get("value", {})
                logger.info(
                    "Received message: topic=%s, key=%s, customer=%s",
                    msg.get("topic"), msg.get("key"),
                    value.get("customer_identifier", "?"),
                )

                try:
                    result = await self.process_message(value)
                    self._update_stats(result)

                    # Publish results to Kafka
                    await self._publish_results(result, value)

                except Exception as e:
                    logger.error("Failed to process message: %s", e, exc_info=True)
                    self._stats["errors"] += 1

        except Exception as e:
            logger.error("Consumer loop error: %s", e, exc_info=True)
        finally:
            await consumer.stop()

    # ── Main Processing Pipeline ──────────────────────────

    async def process_message(self, message: dict) -> ProcessingResult:
        """
        Process a single incoming message through the full pipeline.

        This is the heart of the 24/7 AI employee.

        Args:
            message: Dict matching IncomingMessage schema:
                - customer_identifier (required)
                - channel (required)
                - content (required)
                - subject (optional)
                - customer_name (optional)
                - category (optional)
                - priority (optional)
                - company_name (optional)

        Returns:
            ProcessingResult with outcome of processing.
        """
        start_time = time.monotonic()
        result = ProcessingResult(success=False)

        try:
            customer_id = message.get("customer_identifier", "")
            channel = message.get("channel", "web_form")
            content = message.get("content", "")

            if not customer_id or not content:
                result.error = "Missing customer_identifier or content"
                return result

            logger.info(
                "Processing: customer=%s, channel=%s, content_len=%d",
                customer_id, channel, len(content),
            )

            # ── Step 1: Resolve/Create Customer ──
            result.customer_id = await self._resolve_customer(
                identifier=customer_id,
                channel=channel,
                display_name=message.get("customer_name"),
                company_name=message.get("company_name"),
            )

            # ── Step 2: Get/Create Conversation ──
            result.conversation_id = await self._get_conversation(
                customer_id=result.customer_id,
                topic_summary=message.get("subject", content[:100]),
                channel=channel,
            )

            # ── Step 3: Store Customer Message ──
            await self._store_message(
                conversation_id=result.conversation_id,
                role="customer",
                content=content,
                channel=channel,
            )

            # ── Step 4: Analyze Sentiment ──
            result.sentiment = await self._analyze_sentiment(content)

            # ── Step 5: Classify Intent ──
            result.intent = await self._classify_intent(
                content,
                subject=message.get("subject", ""),
            )

            # ── Step 6: Create Ticket ──
            result.ticket_id = await self._create_ticket(
                customer_id=result.customer_id,
                subject=message.get("subject", content[:80]),
                description=content,
                channel=channel,
                priority=message.get("priority", "medium"),
            )

            # ── Step 7: Run AI Agent ──
            agent_response, used_fallback = await self._run_agent(
                customer_id=result.customer_id,
                channel=channel,
                content=content,
                subject=message.get("subject", ""),
            )

            # ── Step 8: Decide Escalation ──
            # When using fallback (AI agent unavailable), escalate based on
            # sentiment/intent only (not response keywords, since the response
            # is a generic holding message).
            if used_fallback:
                result.was_escalated = self._check_escalation_direct(
                    result.sentiment, result.intent
                )
                result.response_text = agent_response
            else:
                result.was_escalated = self._check_escalation(
                    agent_response, result.sentiment, result.intent
                )

            if result.was_escalated:
                result.escalation_reason = self._extract_escalation_reason(
                    agent_response
                )
                result.response_text = agent_response
                await self._escalate_ticket(
                    ticket_id=result.ticket_id,
                    reason=result.escalation_reason,
                )
                logger.info(
                    "ESCALATED: ticket=%s, reason=%s",
                    result.ticket_id, result.escalation_reason,
                )
            else:
                result.response_text = agent_response

            # ── Step 9: Store Agent Response ──
            await self._store_message(
                conversation_id=result.conversation_id,
                role="agent",
                content=agent_response,
                channel=channel,
            )

            # Success
            result.success = True
            elapsed_ms = (time.monotonic() - start_time) * 1000
            result.processing_time_ms = elapsed_ms

            logger.info(
                "Completed: ticket=%s, sentiment=%s, intent=%s, "
                "escalated=%s, time=%.0fms",
                result.ticket_id, result.sentiment, result.intent,
                result.was_escalated, elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            result.error = str(e)
            result.processing_time_ms = elapsed_ms
            logger.error("Pipeline error: %s", e, exc_info=True)

        return result

    # ── Pipeline Steps ────────────────────────────────────

    async def _resolve_customer(
        self,
        identifier: str,
        channel: str,
        display_name: Optional[str] = None,
        company_name: Optional[str] = None,
    ) -> str:
        """Step 1: Resolve or create customer record."""
        if self._has_db():
            from database import queries
            customer = await queries.create_or_get_customer(
                self._db_pool,
                identifier=identifier,
                channel=channel,
                display_name=display_name,
                company_name=company_name,
            )
            return str(customer["customer_id"])
        else:
            logger.info("Customer resolved (in-memory): %s", identifier)
            return identifier

    async def _get_conversation(
        self,
        customer_id: str,
        topic_summary: str,
        channel: str,
    ) -> str:
        """Step 2: Get latest conversation or create a new one."""
        if self._has_db():
            from database import queries
            conv = await queries.create_conversation(
                self._db_pool,
                customer_id=customer_id,
                topic_summary=topic_summary,
            )
            return str(conv["id"])
        else:
            import uuid
            conv_id = f"CONV-{uuid.uuid4().hex[:8].upper()}"
            logger.info("Conversation created (in-memory): %s", conv_id)
            return conv_id

    async def _store_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        channel: str,
    ):
        """Step 3/9: Store a message in the database."""
        if self._has_db():
            from database import queries
            await queries.store_message(
                self._db_pool,
                conversation_id=conversation_id,
                role=role,
                content=content,
                channel=channel,
            )
        else:
            logger.debug("Message stored (in-memory): role=%s, len=%d", role, len(content))

    async def _analyze_sentiment(self, content: str) -> str:
        """Step 4: Analyze sentiment of the customer message."""
        from prototype import analyze_sentiment
        return analyze_sentiment(content)

    async def _classify_intent(self, content: str, subject: str = "") -> str:
        """Step 5: Classify the intent of the customer message."""
        from prototype import classify_intent
        return classify_intent(content, subject=subject)

    async def _create_ticket(
        self,
        customer_id: str,
        subject: str,
        description: str,
        channel: str,
        priority: str,
    ) -> str:
        """Step 6: Create a support ticket."""
        if self._has_db():
            from database import queries
            ticket = await queries.create_ticket(
                self._db_pool,
                customer_id=customer_id,
                description=description,
                channel=channel,
                subject=subject,
                priority=priority,
            )
            return ticket["ticket_number"]
        else:
            import random
            ticket_id = f"TKT-{random.randint(10000, 99999):05d}"
            logger.info("Ticket created (in-memory): %s", ticket_id)
            return ticket_id

    async def _run_agent(
        self,
        customer_id: str,
        channel: str,
        content: str,
        subject: str = "",
    ) -> tuple[str, bool]:
        """Step 7: Run the AI agent to generate a response.

        Returns:
            Tuple of (response_text, used_fallback).
            used_fallback=True means the real AI agent was unavailable.
        """
        try:
            from agent.customer_success_agent import create_agent, run_agent

            if self._agent is None:
                self._agent = create_agent(model=self._model)

            input_data = {
                "channel": channel,
                "content": content,
            }
            if "@" in customer_id:
                input_data["customer_email"] = customer_id
            else:
                input_data["customer_phone"] = customer_id
            if subject:
                input_data["subject"] = subject

            result = await run_agent(
                self._agent,
                input_data=input_data,
                db_pool=self._db_pool if self._has_db() else None,
            )

            return result.get("response", ""), False

        except Exception as e:
            logger.warning("AI agent unavailable, using fallback: %s", e)
            # Fallback response — do NOT escalate from fallback
            return (
                "Thank you for reaching out. We have received your message "
                "and will review it shortly. A member of our support staff "
                "will respond within 24 hours.\n\n"
                f"Reference: {customer_id}"
            ), True

    def _check_escalation(
        self,
        response_text: str,
        sentiment: str,
        intent: str,
    ) -> bool:
        """Step 8: Decide if the ticket needs escalation.

        Checks sentiment, intent, AND response keywords.
        Used when the real AI agent is available.
        """
        # Direct escalation from sentiment
        if sentiment == "very_negative":
            return True

        # Intent-based escalation
        if intent == "pricing_billing":
            return True

        # Response contains escalation signals
        response_lower = response_text.lower()
        escalation_signals = [
            "escalat",
            "transfer you to a human",
            "connect you with a specialist",
            "hand this off to our team",
            "speak with a manager",
            "human agent",
        ]
        if any(signal in response_lower for signal in escalation_signals):
            return True

        return False

    def _check_escalation_direct(
        self,
        sentiment: str,
        intent: str,
    ) -> bool:
        """Escalation check based on sentiment and intent only.

        Used when the AI agent is unavailable (fallback mode).
        Does NOT check response keywords since the response is generic.
        """
        if sentiment == "very_negative":
            return True
        if intent == "pricing_billing":
            return True
        return False

    def _extract_escalation_reason(self, response_text: str) -> str:
        """Extract a reason for escalation from the agent response."""
        # Try to find the escalation reason from the response
        lines = response_text.split("\n")
        for line in lines:
            if "reason" in line.lower() or "because" in line.lower():
                return line.strip()[:200]
        return "Automatic escalation based on sentiment/intent analysis"

    async def _escalate_ticket(self, ticket_id: str, reason: str):
        """Mark the ticket as escalated."""
        if self._has_db():
            from database import queries
            try:
                await queries.escalate_ticket(
                    self._db_pool,
                    ticket_id=ticket_id,
                    reason=reason,
                    escalated_by="ai_agent",
                )
            except Exception as e:
                logger.warning("Failed to escalate ticket in DB: %s", e)
        else:
            logger.info("Ticket escalated (in-memory): %s", ticket_id)

    # ── Kafka Publishing ──────────────────────────────────

    async def _publish_results(self, result: ProcessingResult, original_msg: dict):
        """Publish processing results to appropriate Kafka topics."""
        if not self._producer:
            return

        try:
            if result.was_escalated:
                from kafka_client import EscalationEvent, Topics

                escalation = EscalationEvent(
                    ticket_id=result.ticket_id,
                    customer_identifier=result.customer_id,
                    reason=result.escalation_reason or "Unknown",
                    urgency="high" if result.sentiment == "very_negative" else "standard",
                    triggered_by="ai_agent",
                )
                await self._producer.send_escalation(escalation)

            if result.response_text:
                from kafka_client import AgentResponse, Topics

                response = AgentResponse(
                    ticket_id=result.ticket_id,
                    customer_identifier=result.customer_id,
                    channel=original_msg.get("channel", "web_form"),
                    response_text=result.response_text,
                    sentiment=result.sentiment,
                    intent=result.intent,
                    was_escalated=result.was_escalated,
                    escalation_reason=result.escalation_reason,
                )
                await self._producer.send_response(response)

        except Exception as e:
            logger.error("Failed to publish results to Kafka: %s", e)

    # ── Metrics ───────────────────────────────────────────

    def _update_stats(self, result: ProcessingResult):
        """Update internal metrics counters."""
        self._stats["messages_processed"] += 1
        self._stats["total_processing_time_ms"] += result.processing_time_ms

        if result.was_escalated:
            self._stats["escalations"] += 1
        if result.response_text and not result.was_escalated:
            self._stats["responses_sent"] += 1
        if not result.success:
            self._stats["errors"] += 1

    def _print_stats(self):
        """Print current processing statistics."""
        total = self._stats["messages_processed"]
        avg_time = (
            self._stats["total_processing_time_ms"] / total
            if total > 0 else 0
        )

        logger.info("=" * 50)
        logger.info("  Message Processor Statistics")
        logger.info("=" * 50)
        logger.info("  Messages processed: %d", total)
        logger.info("  Responses sent:     %d", self._stats["responses_sent"])
        logger.info("  Escalations:        %d", self._stats["escalations"])
        logger.info("  Errors:             %d", self._stats["errors"])
        logger.info("  Avg processing time: %.0fms", avg_time)
        logger.info("=" * 50)

    def get_stats(self) -> dict:
        """Get current statistics as a dict."""
        total = self._stats["messages_processed"]
        return {
            **self._stats,
            "avg_processing_time_ms": (
                self._stats["total_processing_time_ms"] / total
                if total > 0 else 0
            ),
        }

    # ── Helpers ───────────────────────────────────────────

    def _has_db(self) -> bool:
        """Check if database is available."""
        return self._db_pool is not None and self._db_pool != "fallback"


# ──────────────────────────────────────────────────────────────
# DIRECT PROCESSING (no Kafka needed)
# ──────────────────────────────────────────────────────────────

async def process_message_direct(
    message: dict,
    db_pool=None,
    model: str = "gpt-4o",
) -> ProcessingResult:
    """
    Process a single message directly (no Kafka).

    This is used when:
    - The API handles a web form submission directly
    - Testing the pipeline without Kafka
    - Running in a lightweight deployment

    Args:
        message: IncomingMessage dict.
        db_pool: Optional database pool.
        model: OpenAI model name.

    Returns:
        ProcessingResult with the outcome.
    """
    processor = UnifiedMessageProcessor(
        db_pool=db_pool,
        producer=None,  # No Kafka
        model=model,
    )
    await processor.start()
    try:
        return await processor.process_message(message)
    finally:
        await processor.stop()


# ──────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ──────────────────────────────────────────────────────────────

async def _main():
    """Run the message processor as a standalone worker."""
    import signal

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    processor = UnifiedMessageProcessor()

    # Graceful shutdown
    def handle_signal(sig, frame):
        logger.info("Received signal %s, shutting down...", sig)
        asyncio.ensure_future(processor.stop())

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    await processor.start()

    try:
        # Check if Kafka is available
        try:
            from aiokafka import AIOKafkaConsumer
            await processor.run_consumer()
        except ImportError:
            logger.info(
                "aiokafka not available. Running in direct-processing mode.\n"
                "To test, send a message via the API /support/submit endpoint."
            )
            # Keep alive, wait for manual stop
            while processor._running:
                await asyncio.sleep(1)
    except Exception as e:
        logger.error("Worker error: %s", e, exc_info=True)
    finally:
        await processor.stop()


if __name__ == "__main__":
    asyncio.run(_main())
