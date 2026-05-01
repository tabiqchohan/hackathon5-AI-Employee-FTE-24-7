from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
import uuid

router = APIRouter(prefix="/support", tags=["support-form"])

class SupportFormSubmission(BaseModel):
    name: str
    email: EmailStr
    subject: str
    category: str = "general"
    message: str
    priority: str = "medium"
    company_name: Optional[str] = None

class TicketResponse(BaseModel):
    ticket_id: str
    message: str
    status: str = "open"

@router.post("/submit", response_model=TicketResponse)
async def submit_support_form(submission: SupportFormSubmission):
    """Simple version - uses in-memory fallback"""
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"

    print(f"✅ Support form received:")
    print(f"   Name: {submission.name}")
    print(f"   Email: {submission.email}")
    print(f"   Subject: {submission.subject}")
    print(f"   Category: {submission.category}")
    print(f"   Ticket ID: {ticket_id}")

    return TicketResponse(
        ticket_id=ticket_id,
        message="Thank you! Your support request has been received. Our AI assistant will respond shortly.",
        status="open"
    )

@router.get("/ticket/{ticket_id}")
async def get_ticket_status(ticket_id: str):
    """Simple ticket status"""
    return {
        "ticket_id": ticket_id,
        "status": "open",
        "message": "This is a demo response. Full database integration coming soon."
    }