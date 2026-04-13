"""Quick smoke test for Exercise 2.2 channel integrations."""
import sys, os
# production/ is the project root
_prod = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_src = os.path.join(_prod, "..", "src")
for p in [_prod, _src]:
    if p not in sys.path:
        sys.path.insert(0, p)

results = []

def ok(name):
    results.append(f"  PASS: {name}")
    print(f"  PASS: {name}")

def fail(name, err):
    results.append(f"  FAIL: {name} -- {err}")
    print(f"  FAIL: {name} -- {err}")

# 1. Import web_form_handler
try:
    from channels.web_form_handler import (
        router, SupportFormSubmission, TicketResponse,
        TicketStatusResponse, _create_ticket_inmemory,
        _get_ticket_inmemory, _get_customer_tickets_inmemory,
        _normalize_priority, _normalize_category, _estimate_resolution,
    )
    ok("web_form_handler imports")
except Exception as e:
    fail("web_form_handler imports", e)

# 2. Pydantic validation
try:
    s = SupportFormSubmission(
        name="John Doe",
        email="john@test.com",
        subject="Slack integration issue",
        message="My Slack integration stopped working this morning. Tasks are not appearing in the dashboard. I have tried disconnecting and reconnecting but the issue persists.",
        category="integration",
        priority="high",
        company_name="TestCo",
    )
    assert s.name == "John Doe"
    assert s.priority == "high"
    ok("SupportFormSubmission validates")
except Exception as e:
    fail("SupportFormSubmission validates", e)

# 3. Pydantic rejects bad email
try:
    SupportFormSubmission(
        name="J",
        email="not-an-email",
        subject="Test",
        message="This is a test message with enough detail to pass validation.",
    )
    fail("Rejects bad email", "Should have raised")
except Exception:
    ok("Rejects bad email")

# 4. Pydantic rejects short message
try:
    SupportFormSubmission(
        name="John",
        email="john@test.com",
        subject="Test",
        message="Short",
    )
    fail("Rejects short message", "Should have raised")
except Exception:
    ok("Rejects short message (min 10 chars)")

# 5. In-memory ticket CRUD
try:
    t = _create_ticket_inmemory("user@test.com", "Test Subject", "Test desc", "web_form", "medium")
    assert t["ticket_number"].startswith("TKT-")
    assert t["status"] == "open"
    assert t["priority"] == "medium"
    assert t["channel"] == "web_form"
    ok("In-memory ticket created")

    found = _get_ticket_inmemory(t["ticket_number"])
    assert found is not None
    assert found["subject"] == "Test Subject"
    ok("In-memory ticket lookup")

    tickets = _get_customer_tickets_inmemory("user@test.com")
    assert len(tickets) >= 1
    ok("In-memory customer tickets list")
except Exception as e:
    fail("In-memory ticket CRUD", e)

# 6. Priority normalization
try:
    assert _normalize_priority("HIGH") == "high"
    assert _normalize_priority("invalid") == "medium"
    assert _normalize_priority(None) == "medium"
    ok("Priority normalization")
except Exception as e:
    fail("Priority normalization", e)

# 7. Category normalization
try:
    assert _normalize_category("BUG") == "bug"
    assert _normalize_category("invalid") is None
    assert _normalize_category(None) is None
    ok("Category normalization")
except Exception as e:
    fail("Category normalization", e)

# 8. Resolution estimation
try:
    assert _estimate_resolution("critical") == "within 2 hours"
    assert _estimate_resolution("high") == "within 8 hours"
    assert _estimate_resolution("medium") == "within 24 hours"
    assert _estimate_resolution("low") == "within 48 hours"
    ok("Resolution estimation")
except Exception as e:
    fail("Resolution estimation", e)

# 9. Gmail handler placeholder
try:
    from channels.gmail_handler import router as gmail_router, GmailMessagePayload
    route_paths = []
    for r in gmail_router.routes:
        route_paths.append(getattr(r, 'path', str(r)))
    # Webhook is now in api/main.py, gmail_handler just has /status
    assert any("status" in p for p in route_paths), f"Missing status in: {route_paths}"
    ok("Gmail handler structure (status only; webhook in main.py)")
except Exception as e:
    fail("Gmail handler structure", e)

# 10. WhatsApp handler placeholder
try:
    from channels.whatsapp_handler import router as whatsapp_router, WhatsAppIncomingMessage
    route_paths = []
    for r in whatsapp_router.routes:
        route_paths.append(getattr(r, 'path', str(r)))
    # Webhook is now in api/main.py, whatsapp_handler just has /status
    assert any("status" in p for p in route_paths), f"Missing status in: {route_paths}"
    ok("WhatsApp handler structure (status only; webhook in main.py)")
except Exception as e:
    fail("WhatsApp handler structure", e)

# 11. Main app creation
try:
    from api.main import app
    assert app.title == "FlowSync Customer Success API"
    paths = [r.path for r in app.routes]
    assert "/support/submit" in paths
    assert "/support/ticket/{ticket_id}" in paths
    assert "/support/tickets" in paths
    assert "/health" in paths
    assert "/" in paths
    ok("FastAPI app with all routes")
except Exception as e:
    fail("FastAPI app creation", e)

# 12. Response models
try:
    resp = TicketResponse(
        success=True,
        ticket_id="TKT-00001",
        customer_id="user@test.com",
        status="open",
        initial_response="Hi, we're looking into this...",
        created_at="2025-01-01T00:00:00",
        expected_resolution="within 24 hours",
    )
    assert resp.ticket_id == "TKT-00001"
    assert resp.success is True
    ok("TicketResponse model")
except Exception as e:
    fail("TicketResponse model", e)

# 13. TicketStatusResponse
try:
    status_resp = TicketStatusResponse(
        ticket_id="TKT-00001",
        subject="Test",
        status="open",
        priority="medium",
        channel="web_form",
        is_escalated=False,
        created_at="2025-01-01",
        updated_at="2025-01-01",
    )
    assert status_resp.ticket_id == "TKT-00001"
    ok("TicketStatusResponse model")
except Exception as e:
    fail("TicketStatusResponse model", e)

# Summary
print()
passed = sum(1 for r in results if "PASS" in r)
failed = sum(1 for r in results if "FAIL" in r)
print(f"Results: {passed} passed, {failed} failed, {len(results)} total")
if failed:
    print("Failures:")
    for r in results:
        if "FAIL" in r:
            print(f"  {r}")
    sys.exit(1)
else:
    print("All smoke tests passed!")
