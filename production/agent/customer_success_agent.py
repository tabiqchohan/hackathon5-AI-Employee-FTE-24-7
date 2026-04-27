"""
FlowSync Customer Success AI Agent -- Groq Implementation
=======================================================================
Production-grade Custom Agent using Groq (fast & free alternative to OpenAI).

Replaces OpenAI with Groq for better speed and zero cost.

Model: llama-3.3-70b-versatile (best free model on Groq)

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

from groq import Groq
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
    search_knowledge_base,
    create_ticket,
    get_customer_history,
    escalate_to_human,
    send_response,
    analyze_sentiment,
    get_or_create_customer,
)

logger = logging.getLogger("flowsync.agent")

# ──────────────────────────────────────────────────────────────
# GROQ CLIENT
# ──────────────────────────────────────────────────────────────

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ──────────────────────────────────────────────────────────────
# AGENT FACTORY
# ──────────────────────────────────────────────────────────────

def create_agent(
    model: str = "llama-3.3-70b-versatile",   # Best Groq model
    db_pool: Any = None,
    tools: Optional[list] = None,
    handoffs: Optional[list] = None,
) -> Agent:
    """
    Create the FlowSync Customer Success AI Agent using Groq.
    """
    default_tools = [
        search_knowledge_base,
        create_ticket,
        get_customer_history,
        escalate_to_human,
        send_response,
        analyze_sentiment,
        get_or_create_customer,
    ]

    if tools is not None:
        default_tools.extend(tools)

    agent_kwargs: dict[str, Any] = {
        "name": "FlowSync Customer Success Agent",
        "instructions": SYSTEM_PROMPT,
        "model": model,                    # Groq model name
        "tools": default_tools,
        "temperature": 0.3,                # More consistent responses
        "max_tokens": 1024,
    }

    if handoffs:
        agent_kwargs["handoffs"] = handoffs

    agent = Agent(**agent_kwargs)

    db_status = "connected" if db_pool else "in-memory fallback"
    logger.info(
        "Agent created with Groq: model=%s, tools=%d, database=%s",
        model, len(default_tools), db_status,
    )

    return agent


# ──────────────────────────────────────────────────────────────
# AGENT RUNNER (Same as before, only small change in logging)
# ──────────────────────────────────────────────────────────────

async def run_agent(
    agent: Agent,
    input_data: dict,
    db_pool: Any = None,
    conversation_history: Optional[list[dict]] = None,
) -> dict:
    """
    Run the agent on a single customer message using Groq.
    """
    customer_id = (
        input_data.get("customer_email")
        or input_data.get("customer_phone")
        or "anonymous"
    )

    context = AgentContext(
        db_pool=db_pool,
        run_id=str(uuid.uuid4())[:8],
        customer_id=customer_id,
        conversation_id=input_data.get("conversation_id", ""),
        current_channel=input_data.get("channel", "email"),
    )

    input_text = _build_agent_input(input_data)

    logger.info(
        "Running agent with Groq: run_id=%s, customer=%s, channel=%s",
        context.run_id, customer_id, context.current_channel,
    )

    if conversation_history:
        messages = list(conversation_history)
        messages.append({"role": "user", "content": input_text})
        result = await Runner.run(
            agent,
            input=messages,
            context=context,
        )
    else:
        result = await Runner.run(
            agent,
            input=input_text,
            context=context,
        )

    tool_call_count = 0
    if hasattr(result, "last_response") and result.last_response:
        output = result.last_response.output
        if isinstance(output, list):
            tool_call_count = sum(
                1 for item in output
                if getattr(item, "type", None) == "function_call"
                or hasattr(item, "call_id")
            )

    logger.info(
        "Agent completed with Groq: run_id=%s, tool_calls=%d",
        context.run_id, tool_call_count,
    )

    return {
        "response": result.final_output,
        "context": context,
        "tool_calls": tool_call_count,
        "input": input_data,
    }


# _build_agent_input function remains same
def _build_agent_input(input_data: dict) -> str:
    channel = input_data.get("channel", "unknown")
    content = input_data.get("content", "")
    subject = input_data.get("subject", "")
    email = input_data.get("customer_email", "")
    phone = input_data.get("customer_phone", "")

    parts = []
    parts.append("New customer message received:")
    parts.append(f"  Channel: {channel}")
    if email:
        parts.append(f"  Customer Email: {email}")
    if phone:
        parts.append(f"  Customer Phone: {phone}")
    if subject:
        parts.append(f"  Subject: {subject}")
    parts.append(f"  Message: {content}")
    parts.append("")
    parts.append("Process this message using your skills:")
    parts.append("1. Identify the customer")
    parts.append("2. Analyze sentiment")
    parts.append("3. Search knowledge base")
    parts.append("4. Create ticket")
    parts.append("5. Decide escalation")
    parts.append("6. Send response")
    parts.append("")
    parts.append("Follow all rules and brand voice.")

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