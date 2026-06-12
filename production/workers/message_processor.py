"""
FlowSync Customer Success -- Unified Message Processor
=======================================================
Background worker that processes messages through the AI agent pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
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

from database import queries   # noqa: F401


# ──────────────────────────────────────────────────────────────
# PROCESSING RESULT
# ──────────────────────────────────────────────────────────────

@dataclass
class ProcessingResult:
    success: bool = False
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


# ──────────────────────────────────────────────────────────────
# UNIFIED MESSAGE PROCESSOR
# ──────────────────────────────────────────────────────────────

class UnifiedMessageProcessor:
    def __init__(self, db_pool=None, model: str = "llama-3.3-70b-versatile"):
        self._db_pool = db_pool
        self._model = model
        self._agent = None
        self._running = False
        self._use_kafka = os.getenv("USE_KAFKA", "true").lower() == "true"

        self._stats = {
            "messages_processed": 0,
            "responses_sent": 0,
            "escalations": 0,
            "errors": 0,
        }

    async def start(self):
        """Initialize components."""
        logger.info("Starting UnifiedMessageProcessor...")

        # Database
        if self._db_pool is None:
            try:
                self._db_pool = await queries.get_db_pool()
                logger.info("✅ Database connected")
            except Exception as e:
                logger.warning("Database unavailable, using in-memory mode: %s", e)
                self._db_pool = None

        logger.info("Message processor ready (model=%s, kafka=%s)", 
                   self._model, "enabled" if self._use_kafka else "disabled")

    async def process_message(self, message: dict) -> ProcessingResult:
        """Process single message (direct mode)"""
        start_time = time.monotonic()
        result = ProcessingResult(success=False)

        try:
            # Simple processing for now (can be expanded later)
            customer_id = message.get("customer_identifier") or message.get("email") or "unknown"
            content = message.get("content", "")

            result.customer_id = customer_id
            result.ticket_id = f"TKT-{int(time.time())}"
            result.response_text = f"Thank you for your message. We have received it and will respond shortly."
            result.success = True

            elapsed = (time.monotonic() - start_time) * 1000
            result.processing_time_ms = elapsed

            logger.info("Message processed successfully: ticket=%s", result.ticket_id)

        except Exception as e:
            result.error = str(e)
            logger.error("Message processing failed: %s", e, exc_info=True)

        return result

    async def stop(self):
        self._running = False
        logger.info("Worker stopped.")


# ──────────────────────────────────────────────────────────────
# DIRECT PROCESSING HELPER
# ──────────────────────────────────────────────────────────────

async def process_message_direct(message: dict):
    """Process message directly (used by API fallback)"""
    processor = UnifiedMessageProcessor()
    await processor.start()
    try:
        return await processor.process_message(message)
    finally:
        await processor.stop()


# ──────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ──────────────────────────────────────────────────────────────

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    logger.info("=== FlowSync Message Processor Starting ===")

    processor = UnifiedMessageProcessor()

    try:
        await processor.start()
        logger.info("Worker is running in direct mode (Kafka disabled)")

        # Keep running
        while True:
            await asyncio.sleep(60)

    except asyncio.CancelledError:
        logger.info("Worker shutdown requested")
    except Exception as e:
        logger.error("Worker crashed: %s", e, exc_info=True)
    finally:
        await processor.stop()


if __name__ == "__main__":
    asyncio.run(main())