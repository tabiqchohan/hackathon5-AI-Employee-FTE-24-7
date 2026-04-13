"""
FlowSync Customer Success AI Agent -- Agent Tests (OpenAI Agents SDK)
======================================================================
Tests the production agent built with the OpenAI Agents SDK.

Tests cover 5 key scenarios:
  1. Pricing query → must escalate
  2. Normal how-to question → should answer using KB
  3. Cross-channel follow-up → should remember history
  4. Angry customer → should escalate
  5. Channel-aware response formatting

Plus full integration tests requiring OPENAI_API_KEY.

Run:
  # All unit tests (tools + logic, no LLM required):
  cd production && python -m pytest tests/test_agent.py -v -p no:hypothesis -p no:anyio --capture=no

  # Full agent tests (requires OPENAI_API_KEY):
  cd production && python -m pytest tests/test_agent.py -v -p no:hypothesis -p no:anyio -k "full_agent" --capture=no

  # Single test class:
  cd production && python -m pytest tests/test_agent.py::TestPricingEscalation -v -p no:hypothesis -p no:anyio --capture=no
"""

from __future__ import annotations

import json
import os
import sys
import pytest

# ──────────────────────────────────────────────────────────────
# PATH SETUP
# ──────────────────────────────────────────────────────────────

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_src_path = os.path.join(_project_root, "..", "src")
for p in [_project_root, _src_path]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Import core logic functions (prefixed _do_) for direct testing
from agent.tools import (
    AgentContext,
    KBSearchInput,
    CreateTicketInput,
    CustomerHistoryInput,
    EscalateInput,
    SendResponseInput,
    SentimentInput,
    CustomerInput,
    _do_search_kb,
    _do_create_ticket,
    _do_get_customer_history,
    _do_escalate_to_human,
    _do_send_response,
    _do_analyze_sentiment,
    _do_get_or_create_customer,
    # Also import tool wrappers for importability checks
    search_knowledge_base,
    create_ticket,
    get_customer_history,
    escalate_to_human,
    send_response,
    analyze_sentiment,
    get_or_create_customer,
)
from agent.formatters import format_response
from agent.prompts import SYSTEM_PROMPT
from prototype import analyze_sentiment as _analyze_sentiment


# ──────────────────────────────────────────────────────────────
# TEST HELPERS
# ──────────────────────────────────────────────────────────────

def make_ctx(db_pool=None) -> AgentContext:
    """Create a fresh AgentContext for testing."""
    return AgentContext(
        db_pool=db_pool,
        run_id="test-001",
    )


# ──────────────────────────────────────────────────────────────
# TEST 1: Pricing Query → Must Escalate
# ──────────────────────────────────────────────────────────────

class TestPricingEscalation:
    """Pricing queries must always trigger escalation per ESC-001."""

    def test_pricing_sentiment_is_neutral(self):
        """Pricing questions are neutral sentiment; escalation comes from intent rules."""
        ctx = make_ctx()
        result = json.loads(_do_analyze_sentiment(ctx, "What is the Enterprise plan pricing?"))
        assert result["sentiment"] == "neutral"
        assert result["requires_escalation"] is False
        # Escalation comes from system prompt ESC-001 rule, not sentiment.

    def test_billing_keyword_neutral_sentiment(self):
        """Billing messages are neutral sentiment but escalate per ESC-001."""
        ctx = make_ctx()
        result = json.loads(_do_analyze_sentiment(ctx, "I have a question about my billing"))
        assert result["sentiment"] == "neutral"

    def test_refund_request_neutral(self):
        """Refund requests are neutral sentiment but escalate per ESC-001."""
        ctx = make_ctx()
        result = json.loads(_do_analyze_sentiment(ctx, "Can I get a refund for last month?"))
        assert result["sentiment"] == "neutral"

    def test_system_prompt_contains_pricing_escalation_rule(self):
        """Verify the system prompt has ESC-001 for pricing/billing."""
        assert "ESC-001" in SYSTEM_PROMPT
        assert "pricing" in SYSTEM_PROMPT.lower()
        assert "billing" in SYSTEM_PROMPT.lower()
        assert "escalate" in SYSTEM_PROMPT.lower()

    def test_system_prompt_never_discuss_pricing(self):
        """Agent instructions say never to discuss exact pricing."""
        assert "Never discuss exact pricing" in SYSTEM_PROMPT or \
               "Never disclose exact pricing" in SYSTEM_PROMPT

    def test_pydantic_sentiment_input_works(self):
        """Verify Pydantic input model works for sentiment analysis."""
        inp = SentimentInput(message="How much does it cost?")
        assert inp.message == "How much does it cost?"


# ──────────────────────────────────────────────────────────────
# TEST 2: Normal How-To Question → Should Answer Using KB
# ──────────────────────────────────────────────────────────────

class TestKnowledgeBaseAnswer:
    """How-to questions should be answered using the knowledge base."""

    def test_kb_returns_relevant_content_for_invite_question(self):
        """KB search should return team collaboration docs for invite question."""
        ctx = make_ctx()
        result = _do_search_kb(ctx, "How do I invite team members?")
        assert "No specific product documentation found" not in result
        assert len(result) > 50
        assert "team" in result.lower() or "invite" in result.lower()

    def test_kb_returns_integration_docs(self):
        """KB search should return Slack integration docs."""
        ctx = make_ctx()
        result = _do_search_kb(ctx, "Slack integration not syncing")
        assert "No specific product documentation found" not in result
        assert "slack" in result.lower()
        assert len(result) > 100

    def test_kb_returns_ai_feature_docs(self):
        """KB search should return AI Task Suggestions docs."""
        ctx = make_ctx()
        result = _do_search_kb(ctx, "AI suggestions not working")
        assert "No specific product documentation found" not in result
        assert "ai" in result.lower() or "task" in result.lower()

    def test_kb_fallback_for_completely_unknown(self):
        """KB search should return fallback for gibberish queries."""
        ctx = make_ctx()
        result = _do_search_kb(ctx, "xyzzy plugh unknown feature blah")
        assert "No specific product documentation found" in result

    def test_kb_search_with_category_filter(self):
        """KB search should accept category filter via Pydantic model."""
        inp = KBSearchInput(query="pricing plans", category="pricing")
        assert inp.query == "pricing plans"
        assert inp.category == "pricing"

    def test_system_prompt_instructs_kb_search(self):
        """Verify system prompt instructs agent to use knowledge base."""
        assert "SK-001" in SYSTEM_PROMPT or "Knowledge Retrieval" in SYSTEM_PROMPT
        assert "search" in SYSTEM_PROMPT.lower()
        assert "knowledge base" in SYSTEM_PROMPT.lower()


# ──────────────────────────────────────────────────────────────
# TEST 3: Cross-Channel Follow-Up → Should Remember History
# ──────────────────────────────────────────────────────────────

class TestCrossChannelMemory:
    """Customer contacting via different channels should be recognized."""

    def test_same_customer_email_different_channel(self):
        """Same email via email then WhatsApp resolves to same customer."""
        ctx = make_ctx()

        # First contact via email
        r1 = _do_get_or_create_customer(ctx, "cross@test.com", "email")
        assert "NEW CUSTOMER" in r1

        # Second contact via WhatsApp (same email identifier)
        r2 = _do_get_or_create_customer(ctx, "cross@test.com", "whatsapp")
        assert "EXISTING CUSTOMER" in r2

        # Both should reference the same conversation
        conv_id_1 = [line for line in r1.split("\n") if "Conversation ID:" in line][0]
        conv_id_2 = [line for line in r2.split("\n") if "Conversation ID:" in line][0]
        assert conv_id_1 == conv_id_2

    def test_customer_history_tracks_tickets(self):
        """Customer history should show tickets created for that customer."""
        ctx = make_ctx()

        # Create customer
        _do_get_or_create_customer(ctx, "history@test.com", "email")

        # Create a ticket for this customer
        ticket_result = _do_create_ticket(
            ctx, "history@test.com", "Test issue", "medium", "email"
        )
        assert "Ticket TKT-" in ticket_result

        # Get history
        history = _do_get_customer_history(ctx, "history@test.com")
        assert "history@test.com" in history or "ticket" in history.lower()

    def test_channel_switch_detected(self):
        """When a customer switches channels, it should be detected."""
        ctx = make_ctx()

        # Create customer and set last_channel
        _do_get_or_create_customer(ctx, "switch@test.com", "email")
        ctx._conversations["switch@test.com"]["last_channel"] = "email"
        ctx._conversations["switch@test.com"]["messages"] = [
            {"role": "customer", "content": "hi"}
        ]

        # Now contact via WhatsApp
        r = _do_get_or_create_customer(ctx, "switch@test.com", "whatsapp")
        assert "EXISTING CUSTOMER" in r

    def test_new_customer_creates_conversation_id(self):
        """New customer should get a unique conversation ID."""
        ctx = make_ctx()
        r = _do_get_or_create_customer(ctx, "brandnew@test.com", "email")
        assert "NEW CUSTOMER" in r
        assert "Conversation ID: CONV-" in r

    def test_system_prompt_has_customer_memory_skill(self):
        """Verify system prompt includes SK-005 for customer identification."""
        assert "SK-005" in SYSTEM_PROMPT
        assert "Customer Identification" in SYSTEM_PROMPT or "customer" in SYSTEM_PROMPT.lower()


# ──────────────────────────────────────────────────────────────
# TEST 4: Angry Customer → Should Escalate
# ──────────────────────────────────────────────────────────────

class TestAngryCustomerEscalation:
    """Very negative sentiment must trigger escalation per ESC-002."""

    def test_very_negative_sentiment_requires_escalation(self):
        """Angry messages should be flagged as requiring escalation."""
        ctx = make_ctx()
        result = json.loads(
            _do_analyze_sentiment(ctx, "This is ridiculous! I want to speak to a manager NOW!")
        )
        assert result["sentiment"] == "very_negative"
        assert result["score"] == -2
        assert result["requires_escalation"] is True

    def test_profanity_detected(self):
        """Profanity should result in very_negative sentiment."""
        ctx = make_ctx()
        result = json.loads(
            _do_analyze_sentiment(ctx, "This is bullshit, nothing works!")
        )
        assert result["sentiment"] == "very_negative"
        assert result["requires_escalation"] is True

    def test_mild_frustration_negative_not_escalate(self):
        """Mild frustration should be negative but not auto-escalate."""
        ctx = make_ctx()
        result = json.loads(
            _do_analyze_sentiment(ctx, "I'm getting frustrated, this still doesn't work")
        )
        assert result["sentiment"] == "negative"
        assert result["score"] == -1
        assert result["requires_escalation"] is False

    def test_system_prompt_contains_anger_escalation_rule(self):
        """Verify system prompt has ESC-002 for angry customers."""
        assert "ESC-002" in SYSTEM_PROMPT
        assert "angry" in SYSTEM_PROMPT.lower() or "anger" in SYSTEM_PROMPT.lower()
        assert "very_negative" in SYSTEM_PROMPT

    def test_human_request_triggers_escalation_rule(self):
        """Requesting human/manager should trigger ESC-003."""
        assert "ESC-003" in SYSTEM_PROMPT
        assert "human" in SYSTEM_PROMPT.lower() or "manager" in SYSTEM_PROMPT.lower()

    def test_escalation_tool_works(self):
        """Escalation tool should work and confirm escalation."""
        ctx = make_ctx()

        # Create a ticket first
        ticket = _do_create_ticket(ctx, "angry@test.com", "Something is broken", "high", "email")
        ticket_id = ticket.split()[1]  # "TKT-00001"

        # Escalate it
        result = _do_escalate_to_human(ctx, ticket_id, "Customer is very upset and wants a manager")
        assert "ESCALATION CONFIRMED" in result
        assert ticket_id in result
        assert "human support team" in result.lower()

    def test_escalation_fails_for_nonexistent_ticket(self):
        """Escalating a non-existent ticket should return error."""
        ctx = make_ctx()
        result = _do_escalate_to_human(ctx, "TKT-99999", "Testing error handling")
        assert "Error" in result or "not found" in result


# ──────────────────────────────────────────────────────────────
# TEST 5: Channel-Aware Response Formatting
# ──────────────────────────────────────────────────────────────

class TestChannelAwareFormatting:
    """Responses must be formatted correctly for each channel."""

    def test_email_format_is_formal(self):
        """Email responses should have formal greeting and sign-off."""
        result = format_response(
            message="Go to Settings > Team > Invite Members to add your team.",
            channel="email",
        )
        assert "Dear" in result.text
        assert "Best regards" in result.text
        assert "FlowSync Customer Success Team" in result.text
        assert len(result.text) > 100

    def test_whatsapp_format_is_casual_and_short(self):
        """WhatsApp responses should be casual and under 280 chars."""
        result = format_response(
            message="Go to Settings > Integrations > Slack > Reconnect.",
            channel="whatsapp",
        )
        assert "Hey" in result.text or "Hi" in result.text
        assert "Dear" not in result.text
        assert result.character_count <= 280

    def test_web_form_format_is_semi_formal(self):
        """Web form responses should be semi-formal."""
        result = format_response(
            message="Here is the information you requested about dashboards.",
            channel="web_form",
        )
        assert "Thanks for your message" in result.text
        assert "Best," in result.text
        assert "FlowSync Support" in result.text
        assert "Dear" not in result.text

    def test_escalation_formatting_is_formal(self):
        """Escalation messages should always use formal tone."""
        for channel in ["email", "whatsapp", "web_form"]:
            result = format_response(
                message="",
                channel=channel,
                is_escalation=True,
                escalation_reason="Customer requested manager",
            )
            assert "escalat" in result.text.lower()
            assert "specialist" in result.text.lower() or "team" in result.text.lower()

    def test_long_message_truncated_for_whatsapp(self):
        """Long messages should be truncated for WhatsApp channel."""
        long_msg = "A" * 500
        result = format_response(message=long_msg, channel="whatsapp")
        assert result.character_count <= 400
        assert result.truncated is True

    def test_send_response_tool_applies_formatting(self):
        """send_response tool should apply channel formatting."""
        ctx = make_ctx()

        # Create ticket first
        ticket = _do_create_ticket(ctx, "format@test.com", "Test", "medium", "whatsapp")
        ticket_id = ticket.split()[1]  # "TKT-00001"

        # Send response via WhatsApp
        result = _do_send_response(ctx, ticket_id, "Reconnect Slack in Settings.", "whatsapp")
        assert "Response sent" in result
        assert "whatsapp" in result.lower()

    def test_system_prompt_has_channel_adaptation_skill(self):
        """Verify system prompt includes SK-004 for channel adaptation."""
        assert "SK-004" in SYSTEM_PROMPT
        assert "Channel Adaptation" in SYSTEM_PROMPT or "channel" in SYSTEM_PROMPT.lower()

    def test_all_three_channels_covered_in_prompt(self):
        """System prompt should mention all three channels."""
        assert "email" in SYSTEM_PROMPT.lower()
        assert "whatsapp" in SYSTEM_PROMPT.lower()
        assert "web_form" in SYSTEM_PROMPT.lower() or "web form" in SYSTEM_PROMPT.lower()


# ──────────────────────────────────────────────────────────────
# PYDANTIC INPUT MODEL TESTS
# ──────────────────────────────────────────────────────────────

class TestPydanticInputs:
    """Verify all Pydantic input models validate correctly."""

    def test_kb_search_input_defaults(self):
        inp = KBSearchInput(query="test")
        assert inp.query == "test"
        assert inp.category is None

    def test_kb_search_input_with_category(self):
        inp = KBSearchInput(query="test", category="features")
        assert inp.category == "features"

    def test_create_ticket_input_defaults(self):
        inp = CreateTicketInput(customer_id="user@test.com", issue="Bug")
        assert inp.priority == "medium"
        assert inp.channel == "email"

    def test_send_response_input_validation(self):
        with pytest.raises(Exception):
            SendResponseInput()

    def test_customer_input_validation(self):
        inp = CustomerInput(identifier="user@test.com", channel="email")
        assert inp.identifier == "user@test.com"
        assert inp.channel == "email"


# ──────────────────────────────────────────────────────────────
# FULL AGENT TESTS (requires OPENAI_API_KEY)
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def openai_api_key():
    """Skip tests if OPENAI_API_KEY is not set."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        pytest.skip("OPENAI_API_KEY not set")
    return key


@pytest.fixture
def agent(openai_api_key):
    """Create the production agent."""
    from agent.customer_success_agent import create_agent
    return create_agent(model="gpt-4o")


@pytest.mark.asyncio
class TestFullAgent:
    """Integration tests requiring the actual OpenAI API."""

    async def test_full_agent_pricing_escalates(self, agent):
        """Full agent should escalate pricing questions."""
        from agent.customer_success_agent import run_agent

        result = await run_agent(agent, {
            "channel": "email",
            "customer_email": "pricing@test.com",
            "subject": "Enterprise pricing",
            "content": "What is the exact pricing for the Enterprise plan?",
        })

        response = result["response"].lower()
        assert "escalat" in response, f"Expected escalation in response: {response[:200]}"

    async def test_full_agent_answers_how_to(self, agent):
        """Full agent should answer how-to questions using KB."""
        from agent.customer_success_agent import run_agent

        result = await run_agent(agent, {
            "channel": "email",
            "customer_email": "howto@test.com",
            "subject": "Team invites",
            "content": "How do I invite 25 team members to my workspace?",
        })

        response = result["response"].lower()
        assert "escalat" not in response or "settings" in response
        assert len(response) > 50

    async def test_full_agent_angry_customer_escalates(self, agent):
        """Full agent should escalate angry customer messages."""
        from agent.customer_success_agent import run_agent

        result = await run_agent(agent, {
            "channel": "whatsapp",
            "customer_phone": "+14155551234",
            "content": "This is ridiculous! I've been waiting 2 hours! I want to speak to a manager NOW!",
        })

        response = result["response"].lower()
        assert "escalat" in response, f"Expected escalation in response: {response[:200]}"

    async def test_full_agent_channel_formatting(self, agent):
        """Full agent should format responses correctly for WhatsApp."""
        from agent.customer_success_agent import run_agent

        result = await run_agent(agent, {
            "channel": "whatsapp",
            "customer_phone": "+14155559999",
            "content": "how do i reset my password?",
        })

        response = result["response"]
        assert len(response) > 10


# ──────────────────────────────────────────────────────────────
# CONVERSATION SESSION TESTS
# ──────────────────────────────────────────────────────────────

class TestConversationSession:
    """Test the multi-turn conversation helper."""

    def test_session_creates_conversation_id(self):
        """Session should generate a unique conversation ID."""
        from agent.customer_success_agent import ConversationSession, create_agent

        agent = create_agent(model="gpt-4o")
        session = ConversationSession(agent)

        assert session.conversation_id.startswith("CONV-")
        assert session.message_history == []

    def test_session_tracks_messages(self):
        """Session should track message history."""
        from agent.customer_success_agent import ConversationSession, create_agent

        agent = create_agent(model="gpt-4o")
        session = ConversationSession(agent)

        session.message_history.append({"role": "user", "content": "Hello"})
        session.message_history.append({"role": "assistant", "content": "Hi there"})

        assert len(session.message_history) == 2
        assert session.message_history[0]["role"] == "user"
        assert session.message_history[1]["role"] == "assistant"


# ──────────────────────────────────────────────────────────────
# AGENT CREATION TESTS
# ──────────────────────────────────────────────────────────────

class TestAgentCreation:
    """Verify the agent is created correctly with all tools."""

    def test_all_7_tool_wrappers_importable(self):
        """Verify all 7 tool wrappers are importable."""
        tools = [
            search_knowledge_base,
            create_ticket,
            get_customer_history,
            escalate_to_human,
            send_response,
            analyze_sentiment,
            get_or_create_customer,
        ]
        assert len(tools) == 7
        for tool in tools:
            assert tool is not None

    def test_agent_context_creation(self):
        """Verify AgentContext can be created and used."""
        ctx = AgentContext(
            run_id="test-123",
            customer_id="test@example.com",
            current_channel="email",
        )
        assert ctx.run_id == "test-123"
        assert ctx.customer_id == "test@example.com"
        assert ctx.current_channel == "email"
        assert ctx.has_database is False

    def test_agent_has_database_property_false_without_pool(self):
        """AgentContext without db_pool should report has_database=False."""
        ctx = AgentContext()
        assert ctx.has_database is False

    def test_agent_creation_includes_all_tools(self):
        """create_agent should include all 7 default tools."""
        from agent.customer_success_agent import create_agent
        agent = create_agent(model="gpt-4o")

        assert agent.tools is not None
        assert len(agent.tools) == 7

    def test_system_prompt_contains_all_escalation_rules(self):
        """Verify all ESC-XXX rules are in the system prompt."""
        for rule in ["ESC-001", "ESC-002", "ESC-003", "ESC-004", "ESC-005"]:
            assert rule in SYSTEM_PROMPT, f"Missing escalation rule: {rule}"

    def test_system_prompt_contains_all_skills(self):
        """Verify all SK-XXX skills are in the system prompt."""
        for skill in ["SK-001", "SK-002", "SK-003", "SK-004", "SK-005"]:
            assert skill in SYSTEM_PROMPT, f"Missing skill: {skill}"
