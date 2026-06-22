"""
FlowSync Customer Success AI Agent -- Groq + Prototype Fallback
================================================================
Production agent using Groq (OpenAI-compatible) with automatic
fallback to the rule-based prototype engine when LLM is unavailable.

Architecture:
  1. Tries Groq LLM via openai SDK (OpenAI-compatible endpoint)
  2. If Groq is unavailable, falls back to prototype.process_ticket()
     which uses keyword-based intent/sentiment + KB template responses

Usage:
    from agent.customer_success_agent import create_agent, run_agent
    agent = create_agent()
    result = await run_agent(agent, {"channel": "email", "content": "..."})

CLI:
    cd production && python -m agent.customer_success_agent
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Any, Optional

import httpx
from openai import OpenAI

from agents import Agent, Runner, RunContextWrapper

# ──────────────────────────────────────────────────────────────
# PATH SETUP
# ──────────────────────────────────────────────────────────────

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_src_path = os.path.join(_project_root, "src")
_prod_path = os.path.join(_project_root, "production")
for p in [_src_path, _prod_path]:
    if p not in sys.path:
        sys.path.insert(0, p)

from agent.prompts import SYSTEM_PROMPT
from agent.tools import (
    AgentContext,
    search_knowledge_base as _tool_search_kb,
    create_ticket as _tool_create_ticket,
    get_customer_history as _tool_customer_history,
    escalate_to_human as _tool_escalate,
    send_response as _tool_send_response,
    analyze_sentiment as _tool_analyze_sentiment,
    get_or_create_customer as _tool_get_or_create_customer,
)

logger = logging.getLogger("flowsync.agent")

# ──────────────────────────────────────────────────────────────
# LLM CLIENT (Groq via OpenAI-compatible endpoint)
# ──────────────────────────────────────────────────────────────

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
_llm_available = bool(GROQ_API_KEY)

if _llm_available:
    llm_client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
        http_client=httpx.Client(timeout=60.0),
    )
    LLM_MODEL = os.getenv("OPENAI_MODEL", "llama-3.3-70b-versatile")
    logger.info("LLM configured: model=%s", LLM_MODEL)
else:
    llm_client = None
    LLM_MODEL = ""
    logger.info("No API key found — will use prototype fallback engine")


def llm_chat(messages: list[dict], temperature: float = 0.3, max_tokens: int = 1024) -> str | None:
    """Call Groq LLM and return the response text. Returns None on failure."""
    if not llm_client:
        return None
    try:
        resp = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning("LLM call failed: %s", e)
        return None


# ──────────────────────────────────────────────────────────────
# AGENT FACTORY
# ──────────────────────────────────────────────────────────────

def create_agent(
    model: str | None = None,
    db_pool: Any = None,
    tools: Optional[list] = None,
    handoffs: Optional[list] = None,
) -> Agent | None:
    """Create the FlowSync Customer Success AI Agent.

    Returns None if no LLM is available (caller should fall back to prototype).
    """
    if not _llm_available:
        logger.info("create_agent skipped — no LLM configured")
        return None

    actual_model = model or LLM_MODEL
    default_tools = [
        _tool_search_kb,
        _tool_create_ticket,
        _tool_customer_history,
        _tool_escalate,
        _tool_send_response,
        _tool_analyze_sentiment,
        _tool_get_or_create_customer,
    ]
    if tools:
        default_tools.extend(tools)

    agent = Agent(
        name="FlowSync Customer Success Agent",
        instructions=SYSTEM_PROMPT,
        model=actual_model,
        tools=default_tools,
        temperature=0.3,
        max_tokens=1024,
        handoffs=handoffs or None,
    )

    db_status = "connected" if db_pool else "in-memory fallback"
    logger.info("Agent created: model=%s, tools=%d, database=%s", actual_model, len(default_tools), db_status)
    return agent


# ──────────────────────────────────────────────────────────────
# AGENT RUNNER (LLM path + prototype fallback)
# ──────────────────────────────────────────────────────────────

async def run_agent(
    agent: Agent | None,
    input_data: dict,
    db_pool: Any = None,
    conversation_history: Optional[list[dict]] = None,
) -> dict:
    """Run the agent on a single customer message.

    Tries Groq LLM first. Falls back to prototype.process_ticket() when
    no LLM is available or the LLM call fails.
    """
    channel = input_data.get("channel", "email")
    content = input_data.get("content", "")
    customer_email = input_data.get("customer_email", "")
    customer_phone = input_data.get("customer_phone", "")
    customer_id = customer_email or customer_phone or "anonymous"

    # ── LLM path ──
    if agent is not None and _llm_available:
        context = AgentContext(
            db_pool=db_pool,
            run_id=str(uuid.uuid4())[:8],
            customer_id=customer_id,
            conversation_id=input_data.get("conversation_id", ""),
            current_channel=channel,
        )

        logger.info("Running LLM agent: run_id=%s, customer=%s, channel=%s", context.run_id, customer_id, channel)

        try:
            input_text = _build_agent_input(input_data)
            if conversation_history:
                messages = list(conversation_history) + [{"role": "user", "content": input_text}]
                result = await Runner.run(agent, input=messages, context=context)
            else:
                result = await Runner.run(agent, input=input_text, context=context)

            response_text = getattr(result, "final_output", None) or ""
            if response_text:
                logger.info("LLM agent succeeded: run_id=%s", context.run_id)
                return {"response": response_text, "context": context, "tool_calls": 1, "input": input_data}
        except Exception as e:
            logger.warning("LLM agent failed, falling back to prototype: %s", e)

    # ── Prototype fallback ──
    logger.info("Using prototype fallback engine for customer=%s channel=%s", customer_id, channel)
    return _run_prototype(input_data)


def _run_prototype(input_data: dict) -> dict:
    """Run the prototype's rule-based engine."""
    try:
        from prototype import process_ticket, store
        result = process_ticket(input_data)
        return {
            "response": result.response_text,
            "context": None,
            "tool_calls": 0,
            "input": input_data,
            "prototype_result": result,
        }
    except Exception as e:
        logger.error("Prototype engine also failed: %s", e, exc_info=True)
        return {
            "response": "Thank you for reaching out. Our team is reviewing your request and will get back to you shortly.",
            "context": None,
            "tool_calls": 0,
            "input": input_data,
        }


def _build_agent_input(input_data: dict) -> str:
    channel = input_data.get("channel", "unknown")
    content = input_data.get("content", "")
    subject = input_data.get("subject", "")
    email = input_data.get("customer_email", "")
    phone = input_data.get("customer_phone", "")

    parts = [
        "New customer message received:",
        f"  Channel: {channel}",
    ]
    if email:
        parts.append(f"  Customer Email: {email}")
    if phone:
        parts.append(f"  Customer Phone: {phone}")
    if subject:
        parts.append(f"  Subject: {subject}")
    parts.extend([
        f"  Message: {content}",
        "",
        "Process this message using your skills:",
        "1. Identify the customer",
        "2. Analyze sentiment",
        "3. Search knowledge base",
        "4. Create ticket",
        "5. Decide escalation",
        "6. Send response",
        "",
        "Follow all rules and brand voice.",
    ])
    return "\n".join(parts)


# ConversationSession class remains same
class ConversationSession:
    def __init__(self, agent: Agent, db_pool: Any = None):
        self.agent = agent
        self.db_pool = db_pool
        self.message_history: list[dict] = []
        self.context: Optional[AgentContext] = None
        self.conversation_id: str = f"CONV-{uuid.uuid4().hex[:8].upper()}"

    async def send_message(self, input_data: dict) -> dict:
        input_data["conversation_id"] = self.conversation_id

        result = await run_agent(
            self.agent,
            input_data,
            db_pool=self.db_pool,
            conversation_history=self.message_history if self.message_history else None,
        )

        self.message_history.append({"role": "user", "content": input_data.get("content", "")})
        self.message_history.append({"role": "assistant", "content": result["response"]})

        if self.context is None:
            self.context = result["context"]

        return result


# ──────────────────────────────────────────────────────────────
# CLI ENTRY POINT (Updated message)
# ──────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 70)
    print("  FlowSync Customer Success AI Agent -- Groq")
    print("  Model: llama-3.3-70b-versatile (Fast & Free)")
    print("=" * 70)
    print()
    print("  Commands:")
    print("    - Type a JSON message")
    print("    - Type 'sample' to run sample tickets")
    print("    - Type 'quit' to stop")
    print()
    print("  NOTE: Requires GROQ_API_KEY environment variable.")
    print()

    agent = create_agent(model="llama-3.3-70b-versatile")

    # ... (sample_tickets same as before)

    sample_tickets = [ ... ]   # tumhara purana sample_tickets yahan paste kar dena

    async def run_single(input_data):
        result = await run_agent(agent, input_data)
        print(f"\n  Response:\n  {result['response']}\n")
        return result

    while True:
        try:
            user_input = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!\n")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("\n  Goodbye!\n")
            break

        if user_input.lower() == "sample":
            for i, ticket in enumerate(sample_tickets, 1):
                print(f"\n  {'#' * 50}")
                print(f"  SAMPLE {i}/{len(sample_tickets)}")
                print(f"  {'#' * 50}")
                print(f"  Input: {json.dumps(ticket, indent=4)}")
                asyncio.run(run_single(ticket))
            continue

        try:
            raw_input = json.loads(user_input)
        except json.JSONDecodeError as e:
            print(f"\n  Invalid JSON: {e}\n")
            continue

        if "channel" not in raw_input or "content" not in raw_input:
            print("\n  Missing required fields: 'channel' and 'content'.\n")
            continue

        asyncio.run(run_single(raw_input))


if __name__ == "__main__":
    main()