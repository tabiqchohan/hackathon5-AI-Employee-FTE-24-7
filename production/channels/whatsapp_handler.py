"""
FlowSync Customer Success -- WhatsApp Channel Handler (Placeholder)
====================================================================
Future integration with Twilio WhatsApp API for processing customer
support messages via WhatsApp.

Planned Architecture:
  1. Twilio sends webhook POST to /channels/whatsapp/incoming
  2. Handler extracts customer phone, message content, media
  3. Creates/resolves customer in PostgreSQL
  4. Creates ticket
  5. Runs AI agent for response
  6. Sends reply via Twilio Messaging API

Setup Required:
  - Twilio account with WhatsApp Business API enabled
  - Approved WhatsApp Business number (sandbox or production)
  - Webhook URL configured in Twilio console
  - Twilio Auth Token and Account SID

Environment Variables:
  - TWILIO_ACCOUNT_SID: Twilio account identifier
  - TWILIO_AUTH_TOKEN: Twilio authentication token
  - TWILIO_WHATSAPP_NUMBER: WhatsApp Business number (e.g. "whatsapp:+14155238886")
  - TWILIO_VERIFY_SERVICE_SID: (optional) For phone verification

Dependencies (add to requirements.txt when implementing):
  - twilio>=8.0.0
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("flowsync.channels.whatsapp")

router = APIRouter(
    prefix="/channels/whatsapp",
    tags=["WhatsApp Channel"],
    responses={501: {"description": "Not yet implemented"}},
)


# ──────────────────────────────────────────────────────────────
# PYDANTIC MODELS (placeholder)
# ──────────────────────────────────────────────────────────────

class WhatsAppIncomingMessage(BaseModel):
    """Structure of an incoming WhatsApp message from Twilio."""
    from_number: str = Field(..., description="Customer's WhatsApp number")
    body: str = Field(..., description="Message text content")
    media_urls: list[str] = Field(default_factory=list, description="Attached media URLs")
    message_sid: Optional[str] = None
    conversation_sid: Optional[str] = None


class WhatsAppOutgoingMessage(BaseModel):
    """Structure for sending a WhatsApp reply via Twilio."""
    to_number: str = Field(..., description="Customer's WhatsApp number")
    body: str = Field(..., min_length=1, max_length=4096, description="Reply message text")
    media_url: Optional[str] = None


# ──────────────────────────────────────────────────────────────
# ENDPOINTS (stubs)
# ──────────────────────────────────────────────────────────────

@router.get(
    "/status",
    summary="WhatsApp integration status",
    description="Check whether WhatsApp integration is configured.",
)
async def whatsapp_integration_status():
    """
    Return the current status of WhatsApp integration.
    """
    return {
        "channel": "whatsapp",
        "status": "active",
        "endpoint": "/channels/whatsapp/incoming",
        "message": "WhatsApp webhook active. Messages are published to Kafka.",
    }


# ──────────────────────────────────────────────────────────────
# HELPER FUNCTIONS (stubs for future implementation)
# ──────────────────────────────────────────────────────────────

async def _send_whatsapp_reply(to_number: str, body: str, media_url: Optional[str] = None):
    """
    Send a WhatsApp reply via Twilio Messaging API.

    TODO:
    from twilio.rest import Client

    client = Client(
        os.environ["TWILIO_ACCOUNT_SID"],
        os.environ["TWILIO_AUTH_TOKEN"],
    )

    params = {
        "from_": os.environ["TWILIO_WHATSAPP_NUMBER"],
        "to": f"whatsapp:{to_number}",
        "body": body,
    }
    if media_url:
        params["media_url"] = [media_url]

    message = client.messages.create(**params)
    return message.sid
    """
    raise NotImplementedError("WhatsApp reply sending not implemented")


async def _send_whatsapp_template(to_number: str, template_name: str, language: str = "en"):
    """
    Send a WhatsApp template message (for proactive notifications).

    Template messages are required for outbound messages outside the
    24-hour customer service window.

    TODO:
    - Use Twilio's Content Templates or WhatsApp Template API
    - Handle template approval process
    - Track template usage for billing
    """
    raise NotImplementedError("WhatsApp template messages not implemented")


def _validate_whatsapp_number(phone_number: str) -> bool:
    """
    Validate a WhatsApp phone number format.

    TODO:
    - Strip "whatsapp:" prefix if present
    - Validate E.164 format
    - Optionally verify via Twilio Lookup API
    """
    cleaned = phone_number.replace("whatsapp:", "").strip()
    return cleaned.startswith("+") and len(cleaned) >= 8
