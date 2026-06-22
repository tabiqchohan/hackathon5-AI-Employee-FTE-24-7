"""
FlowSync Message Processor — Kafka Consumer + Direct Processing
================================================================
Consumes messages from Kafka topics and processes them through the
FlowSync agent engine. Falls back to direct processing when Kafka
is unavailable (e.g., Render deployment).

Modes:
  1. Kafka mode   — consumes from fte.tickets.incoming topic
  2. Direct mode  — processes messages synchronously (no Kafka needed)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime

logger = logging.getLogger("flowsync.worker")

# PATH SETUP
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_src_path = os.path.join(_project_root, "..", "src")
for p in [_project_root, _src_path]:
    if p not in sys.path:
        sys.path.insert(0, p)


def process_message(input_data: dict) -> dict:
    """Process a single message through the engine (prototype fallback chain)."""
    try:
        from prototype import process_ticket
        result = process_ticket(input_data)
        return {
            "status": "ok",
            "response": result.response_text,
            "escalated": result.escalation_needed,
            "intent": result.intent,
            "sentiment": result.sentiment,
        }
    except Exception as e:
        logger.error("Processing failed: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


def process_message_direct(input_data: dict) -> dict:
    """Direct synchronous processing — used for quick testing / non-Kafka mode."""
    return process_message(input_data)


async def _run_kafka_consumer():
    """Run Kafka consumer loop (aiokafka)."""
    try:
        from kafka_client import FTEKafkaConsumer, Topics

        bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        group_id = os.getenv("KAFKA_CONSUMER_GROUP", "flowsync-message-processor")

        consumer = FTEKafkaConsumer(
            bootstrap_servers=[bootstrap],
            group_id=group_id,
            topics=[Topics.TICKETS_INCOMING],
        )
        await consumer.start()
        logger.info("Kafka consumer connected to %s", bootstrap)

        async for message in consumer:
            try:
                data = json.loads(message.value) if isinstance(message.value, (bytes, bytearray)) else message.value
                logger.info("Received message: %s", data.get("content", "")[:80])
                result = process_message(data)
                logger.info("Processed: intent=%s, sentiment=%s, escalated=%s", result.get("intent"), result.get("sentiment"), result.get("escalated"))
            except Exception as e:
                logger.error("Message processing error: %s", e)

    except ImportError:
        logger.warning("aiokafka not installed — falling back to direct mode")
        await _run_direct_mode()
    except Exception as e:
        logger.error("Kafka connection failed: %s", e)
        logger.info("Falling back to direct processing mode")
        await _run_direct_mode()


async def _run_direct_mode():
    """Simple keep-alive loop for direct/non-Kafka deployments (Render)."""
    logger.info("Direct processing mode — ready to handle messages synchronously")
    while True:
        logger.info("Worker healthy — waiting for direct processing requests")
        await asyncio.sleep(60)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("=" * 50)
    logger.info("  FlowSync Message Processor")
    logger.info("  Started at %s", datetime.now().isoformat())
    logger.info("=" * 50)

    kafka_enabled = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "").strip() != ""

    if kafka_enabled:
        logger.info("Kafka configured — starting consumer")
        await _run_kafka_consumer()
    else:
        logger.info("No Kafka configured — running in direct processing mode")
        await _run_direct_mode()


if __name__ == "__main__":
    asyncio.run(main())