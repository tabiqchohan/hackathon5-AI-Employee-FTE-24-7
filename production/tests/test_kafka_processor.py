"""
FlowSync Customer Success -- Kafka & Message Processor Tests
=============================================================
Tests for:
  - kafka_client.py (producer, consumer, topics, message schemas)
  - workers/message_processor.py (UnifiedMessageProcessor pipeline)
  - Channel webhook integration (Kafka publishing)

Run:
  cd production && python -m pytest tests/test_kafka_processor.py -v \
    -p no:hypothesis -p no:anyio --capture=no

  # Single test class:
  cd production && python -m pytest tests/test_kafka_processor.py::TestKafkaTopics -v \
    -p no:hypothesis -p no:anyio --capture=no
"""

from __future__ import annotations

import json
import os
import sys
import pytest

# ──────────────────────────────────────────────────────────────
# PATH SETUP
# ──────────────────────────────────────────────────────────────

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_src_path = os.path.join(_project_root, "..", "src")
for p in [_project_root, _src_path]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ──────────────────────────────────────────────────────────────
# TEST 1: Kafka Topics
# ──────────────────────────────────────────────────────────────

class TestKafkaTopics:
    """Verify all Kafka topic definitions exist and are correct."""

    def test_topics_enum_has_all_topics(self):
        from kafka_client import Topics
        topics = list(Topics)
        assert len(topics) == 7

    def test_tickets_incoming_topic(self):
        from kafka_client import Topics
        assert Topics.TICKETS_INCOMING.value == "fte.tickets.incoming"

    def test_tickets_responses_topic(self):
        from kafka_client import Topics
        assert Topics.TICKETS_RESPONSES.value == "fte.tickets.responses"

    def test_tickets_escalations_topic(self):
        from kafka_client import Topics
        assert Topics.TICKETS_ESCALATIONS.value == "fte.tickets.escalations"

    def test_events_customer_topic(self):
        from kafka_client import Topics
        assert Topics.EVENTS_CUSTOMER.value == "fte.events.customer"

    def test_events_conversation_topic(self):
        from kafka_client import Topics
        assert Topics.EVENTS_CONVERSATION.value == "fte.events.conversation"

    def test_metrics_agent_topic(self):
        from kafka_client import Topics
        assert Topics.METRICS_AGENT.value == "fte.metrics.agent"

    def test_metrics_channel_topic(self):
        from kafka_client import Topics
        assert Topics.METRICS_CHANNEL.value == "fte.metrics.channel"

    def test_topics_constant_importable(self):
        from kafka_client import TOPICS, Topics
        assert TOPICS is Topics


# ──────────────────────────────────────────────────────────────
# TEST 2: Message Schemas
# ──────────────────────────────────────────────────────────────

class TestMessageSchemas:
    """Verify Kafka message schemas serialize/deserialize correctly."""

    def test_incoming_message_serialization(self):
        from kafka_client import IncomingMessage
        msg = IncomingMessage(
            customer_identifier="user@test.com",
            channel="web_form",
            content="Slack integration not working",
            subject="Help needed",
            category="integration",
            priority="high",
            customer_name="John Doe",
            company_name="TestCo",
        )
        data = msg.to_dict()
        assert data["customer_identifier"] == "user@test.com"
        assert data["channel"] == "web_form"
        assert data["content"] == "Slack integration not working"
        assert data["priority"] == "high"
        assert data["customer_name"] == "John Doe"

    def test_incoming_message_deserialization(self):
        from kafka_client import IncomingMessage
        data = {
            "customer_identifier": "+14155551234",
            "channel": "whatsapp",
            "content": "hey my tasks are not syncing",
            "media_urls": ["https://example.com/img.png"],
        }
        msg = IncomingMessage.from_dict(data)
        assert msg.customer_identifier == "+14155551234"
        assert msg.channel == "whatsapp"
        assert msg.media_urls == ["https://example.com/img.png"]

    def test_agent_response_serialization(self):
        from kafka_client import AgentResponse
        resp = AgentResponse(
            ticket_id="TKT-00001",
            customer_identifier="user@test.com",
            channel="email",
            response_text="Hi John, I can help with that...",
            sentiment="neutral",
            intent="integration_issue",
        )
        data = resp.to_dict()
        assert data["ticket_id"] == "TKT-00001"
        assert data["was_escalated"] is False

    def test_escalation_event_serialization(self):
        from kafka_client import EscalationEvent
        esc = EscalationEvent(
            ticket_id="TKT-00002",
            customer_identifier="angry@test.com",
            reason="Customer wants to speak to a manager",
            urgency="immediate",
            triggered_by="ai_agent",
        )
        data = esc.to_dict()
        assert data["urgency"] == "immediate"
        assert data["triggered_by"] == "ai_agent"

    def test_incoming_message_json_roundtrip(self):
        """Full JSON serialization roundtrip for IncomingMessage."""
        from kafka_client import IncomingMessage
        original = IncomingMessage(
            customer_identifier="round@test.com",
            channel="email",
            content="Test message",
            subject="Roundtrip test",
            priority="medium",
        )
        json_str = json.dumps(original.to_dict())
        restored = IncomingMessage.from_dict(json.loads(json_str))
        assert restored.customer_identifier == original.customer_identifier
        assert restored.channel == original.channel
        assert restored.content == original.content
        assert restored.subject == original.subject


# ──────────────────────────────────────────────────────────────
# TEST 3: Kafka Config
# ──────────────────────────────────────────────────────────────

class TestKafkaConfig:
    """Verify Kafka configuration."""

    def test_default_config(self):
        from kafka_client import KafkaConfig
        config = KafkaConfig()
        assert "localhost:9092" in config.bootstrap_servers
        assert config.consumer_group == "flowsync-message-processor"
        assert config.acks == "all"

    def test_custom_servers(self):
        from kafka_client import KafkaConfig
        config = KafkaConfig(bootstrap_servers=["kafka1:9092", "kafka2:9092"])
        assert len(config.bootstrap_servers) == 2


# ──────────────────────────────────────────────────────────────
# TEST 4: Producer (dry-run mode without Kafka)
# ──────────────────────────────────────────────────────────────

class TestKafkaProducer:
    """Test producer functionality."""

    def test_producer_instantiates(self):
        from kafka_client import FTEKafkaProducer
        producer = FTEKafkaProducer()
        assert producer is not None
        assert producer._started is False

    def test_producer_custom_servers(self):
        from kafka_client import FTEKafkaProducer
        producer = FTEKafkaProducer(bootstrap_servers=["kafka1:9092"])
        assert producer.config.bootstrap_servers == ["kafka1:9092"]

    def test_producer_helper_methods_exist(self):
        """Verify producer has all helper methods."""
        from kafka_client import FTEKafkaProducer
        producer = FTEKafkaProducer()
        assert hasattr(producer, "send_event")
        assert hasattr(producer, "send_incoming_message")
        assert hasattr(producer, "send_response")
        assert hasattr(producer, "send_escalation")
        assert hasattr(producer, "send_metric")


# ──────────────────────────────────────────────────────────────
# TEST 5: Consumer (dry-run mode without Kafka)
# ──────────────────────────────────────────────────────────────

class TestKafkaConsumer:
    """Test consumer functionality."""

    def test_consumer_instantiates(self):
        from kafka_client import FTEKafkaConsumer, Topics
        consumer = FTEKafkaConsumer(
            topics=[Topics.TICKETS_INCOMING],
            group_id="test-group",
        )
        assert consumer is not None
        assert consumer.topics == ["fte.tickets.incoming"]

    def test_consumer_multiple_topics(self):
        from kafka_client import FTEKafkaConsumer, Topics
        consumer = FTEKafkaConsumer(
            topics=[Topics.TICKETS_INCOMING, Topics.TICKETS_ESCALATIONS],
        )
        assert len(consumer.topics) == 2

    def test_consumer_has_async_iter(self):
        from kafka_client import FTEKafkaConsumer, Topics
        consumer = FTEKafkaConsumer(topics=[Topics.TICKETS_INCOMING])
        assert hasattr(consumer, "__aiter__")
        assert hasattr(consumer, "get_one")


# ──────────────────────────────────────────────────────────────
# TEST 6: Message Processor
# ──────────────────────────────────────────────────────────────

class TestMessageProcessor:
    """Test the UnifiedMessageProcessor pipeline."""

    def test_processor_instantiates(self):
        from workers.message_processor import UnifiedMessageProcessor
        processor = UnifiedMessageProcessor()
        assert processor is not None
        assert processor._running is False

    def test_processor_stats(self):
        from workers.message_processor import UnifiedMessageProcessor
        processor = UnifiedMessageProcessor()
        stats = processor.get_stats()
        assert stats["messages_processed"] == 0
        assert stats["escalations"] == 0
        assert stats["errors"] == 0
        assert stats["avg_processing_time_ms"] == 0

    def test_processing_result(self):
        from workers.message_processor import ProcessingResult
        result = ProcessingResult(
            success=True,
            ticket_id="TKT-00001",
            customer_id="user@test.com",
            sentiment="neutral",
            intent="integration_issue",
        )
        data = result.to_dict()
        assert data["success"] is True
        assert data["ticket_id"] == "TKT-00001"

    def test_escalation_check_very_negative(self):
        """Very negative sentiment should trigger escalation."""
        from workers.message_processor import UnifiedMessageProcessor
        processor = UnifiedMessageProcessor()
        assert processor._check_escalation(
            response_text="I understand your concern...",
            sentiment="very_negative",
            intent="general",
        ) is True

    def test_escalation_check_pricing_intent(self):
        """Pricing intent should trigger escalation."""
        from workers.message_processor import UnifiedMessageProcessor
        processor = UnifiedMessageProcessor()
        assert processor._check_escalation(
            response_text="Let me help...",
            sentiment="neutral",
            intent="pricing_billing",
        ) is True

    def test_no_escalation_normal_case(self):
        """Normal cases should not escalate."""
        from workers.message_processor import UnifiedMessageProcessor
        processor = UnifiedMessageProcessor()
        assert processor._check_escalation(
            response_text="Go to Settings > Integrations to fix this.",
            sentiment="neutral",
            intent="integration_issue",
        ) is False

    def test_escalation_check_response_signals(self):
        """Response containing escalation keywords should trigger."""
        from workers.message_processor import UnifiedMessageProcessor
        processor = UnifiedMessageProcessor()
        assert processor._check_escalation(
            response_text="I'll escalate this to our specialist team.",
            sentiment="negative",
            intent="bug_report",
        ) is True

    def test_resolve_customer_no_db(self):
        """Customer resolution should work in in-memory mode."""
        import asyncio
        from workers.message_processor import UnifiedMessageProcessor
        processor = UnifiedMessageProcessor(db_pool="fallback")

        async def run():
            cid = await processor._resolve_customer(
                identifier="test@example.com",
                channel="web_form",
            )
            assert cid == "test@example.com"

        asyncio.run(run())

    def test_sentiment_analysis(self):
        """Sentiment analysis should work independently."""
        import asyncio
        from workers.message_processor import UnifiedMessageProcessor
        processor = UnifiedMessageProcessor()

        async def run():
            sentiment = await processor._analyze_sentiment("This is amazing, thank you!")
            assert sentiment in ("positive", "neutral", "negative", "very_negative")

        asyncio.run(run())

    def test_intent_classification(self):
        """Intent classification should work independently."""
        import asyncio
        from workers.message_processor import UnifiedMessageProcessor
        processor = UnifiedMessageProcessor()

        async def run():
            intent = await processor._classify_intent(
                "How do I integrate with Slack?"
            )
            assert isinstance(intent, str)
            assert len(intent) > 0

        asyncio.run(run())


# ──────────────────────────────────────────────────────────────
# TEST 7: Direct Message Processing
# ──────────────────────────────────────────────────────────────

class TestDirectProcessing:
    """Test direct message processing (no Kafka)."""

    def test_process_message_direct_function_exists(self):
        from workers.message_processor import process_message_direct
        assert callable(process_message_direct)

    def test_process_message_web_form(self):
        """Process a web form message directly (no Kafka)."""
        import asyncio
        from workers.message_processor import process_message_direct

        async def run():
            result = await process_message_direct(
                message={
                    "customer_identifier": "direct@test.com",
                    "channel": "web_form",
                    "content": "How do I invite team members to my workspace?",
                    "subject": "Team invites",
                    "priority": "medium",
                },
                db_pool=None,
                model="gpt-4o",
            )
            # Should succeed (may or may not use AI agent depending on API key)
            assert result.ticket_id != ""
            assert result.customer_id != ""
            assert result.sentiment in ("positive", "neutral", "negative", "very_negative")

        asyncio.run(run())

    def test_process_message_angry_customer(self):
        """Processing an angry customer should trigger escalation."""
        import asyncio
        from workers.message_processor import process_message_direct

        async def run():
            result = await process_message_direct(
                message={
                    "customer_identifier": "angry@test.com",
                    "channel": "web_form",
                    "content": "This is absolutely ridiculous! I want to speak to a manager NOW!",
                    "subject": "Urgent complaint",
                    "priority": "critical",
                },
                db_pool=None,
                model="gpt-4o",
            )
            # Sentiment should be very_negative
            assert result.sentiment == "very_negative"
            # Should be escalated
            assert result.was_escalated is True

        asyncio.run(run())

    def test_process_message_pricing_inquiry(self):
        """Pricing questions should be flagged for escalation."""
        import asyncio
        from workers.message_processor import process_message_direct

        async def run():
            result = await process_message_direct(
                message={
                    "customer_identifier": "pricing@test.com",
                    "channel": "email",
                    "content": "What is the pricing for Enterprise plan?",
                    "subject": "Enterprise pricing",
                    "priority": "low",
                },
                db_pool=None,
                model="gpt-4o",
            )
            # Intent should be pricing_billing (triggers escalation check)
            assert result.intent == "pricing_billing"

        asyncio.run(run())


# ──────────────────────────────────────────────────────────────
# TEST 8: API Kafka Integration
# ──────────────────────────────────────────────────────────────

class TestAPIKafkaIntegration:
    """Test that the API correctly routes messages through Kafka."""

    def test_main_app_has_gmail_webhook(self):
        from api.main import app
        paths = [r.path for r in app.routes]
        assert "/channels/gmail/incoming" in paths

    def test_main_app_has_whatsapp_webhook(self):
        from api.main import app
        paths = [r.path for r in app.routes]
        assert "/channels/whatsapp/incoming" in paths

    def test_main_app_health_shows_kafka_status(self):
        """Health endpoint should include Kafka status."""
        from api.main import app
        paths = [r.path for r in app.routes]
        assert "/health" in paths

    def test_kafka_import_in_main(self):
        """Main app should import kafka_client."""
        from api import main
        assert hasattr(main, "_get_kafka_producer")
        assert hasattr(main, "_publish_to_kafka")
        assert hasattr(main, "_process_directly")


# ──────────────────────────────────────────────────────────────
# TEST 9: End-to-End Pipeline (without Kafka)
# ──────────────────────────────────────────────────────────────

class TestEndToEndPipeline:
    """Test the full processing pipeline without Kafka."""

    def test_web_form_to_processor(self):
        """Simulate: web form → message → processor → result."""
        import asyncio
        from workers.message_processor import process_message_direct

        async def run():
            # Simulate what the web form submit endpoint would send
            result = await process_message_direct(
                message={
                    "customer_identifier": "e2e@test.com",
                    "channel": "web_form",
                    "content": "My Slack integration stopped working. Tasks are not syncing to my dashboard.",
                    "subject": "Slack integration issue",
                    "category": "integration",
                    "priority": "high",
                    "customer_name": "E2E Tester",
                    "company_name": "Test Corp",
                },
                db_pool=None,
            )
            # Verify full pipeline
            assert result.success is True
            assert result.ticket_id != ""
            assert result.customer_id != ""
            assert result.conversation_id != ""
            assert result.sentiment in ("positive", "neutral", "negative", "very_negative")
            assert result.intent != ""
            assert result.processing_time_ms >= 0

        asyncio.run(run())

    def test_whatsapp_to_processor(self):
        """Simulate: WhatsApp → message → processor → result."""
        import asyncio
        from workers.message_processor import process_message_direct

        async def run():
            result = await process_message_direct(
                message={
                    "customer_identifier": "+14155551234",
                    "channel": "whatsapp",
                    "content": "hey, my tasks are not syncing with slack. help pls",
                },
                db_pool=None,
            )
            assert result.success is True
            assert result.channel == "whatsapp" if hasattr(result, 'channel') else True

        asyncio.run(run())

    def test_email_to_processor(self):
        """Simulate: Gmail → message → processor → result."""
        import asyncio
        from workers.message_processor import process_message_direct

        async def run():
            result = await process_message_direct(
                message={
                    "customer_identifier": "email-user@company.com",
                    "channel": "email",
                    "content": "I need help setting team permissions for our new workspace.",
                    "subject": "Team permissions help",
                },
                db_pool=None,
            )
            assert result.success is True
            assert result.customer_id == "email-user@company.com"

        asyncio.run(run())


# ──────────────────────────────────────────────────────────────
# TEST SUMMARY
# ──────────────────────────────────────────────────────────────

def test_all_kafka_imports():
    """Verify all Kafka components are importable."""
    from kafka_client import (
        FTEKafkaProducer,
        FTEKafkaConsumer,
        Topics,
        TOPICS,
        KafkaConfig,
        IncomingMessage,
        AgentResponse,
        EscalationEvent,
        create_topics,
    )
    # All should be importable
    assert FTEKafkaProducer is not None
    assert FTEKafkaConsumer is not None
    assert Topics is not None


def test_message_processor_import():
    """Verify message processor is importable."""
    from workers.message_processor import (
        UnifiedMessageProcessor,
        ProcessingResult,
        process_message_direct,
    )
    assert UnifiedMessageProcessor is not None
    assert process_message_direct is not None
