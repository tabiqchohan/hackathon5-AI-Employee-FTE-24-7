"""
FlowSync Customer Success -- Gmail Channel Handler
====================================================
Processes incoming Gmail support emails through the FlowSync engine.

Two modes:
  1. Webhook mode — POST /channels/gmail/incoming receives email data
  2. API mode — future Gmail API integration (Pub/Sub + OAuth)

Setup for Gmail API integration (future):
  - Google Cloud project with Gmail API enabled
  - OAuth 2.0 service account credentials
  - Pub/Sub topic configured for Gmail push notifications
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_src_path = os.path.join(_project_root, "src")
for p in [_src_path, _project_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

logger = logging.getLogger("flowsync.channels.gmail")

router = APIRouter(
    prefix="/channels/gmail",
    tags=["Gmail Channel"],
)


# ──────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ──────────────────────────────────────────────────────────────

class GmailIncomingMessage(BaseModel):
    """Incoming email data for processing (webhook-style)."""
    from_address: str = Field(..., description="Sender email address")
    subject: str = Field(default="", description="Email subject line")
    body: str = Field(..., description="Email body content (plain text)")
    message_id: Optional[str] = None


class GmailResponse(BaseModel):
    """Response returned after processing a Gmail message."""
    ticket_id: str
    channel: str
    response: str
    escalation_needed: bool = False
    escalation_reason: str = ""


# ──────────────────────────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────────────────────────

@router.get("/status")
async def gmail_status():
    """Check Gmail channel status."""
    return {
        "channel": "gmail",
        "status": "active",
        "endpoint": "/channels/gmail/incoming",
        "message": "Gmail webhook endpoint ready.",
    }


@router.post("/incoming", response_model=GmailResponse)
async def gmail_incoming(payload: GmailIncomingMessage):
    """Receive an email and return an AI-generated response.

    Processes the email through the FlowSync engine (intent + sentiment
    + KB search + response generation). Works without any external API keys.
    """
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    logger.info("Gmail from=%s subject=%s", payload.from_address, payload.subject)

    input_data = {
        "channel": "email",
        "customer_email": payload.from_address,
        "subject": payload.subject,
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
                return GmailResponse(
                    ticket_id=ticket_id, channel="email",
                    response=ai_response.strip(),
                )
    except Exception:
        logger.info("LLM agent unavailable for Gmail, using prototype")

    from prototype import process_ticket
    result = process_ticket(input_data)
    return GmailResponse(
        ticket_id=ticket_id, channel="email",
        response=result.response_text.strip(),
        escalation_needed=result.escalation_needed,
        escalation_reason=result.escalation_reason,
    )


# ──────────────────────────────────────────────────────────────
# HELPER FUNCTIONS (stubs for future Gmail API integration)
# ──────────────────────────────────────────────────────────────

async def _get_gmail_service():
    """Create an authenticated Gmail API service.

    Future: Use service account + domain-wide delegation.
    """
    raise NotImplementedError(
        "Gmail API service not configured. "
        "Set GMAIL_CREDENTIALS_PATH and GMAIL_ADMIN_EMAIL env vars."
    )


async def _parse_email_message(raw_message: str) -> GmailIncomingMessage:
    """Parse a raw Gmail API message into structured data.

    Future: Decode base64url body, extract headers.
    """
    raise NotImplementedError("Raw email parsing not yet implemented")


async def _send_gmail_reply(message_id, thread_id, to_address, subject, body):
    """Send a reply via Gmail API.

    Future: MIME message creation + users.messages.send().
    """
    raise NotImplementedError("Gmail reply sending not yet implemented")
