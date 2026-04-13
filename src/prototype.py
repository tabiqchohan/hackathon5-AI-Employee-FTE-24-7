"""
FlowSync Customer Success AI Agent -- Prototype v2.0 (Exercise 1.3 + 1.5)
==========================================================================
Adds conversation memory, state management, multi-turn context awareness,
sentiment trend tracking, cross-channel conversation resolution, and
a formal system prompt incorporating all 5 agent skills.

Agent Skills (see specs/agent-skills.md):
  SK-001: Knowledge Retrieval
  SK-002: Sentiment Analysis & Trend
  SK-003: Escalation Decision
  SK-004: Channel Adaptation
  SK-005: Customer Identification & Memory

Run: python src/prototype.py
"""

import sys
import json
import io
from datetime import datetime
from typing import Optional

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ──────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are FlowSync's Customer Success AI Agent -- a 24/7 digital employee
that handles customer support across email, WhatsApp, and web forms.

COMPANY: TechCorp
PRODUCT: FlowSync -- AI-powered project management and team collaboration
CUSTOMERS: 8,500+ teams including product managers, engineering teams,
           marketing agencies, and remote-first companies.

BRAND VOICE:
  - Email: Formal, professional, empathetic, detailed
  - WhatsApp: Casual, friendly, concise (max ~280 chars)
  - Web Form: Semi-formal, clear, solution-focused

YOUR SKILLS (execute in order for every message):

  SK-005: Customer Identification & Memory
    - Resolve customer identity from email or phone
    - Retrieve conversation history (last 5 messages)
    - Track topics, sentiment trend, resolution status
    - Detect channel switches

  SK-002: Sentiment Analysis & Trend
    - Analyze emotional tone of every message
    - Track sentiment direction: improving / worsening / stable
    - Scores: +2 (positive), 0 (neutral), -1 (negative), -2 (very_negative)
    - Flag very_negative for potential escalation

  SK-001: Knowledge Retrieval
    - Search product documentation for the customer's query
    - Return relevant setup guides, troubleshooting steps, feature info
    - Never invent features or information not in the knowledge base
    - Never disclose exact pricing -- redirect to sales team

  SK-003: Escalation Decision (CRITICAL -- when in doubt, escalate)
    Escalate IMMEDIATELY if ANY of these apply:
      - Customer asks about pricing, billing, refunds, contracts
      - Customer is angry or uses profanity (very_negative sentiment)
      - Customer explicitly requests human/manager/real person
      - Issue involves legal, security, or data loss
      - Sentiment trend is worsening across multiple messages
      - Cannot resolve after 2 knowledge base searches
    When escalating: be polite, explain you're connecting them to a specialist,
    and give an expected response time.

  SK-004: Channel Adaptation
    - Format every response according to the customer's channel
    - Email: formal greeting, detailed answer, professional sign-off
    - WhatsApp: casual greeting, concise answer, friendly sign-off
    - Web Form: semi-formal, clear, balanced length

ESCALATION RULES (non-negotiable):
  ESC-001: Pricing / Billing / Refunds / Contracts -> escalate
  ESC-002: Angry customer (very_negative sentiment) -> escalate
  ESC-003: Customer requests human/manager -> escalate
  ESC-004: Security / Legal / Data Loss -> escalate
  ESC-005: Worsening sentiment trend -> escalate

PRICING: FlowSync has Starter, Pro, and Enterprise tiers.
  Never discuss exact pricing. If asked, escalate to human.

RESPONSE PRINCIPLES:
  1. Be helpful and solution-focused
  2. Acknowledge the customer's situation empathetically
  3. Provide actionable steps or clear explanations
  4. Reference prior conversation when relevant
  5. Never argue with or dismiss customer concerns
  6. When you don't know the answer, say so and escalate
"""

from knowledge_base import search_kb, KNOWLEDGE_BASE
from memory import (
    ConversationStore,
    Conversation,
    Message,
    build_context_for_agent,
)


# ──────────────────────────────────────────────────────────────
# DATA MODELS
# ──────────────────────────────────────────────────────────────

class Ticket:
    """Normalized ticket from any channel."""

    def __init__(
        self,
        channel: str,
        content: str,
        customer_email: Optional[str] = None,
        customer_phone: Optional[str] = None,
        subject: Optional[str] = None,
        timestamp: Optional[str] = None,
    ):
        self.channel = channel.lower().strip()
        self.content = content.strip()
        self.customer_email = customer_email
        self.customer_phone = customer_phone
        self.subject = subject
        self.timestamp = timestamp or datetime.now().isoformat()
        self.ticket_id = f"TKT-{self.timestamp[:19].replace('-', '').replace(':', '').replace('T', '-')}"

    def __repr__(self):
        return f"Ticket({self.ticket_id}, {self.channel}, {self.customer_email or self.customer_phone})"


class AgentResponse:
    """Response generated by the AI agent."""

    def __init__(
        self,
        ticket: Ticket,
        response_text: str,
        escalation_needed: bool,
        escalation_reason: str,
        intent: str,
        sentiment: str,
        kb_searches_used: int,
        reasoning: str,
        conversation: Optional[Conversation] = None,
    ):
        self.ticket = ticket
        self.response_text = response_text
        self.escalation_needed = escalation_needed
        self.escalation_reason = escalation_reason
        self.intent = intent
        self.sentiment = sentiment
        self.kb_searches_used = kb_searches_used
        self.reasoning = reasoning
        self.conversation = conversation

    def display(self):
        """Pretty-print the full agent decision + response."""
        sep = "=" * 70
        dash = "-" * 70
        print("\n" + sep)
        print(f"  AGENT RESPONSE -- {self.ticket.ticket_id}")
        print(sep)
        print(f"  Channel:     {self.ticket.channel}")
        print(f"  Customer:    {self.ticket.customer_email or self.ticket.customer_phone}")
        print(f"  Intent:      {self.intent}")
        print(f"  Sentiment:   {self.sentiment}")
        print(f"  KB Searches: {self.kb_searches_used}")
        esc = "YES -- " + self.escalation_reason if self.escalation_needed else "No"
        print(f"  Escalation:  {esc}")

        # Memory info
        if self.conversation:
            conv = self.conversation
            print(f"  Conversation: {conv.conversation_id}")
            print(f"  Msg Count:   {conv.message_count}")
            print(f"  Topics:      {', '.join(conv.topics) if conv.topics else 'None'}")
            print(f"  Sent Trend:   {conv.sentiment_trend.direction} ({conv.sentiment_trend.summary})")
            print(f"  Status:      {conv.resolution_status}")

        print(dash)
        print(f"  REASONING:\n  {self.reasoning}")
        print(dash)
        print(f"  RESPONSE TO CUSTOMER:")
        print(f"  {'-' * 40}")
        for line in self.response_text.split("\n"):
            print(f"  {line}")
        print(sep)
        print()


# ──────────────────────────────────────────────────────────────
# INTENT CLASSIFIER
# ──────────────────────────────────────────────────────────────

INTENT_CATEGORIES = {
    "how_to": "How-To / Guidance",
    "bug_report": "Bug Report",
    "feature_issue": "Feature Issue / Not Working",
    "pricing_billing": "Pricing / Billing",
    "account_management": "Account Management",
    "integration_issue": "Integration Issue",
    "security_legal": "Security / Legal",
    "general": "General Inquiry",
    "follow_up": "Follow-Up",
}


def classify_intent(content: str, subject: str = "", conversation: Optional[Conversation] = None) -> str:
    """Classify the intent of a customer message using keyword matching."""
    text = (content + " " + subject).lower()

    # Detect follow-ups (short messages referencing prior context)
    followup_indicators = [
        "still", "any update", "follow up", "following up", "what about",
        "and then", "also", "another thing", "one more", "regarding",
        "about that", "you said", "earlier you", "so what",
        "did that work", "tried that", "didn't work", "didn't help",
        "still not", "still nothing", "still broken",
    ]
    if conversation and conversation.message_count > 0:
        if any(indicator in text for indicator in followup_indicators):
            return "follow_up"

    # Pricing / Billing (highest priority -- triggers escalation)
    pricing_keywords = [
        "pricing", "price", "cost", "how much", "billing", "bill", "charge",
        "refund", "invoice", "payment", "contract", "subscription cost",
        "enterprise pricing", "plan cost", "how much does", "upgrade price",
        "downgrade price", "money", "dollar", "pay",
    ]
    if any(kw in text for kw in pricing_keywords):
        return "pricing_billing"

    # Security / Legal (highest priority -- triggers escalation)
    security_keywords = [
        "data breach", "hack", "stolen data", "gdpr", "compliance", "legal",
        "lawsuit", "security issue", "vulnerability", "password stolen",
        "unauthorized access", "data loss", "lost data", "deleted data",
        "privacy", "regulation",
    ]
    if any(kw in text for kw in security_keywords):
        return "security_legal"

    # Integration issues
    integration_keywords = [
        "slack", "google drive", "github", "figma", "zoom", "integration",
        "sync", "connect", "not linking", "not connecting", "webhook",
        "api not working", "third party",
    ]
    if any(kw in text for kw in integration_keywords):
        return "integration_issue"

    # Bug reports
    bug_keywords = [
        "not working", "broken", "error", "crash", "bug", "issue", "problem",
        "not loading", "stuck", "frozen", "failed", "doesn't work", "doesnt work",
        "not showing", "missing", "wrong", "incorrect",
    ]
    if any(kw in text for kw in bug_keywords):
        return "bug_report"

    # Feature issues (similar to bugs but more about underperformance)
    feature_keywords = [
        "not giving", "not suggesting", "not recommending", "not helpful",
        "not accurate", "poor quality", "slow", "delayed",
    ]
    if any(kw in text for kw in feature_keywords):
        return "feature_issue"

    # Account management
    account_keywords = [
        "cancel", "downgrade", "upgrade", "delete account", "close account",
        "change plan", "switch plan", "unsubscribe",
    ]
    if any(kw in text for kw in account_keywords):
        return "account_management"

    # How-to questions
    howto_keywords = [
        "how do", "how to", "how can", "how do i", "how can i",
        "steps to", "guide me", "walk me through", "tell me how",
        "what is", "what are", "explain", "help me",
        "invite", "add member", "set up", "setup", "configure",
    ]
    if any(kw in text for kw in howto_keywords):
        return "how_to"

    return "general"


# ──────────────────────────────────────────────────────────────
# SENTIMENT ANALYZER
# ──────────────────────────────────────────────────────────────

def analyze_sentiment(content: str) -> str:
    """Analyze customer sentiment to detect frustration/anger."""
    text = content.lower()

    # Strong negative indicators
    anger_indicators = [
        "angry", "furious", "ridiculous", "unacceptable", "terrible",
        "worst", "horrible", "useless", "waste", "scam", "fraud",
        "damn", "hell", "crap", "sucks", "bullshit", "wtf",
        "are you kidding", "are you serious", "this is insane",
        "i want to speak", "i want to talk", "get me a",
        "this is garbage", "trash", "pathetic",
    ]

    # Moderate frustration
    frustration_indicators = [
        "frustrated", "frustrating", "annoyed", "disappointed", "not happy",
        "still not working", "still broken", "again", "already tried",
        "this is the", "time", "waiting", "waited", "no response",
        "nobody helped", "no one helped", "useless support",
        "getting frustrated", "so frustrating",
    ]

    if any(indicator in text for indicator in anger_indicators):
        return "very_negative"

    if any(indicator in text for indicator in frustration_indicators):
        return "negative"

    # Check for profanity (word-boundary matching to avoid false positives like "ass" in "password")
    profanity = ["fuck", "shit", "damn", "ass", "bitch", "crap", "bastard"]
    words_in_text = set(text.split())
    if any(word in words_in_text for word in profanity):
        return "very_negative"

    # Positive indicators
    positive_indicators = [
        "thanks", "thank you", "great", "awesome", "love", "helpful",
        "appreciate", "perfect", "wonderful", "excellent",
    ]
    if any(indicator in text for indicator in positive_indicators):
        return "positive"

    return "neutral"


# ──────────────────────────────────────────────────────────────
# ESCALATION ENGINE
# ──────────────────────────────────────────────────────────────

ESCALATION_RULES = [
    {
        "id": "ESC-001",
        "name": "Pricing / Billing / Refunds / Contracts",
        "trigger_intents": ["pricing_billing", "account_management"],
        "reason": "Pricing, billing, or contract questions require human sales/support team.",
    },
    {
        "id": "ESC-002",
        "name": "Angry Customer",
        "trigger_sentiments": ["very_negative"],
        "reason": "Customer shows signs of significant frustration or anger.",
    },
    {
        "id": "ESC-003",
        "name": "Human Request",
        "trigger_keywords": [
            "human", "real person", "manager", "agent", "somebody",
            "someone", "speak to", "talk to", "live person",
            "customer service", "representative",
        ],
        "reason": "Customer explicitly requested human assistance.",
    },
    {
        "id": "ESC-004",
        "name": "Security / Legal / Data Loss",
        "trigger_intents": ["security_legal"],
        "reason": "Security, legal, or data loss issues require immediate human escalation.",
    },
    {
        "id": "ESC-005",
        "name": "Worsening Sentiment Trend",
        "trigger_condition": "sentiment_worsening",
        "reason": "Customer sentiment is worsening across multiple interactions.",
    },
]


def check_escalation(
    content: str,
    subject: str,
    intent: str,
    sentiment: str,
    kb_searches_used: int,
    conversation: Optional[Conversation] = None,
) -> tuple[bool, str]:
    """
    Check if this ticket requires escalation.
    Returns (escalation_needed, reason).
    """
    text = (content + " " + subject).lower()

    for rule in ESCALATION_RULES:
        # Check intent-based triggers
        if "trigger_intents" in rule and intent in rule["trigger_intents"]:
            return True, rule["reason"]

        # Check sentiment-based triggers
        if "trigger_sentiments" in rule and sentiment in rule["trigger_sentiments"]:
            return True, rule["reason"]

        # Check keyword-based triggers
        if "trigger_keywords" in rule:
            if any(kw in text for kw in rule["trigger_keywords"]):
                return True, rule["reason"]

        # Check conversation-level conditions
        if "trigger_condition" in rule:
            if rule["trigger_condition"] == "sentiment_worsening":
                if conversation and conversation.sentiment_trend.direction == "worsening":
                    return True, rule["reason"]

    # Check if KB search failed multiple times
    if kb_searches_used >= 2:
        return True, "Could not resolve after 2 knowledge base searches."

    return False, ""


# ──────────────────────────────────────────────────────────────
# RESPONSE GENERATOR (Memory-Aware)
# ──────────────────────────────────────────────────────────────

def generate_response(
    ticket: Ticket,
    intent: str,
    sentiment: str,
    kb_result: str,
    escalation_needed: bool,
    escalation_reason: str,
    conversation: Optional[Conversation] = None,
) -> str:
    """Generate a channel-appropriate response with conversation context."""

    channel = ticket.channel
    content = ticket.content

    # Build context prefix from conversation history
    context_prefix = ""
    if conversation and conversation.message_count > 0:
        context_prefix = _build_context_prefix(conversation, ticket)

    # Escalation response
    if escalation_needed:
        base = _format_escalation_response(channel, escalation_reason)
        return context_prefix + base if context_prefix else base

    # Normal response based on intent
    if intent == "how_to":
        base = _format_howto_response(channel, kb_result)
    elif intent == "follow_up":
        base = _format_followup_response(channel, kb_result, conversation)
    elif intent in ("bug_report", "feature_issue"):
        base = _format_bug_response(channel, kb_result, content)
    elif intent == "integration_issue":
        base = _format_integration_response(channel, kb_result, content)
    elif intent == "general":
        base = _format_general_response(channel, kb_result, content)
    else:
        base = _format_general_response(channel, kb_result, content)

    return context_prefix + base if context_prefix else base


def _build_context_prefix(conversation: Conversation, ticket: Ticket) -> str:
    """
    Build a context-aware opening line that references previous conversation.
    Only used for email and web_form (WhatsApp stays concise).
    """
    channel = ticket.channel
    recent = conversation.get_recent_messages(3)

    # Find last customer message topic
    last_customer_topics = []
    for msg in recent:
        if msg.role == "customer" and msg.intent:
            last_customer_topics.append(msg.intent)

    # Channel switch notice
    channel_notice = conversation.get_channel_switch_notice(channel)

    if channel == "whatsapp":
        # Keep WhatsApp responses short -- only add context if topic changed
        if "integration_issue" in last_customer_topics and ticket.channel != conversation.last_channel_used:
            return "Following up on your Slack issue -- "
        return ""

    # Email and web_form can have richer context
    context_parts = []

    if channel_notice:
        context_parts.append("I see you're reaching out from a different channel now. ")

    if last_customer_topics:
        topic_map = {
            "integration_issue": "Slack integration",
            "bug_report": "the issue you reported",
            "feature_issue": "the feature concern",
            "how_to": "your earlier question",
            "pricing_billing": "your pricing question",
            "general": "your previous message",
        }
        last_topic = last_customer_topics[-1]
        topic_ref = topic_map.get(last_topic, "your previous message")
        context_parts.append(f"Following up on {topic_ref}, ")

    if conversation.sentiment_trend.direction == "worsening":
        context_parts.append("I want to make sure we get this resolved for you. ")

    if not context_parts:
        context_parts.append("Thank you for following up. ")

    return "".join(context_parts)


def _format_escalation_response(channel: str, reason: str) -> str:
    """Format an escalation handoff message."""
    if channel == "whatsapp":
        return (
            f"I understand your concern, and I want to make sure you get the best help possible. "
            f"I'm escalating this to our specialist team who can assist you directly. "
            f"You'll hear from them shortly. Thanks for your patience!"
        )
    elif channel == "email":
        return (
            f"Dear Valued Customer,\n\n"
            f"Thank you for reaching out to us. I understand the importance of your inquiry, "
            f"and I want to ensure you receive the most accurate and comprehensive assistance.\n\n"
            f"Your case has been escalated to our specialist team who are best equipped to "
            f"address your specific needs. They will review your case and respond within "
            f"the next 4 business hours.\n\n"
            f"Reason for escalation: {reason}\n\n"
            f"We appreciate your patience and value your relationship with FlowSync.\n\n"
            f"Best regards,\n"
            f"FlowSync Customer Success Team"
        )
    else:  # web_form
        return (
            f"Thank you for your message. Based on your inquiry, I'm escalating this to "
            f"our specialist team who can provide you with the most accurate assistance.\n\n"
            f"Reason: {reason}\n\n"
            f"A team member will follow up with you within 4 business hours. "
            f"We appreciate your patience.\n\n"
            f"Best regards,\n"
            f"FlowSync Support"
        )


def _format_howto_response(channel: str, kb_result: str) -> str:
    """Format a how-to guidance response."""
    if channel == "whatsapp":
        lines = [l for l in kb_result.split("\n") if l.strip() and not l.startswith("###")]
        short_text = " ".join(lines[:3])
        if len(short_text) > 280:
            short_text = short_text[:277] + "..."
        return (
            f"Hey! Here's what you need to do:\n\n"
            f"{short_text}\n\n"
            f"Let me know if you need more help!"
        )
    elif channel == "email":
        return (
            f"Dear Valued Customer,\n\n"
            f"Thank you for your question! I'd be happy to help you with that.\n\n"
            f"Here's a step-by-step guide:\n\n"
            f"{kb_result}\n"
            f"If you need any further assistance or have additional questions, "
            f"please don't hesitate to reach out. We're here to help!\n\n"
            f"Best regards,\n"
            f"FlowSync Customer Success Team"
        )
    else:  # web_form
        return (
            f"Thanks for reaching out! Here's how you can do that:\n\n"
            f"{kb_result}\n"
            f"If you need anything else, feel free to ask. Happy to help!\n\n"
            f"Best,\n"
            f"FlowSync Support"
        )


def _format_bug_response(channel: str, kb_result: str, customer_content: str) -> str:
    """Format a bug report / troubleshooting response."""
    if channel == "whatsapp":
        lines = [l for l in kb_result.split("\n") if l.strip() and l.startswith("-")]
        steps = "\n".join(lines[:3]) if lines else "Let me look into this for you."
        return (
            f"Sorry about that! Let's get this fixed. Try these steps:\n\n"
            f"{steps}\n\n"
            f"Still not working? I'll escalate this for you."
        )
    elif channel == "email":
        return (
            f"Dear Valued Customer,\n\n"
            f"Thank you for reporting this issue. I understand how frustrating this can be, "
            f"and I'm here to help resolve it as quickly as possible.\n\n"
            f"Based on your description, here are some troubleshooting steps to try:\n\n"
            f"{kb_result}\n"
            f"Please try these steps and let me know the results. If the issue persists, "
            f"I'll escalate this to our engineering team right away.\n\n"
            f"Best regards,\n"
            f"FlowSync Customer Success Team"
        )
    else:  # web_form
        return (
            f"Thanks for letting us know about this issue. I'm sorry for the inconvenience!\n\n"
            f"Here are some troubleshooting steps that should help:\n\n"
            f"{kb_result}\n"
            f"Please try these and let me know if the issue is resolved. "
            f"If not, I'll escalate this to our team.\n\n"
            f"Best,\n"
            f"FlowSync Support"
        )


def _format_integration_response(channel: str, kb_result: str, customer_content: str) -> str:
    """Format an integration-specific response."""
    if channel == "whatsapp":
        lines = [l for l in kb_result.split("\n") if l.strip() and not l.startswith("###")]
        short_text = " ".join(lines[:3])
        if len(short_text) > 280:
            short_text = short_text[:277] + "..."
        return (
            f"Got it! Here's what to check:\n\n"
            f"{short_text}\n\n"
            f"Still stuck? Let me know and I'll get more help!"
        )
    elif channel == "email":
        return (
            f"Dear Valued Customer,\n\n"
            f"Thank you for reaching out about your integration issue. I understand how "
            f"important seamless connectivity is for your workflow.\n\n"
            f"Here's what I found that should help:\n\n"
            f"{kb_result}\n"
            f"If these steps don't resolve the issue, please let me know and I'll escalate "
            f"this to our integrations specialist team.\n\n"
            f"Best regards,\n"
            f"FlowSync Customer Success Team"
        )
    else:  # web_form
        return (
            f"Thanks for reporting this integration issue. Let me help you get this sorted:\n\n"
            f"{kb_result}\n"
            f"If the issue persists after trying these steps, I'll escalate this to "
            f"our integrations team.\n\n"
            f"Best,\n"
            f"FlowSync Support"
        )


def _format_followup_response(channel: str, kb_result: str, conversation: Optional[Conversation]) -> str:
    """Format a follow-up response that acknowledges prior context."""
    if channel == "whatsapp":
        return (
            f"Thanks for following up! Based on our earlier conversation, "
            f"here's what I can add:\n\n"
            f"{kb_result[:200]}\n\n"
            f"Anything else I can help with?"
        )
    elif channel == "email":
        return (
            f"Dear Valued Customer,\n\n"
            f"Thank you for following up. I've reviewed our previous conversation "
            f"and I'm happy to provide additional assistance.\n\n"
            f"Here's some additional information:\n\n"
            f"{kb_result}\n"
            f"Please let me know if there's anything else I can help with.\n\n"
            f"Best regards,\n"
            f"FlowSync Customer Success Team"
        )
    else:  # web_form
        return (
            f"Thanks for following up! I've reviewed our conversation history "
            f"and here's what I can add:\n\n"
            f"{kb_result}\n"
            f"Let me know if you need anything else!\n\n"
            f"Best,\n"
            f"FlowSync Support"
        )


def _format_general_response(channel: str, kb_result: str, customer_content: str) -> str:
    """Format a general inquiry response."""
    if channel == "whatsapp":
        lines = [l for l in kb_result.split("\n") if l.strip() and not l.startswith("###")]
        short_text = " ".join(lines[:3])
        if len(short_text) > 280:
            short_text = short_text[:277] + "..."
        return (
            f"Here's what I found:\n\n"
            f"{short_text}\n\n"
            f"Need more details? Just ask!"
        )
    elif channel == "email":
        return (
            f"Dear Valued Customer,\n\n"
            f"Thank you for contacting FlowSync support. I'd be happy to help with your inquiry.\n\n"
            f"Here's the information you requested:\n\n"
            f"{kb_result}\n"
            f"If you have any further questions, please don't hesitate to ask.\n\n"
            f"Best regards,\n"
            f"FlowSync Customer Success Team"
        )
    else:  # web_form
        return (
            f"Thanks for your message! Here's what I found:\n\n"
            f"{kb_result}\n"
            f"Let me know if you need anything else!\n\n"
            f"Best,\n"
            f"FlowSync Support"
        )


# ──────────────────────────────────────────────────────────────
# CORE AGENT LOOP (Memory-Aware)
# ──────────────────────────────────────────────────────────────

# Global conversation store
store = ConversationStore()


def process_ticket(raw_input: dict) -> AgentResponse:
    """
    Main agent function: takes raw customer message, processes it through
    the full pipeline with memory, and returns an AgentResponse.

    Args:
        raw_input: dict with keys:
            - channel: "email", "whatsapp", "web_form"
            - content: the message text
            - customer_email: (optional)
            - customer_phone: (optional)
            - subject: (optional)

    Returns:
        AgentResponse object
    """
    # Step 1: Normalize
    ticket = Ticket(
        channel=raw_input["channel"],
        content=raw_input["content"],
        customer_email=raw_input.get("customer_email"),
        customer_phone=raw_input.get("customer_phone"),
        subject=raw_input.get("subject", ""),
    )

    # Step 2: Get or create conversation
    conversation = store.get_or_create(
        email=ticket.customer_email,
        phone=ticket.customer_phone,
    )

    # Step 3: Classify intent (with conversation context)
    intent = classify_intent(ticket.content, ticket.subject or "", conversation)

    # Step 4: Analyze sentiment
    sentiment = analyze_sentiment(ticket.content)

    # Step 5: Search knowledge base
    kb_result = search_kb(ticket.content)
    kb_searches_used = 1

    # Step 6: Check escalation (with conversation context)
    escalation_needed, escalation_reason = check_escalation(
        content=ticket.content,
        subject=ticket.subject or "",
        intent=intent,
        sentiment=sentiment,
        kb_searches_used=kb_searches_used,
        conversation=conversation,
    )

    # Step 7: Generate response (with conversation context)
    response_text = generate_response(
        ticket=ticket,
        intent=intent,
        sentiment=sentiment,
        kb_result=kb_result,
        escalation_needed=escalation_needed,
        escalation_reason=escalation_reason,
        conversation=conversation,
    )

    # Step 8: Record messages in conversation
    customer_msg = Message(
        role="customer",
        content=ticket.content,
        channel=ticket.channel,
        timestamp=ticket.timestamp,
        intent=intent,
        sentiment=sentiment,
    )
    conversation.add_message(customer_msg)

    agent_msg = Message(
        role="agent",
        content=response_text,
        channel=ticket.channel,
        intent=intent,
        sentiment=sentiment,
        escalation=escalation_needed,
    )
    conversation.add_message(agent_msg)

    # Step 9: Build reasoning summary
    context_note = ""
    if conversation.message_count > 2:
        context_note = (
            f"Conversation has {conversation.message_count} messages across "
            f"{len(conversation.topics)} topic(s). "
        )

    reasoning = (
        f"{context_note}"
        f"Intent classified as '{INTENT_CATEGORIES.get(intent, intent)}'. "
        f"Sentiment detected: '{sentiment}'. "
        f"KB search returned {'relevant' if 'No specific' not in kb_result else 'no specific'} documentation. "
        f"{'Escalation triggered: ' + escalation_reason if escalation_needed else 'No escalation needed.'}"
    )

    return AgentResponse(
        ticket=ticket,
        response_text=response_text,
        escalation_needed=escalation_needed,
        escalation_reason=escalation_reason,
        intent=INTENT_CATEGORIES.get(intent, intent),
        sentiment=sentiment,
        kb_searches_used=kb_searches_used,
        reasoning=reasoning,
        conversation=conversation,
    )


# ──────────────────────────────────────────────────────────────
# INTERACTIVE CLI
# ──────────────────────────────────────────────────────────────

def print_banner():
    print("\n" + "=" * 70)
    print("  FlowSync Customer Success AI Agent -- Prototype v2.0")
    print("  Hackathon 5 | Exercise 1.3 -- Memory & State")
    print("=" * 70)
    print()
    print("  Commands:")
    print("    - Type a JSON message to test the agent")
    print("    - Type 'sample' to run sample multi-turn conversations")
    print("    - Type 'conversations' to view all active conversations")
    print("    - Type 'help' for usage examples")
    print("    - Type 'quit' or 'exit' to stop")
    print()


def run_sample_multiturn():
    """
    Run 3 multi-turn conversation scenarios demonstrating:
    1. Same customer, same channel, follow-up questions
    2. Same customer, cross-channel (email -> whatsapp)
    3. Sentiment worsening leading to escalation
    """
    scenarios = [
        # Scenario 1: Multi-turn on same channel
        {
            "name": "Scenario 1: Multi-turn team invite conversation (email)",
            "messages": [
                {
                    "channel": "email",
                    "customer_email": "ahmed@startup.io",
                    "subject": "How to invite my whole team?",
                    "content": "Hi, I just signed up for Pro plan. How do I invite 25 team members at once?",
                },
                {
                    "channel": "email",
                    "customer_email": "ahmed@startup.io",
                    "subject": "Re: How to invite my whole team?",
                    "content": "Thanks! Also, can I set different roles for different members?",
                },
                {
                    "channel": "email",
                    "customer_email": "ahmed@startup.io",
                    "subject": "Re: How to invite my whole team?",
                    "content": "Great, one more thing -- can I import them from a CSV file?",
                },
            ],
        },
        # Scenario 2: Cross-channel conversation
        {
            "name": "Scenario 2: Cross-channel (email -> whatsapp) -- same customer",
            "messages": [
                {
                    "channel": "email",
                    "customer_email": "sara@agency.com",
                    "subject": "AI suggestions not working",
                    "content": "The AI task suggestion feature is not giving any recommendations today.",
                },
                {
                    "channel": "whatsapp",
                    "customer_email": "sara@agency.com",
                    "content": "hey, still no AI suggestions. tried the steps you mentioned.",
                },
                {
                    "channel": "whatsapp",
                    "customer_email": "sara@agency.com",
                    "content": "this is getting frustrating. it's been a whole day now.",
                },
            ],
        },
        # Scenario 3: Sentiment worsening -> escalation
        {
            "name": "Scenario 3: Sentiment worsening leading to escalation (whatsapp)",
            "messages": [
                {
                    "channel": "whatsapp",
                    "customer_phone": "+14155551234",
                    "content": "hi, my slack integration stopped working this morning",
                },
                {
                    "channel": "whatsapp",
                    "customer_phone": "+14155551234",
                    "content": "tried disconnecting and reconnecting but still nothing",
                },
                {
                    "channel": "whatsapp",
                    "customer_phone": "+14155551234",
                    "content": "this is ridiculous! I have a deadline today and nobody is helping me!",
                },
            ],
        },
    ]

    total_msgs = sum(len(s["messages"]) for s in scenarios)
    msg_counter = 0

    for scenario in scenarios:
        print(f"\n  {'#' * 60}")
        print(f"  {scenario['name']}")
        print(f"  {'#' * 60}")

        for msg in scenario["messages"]:
            msg_counter += 1
            print(f"\n  --- Message {msg_counter}/{total_msgs} ---")
            print(f"  Input: {json.dumps(msg, indent=4)}")

            response = process_ticket(msg)
            response.display()

    # Show final conversation store
    store.display_all()


def print_help():
    """Print usage examples."""
    print("\n  Usage Examples:")
    print("  " + "-" * 50)
    print()
    print("  WhatsApp message:")
    print('  {"channel": "whatsapp", "customer_phone": "+923001234567", "content": "hey, tasks not syncing with slack"}')
    print()
    print("  Email:")
    print('  {"channel": "email", "customer_email": "test@example.com", "subject": "Help needed", "content": "How do I invite team members?"}')
    print()
    print("  Web form:")
    print('  {"channel": "web_form", "customer_email": "test@example.com", "subject": "Bug report", "content": "Dashboard not loading"}')
    print()
    print("  Follow-up (same customer):")
    print('  {"channel": "email", "customer_email": "test@example.com", "content": "still not working, any update?"}')
    print()


def main():
    """Interactive main loop."""
    print_banner()

    while True:
        try:
            user_input = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Goodbye!\n")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("\n  Goodbye!\n")
            break

        if user_input.lower() == "sample":
            run_sample_multiturn()
            continue

        if user_input.lower() == "conversations":
            store.display_all()
            continue

        if user_input.lower() == "help":
            print_help()
            continue

        # Parse JSON input
        try:
            raw_input = json.loads(user_input)
        except json.JSONDecodeError as e:
            print(f"\n  Invalid JSON: {e}")
            print("  Type 'help' for usage examples.\n")
            continue

        # Validate required fields
        if "channel" not in raw_input or "content" not in raw_input:
            print("\n  Missing required fields: 'channel' and 'content' are required.")
            print("  Type 'help' for usage examples.\n")
            continue

        if raw_input["channel"] not in ("email", "whatsapp", "web_form"):
            print(f"\n  Unknown channel: '{raw_input['channel']}'. Use: email, whatsapp, web_form\n")
            continue

        # Process the ticket
        response = process_ticket(raw_input)
        response.display()


if __name__ == "__main__":
    main()
