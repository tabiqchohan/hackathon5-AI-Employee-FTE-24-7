"""
FlowSync Customer Success -- WhatsApp Channel Handler
======================================================
Receives WhatsApp messages via webhook, processes through FlowSync engine,
and sends the AI-generated reply back via Twilio WhatsApp API.

Reply flow:
  1. POST /channels/whatsapp/incoming  ← Twilio sends webhook
  2. Process through engine
  3. Send reply back via Twilio API
  4. Return confirmation

Twilio setup (env vars):
  TWILIO_ACCOUNT_SID=your-twilio-account-sid
  TWILIO_AUTH_TOKEN=your-twilio-auth-token
  TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_src_path = os.path.join(_project_root, "src")
for p in [_src_path, _project_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

logger = logging.getLogger("flowsync.channels.whatsapp")

router = APIRouter(prefix="/channels/whatsapp", tags=["WhatsApp Channel"])


# ── Pydantic models ──

class WhatsAppIncomingMessage(BaseModel):
    from_number: str = Field(..., description="Customer's WhatsApp number")
    body: str = Field(..., description="Message text content")
    media_urls: list[str] = Field(default_factory=list, description="Attached media URLs")
    message_sid: Optional[str] = None
    conversation_sid: Optional[str] = None


class WhatsAppResponse(BaseModel):
    ticket_id: str
    channel: str
    response: str
    reply_sent: bool = False
    reply_method: str = "api"
    escalation_needed: bool = False
    escalation_reason: str = ""


# ── Twilio config ──

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "")
_twilio_configured = all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER])


async def send_whatsapp_reply(to_number: str, body: str) -> bool:
    """Send a WhatsApp reply via Twilio API. Returns True if sent."""
    if not _twilio_configured:
        logger.warning("Twilio not configured — set TWILIO_ACCOUNT_SID/AUTH_TOKEN/NUMBER")
        return False

    try:
        from twilio.rest import Client

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        number = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number

        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=number,
            body=body[:4096],
        )
        logger.info("WhatsApp reply sent to %s (sid=%s)", to_number, message.sid)
        return True
    except Exception as e:
        logger.error("Twilio send failed: %s", e)
        return False


async def _process_message(from_number: str, body: str) -> dict:
    """Run the engine and return the response + metadata."""
    input_data = {
        "channel": "whatsapp",
        "customer_phone": from_number,
        "content": body,
    }

    try:
        from agent.customer_success_agent import create_agent, run_agent
        agent = create_agent()
        if agent is not None:
            result = await run_agent(agent, input_data)
            ai_response = result.get("response", "")
            if ai_response:
                return {"response": ai_response.strip(), "escalation_needed": False, "escalation_reason": ""}
    except Exception:
        logger.info("LLM agent unavailable for WhatsApp, using prototype")

    from prototype import process_ticket
    result = process_ticket(input_data)
    return {
        "response": result.response_text.strip(),
        "escalation_needed": result.escalation_needed,
        "escalation_reason": result.escalation_reason,
    }


# ── Endpoints ──

@router.get("/status")
async def whatsapp_integration_status():
    return {
        "channel": "whatsapp",
        "status": "active",
        "twilio_configured": _twilio_configured,
        "endpoint": "/channels/whatsapp/incoming",
    }


@router.post("/incoming", response_model=WhatsAppResponse)
async def whatsapp_incoming(payload: WhatsAppIncomingMessage):
    """Receive WhatsApp message → process → send reply via Twilio → return confirmation."""
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    logger.info("WhatsApp from=%s body=%s", payload.from_number, payload.body[:80])

    engine_result = await _process_message(payload.from_number, payload.body)
    reply = engine_result["response"]

    reply_sent = await send_whatsapp_reply(payload.from_number, reply)

    return WhatsAppResponse(
        ticket_id=ticket_id,
        channel="whatsapp",
        response=reply,
        reply_sent=reply_sent,
        reply_method="twilio" if reply_sent else "api",
        escalation_needed=engine_result["escalation_needed"],
        escalation_reason=engine_result["escalation_reason"],
    )


# ── Helpers ──

def _validate_whatsapp_number(phone_number: str) -> bool:
    """Validate a WhatsApp phone number (E.164 format)."""
    cleaned = phone_number.replace("whatsapp:", "").strip()
    return cleaned.startswith("+") and len(cleaned) >= 8
