"""
FlowSync Customer Success -- Gmail Channel Handler
====================================================
Receives emails via webhook, processes through FlowSync engine,
and sends the AI-generated reply back to the customer via SMTP.

Email reply flow:
  1. POST /channels/gmail/incoming  ← external service sends email data
  2. Process through engine (intent + sentiment + KB + response)
  3. Send reply back via SMTP (using sender's SMTP server)
  4. Return confirmation

SMTP setup (env vars):
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USERNAME=your@email.com
  SMTP_PASSWORD=your-app-password
  SMTP_FROM_EMAIL=support@flowsync.com
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import Optional

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import APIRouter
from pydantic import BaseModel, Field

# Path setup — Walk up from __file__ to find src/ directory.
_file_dir = os.path.dirname(os.path.abspath(__file__))
_check = _file_dir
for _ in range(10):
    _src = os.path.join(_check, "src")
    if os.path.isdir(_src):
        for _p in [_src, _check]:
            if _p not in sys.path:
                sys.path.insert(0, _p)
        break
    _next = os.path.dirname(_check)
    if _next == _check:
        break
    _check = _next

logger = logging.getLogger("flowsync.channels.gmail")

router = APIRouter(prefix="/channels/gmail", tags=["Gmail Channel"])


# ── Pydantic models ──

class GmailIncomingMessage(BaseModel):
    from_address: str = Field(..., description="Sender email address")
    subject: str = Field(default="", description="Email subject line")
    body: str = Field(..., description="Email body content")
    message_id: Optional[str] = None


class GmailResponse(BaseModel):
    ticket_id: str
    channel: str
    response: str
    reply_sent: bool = False
    reply_method: str = "api"
    escalation_needed: bool = False
    escalation_reason: str = ""


# ── SMTP config ──

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
_smtp_configured = all([SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL])


async def send_email_reply(to_address: str, subject: str, body: str) -> bool:
    """Send an email reply via SMTP. Returns True if sent successfully."""
    if not _smtp_configured:
        logger.warning("SMTP not configured — set SMTP_HOST/EMAIL/PASSWORD env vars")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_FROM_EMAIL
        msg["To"] = to_address
        msg["Subject"] = f"Re: {subject}" if subject else "Re: FlowSync Support"

        html_body = body.replace("\n", "<br>\n")
        msg.attach(MIMEText(body, "plain", "utf-8"))
        msg.attach(MIMEText(f"<html><body>{html_body}</body></html>", "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)

        logger.info("Email reply sent to %s via SMTP", to_address)
        return True
    except Exception as e:
        logger.error("SMTP send failed: %s", e)
        return False


async def _process_email(from_address: str, subject: str, body: str) -> dict:
    """Run the engine and return the response + metadata."""
    input_data = {
        "channel": "email",
        "customer_email": from_address,
        "subject": subject,
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
        logger.info("LLM agent unavailable for Gmail, using prototype")

    from prototype import process_ticket
    result = process_ticket(input_data)
    return {
        "response": result.response_text.strip(),
        "escalation_needed": result.escalation_needed,
        "escalation_reason": result.escalation_reason,
    }


# ── Endpoints ──

@router.get("/status")
async def gmail_status():
    return {
        "channel": "gmail",
        "status": "active",
        "smtp_configured": _smtp_configured,
        "endpoint": "/channels/gmail/incoming",
    }


@router.post("/incoming", response_model=GmailResponse)
async def gmail_incoming(payload: GmailIncomingMessage):
    """Receive email → process → send reply via SMTP → return confirmation."""
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    logger.info("Gmail from=%s subject=%s", payload.from_address, payload.subject)

    engine_result = await _process_email(payload.from_address, payload.subject, payload.body)
    reply = engine_result["response"]

    reply_sent = await send_email_reply(payload.from_address, payload.subject, reply)

    return GmailResponse(
        ticket_id=ticket_id,
        channel="email",
        response=reply,
        reply_sent=reply_sent,
        reply_method="smtp" if reply_sent else "api",
        escalation_needed=engine_result["escalation_needed"],
        escalation_reason=engine_result["escalation_reason"],
    )
