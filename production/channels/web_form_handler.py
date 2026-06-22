"""
FlowSync Customer Success -- Web Form Channel Handler
=====================================================
Processes support form submissions using the prototype engine
(rule-based intent/sentiment/KB/response) with optional LLM upgrade.
"""

import uuid
import logging
import os
import sys
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

# Path setup for importing prototype
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_src_path = os.path.join(_project_root, "src")
for p in [_src_path, _project_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

logger = logging.getLogger("flowsync.channels.web_form")

router = APIRouter(prefix="/support", tags=["support-form"])


class SupportFormSubmission(BaseModel):
    name: str
    email: EmailStr
    subject: str
    category: str = "general"
    priority: str = "medium"
    message: str
    company_name: Optional[str] = None


class TicketResponse(BaseModel):
    ticket_id: str
    message: str
    initial_response: str = ""
    status: str = "open"


@router.post("/submit", response_model=TicketResponse)
async def submit_support_form(submission: SupportFormSubmission):
    """Submit support form → process via prototype engine → return AI response."""
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    logger.info("Support form received: %s - %s", submission.email, submission.subject)

    input_data = {
        "channel": "web_form",
        "customer_email": submission.email,
        "subject": submission.subject,
        "content": submission.message,
    }

    # Primary: prototype rule-based engine (always works, no API key)
    try:
        from prototype import process_ticket
        logger.info("Using prototype engine for web_form submission")

        result = process_ticket(input_data)
        response_text = result.response_text.strip()

        logger.info("Prototype response: intent=%s, sentiment=%s, len=%d",
                     result.intent, result.sentiment, len(response_text))

        if response_text:
            return TicketResponse(
                ticket_id=ticket_id,
                message="Your request has been processed by our AI assistant.",
                initial_response=response_text,
                status="escalated" if result.escalation_needed else "open",
            )
    except Exception as e:
        logger.error("Prototype engine failed, trying LLM: %s", e, exc_info=True)

    # Fallback: LLM agent (if GROQ_API_KEY is set)
    try:
        from agent.customer_success_agent import create_agent, run_agent
        agent = create_agent()
        if agent is not None:
            result = await run_agent(agent, input_data)
            ai_response = result.get("response", "")
            if ai_response:
                return TicketResponse(
                    ticket_id=ticket_id,
                    message="Your request has been processed by our AI assistant.",
                    initial_response=ai_response.strip(),
                    status="open",
                )
    except Exception as e:
        logger.warning("LLM agent failed: %s", e)

    # Last resort: static fallback
    logger.error("All engines failed, returning static fallback")
    return TicketResponse(
        ticket_id=ticket_id,
        message="Thank you! Your support request has been received.",
        initial_response=(
            f"Dear {submission.name.split()[0]},\n\n"
            f"Thank you for reaching out regarding **{submission.subject}**.\n\n"
            f"We have received your message and our team is reviewing it.\n"
            f"You can track your request using Ticket ID: **{ticket_id}**.\n\n"
            "Best regards,\n"
            "FlowSync AI Support"
        ),
        status="open",
    )


@router.get("/ticket/{ticket_id}")
async def get_ticket_status(ticket_id: str):
    """Get ticket status"""
    return {
        "ticket_id": ticket_id,
        "status": "open",
        "message": "Your request is being processed by our AI assistant."
    }