"""
FlowSync Customer Success AI Agent -- Channel Formatters
=========================================================
Handles channel-specific response formatting, ensuring brand voice
consistency across email, WhatsApp, and web form channels.

Each formatter implements a common interface and produces output
optimized for its target channel's constraints and conventions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class Channel(str, Enum):
    """Supported communication channels."""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


@dataclass
class ResponseContext:
    """Context for generating a channel-appropriate response."""
    core_message: str
    customer_name: str | None = None
    is_escalation: bool = False
    escalation_reason: str | None = None
    context_prefix: str | None = None
    kb_context: str | None = None


@dataclass
class FormattedResponse:
    """A fully formatted, channel-optimized response."""
    text: str
    channel: str
    character_count: int
    truncated: bool = False
    greeting: str = ""
    sign_off: str = ""


# ──────────────────────────────────────────────────────────────
# BASE FORMATTER
# ──────────────────────────────────────────────────────────────

class BaseFormatter(ABC):
    """Abstract base class for channel formatters."""

    @property
    @abstractmethod
    def channel(self) -> str:
        """Return the channel name."""

    @property
    @abstractmethod
    def max_length(self) -> int:
        """Maximum recommended response length."""

    @property
    @abstractmethod
    def greeting(self) -> str:
        """Channel-appropriate greeting."""

    @property
    @abstractmethod
    def sign_off(self) -> str:
        """Channel-appropriate sign-off."""

    @abstractmethod
    def format(self, ctx: ResponseContext) -> FormattedResponse:
        """Format a response for this channel."""

    def _truncate(self, text: str, max_len: int) -> tuple[str, bool]:
        """Truncate text to max length, preserving word boundaries."""
        if len(text) <= max_len:
            return text, False
        # Find last space before max_len
        cutoff = text.rfind(" ", 0, max_len - 3)
        if cutoff == -1:
            cutoff = max_len - 3
        return text[:cutoff] + "...", True


# ──────────────────────────────────────────────────────────────
# EMAIL FORMATTER
# ──────────────────────────────────────────────────────────────

class EmailFormatter(BaseFormatter):
    """Formats responses for email channel.

    Tone: Formal, professional, empathetic, detailed.
    Structure: Acknowledge -> Answer -> Offer further help -> Sign-off.
    """

    @property
    def channel(self) -> str:
        return Channel.EMAIL.value

    @property
    def max_length(self) -> int:
        return 2000

    @property
    def greeting(self) -> str:
        return "Dear Valued Customer,"

    @property
    def sign_off(self) -> str:
        return "Best regards,\nFlowSync Customer Success Team"

    def format(self, ctx: ResponseContext) -> FormattedResponse:
        parts = []

        # Greeting
        if ctx.customer_name:
            parts.append(f"Dear {ctx.customer_name},")
        else:
            parts.append(self.greeting)
        parts.append("")

        # Context prefix (for follow-ups)
        if ctx.context_prefix:
            parts.append(ctx.context_prefix)
            parts.append("")

        # Escalation message
        if ctx.is_escalation:
            parts.append(
                "Thank you for reaching out to us. I understand the importance "
                "of your inquiry, and I want to ensure you receive the most "
                "accurate and comprehensive assistance."
            )
            parts.append("")
            parts.append(
                "Your case has been escalated to our specialist team who are "
                "best equipped to address your specific needs. They will review "
                "your case and respond within the next 4 business hours."
            )
            if ctx.escalation_reason:
                parts.append("")
                parts.append(f"Reason for escalation: {ctx.escalation_reason}")
        else:
            # Normal response
            parts.append(
                "Thank you for contacting FlowSync support. "
                "I'd be happy to help with your inquiry."
            )
            parts.append("")

            if ctx.kb_context:
                parts.append(ctx.kb_context)
            else:
                parts.append(ctx.core_message)

            parts.append("")
            parts.append(
                "If you have any further questions, please don't "
                "hesitate to reach out. We're here to help!"
            )

        parts.append("")
        parts.append(self.sign_off)

        text = "\n".join(parts)
        truncated = False

        # Truncate if needed
        if len(text) > self.max_length:
            body_max = self.max_length - len(self.greeting) - len(self.sign_off) - 50
            body = ctx.core_message
            body, truncated = self._truncate(body, body_max)
            text = f"{self.greeting}\n\n{body}\n\n{self.sign_off}"

        return FormattedResponse(
            text=text,
            channel=self.channel,
            character_count=len(text),
            truncated=truncated,
            greeting=self.greeting,
            sign_off=self.sign_off,
        )


# ──────────────────────────────────────────────────────────────
# WHATSAPP FORMATTER
# ──────────────────────────────────────────────────────────────

class WhatsAppFormatter(BaseFormatter):
    """Formats responses for WhatsApp channel.

    Tone: Casual, friendly, concise.
    Structure: Direct answer -> Quick follow-up offer.
    Max: ~280 characters for mobile readability.
    """

    @property
    def channel(self) -> str:
        return Channel.WHATSAPP.value

    @property
    def max_length(self) -> int:
        return 280

    @property
    def greeting(self) -> str:
        return "Hey!"

    @property
    def sign_off(self) -> str:
        return "Let me know if you need more help!"

    def format(self, ctx: ResponseContext) -> FormattedResponse:
        parts = []

        # Greeting
        parts.append(self.greeting)
        parts.append("")

        # Context prefix (brief for WhatsApp)
        if ctx.context_prefix:
            # Shorten context prefix for WhatsApp
            prefix = ctx.context_prefix[:80]
            parts.append(prefix)
            parts.append("")

        # Escalation message
        if ctx.is_escalation:
            parts.append(
                "I understand your concern, and I want to make sure you get "
                "the best help possible. I'm escalating this to our specialist "
                "team who can assist you directly. You'll hear from them shortly. "
                "Thanks for your patience!"
            )
        else:
            # Normal response -- keep it short
            message = ctx.core_message
            body_truncated = False
            if len(message) > 200:
                message = message[:197] + "..."
                body_truncated = True
            parts.append(message)
            parts.append("")
            parts.append(self.sign_off)

        text = "\n".join(parts)
        truncated = False

        # Truncate if needed
        if len(text) > self.max_length:
            body_max = self.max_length - len(self.greeting) - len(self.sign_off) - 20
            body = ctx.core_message
            body, truncated = self._truncate(body, body_max)
            text = f"{self.greeting}\n\n{body}\n\n{self.sign_off}"
        elif ctx.is_escalation is False and body_truncated:
            truncated = True

        return FormattedResponse(
            text=text,
            channel=self.channel,
            character_count=len(text),
            truncated=truncated,
            greeting=self.greeting,
            sign_off=self.sign_off,
        )


# ──────────────────────────────────────────────────────────────
# WEB FORM FORMATTER
# ──────────────────────────────────────────────────────────────

class WebFormFormatter(BaseFormatter):
    """Formats responses for web form channel.

    Tone: Semi-formal, clear, solution-focused.
    Structure: Answer -> Follow-up option -> Sign-off.
    """

    @property
    def channel(self) -> str:
        return Channel.WEB_FORM.value

    @property
    def max_length(self) -> int:
        return 1000

    @property
    def greeting(self) -> str:
        return "Thanks for your message!"

    @property
    def sign_off(self) -> str:
        return "Best,\nFlowSync Support"

    def format(self, ctx: ResponseContext) -> FormattedResponse:
        parts = []

        # Greeting
        parts.append(self.greeting)
        parts.append("")

        # Context prefix
        if ctx.context_prefix:
            parts.append(ctx.context_prefix)
            parts.append("")

        # Escalation message
        if ctx.is_escalation:
            parts.append(
                "Based on your inquiry, I'm escalating this to our specialist "
                "team who can provide you with the most accurate assistance."
            )
            if ctx.escalation_reason:
                parts.append("")
                parts.append(f"Reason: {ctx.escalation_reason}")
            parts.append("")
            parts.append(
                "A team member will follow up with you within 4 business hours. "
                "We appreciate your patience."
            )
        else:
            # Normal response
            if ctx.kb_context:
                parts.append(ctx.kb_context)
            else:
                parts.append(ctx.core_message)

            parts.append("")
            parts.append("Let me know if you need anything else!")

        parts.append("")
        parts.append(self.sign_off)

        text = "\n".join(parts)
        truncated = False

        # Truncate if needed
        if len(text) > self.max_length:
            body_max = self.max_length - len(self.greeting) - len(self.sign_off) - 50
            body = ctx.core_message
            body, truncated = self._truncate(body, body_max)
            text = f"{self.greeting}\n\n{body}\n\n{self.sign_off}"

        return FormattedResponse(
            text=text,
            channel=self.channel,
            character_count=len(text),
            truncated=truncated,
            greeting=self.greeting,
            sign_off=self.sign_off,
        )


# ──────────────────────────────────────────────────────────────
# FORMATTER REGISTRY
# ──────────────────────────────────────────────────────────────

FORMATTERS: dict[str, BaseFormatter] = {
    Channel.EMAIL.value: EmailFormatter(),
    Channel.WHATSAPP.value: WhatsAppFormatter(),
    Channel.WEB_FORM.value: WebFormFormatter(),
}


def get_formatter(channel: str) -> BaseFormatter:
    """Get the appropriate formatter for a channel.

    Args:
        channel: One of 'email', 'whatsapp', 'web_form'.

    Returns:
        The channel-specific formatter instance.

    Raises:
        ValueError: If the channel is not supported.
    """
    formatter = FORMATTERS.get(channel.lower())
    if not formatter:
        raise ValueError(
            f"Unsupported channel: '{channel}'. "
            f"Supported channels: {list(FORMATTERS.keys())}"
        )
    return formatter


def format_response(
    message: str,
    channel: str,
    is_escalation: bool = False,
    escalation_reason: str | None = None,
    context_prefix: str | None = None,
    customer_name: str | None = None,
    kb_context: str | None = None,
) -> FormattedResponse:
    """Convenience function to format a response for any channel.

    Args:
        message: The core response content.
        channel: Target channel ('email', 'whatsapp', 'web_form').
        is_escalation: Whether this is an escalation handoff.
        escalation_reason: Reason for escalation.
        context_prefix: Conversation-aware opening line.
        customer_name: Customer's name for personalization.
        kb_context: Knowledge base context text.

    Returns:
        FormattedResponse with channel-optimized text and metadata.
    """
    formatter = get_formatter(channel)
    ctx = ResponseContext(
        core_message=message,
        customer_name=customer_name,
        is_escalation=is_escalation,
        escalation_reason=escalation_reason,
        context_prefix=context_prefix,
        kb_context=kb_context,
    )
    return formatter.format(ctx)
