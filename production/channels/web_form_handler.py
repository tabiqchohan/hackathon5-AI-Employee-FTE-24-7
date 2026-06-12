from fastapi import APIRouter
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid
import logging

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
    """Submit support form and generate AI response using Groq"""
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"

    logger.info(f"Support form received: {submission.email} - {submission.subject}")

    # Generate AI Response using Groq Agent
    try:
        from agent.customer_success_agent import create_agent, run_agent

        agent = create_agent()

        input_data = {
            "channel": "web_form",
            "customer_email": submission.email,
            "subject": submission.subject,
            "content": submission.message,
            "category": submission.category,
            "priority": submission.priority,
        }

        result = await run_agent(agent, input_data)
        ai_response = result.get("response", "Thank you for your request. We will get back to you shortly.")

    except Exception as e:
        logger.warning(f"AI response generation failed: {e}")
        ai_response = (
            f"Dear {submission.name.split()[0]},\n\n"
            f"Thank you for reaching out regarding **{submission.subject}**.\n\n"
            f"We have received your message and our team is reviewing it.\n"
            f"You can track your request using Ticket ID: **{ticket_id}**.\n\n"
            "Best regards,\n"
            "FlowSync AI Support"
        )

    return TicketResponse(
        ticket_id=ticket_id,
        message="Thank you! Your support request has been received.",
        initial_response=ai_response.strip(),
        status="open"
    )


@router.get("/ticket/{ticket_id}")
async def get_ticket_status(ticket_id: str):
    """Get ticket status"""
    return {
        "ticket_id": ticket_id,
        "status": "open",
        "message": "Your request is being processed by our AI assistant."
    }