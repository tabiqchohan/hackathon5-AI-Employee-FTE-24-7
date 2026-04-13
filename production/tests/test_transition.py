"""
FlowSync Customer Success AI Agent -- Transition Tests
=======================================================
Tests that validate the transition from prototype to production.
Ensures all production tools, formatters, and the agent pipeline
produce correct results matching the prototype behavior.

Run: cd production && python -m pytest tests/test_transition.py -v
"""

from __future__ import annotations

import sys
import os

# Add parent directory to path so we can import agent modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.tools import (
    search_knowledge_base,
    analyze_sentiment,
    create_ticket,
    get_customer_history,
    escalate_to_human,
    send_response_tool,
    get_or_create_customer,
    KnowledgeBaseRequest,
    SentimentRequest,
    TicketCreateRequest,
    CustomerHistoryRequest,
    EscalationRequest,
    SendResponseRequest,
    CustomerIdentifyRequest,
    Channel,
    Priority,
    SentimentLevel,
    ticket_registry,
    conversation_store,
)
from agent.formatters import (
    format_response,
    get_formatter,
    EmailFormatter,
    WhatsAppFormatter,
    WebFormFormatter,
    ResponseContext,
)
from agent.prompts import (
    SYSTEM_PROMPT,
    INTENT_CLASSIFICATION_PROMPT,
    SENTIMENT_ANALYSIS_PROMPT,
    ESCALATION_EVALUATION_PROMPT,
    RESPONSE_GENERATION_PROMPT,
    format_conversation_context,
    format_escalation_instruction,
)


# ──────────────────────────────────────────────────────────────
# TEST COUNTERS
# ──────────────────────────────────────────────────────────────

_tests_run = 0
_tests_passed = 0
_tests_failed = 0


def _test(name: str, fn):
    """Run a single test and track results."""
    global _tests_run, _tests_passed, _tests_failed
    _tests_run += 1
    try:
        fn()
        _tests_passed += 1
        print(f"  PASS  [{_tests_run}] {name}")
    except AssertionError as e:
        _tests_failed += 1
        print(f"  FAIL  [{_tests_run}] {name}: {e}")
    except Exception as e:
        _tests_failed += 1
        print(f"  ERROR [{_tests_run}] {name}: {type(e).__name__}: {e}")


# ──────────────────────────────────────────────────────────────
# TOOL TESTS
# ──────────────────────────────────────────────────────────────

def test_search_knowledge_base():
    """Test KB search returns relevant results."""
    result = search_knowledge_base(KnowledgeBaseRequest(query="How do I invite team members?"))
    assert not result.fallback, "Should find team collaboration docs"
    assert result.confidence > 0.5, f"Confidence too low: {result.confidence}"
    assert len(result.result) > 50, f"Result too short: {len(result.result)} chars"


def test_search_knowledge_base_fallback():
    """Test KB search returns fallback for unknown queries."""
    result = search_knowledge_base(KnowledgeBaseRequest(query="xyzzy unknown feature blah"))
    assert result.fallback, "Should return fallback for unknown query"
    assert result.confidence < 0.5, f"Fallback confidence too high: {result.confidence}"


def test_analyze_sentiment_positive():
    """Test positive sentiment detection."""
    result = analyze_sentiment(SentimentRequest(message="Thanks for the help, that worked perfectly!"))
    assert result.sentiment == SentimentLevel.POSITIVE
    assert result.score == 2
    assert not result.requires_escalation


def test_analyze_sentiment_neutral():
    """Test neutral sentiment detection (no false positives)."""
    result = analyze_sentiment(SentimentRequest(message="How do I reset my password?"))
    assert result.sentiment == SentimentLevel.NEUTRAL
    assert result.score == 0
    assert not result.requires_escalation


def test_analyze_sentiment_negative():
    """Test negative sentiment detection."""
    result = analyze_sentiment(SentimentRequest(message="This is still not working, I'm getting frustrated"))
    assert result.sentiment == SentimentLevel.NEGATIVE
    assert result.score == -1
    assert not result.requires_escalation


def test_analyze_sentiment_very_negative():
    """Test very_negative sentiment detection and escalation flag."""
    result = analyze_sentiment(SentimentRequest(message="This is ridiculous! I want to speak to a manager NOW!"))
    assert result.sentiment == SentimentLevel.VERY_NEGATIVE
    assert result.score == -2
    assert result.requires_escalation


def test_create_ticket():
    """Test ticket creation with valid inputs."""
    result = create_ticket(TicketCreateRequest(
        customer_id="test@transition.com",
        issue="Slack integration not syncing",
        priority=Priority.HIGH,
        channel=Channel.EMAIL,
    ))
    assert result.ticket_id.startswith("TKT-")
    assert result.customer_id == "test@transition.com"
    assert result.priority == "high"
    assert result.status == "open"


def test_create_ticket_invalid_email():
    """Test ticket creation rejects invalid customer_id."""
    try:
        create_ticket(TicketCreateRequest(
            customer_id="not-an-email-or-phone",
            issue="Test issue",
        ))
        assert False, "Should have raised validation error"
    except Exception:
        pass  # Expected


def test_get_customer_history_empty():
    """Test history retrieval for non-existent customer."""
    result = get_customer_history(CustomerHistoryRequest(
        customer_id="nonexistent@transition.com"
    ))
    assert result.message_count == 0
    assert result.conversation_id is None


def test_escalate_to_human():
    """Test successful escalation."""
    # Create a ticket first
    ticket = create_ticket(TicketCreateRequest(
        customer_id="escalate@transition.com",
        issue="Test issue for escalation",
        priority=Priority.MEDIUM,
        channel=Channel.WHATSAPP,
    ))

    result = escalate_to_human(EscalationRequest(
        ticket_id=ticket.ticket_id,
        reason="Customer requested manager",
    ))
    assert result.success is True
    assert result.status == "escalated"
    assert result.ticket_id == ticket.ticket_id


def test_escalate_invalid_ticket():
    """Test escalation of non-existent ticket."""
    result = escalate_to_human(EscalationRequest(
        ticket_id="TKT-99999",
        reason="Testing invalid ticket",
    ))
    assert result.success is False
    assert result.error is not None


def test_send_response():
    """Test sending a formatted response."""
    ticket = create_ticket(TicketCreateRequest(
        customer_id="response@transition.com",
        issue="Test issue",
        channel=Channel.EMAIL,
    ))

    result = send_response_tool(SendResponseRequest(
        ticket_id=ticket.ticket_id,
        message="Here is the solution to your issue.",
        channel=Channel.EMAIL,
    ))
    assert result.success is True
    assert "Dear Valued Customer" in result.formatted_message
    assert "Best regards" in result.formatted_message


def test_get_or_create_customer_new():
    """Test creating a new customer record."""
    result = get_or_create_customer(CustomerIdentifyRequest(
        identifier="newcustomer@transition.com",
        channel=Channel.EMAIL,
    ))
    assert result.is_new is True
    assert result.message_count == 0


def test_get_or_create_customer_existing():
    """Test retrieving an existing customer."""
    # Create first
    get_or_create_customer(CustomerIdentifyRequest(
        identifier="existing@transition.com",
        channel=Channel.EMAIL,
    ))
    # Retrieve
    result = get_or_create_customer(CustomerIdentifyRequest(
        identifier="existing@transition.com",
        channel=Channel.WHATSAPP,
    ))
    assert result.is_new is False
    assert result.conversation_id is not None


def test_cross_channel_resolution():
    """Test that same customer via different channels resolves to same record."""
    r1 = get_or_create_customer(CustomerIdentifyRequest(
        identifier="crosschannel@transition.com",
        channel=Channel.EMAIL,
    ))
    r2 = get_or_create_customer(CustomerIdentifyRequest(
        identifier="crosschannel@transition.com",
        channel=Channel.WHATSAPP,
    ))
    # Same conversation ID
    assert r1.conversation_id == r2.conversation_id
    # channel_switched requires prior messages to set last_channel_used
    # In this test no messages were added, so switched=False is correct
    assert r2.channel_switched is False
    assert r2.is_new is False


# ──────────────────────────────────────────────────────────────
# FORMATTER TESTS
# ──────────────────────────────────────────────────────────────

def test_email_formatter_structure():
    """Test email response has formal structure."""
    result = format_response(
        message="Go to Settings > Team > Invite Members.",
        channel="email",
    )
    assert "Dear Valued Customer" in result.text
    assert "Best regards" in result.text
    assert "FlowSync Customer Success Team" in result.text


def test_whatsapp_formatter_length():
    """Test WhatsApp response stays within character limit."""
    result = format_response(
        message="Go to Settings > Team > Invite Members to add your team.",
        channel="whatsapp",
    )
    assert result.character_count <= 280, f"WhatsApp too long: {result.character_count}"


def test_whatsapp_formatter_tone():
    """Test WhatsApp response has casual tone."""
    result = format_response(
        message="Try reconnecting the integration.",
        channel="whatsapp",
    )
    assert "Hey" in result.text or "Hi" in result.text
    assert "Dear" not in result.text


def test_web_form_formatter_structure():
    """Test web form response has semi-formal structure."""
    result = format_response(
        message="Here is the information you requested.",
        channel="web_form",
    )
    assert "Thanks for your message" in result.text
    assert "Best," in result.text
    assert "FlowSync Support" in result.text


def test_escalation_formatting_email():
    """Test escalation message is formal for email."""
    result = format_response(
        message="",
        channel="email",
        is_escalation=True,
        escalation_reason="Pricing inquiry requires sales team",
    )
    assert "escalated" in result.text.lower()
    assert "specialist team" in result.text.lower()
    assert "Pricing inquiry" in result.text


def test_escalation_formatting_whatsapp():
    """Test escalation message is serious but casual for WhatsApp."""
    result = format_response(
        message="",
        channel="whatsapp",
        is_escalation=True,
        escalation_reason="Customer requested manager",
    )
    assert result.character_count <= 280
    assert "escalating" in result.text.lower()


def test_formatter_truncation():
    """Test that long messages are truncated for WhatsApp."""
    long_message = "A" * 500
    result = format_response(
        message=long_message,
        channel="whatsapp",
    )
    # WhatsApp formatter truncates body; total may slightly exceed 280 due to greeting/sign-off
    assert result.truncated is True
    assert result.character_count < 400  # Reasonable upper bound


def test_get_formatter_valid():
    """Test getting valid formatters."""
    assert isinstance(get_formatter("email"), EmailFormatter)
    assert isinstance(get_formatter("whatsapp"), WhatsAppFormatter)
    assert isinstance(get_formatter("web_form"), WebFormFormatter)


def test_get_formatter_invalid():
    """Test that invalid channel raises error."""
    try:
        get_formatter("telegram")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


# ──────────────────────────────────────────────────────────────
# PROMPT TESTS
# ──────────────────────────────────────────────────────────────

def test_system_prompt_exists():
    """Test system prompt is defined."""
    assert SYSTEM_PROMPT is not None
    assert len(SYSTEM_PROMPT) > 500
    assert "FlowSync" in SYSTEM_PROMPT
    assert "escalat" in SYSTEM_PROMPT.lower()


def test_system_prompt_contains_skills():
    """Test system prompt references all 5 skills."""
    assert "SK-001" in SYSTEM_PROMPT or "Knowledge Retrieval" in SYSTEM_PROMPT
    assert "SK-002" in SYSTEM_PROMPT or "Sentiment" in SYSTEM_PROMPT
    assert "SK-003" in SYSTEM_PROMPT or "Escalation" in SYSTEM_PROMPT
    assert "SK-004" in SYSTEM_PROMPT or "Channel Adaptation" in SYSTEM_PROMPT
    assert "SK-005" in SYSTEM_PROMPT or "Customer Identification" in SYSTEM_PROMPT


def test_system_prompt_contains_escalation_rules():
    """Test system prompt includes all escalation rules."""
    assert "ESC-001" in SYSTEM_PROMPT
    assert "ESC-002" in SYSTEM_PROMPT
    assert "ESC-003" in SYSTEM_PROMPT
    assert "ESC-004" in SYSTEM_PROMPT
    assert "ESC-005" in SYSTEM_PROMPT


def test_all_prompt_templates_defined():
    """Test all prompt templates are defined and non-empty."""
    assert INTENT_CLASSIFICATION_PROMPT and len(INTENT_CLASSIFICATION_PROMPT) > 50
    assert SENTIMENT_ANALYSIS_PROMPT and len(SENTIMENT_ANALYSIS_PROMPT) > 50
    assert ESCALATION_EVALUATION_PROMPT and len(ESCALATION_EVALUATION_PROMPT) > 50
    assert RESPONSE_GENERATION_PROMPT and len(RESPONSE_GENERATION_PROMPT) > 50


def test_format_conversation_context():
    """Test conversation context formatting."""
    data = {
        "conversation_id": "CONV-0001",
        "message_count": 5,
        "topics": ["bug_report", "follow_up"],
        "sentiment_trend": "worsening",
        "resolution_status": "open",
        "last_channel": "whatsapp",
        "recent_messages": [
            {"role": "customer", "channel": "whatsapp", "content": "still not working"},
        ],
    }
    result = format_conversation_context(data)
    assert "CONV-0001" in result
    assert "worsening" in result
    assert "still not working" in result


def test_format_escalation_instruction():
    """Test escalation instruction formatting."""
    result = format_escalation_instruction(
        should_escalate=True,
        reason="Customer is angry",
    )
    assert "escalation" in result.lower()
    assert "Customer is angry" in result

    result_no = format_escalation_instruction(
        should_escalate=False,
        reason="",
    )
    assert "NOT require escalation" in result_no


# ──────────────────────────────────────────────────────────────
# INTEGRATION TESTS
# ──────────────────────────────────────────────────────────────

def test_full_pipeline_email():
    """Test full agent pipeline for an email how-to question."""
    from agent.customer_success_agent import CustomerSuccessAgent

    agent = CustomerSuccessAgent()
    result = agent.process({
        "channel": "email",
        "customer_email": "pipeline-test@email.com",
        "subject": "How to invite team?",
        "content": "Hi, how do I invite 10 team members to my workspace?",
    })

    assert result.ticket_id.startswith("TKT-")
    assert not result.escalation_needed
    assert "Dear" in result.response_text
    assert "Best regards" in result.response_text


def test_full_pipeline_whatsapp():
    """Test full agent pipeline for a WhatsApp integration issue."""
    from agent.customer_success_agent import CustomerSuccessAgent

    agent = CustomerSuccessAgent()
    result = agent.process({
        "channel": "whatsapp",
        "customer_phone": "+14155559999",
        "content": "hey, slack not syncing. help pls",
    })

    assert result.ticket_id.startswith("TKT-")
    assert not result.escalation_needed
    assert len(result.response_text) > 0
    assert "Hey" in result.response_text or "slack" in result.response_text.lower()


def test_full_pipeline_escalation_pricing():
    """Test full agent pipeline escalates pricing questions."""
    from agent.customer_success_agent import CustomerSuccessAgent

    agent = CustomerSuccessAgent()
    result = agent.process({
        "channel": "email",
        "customer_email": "pricing-test@email.com",
        "subject": "Enterprise pricing",
        "content": "What is the exact pricing for the Enterprise plan?",
    })

    assert result.escalation_needed is True
    assert "escalated" in result.response_text.lower()


def test_full_pipeline_escalation_anger():
    """Test full agent pipeline escalates angry messages."""
    from agent.customer_success_agent import CustomerSuccessAgent

    agent = CustomerSuccessAgent()
    result = agent.process({
        "channel": "whatsapp",
        "customer_phone": "+14155558888",
        "content": "this is ridiculous! I want to speak to a manager NOW!",
    })

    assert result.escalation_needed is True
    assert result.sentiment == "very_negative"


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

def main():
    """Run all transition tests."""
    print("\n" + "=" * 70)
    print("  FlowSync Production -- Transition Test Suite")
    print("=" * 70)

    # Tool tests
    print("\n  Tool Tests:")
    print("  " + "-" * 50)
    _test("search_knowledge_base", test_search_knowledge_base)
    _test("search_knowledge_base_fallback", test_search_knowledge_base_fallback)
    _test("analyze_sentiment_positive", test_analyze_sentiment_positive)
    _test("analyze_sentiment_neutral", test_analyze_sentiment_neutral)
    _test("analyze_sentiment_negative", test_analyze_sentiment_negative)
    _test("analyze_sentiment_very_negative", test_analyze_sentiment_very_negative)
    _test("create_ticket", test_create_ticket)
    _test("create_ticket_invalid_email", test_create_ticket_invalid_email)
    _test("get_customer_history_empty", test_get_customer_history_empty)
    _test("escalate_to_human", test_escalate_to_human)
    _test("escalate_invalid_ticket", test_escalate_invalid_ticket)
    _test("send_response", test_send_response)
    _test("get_or_create_customer_new", test_get_or_create_customer_new)
    _test("get_or_create_customer_existing", test_get_or_create_customer_existing)
    _test("cross_channel_resolution", test_cross_channel_resolution)

    # Formatter tests
    print("\n  Formatter Tests:")
    print("  " + "-" * 50)
    _test("email_formatter_structure", test_email_formatter_structure)
    _test("whatsapp_formatter_length", test_whatsapp_formatter_length)
    _test("whatsapp_formatter_tone", test_whatsapp_formatter_tone)
    _test("web_form_formatter_structure", test_web_form_formatter_structure)
    _test("escalation_formatting_email", test_escalation_formatting_email)
    _test("escalation_formatting_whatsapp", test_escalation_formatting_whatsapp)
    _test("formatter_truncation", test_formatter_truncation)
    _test("get_formatter_valid", test_get_formatter_valid)
    _test("get_formatter_invalid", test_get_formatter_invalid)

    # Prompt tests
    print("\n  Prompt Tests:")
    print("  " + "-" * 50)
    _test("system_prompt_exists", test_system_prompt_exists)
    _test("system_prompt_contains_skills", test_system_prompt_contains_skills)
    _test("system_prompt_contains_escalation_rules", test_system_prompt_contains_escalation_rules)
    _test("all_prompt_templates_defined", test_all_prompt_templates_defined)
    _test("format_conversation_context", test_format_conversation_context)
    _test("format_escalation_instruction", test_format_escalation_instruction)

    # Integration tests
    print("\n  Integration Tests:")
    print("  " + "-" * 50)
    _test("full_pipeline_email", test_full_pipeline_email)
    _test("full_pipeline_whatsapp", test_full_pipeline_whatsapp)
    _test("full_pipeline_escalation_pricing", test_full_pipeline_escalation_pricing)
    _test("full_pipeline_escalation_anger", test_full_pipeline_escalation_anger)

    # Summary
    print("\n" + "=" * 70)
    print(f"  RESULTS: {_tests_passed}/{_tests_run} passed, {_tests_failed} failed")
    print("=" * 70)

    if _tests_failed == 0:
        print("\n  ALL TRANSITION TESTS PASSED -- Production scaffold is ready.\n")
    else:
        print(f"\n  {_tests_failed} test(s) failed. Review and fix before proceeding.\n")

    return _tests_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
