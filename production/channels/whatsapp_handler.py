"""
FlowSync Customer Success -- WhatsApp Channel Handler
======================================================
Processes incoming WhatsApp messages through the FlowSync engine.

Two modes:
  1. Webhook mode — POST /channels/whatsapp/incoming receives message data
  2. API mode — future Twilio WhatsApp Business API integration

Setup for Twilio integration (future):
  - Twilio account with WhatsApp Business API enabled
  - TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER env vars
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request
from pydantic import BaseModel, Field

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_src_path = os.path.join(_project_root, "src")
for p in [_src_path, _project_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

logger = logging.getLogger("flowsync.channels.whatsapp")

router = APIRouter(
    prefix="/channels/whatsapp",
    tags=["WhatsApp Channel"],
)


# ──────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ──────────────────────────────────────────────────────────────

class WhatsAppIncomingMessage(BaseModel):
    """Incoming WhatsApp message for processing."""
    from_number: str = Field(..., description="Customer's WhatsApp number")
    body: str = Field(..., description="Message text content")
    media_urls: list[str] = Field(default_factory=list, description="Attached media URLs")
    message_sid: Optional[str] = None
    conversation_sid: Optional[str] = None


class WhatsAppResponse(BaseModel):
    """Response returned after processing a WhatsApp message."""
    ticket_id: str
    channel: str
    response: str
    escalation_needed: bool = False
    escalation_reason: str = ""


# ──────────────────────────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────────────────────────

@router.get("/status")
async def whatsapp_integration_status():
    """Check WhatsApp channel status."""
    return {
        "channel": "whatsapp",
        "status": "active",
        "endpoint": "/channels/whatsapp/incoming",
        "message": "WhatsApp webhook endpoint ready.",
    }


@router.post("/incoming", response_model=WhatsAppResponse)
async def whatsapp_incoming(payload: WhatsAppIncomingMessage):
    """Receive a WhatsApp message and return an AI-generated response.

    Processes the message through the FlowSync engine. Returns a
    WhatsApp-appropriate response (casual, concise, ~280 chars).
    """
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    logger.info("WhatsApp from=%s body=%s", payload.from_number, payload.body[:80])

    input_data = {
        "channel": "whatsapp",
        "customer_phone": payload.from_number,
        "content": payload.body,
    }

    # Try LLM agent first, fall back to prototype
    try:
        from agent.customer_success_agent import create_agent, run_agent
        agent = create_agent()
        if agent is not None:
            result = await run_agent(agent, input_data)
            ai_response = result.get("response", "")
            if ai_response:
                return WhatsAppResponse(
                    ticket_id=ticket_id, channel="whatsapp",
                    response=ai_response.strip(),
                )
    except Exception:
        logger.info("LLM agent unavailable for WhatsApp, using prototype")

    from prototype import process_ticket
    result = process_ticket(input_data)
    return WhatsAppResponse(
        ticket_id=ticket_id, channel="whatsapp",
        response=result.response_text.strip(),
        escalation_needed=result.escalation_needed,
        escalation_reason=result.escalation_reason,
    )


# ──────────────────────────────────────────────────────────────
# HELPER FUNCTIONS (stubs for future Twilio integration)
# ──────────────────────────────────────────────────────────────

async def _send_whatsapp_reply(to_number: str, body: str, media_url: Optional[str] = None):
    """Send a WhatsApp reply via Twilio Messaging API.

    Future: Use Twilio client with TWILIO_ACCOUNT_SID/AUTH_TOKEN.
    """
    raise NotImplementedError(
        "WhatsApp sending not configured. "
        "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_WHATSAPP_NUMBER env vars."
    )


async def _send_whatsapp_template(to_number: str, template_name: str, language: str = "en"):
    """Send a WhatsApp template message (for proactive notifications).

    Future: Required for outbound messages outside 24-hour window.
    """
    raise NotImplementedError("WhatsApp template messages not yet implemented")


def _validate_whatsapp_number(phone_number: str) -> bool:
    """Validate a WhatsApp phone number (E.164 format)."""
    cleaned = phone_number.replace("whatsapp:", "").strip()
    return cleaned.startswith("+") and len(cleaned) >= 8
