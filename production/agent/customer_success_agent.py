"""
FlowSync Customer Success AI Agent -- OpenAI Agents SDK Implementation
=======================================================================
Production-grade Custom Agent using the OpenAI Agents SDK.

Replaces the prototype (src/prototype.py) with:
  - OpenAI Agents SDK (Agent, Runner, function_tool)
  - PostgreSQL-backed tools via RunContextWrapper[AgentContext]
  - System prompt from prompts.py
  - model="gpt-4o"

All tools use Pydantic input models and are decorated with @function_tool.
Tools优先 use PostgreSQL via database/queries.py, with in-memory fallback.

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
# AGENT FACTORY
# ──────────────────────────────────────────────────────────────

def create_agent(
    model: str = "gpt-4o",
    db_pool: Any = None,
    tools: Optional[list] = None,
    handoffs: Optional[list] = None,
) -> Agent:
    """
    Create the FlowSync Customer Success AI Agent.

    Args:
        model: OpenAI model to use. Default: "gpt-4o".
        db_pool: Optional asyncpg.Pool for database-backed tools.
                 If None, tools fall back to in-memory storage.
        tools: Optional list of additional tools. If None, uses the
               default 7 FlowSync tools.
        handoffs: Optional list of handoff destinations for multi-agent
                  routing (e.g., human_agent, billing_specialist).

    Returns:
        An Agent instance configured with the system prompt and all tools.

    Example:
        agent = create_agent(model="gpt-4o")
        result = await Runner.run(agent, "How do I invite team members?")
        print(result.final_output)
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
        "model": model,
        "tools": default_tools,
    }

    # Add handoffs if provided (for multi-agent setups)
    if handoffs:
        agent_kwargs["handoffs"] = handoffs

    agent = Agent(**agent_kwargs)

    db_status = "connected" if db_pool else "in-memory fallback"
    logger.info(
        "Agent created: model=%s, tools=%d, database=%s",
        model, len(default_tools), db_status,
    )

    return agent


# ──────────────────────────────────────────────────────────────
# AGENT RUNNER
# ──────────────────────────────────────────────────────────────

async def run_agent(
    agent: Agent,
    input_data: dict,
    db_pool: Any = None,
    conversation_history: Optional[list[dict]] = None,
) -> dict:
    """
    Run the agent on a single customer message.

    Args:
        agent: Agent instance from create_agent().
        input_data: Dict with customer message details:
            - channel: "email", "whatsapp", or "web_form"
            - content: The customer's message text
            - customer_email: (optional) Customer email
            - customer_phone: (optional) Customer phone
            - subject: (optional) Email subject line
        db_pool: Optional asyncpg.Pool for database tools.
        conversation_history: Optional list of prior messages for
                              multi-turn context (OpenAI message format).

    Returns:
        Dict with:
            - response: The agent's final response text
            - context: The AgentContext used (for inspection)
            - tool_calls: Number of tool calls made during this run
            - input: The original input data
    """
    # Build context
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

    # Build input prompt
    input_text = _build_agent_input(input_data)

    logger.info(
        "Running agent: run_id=%s, customer=%s, channel=%s",
        context.run_id, customer_id, context.current_channel,
    )

    # Build the input: either a simple string or a message list + string
    if conversation_history:
        # Multi-turn: append the new message to existing history
        messages = list(conversation_history)
        messages.append({"role": "user", "content": input_text})
        result = await Runner.run(
            agent,
            input=messages,
            context=context,
        )
    else:
        # Single-turn
        result = await Runner.run(
            agent,
            input=input_text,
            context=context,
        )

    # Count tool calls from the run
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
        "Agent completed: run_id=%s, tool_calls=%d",
        context.run_id, tool_call_count,
    )

    return {
        "response": result.final_output,
        "context": context,
        "tool_calls": tool_call_count,
        "input": input_data,
    }


def _build_agent_input(input_data: dict) -> str:
    """
    Build the input text to send to the agent for a customer message.

    Formats the raw input into a clear message telling the agent
    what channel, customer, and content to work with.
    """
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
    parts.append("1. Identify the customer (get_or_create_customer)")
    parts.append("2. Analyze their sentiment (analyze_sentiment)")
    parts.append("3. Search the knowledge base (search_knowledge_base)")
    parts.append("4. Create a ticket (create_ticket)")
    parts.append("5. Decide if escalation is needed (escalate_to_human if needed)")
    parts.append("6. Send an appropriate response (send_response)")
    parts.append("")
    parts.append("Follow all escalation rules and brand voice guidelines.")

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────
# MULTI-TURN CONVERSATION HELPER
# ──────────────────────────────────────────────────────────────

class ConversationSession:
    """
    Manages a multi-turn conversation with the agent.

    Keeps track of message history and conversation context so
    the agent can reference prior interactions.

    Usage:
        session = ConversationSession(agent, db_pool=pool)
        resp1 = await session.send_message({
            "channel": "email",
            "content": "How do I invite team members?",
            "customer_email": "user@example.com",
        })
        resp2 = await session.send_message({
            "channel": "email",
            "content": "Thanks! What about permissions?",
        })
    """

    def __init__(self, agent: Agent, db_pool: Any = None):
        self.agent = agent
        self.db_pool = db_pool
        self.message_history: list[dict] = []
        self.context: Optional[AgentContext] = None
        self.conversation_id: str = f"CONV-{uuid.uuid4().hex[:8].upper()}"

    async def send_message(self, input_data: dict) -> dict:
        """Send a message in the ongoing conversation."""
        input_data["conversation_id"] = self.conversation_id

        result = await run_agent(
            self.agent,
            input_data,
            db_pool=self.db_pool,
            conversation_history=self.message_history if self.message_history else None,
        )

        # Update message history
        self.message_history.append({"role": "user", "content": input_data.get("content", "")})
        self.message_history.append({"role": "assistant", "content": result["response"]})

        # Save context for future reference
        if self.context is None:
            self.context = result["context"]

        return result


# ──────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ──────────────────────────────────────────────────────────────

def main():
    """Interactive CLI for testing the agent."""
    print("\n" + "=" * 70)
    print("  FlowSync Customer Success AI Agent -- OpenAI Agents SDK")
    print("  Model: gpt-4o")
    print("=" * 70)
    print()
    print("  Commands:")
    print("    - Type a JSON message to test the agent")
    print("    - Type 'sample' to run sample tickets")
    print("    - Type 'quit' or 'exit' to stop")
    print()
    print("  NOTE: Requires OPENAI_API_KEY environment variable.")
    print()

    agent = create_agent(model="gpt-4o")

    sample_tickets = [
        {
            "channel": "email",
            "customer_email": "ahmed@startup.io",
            "subject": "How to invite my whole team?",
            "content": "Hi, I just signed up for Pro plan. How do I invite 25 team members at once?",
        },
        {
            "channel": "whatsapp",
            "customer_phone": "+923001234567",
            "content": "hey, my tasks are not syncing with slack. help pls",
        },
        {
            "channel": "email",
            "customer_email": "mike@techflow.dev",
            "subject": "Billing question",
            "content": "What are the exact pricing for Enterprise plan?",
        },
        {
            "channel": "whatsapp",
            "customer_phone": "+14155551234",
            "content": "this is ridiculous! I want to speak to a manager NOW",
        },
    ]

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
