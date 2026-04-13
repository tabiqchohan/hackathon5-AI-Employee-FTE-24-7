"""
FlowSync Customer Success -- Main API Server
==============================================
FastAPI application that serves all channel endpoints.

Architecture:
  All incoming messages (web form, Gmail, WhatsApp) are published
  to Kafka topic fte.tickets.incoming for unified processing by
  the message worker. The API can also process directly if Kafka
  is unavailable (fallback mode).

Includes:
  - Health check: GET /
  - Health check: GET /health
  - Web Support Form: POST /support/submit
  - Ticket lookup: GET /support/ticket/{id}
  - Ticket listing: GET /support/tickets?email=...
  - Gmail webhook: POST /channels/gmail/incoming
  - WhatsApp webhook: POST /channels/whatsapp/incoming

Run locally:
  cd production
  uvicorn api.main:app --reload --port 8000

  Then test:
  curl http://localhost:8000/health
  curl http://localhost:8000/docs  # Swagger UI
"""

from __future__ import annotations

import logging
import sys
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Form, HTTPException

# ──────────────────────────────────────────────────────────────
# PATH SETUP
# ──────────────────────────────────────────────────────────────

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_src_path = os.path.join(_project_root, "..", "src")
for p in [_src_path, _project_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ──────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("flowsync.api")

# ──────────────────────────────────────────────────────────────
# GLOBAL KAFKA PRODUCER
# ──────────────────────────────────────────────────────────────

_kafka_producer = None


async def _get_kafka_producer():
    """Get or create the global Kafka producer."""
    global _kafka_producer
    if _kafka_producer is None:
        try:
            from kafka_client import FTEKafkaProducer
            _kafka_producer = FTEKafkaProducer()
            await _kafka_producer.start()
            logger.info("Kafka producer started")
        except Exception as e:
            logger.warning("Kafka producer unavailable: %s", e)
            _kafka_producer = "unavailable"
    if _kafka_producer == "unavailable":
        return None
    return _kafka_producer


async def _publish_to_kafka(message_dict: dict, key: str):
    """
    Publish an incoming message to Kafka for processing.

    Falls back to direct processing if Kafka is unavailable.
    """
    try:
        producer = await _get_kafka_producer()
        if producer:
            from kafka_client import Topics
            await producer.send_event(
                topic=Topics.TICKETS_INCOMING,
                value=message_dict,
                key=key,
            )
            return True
    except Exception as e:
        logger.warning("Failed to publish to Kafka, using direct processing: %s", e)

    # Fallback: process directly via the message processor
    return False


async def _process_directly(message_dict: dict):
    """
    Process a message directly (no Kafka) for fallback mode.

    Returns a quick ticket ID for the response.
    """
    from workers.message_processor import process_message_direct

    result = await process_message_direct(message_dict)
    return result


# ──────────────────────────────────────────────────────────────
# IMPORT CHANNEL ROUTERS
# ──────────────────────────────────────────────────────────────

from channels.web_form_handler import router as web_form_router

# Gmail and WhatsApp handlers are imported but we override their
# webhook endpoints in main.py to publish to Kafka
from channels.gmail_handler import (
    GmailNotification,
    GmailMessagePayload,
    router as gmail_status_router,
)
from channels.whatsapp_handler import (
    WhatsAppIncomingMessage,
    router as whatsapp_status_router,
)


# ──────────────────────────────────────────────────────────────
# LIFESPAN (startup / shutdown)
# ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    # ── Startup ──
    logger.info("=" * 60)
    logger.info("  FlowSync Customer Success API -- Starting")
    logger.info("=" * 60)
    logger.info("  Channels registered:")
    logger.info("    - Web Support Form:   /support/*")
    logger.info("    - Gmail webhook:      /channels/gmail/incoming")
    logger.info("    - WhatsApp webhook:   /channels/whatsapp/incoming")
    logger.info("")
    logger.info("  Message routing:")
    logger.info("    - All channels → Kafka fte.tickets.incoming")
    logger.info("    - Worker processes → AI agent → PostgreSQL")
    logger.info("")

    # Try to initialize database pool
    try:
        from database import queries
        pool = await queries.get_db_pool()
        logger.info("  Database: Connected")
    except Exception as e:
        logger.warning("  Database: Not available (%s)", e)
        logger.info("  Database: Using in-memory fallback")

    # Try to initialize Kafka producer
    try:
        from kafka_client import FTEKafkaProducer
        _kp = FTEKafkaProducer()
        await _kp.start()
        globals()["_kafka_producer"] = _kp
        logger.info("  Kafka:Connected")
    except Exception as e:
        logger.warning("  Kafka:Not available (%s)", e)
        logger.info("  Kafka: Operating in direct-processing mode")

    logger.info("")
    logger.info("  Server ready at http://localhost:8000")
    logger.info("  API docs: http://localhost:8000/docs")
    logger.info("=" * 60)

    yield

    # ── Shutdown ──
    logger.info("Shutting down FlowSync API...")
    _kp_now = globals().get("_kafka_producer")
    if _kp_now and _kp_now != "unavailable":
        await _kp_now.stop()
    try:
        from database import queries
        await queries.close_db_pool()
        logger.info("Database pool closed")
    except Exception:
        pass
    logger.info("Shutdown complete")


# ──────────────────────────────────────────────────────────────
# APP FACTORY
# ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI instance with all routers mounted.
    """
    app = FastAPI(
        title="FlowSync Customer Success API",
        description=(
            "Production API for the FlowSync Customer Success AI Agent.\n\n"
            "All incoming messages are published to Kafka topic "
            "`fte.tickets.incoming` for unified processing by the "
            "message worker.\n\n"
            "Supports multiple channels:\n"
            "- **Web Form**: Submit support requests via the web form\n"
            "- **Gmail**: Process incoming email support requests\n"
            "- **WhatsApp**: Process incoming WhatsApp messages\n\n"
            "All requests are processed by the AI agent and tracked in PostgreSQL."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── Mount web form router (full endpoints) ──
    app.include_router(web_form_router)

    # ── Mount Gmail/WhatsApp status-only routers ──
    # (We override their incoming endpoints below)
    app.include_router(gmail_status_router)
    app.include_router(whatsapp_status_router)

    # ── Root endpoints ──
    @app.get("/", tags=["Health"])
    async def root():
        """Root endpoint -- returns API status."""
        kafka_status = "connected"
        if _kafka_producer is None or _kafka_producer == "unavailable":
            kafka_status = "direct-processing mode"
        return {
            "service": "FlowSync Customer Success API",
            "version": "1.0.0",
            "status": "healthy",
            "kafka": kafka_status,
            "docs": "/docs",
            "channels": {
                "web_form": "active",
                "gmail": "active",
                "whatsapp": "active",
            },
        }

    @app.get("/health", tags=["Health"])
    async def health_check():
        """
        Health check endpoint.

        Returns service status and database connectivity.
        Useful for liveness probes in Docker / Kubernetes.
        """
        db_status = "unknown"
        try:
            from database import queries
            pool = await queries.get_db_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_status = "connected"
        except Exception as e:
            db_status = f"disconnected ({str(e)[:50]})"

        kafka_status = "connected"
        try:
            producer = await _get_kafka_producer()
            if producer is None:
                kafka_status = "direct-processing mode"
        except Exception:
            kafka_status = "unavailable"

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": db_status,
            "kafka": kafka_status,
        }

    @app.get("/api/status", tags=["Health"])
    async def api_status():
        """
        Detailed API status including all channel configurations.
        """
        return {
            "service": "FlowSync Customer Success API",
            "version": "1.0.0",
            "status": "healthy",
            "channels": {
                "web_form": {
                    "status": "active",
                    "endpoint": "/support/submit",
                },
                "gmail": {
                    "status": "active",
                    "endpoint": "/channels/gmail/incoming",
                },
                "whatsapp": {
                    "status": "active",
                    "endpoint": "/channels/whatsapp/incoming",
                },
            },
            "message_routing": {
                "topic": "fte.tickets.incoming",
                "processor": "workers.message_processor.UnifiedMessageProcessor",
            },
        }

    # ──────────────────────────────────────────────────────
    # GMAIL WEBHOOK (overrides placeholder from gmail_handler)
    # ──────────────────────────────────────────────────────

    @app.post(
        "/channels/gmail/incoming",
        tags=["Gmail Channel"],
        summary="Process incoming Gmail support email",
        description="Accepts an incoming support email from Gmail. "
                    "Publishes to Kafka fte.tickets.incoming for processing.",
    )
    async def gmail_incoming(
        from_address: str = Form(..., description="Sender email address"),
        subject: str = Form(..., description="Email subject"),
        body: str = Form(..., description="Email body (plain text)"),
    ):
        """
        Handle incoming support email from Gmail.

        Publishes the message to Kafka for unified processing
        by the message worker.
        """
        message = {
            "customer_identifier": from_address,
            "channel": "email",
            "content": body,
            "subject": subject,
            "metadata": {"source": "gmail"},
        }
        key = from_address

        logger.info(
            "Gmail incoming: from=%s, subject=%s",
            from_address, subject,
        )

        # Publish to Kafka
        published = await _publish_to_kafka(message, key)

        if not published:
            # Fallback: process directly
            result = await _process_directly(message)
            return {
                "success": result.success,
                "ticket_id": result.ticket_id,
                "processing_mode": "direct",
                "kafka": "unavailable",
            }

        return {
            "success": True,
            "message": "Email received and queued for processing",
            "processing_mode": "kafka",
            "topic": "fte.tickets.incoming",
        }

    # ──────────────────────────────────────────────────────
    # WHATSAPP WEBHOOK (overrides placeholder from whatsapp_handler)
    # ──────────────────────────────────────────────────────

    @app.post(
        "/channels/whatsapp/incoming",
        tags=["WhatsApp Channel"],
        summary="Process incoming WhatsApp message",
        description="Accepts an incoming WhatsApp message from Twilio webhook. "
                    "Publishes to Kafka fte.tickets.incoming for processing.",
    )
    async def whatsapp_incoming(
        From: str = Form(..., description="Customer's WhatsApp number"),
        Body: str = Form(..., description="Message text"),
        MediaUrl0: Optional[str] = Form(default=None, description="Attached media URL"),
    ):
        """
        Handle incoming WhatsApp message from Twilio webhook.

        Publishes the message to Kafka for unified processing
        by the message worker.
        """
        # Clean phone number
        phone = From.replace("whatsapp:", "").strip()

        message = {
            "customer_identifier": phone,
            "channel": "whatsapp",
            "content": Body,
            "metadata": {
                "source": "whatsapp",
                "twilio_from": From,
            },
        }
        if MediaUrl0:
            message["media_urls"] = [MediaUrl0]
        if MediaUrl0:
            message["metadata"]["media_url"] = MediaUrl0

        key = phone

        logger.info(
            "WhatsApp incoming: from=%s, content_len=%d",
            phone, len(Body),
        )

        # Publish to Kafka
        published = await _publish_to_kafka(message, key)

        if not published:
            # Fallback: process directly
            result = await _process_directly(message)
            return {
                "success": result.success,
                "ticket_id": result.ticket_id,
                "processing_mode": "direct",
                "kafka": "unavailable",
            }

        return {
            "success": True,
            "message": "WhatsApp message received and queued for processing",
            "processing_mode": "kafka",
            "topic": "fte.tickets.incoming",
        }

    return app


# ──────────────────────────────────────────────────────────────
# APP INSTANCE (for uvicorn)
# ──────────────────────────────────────────────────────────────

app = create_app()


# ──────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
