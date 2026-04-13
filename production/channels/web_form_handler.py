"""
FlowSync Customer Success -- Web Support Form Handler
======================================================
FastAPI router for the web-based customer support form.

Endpoints:
  POST /support/submit       -- Submit a support request
  GET  /support/ticket/{id}  -- Check ticket status
  GET  /support/tickets      -- List recent tickets (by email)

The submit endpoint:
  1. Validates the form submission (Pydantic)
  2. Creates/resolves the customer in PostgreSQL
  3. Creates a support ticket in PostgreSQL
  4. Runs the AI agent to generate an initial response
  5. Stores the agent's response as a message
  6. Returns ticket_id, status, and initial response

Usage:
    from fastapi import FastAPI
    from channels.web_form_handler import router as web_form_router

    app = FastAPI()
    app.include_router(web_form_router, prefix="/api")
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger("flowsync.channels.web_form")

router = APIRouter(
    prefix="/support",
    tags=["Web Support Form"],
    responses={400: {"description": "Validation error"}, 500: {"description": "Internal server error"}},
)


# ──────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ──────────────────────────────────────────────────────────────

class SupportFormSubmission(BaseModel):
    """Validated web support form submission."""

    # Customer identity
    name: str = Field(..., min_length=1, max_length=200, description="Customer's full name")
    email: EmailStr = Field(..., description="Customer's email address")

    # Issue details
    subject: str = Field(..., min_length=3, max_length=300, description="Brief subject of the issue")
    message: str = Field(..., min_length=10, max_length=5000, description="Detailed description of the issue")

    # Classification (optional -- agent can infer if not provided)
    category: Optional[str] = Field(
        default=None,
        description="Issue category: 'bug', 'feature_request', 'integration', 'billing', 'general'",
    )
    priority: Optional[str] = Field(
        default="medium",
        description="Priority level: 'low', 'medium', 'high', 'critical'",
    )

    # Metadata
    company_name: Optional[str] = Field(default=None, max_length=200)
    referral_source: Optional[str] = Field(default=None, max_length=100)

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "name": "Ahmed Hassan",
                    "email": "ahmed@startup.io",
                    "subject": "Slack integration not syncing tasks",
                    "message": "I connected my Slack workspace yesterday but tasks aren't appearing in my dashboard. I've tried disconnecting and reconnecting but it still doesn't work.",
                    "category": "integration",
                    "priority": "high",
                    "company_name": "StartupIO",
                }
            ]
        }


class TicketResponse(BaseModel):
    """Response returned after successful form submission."""

    success: bool = Field(..., description="Whether the submission was successful")
    ticket_id: str = Field(..., description="Unique ticket ID (e.g. TKT-00042)")
    customer_id: str = Field(..., description="Customer identifier")
    status: str = Field(..., description="Ticket status: open, in_progress, escalated")
    initial_response: str = Field(..., description="AI-generated initial response to the customer")
    created_at: str = Field(..., description="ISO timestamp of ticket creation")
    expected_resolution: Optional[str] = Field(
        default=None,
        description="Expected resolution time (e.g. 'within 24 hours')",
    )


class TicketStatusResponse(BaseModel):
    """Response for ticket status lookup."""

    ticket_id: str
    subject: str
    status: str
    priority: str
    channel: str
    is_escalated: bool
    created_at: str
    updated_at: str
    latest_response: Optional[str] = None


# ──────────────────────────────────────────────────────────────
# HELPER: Database pool (lazy init)
# ──────────────────────────────────────────────────────────────

_db_pool = None


async def _get_db_pool():
    """Get or create the database connection pool."""
    global _db_pool
    if _db_pool is None:
        try:
            from database import queries
            _db_pool = await queries.get_db_pool()
            logger.info("Database pool connected")
        except Exception as e:
            logger.warning("Database pool not available, using in-memory fallback: %s", e)
            _db_pool = "fallback"
    return _db_pool


def _is_db_available() -> bool:
    """Check if database is available (not fallback)."""
    return _db_pool is not None and _db_pool != "fallback"


# ──────────────────────────────────────────────────────────────
# HELPER: Priority mapping
# ──────────────────────────────────────────────────────────────

_VALID_PRIORITIES = {"low", "medium", "high", "critical"}
_VALID_CATEGORIES = {"bug", "feature_request", "integration", "billing", "general"}


def _normalize_priority(priority: Optional[str]) -> str:
    """Normalize and validate priority value."""
    if not priority or priority.lower() not in _VALID_PRIORITIES:
        return "medium"
    return priority.lower()


def _normalize_category(category: Optional[str]) -> Optional[str]:
    """Normalize and validate category value."""
    if category and category.lower() in _VALID_CATEGORIES:
        return category.lower()
    return None


# ──────────────────────────────────────────────────────────────
# HELPER: In-memory fallback store
# ──────────────────────────────────────────────────────────────

_inmemory_tickets: dict[str, dict] = {}
_inmemory_counter = 0


def _create_ticket_inmemory(
    customer_id: str,
    subject: str,
    description: str,
    channel: str,
    priority: str,
) -> dict:
    """Create a ticket in the in-memory fallback store."""
    global _inmemory_counter
    _inmemory_counter += 1
    ticket_id = f"TKT-{_inmemory_counter:05d}"
    ticket = {
        "ticket_id": ticket_id,
        "ticket_number": ticket_id,
        "customer_id": customer_id,
        "subject": subject,
        "description": description,
        "channel": channel,
        "priority": priority,
        "status": "open",
        "is_escalated": False,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _inmemory_tickets[ticket_id] = ticket
    return ticket


def _get_ticket_inmemory(ticket_id: str) -> Optional[dict]:
    """Get a ticket from the in-memory fallback store."""
    return _inmemory_tickets.get(ticket_id)


def _get_customer_tickets_inmemory(customer_id: str, limit: int = 20) -> list[dict]:
    """Get tickets for a customer from the in-memory fallback store."""
    tickets = [
        t for t in _inmemory_tickets.values()
        if t["customer_id"] == customer_id
    ]
    tickets.sort(key=lambda t: t["created_at"], reverse=True)
    return tickets[:limit]


# ──────────────────────────────────────────────────────────────
# ENDPOINT: POST /support/submit
# ──────────────────────────────────────────────────────────────

@router.post(
    "/submit",
    response_model=TicketResponse,
    summary="Submit a support request",
    description="Submit a support request via the web form. Creates a customer record, "
                "a support ticket, runs the AI agent for an initial response, and returns "
                "the ticket ID and response.",
)
async def submit_support_form(submission: SupportFormSubmission):
    """
    Handle a web support form submission.

    Workflow:
    1. Validate the form (Pydantic)
    2. Create/resolve customer in database
    3. Create a support ticket
    4. Run the AI agent for an initial response
    5. Return ticket details and response

    Returns:
        TicketResponse with ticket_id, status, and initial AI response.
    """
    pool = await _get_db_pool()
    priority = _normalize_priority(submission.priority)
    category = _normalize_category(submission.category)

    logger.info(
        "Support form submission: name=%s, email=%s, subject=%s, priority=%s, category=%s",
        submission.name, submission.email, submission.subject, priority, category,
    )

    try:
        # ── Step 1: Create/resolve customer ──
        customer_id = submission.email

        if _is_db_available():
            from database import queries
            customer_result = await queries.create_or_get_customer(
                pool,
                identifier=submission.email,
                channel="web_form",
                display_name=submission.name,
                company_name=submission.company_name,
            )
            customer_id = str(customer_result["customer_id"])
            logger.info("Customer resolved (DB): %s (is_new=%s)", customer_id, customer_result["is_new"])
        else:
            logger.info("Customer resolved (in-memory): %s", customer_id)

        # ── Step 2: Create ticket ──
        # Build description from subject + message
        full_description = f"Subject: {submission.subject}\n\n{submission.message}"
        if category:
            full_description = f"[Category: {category}]\n\n{full_description}"

        if _is_db_available():
            from database import queries
            ticket = await queries.create_ticket(
                pool,
                customer_id=customer_id,
                description=full_description,
                channel="web_form",
                subject=submission.subject,
                priority=priority,
            )
            ticket_id = ticket["ticket_number"]
            logger.info("Ticket created (DB): %s", ticket_id)
        else:
            ticket = _create_ticket_inmemory(
                customer_id=customer_id,
                subject=submission.subject,
                description=full_description,
                channel="web_form",
                priority=priority,
            )
            ticket_id = ticket["ticket_number"]
            logger.info("Ticket created (in-memory): %s", ticket_id)

        # ── Step 3: Run AI agent for initial response ──
        initial_response_text = await _run_agent_for_ticket(
            customer_id=customer_id,
            subject=submission.subject,
            message=submission.message,
            customer_name=submission.name,
        )

        # ── Step 4: Determine expected resolution time ──
        expected_resolution = _estimate_resolution(priority)

        # ── Step 5: Return response ──
        return TicketResponse(
            success=True,
            ticket_id=ticket_id,
            customer_id=customer_id,
            status=ticket.get("status", "open"),
            initial_response=initial_response_text,
            created_at=ticket.get("created_at", datetime.now().isoformat()),
            expected_resolution=expected_resolution,
        )

    except Exception as e:
        logger.error("Support form submission failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process support request: {str(e)}")


# ──────────────────────────────────────────────────────────────
# ENDPOINT: GET /support/ticket/{ticket_id}
# ──────────────────────────────────────────────────────────────

@router.get(
    "/ticket/{ticket_id}",
    response_model=TicketStatusResponse,
    summary="Check ticket status",
    description="Look up the current status of a support ticket by its ID.",
)
async def get_ticket_status(ticket_id: str):
    """
    Get the current status of a support ticket.

    Args:
        ticket_id: The ticket ID (e.g. TKT-00001).

    Returns:
        TicketStatusResponse with current status, priority, and latest response.
    """
    pool = await _get_db_pool()

    try:
        if _is_db_available():
            from database import queries
            ticket = await queries.get_ticket(pool, ticket_id)
            if not ticket:
                raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

            return TicketStatusResponse(
                ticket_id=ticket.get("ticket_number", ticket_id),
                subject=ticket.get("subject", ""),
                status=ticket.get("status", "open"),
                priority=ticket.get("priority", "medium"),
                channel=ticket.get("channel", "web_form"),
                is_escalated=ticket.get("is_escalated", False),
                created_at=str(ticket.get("created_at", "")),
                updated_at=str(ticket.get("updated_at", "")),
                latest_response=None,
            )
        else:
            ticket = _get_ticket_inmemory(ticket_id)
            if not ticket:
                raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

            return TicketStatusResponse(
                ticket_id=ticket["ticket_number"],
                subject=ticket["subject"],
                status=ticket["status"],
                priority=ticket["priority"],
                channel=ticket["channel"],
                is_escalated=ticket.get("is_escalated", False),
                created_at=ticket["created_at"],
                updated_at=ticket["updated_at"],
                latest_response=None,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get ticket status: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get ticket status: {str(e)}")


# ──────────────────────────────────────────────────────────────
# ENDPOINT: GET /support/tickets
# ──────────────────────────────────────────────────────────────

@router.get(
    "/tickets",
    summary="List tickets by email",
    description="List all support tickets for a given customer email.",
)
async def list_customer_tickets(
    email: EmailStr = Query(..., description="Customer email address"),
    limit: int = Query(default=20, ge=1, le=100, description="Max tickets to return"),
):
    """
    List all support tickets for a customer.

    Args:
        email: Customer email address.
        limit: Maximum number of tickets to return (1-100).

    Returns:
        List of ticket summaries.
    """
    pool = await _get_db_pool()

    try:
        if _is_db_available():
            from database import queries

            # Resolve customer ID from email
            customer = await queries.create_or_get_customer(pool, identifier=email, channel="web_form")
            customer_id = str(customer["customer_id"])

            tickets = await queries.get_customer_tickets(pool, customer_id, limit=limit)
            return {
                "customer_id": customer_id,
                "email": email,
                "total": len(tickets),
                "tickets": [
                    {
                        "ticket_id": t["ticket_number"],
                        "subject": t.get("subject", ""),
                        "status": t["status"],
                        "priority": t["priority"],
                        "created_at": str(t["created_at"]),
                    }
                    for t in tickets
                ],
            }
        else:
            tickets = _get_customer_tickets_inmemory(email, limit)
            return {
                "customer_id": email,
                "email": email,
                "total": len(tickets),
                "tickets": [
                    {
                        "ticket_id": t["ticket_number"],
                        "subject": t["subject"],
                        "status": t["status"],
                        "priority": t["priority"],
                        "created_at": t["created_at"],
                    }
                    for t in tickets
                ],
            }

    except Exception as e:
        logger.error("Failed to list tickets: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list tickets: {str(e)}")


# ──────────────────────────────────────────────────────────────
# HELPER: Run AI agent for initial response
# ──────────────────────────────────────────────────────────────

async def _run_agent_for_ticket(
    customer_id: str,
    subject: str,
    message: str,
    customer_name: str,
) -> str:
    """
    Run the AI agent to generate an initial response for a new ticket.

    Falls back to a templated response if the agent is unavailable.

    Args:
        customer_id: Customer identifier.
        subject: Ticket subject.
        message: Customer's message.
        customer_name: Customer's display name.

    Returns:
        The agent's response text, or a fallback response.
    """
    try:
        from agent.customer_success_agent import create_agent, run_agent

        agent = create_agent(model="gpt-4o")

        result = await run_agent(
            agent,
            input_data={
                "channel": "web_form",
                "customer_email": customer_id if "@" in customer_id else None,
                "customer_phone": customer_id if "@" not in customer_id else None,
                "subject": subject,
                "content": message,
            },
        )

        response_text = result.get("response", "")
        if response_text and len(response_text) > 20:
            logger.info("AI agent generated initial response (%d chars)", len(response_text))
            return response_text

    except Exception as e:
        logger.warning("AI agent unavailable, using fallback response: %s", e)

    # Fallback: templated response
    return (
        f"Hi {customer_name},\n\n"
        f"Thank you for contacting FlowSync support. We've received your request "
        f"regarding: \"{subject}\"\n\n"
        f"Your ticket has been created and our team is reviewing it. "
        f"You can expect a response within 24 hours.\n\n"
        f"Ticket ID: (see response)\n\n"
        f"Best regards,\n"
        f"FlowSync Customer Success Team"
    )


# ──────────────────────────────────────────────────────────────
# HELPER: Estimate resolution time
# ──────────────────────────────────────────────────────────────

def _estimate_resolution(priority: str) -> str:
    """
    Estimate resolution time based on ticket priority.

    Args:
        priority: Ticket priority level.

    Returns:
        Human-readable expected resolution time.
    """
    estimates = {
        "low": "within 48 hours",
        "medium": "within 24 hours",
        "high": "within 8 hours",
        "critical": "within 2 hours",
    }
    return estimates.get(priority, "within 24 hours")
