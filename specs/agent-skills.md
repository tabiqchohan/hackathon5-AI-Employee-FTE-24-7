# Agent Skills Manifest -- FlowSync Customer Success AI FTE

**Project:** FlowSync Customer Success Digital Employee  
**Version:** 1.0  
**Date:** 2026-04-09  
**Phase:** Incubation -- Exercise 1.5  

---

## Overview

This document defines the specialized skills (capabilities) of the FlowSync Customer Success AI Agent. Each skill is a self-contained capability that the agent activates based on context, input signals, and trigger conditions. Skills are designed to be **modular, testable, and composable** -- they can be invoked independently or chained together in the agent's reasoning pipeline.

| Skill ID | Skill Name | Category | Priority |
|----------|-----------|----------|----------|
| SK-001 | Knowledge Retrieval | Information | Core |
| SK-002 | Sentiment Analysis & Trend | Emotional Intelligence | Core |
| SK-003 | Escalation Decision | Risk Management | Critical |
| SK-004 | Channel Adaptation | Communication | Core |
| SK-005 | Customer Identification & Memory | Context Management | Core |

---

## SK-001: Knowledge Retrieval

**Description:**  
Searches the FlowSync product knowledge base to find relevant documentation, troubleshooting steps, setup guides, and feature information for a customer's query.

### When to Use
- Customer asks a question about any FlowSync feature
- Customer reports an issue that may have documented troubleshooting steps
- Customer needs guidance on setup, configuration, or best practices
- Customer asks about plan features, integrations, or general product information
- Agent needs factual grounding before generating a response

### Trigger Conditions
- Intent classification returns: `how_to`, `bug_report`, `feature_issue`, `integration_issue`, `general`
- Customer message contains question marks or request phrases ("how do I", "what is", "help me with")
- Customer describes a problem that may have a documented solution

### Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | The customer's question or problem description. Should be the raw message or a refined version of it. |

### Outputs
| Parameter | Type | Description |
|-----------|------|-------------|
| `result` | string | Formatted knowledge base content including relevant sections, setup instructions, troubleshooting steps, and feature descriptions. |
| `sections_matched` | list[str] | Names of KB sections that matched the query. |
| `confidence` | float | Confidence score (0.0 - 1.0) indicating how well the query matched available documentation. |
| `fallback` | bool | True if no specific documentation was found. |

### Success Criteria
- Returns relevant documentation for >= 80% of product-related queries
- Response includes actionable troubleshooting steps for bug reports
- Does not hallucinate information not present in the knowledge base
- Returns fallback message gracefully when no match is found

### Related MCP Tools
- `search_knowledge_base(query: str) -> str`

### Guardrails / Safety Rules
1. **Never invent product features** -- only return information present in the knowledge base
2. **Never disclose exact pricing** -- redirect to sales team for pricing questions
3. **Do not share internal/proprietary information** -- only customer-facing documentation
4. **Limit response length** -- truncate to most relevant sections to avoid overwhelming the customer
5. **If KB returns contradictory info** -- flag for human review

### Example Usage Scenario
```
Customer (email): "Hi, I just signed up for Pro plan. How do I invite 25 team members at once?"

Agent activates SK-001:
  Input: query = "How do I invite 25 team members at once?"
  Output: 
    - sections_matched: ["Team Collaboration", "Pricing Plans"]
    - result: "To invite team members: Go to Settings > Team > Invite Members. 
               You can invite individuals by email or upload a CSV for bulk invites.
               Pro plan supports up to 50 members..."
    - confidence: 0.92
    - fallback: false
```

---

## SK-002: Sentiment Analysis & Trend

**Description:**  
Analyzes the emotional tone of a customer's message and tracks sentiment direction over time across the conversation. Detects frustration, anger, satisfaction, and neutral states to guide response tone and escalation decisions.

### When to Use
- Every incoming customer message (mandatory for all messages)
- Before generating any response (to calibrate tone)
- When evaluating whether escalation is warranted
- When tracking conversation health over multiple interactions
- When the customer's tone appears ambiguous and needs clarification

### Trigger Conditions
- **Always active** -- runs on every customer message without exception
- Re-evaluated after each message in a multi-turn conversation
- Triggered immediately if message contains emotional language indicators

### Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message` | string | Yes | The raw customer message text, unmodified. |
| `conversation_id` | string | No | If provided, includes historical sentiment data for trend analysis. |
| `previous_sentiments` | list[str] | No | List of previous sentiment values for this conversation. |

### Outputs
| Parameter | Type | Description |
|-----------|------|-------------|
| `sentiment` | string | One of: `positive`, `neutral`, `negative`, `very_negative` |
| `score` | int | Numeric score: +2 (positive), 0 (neutral), -1 (negative), -2 (very_negative) |
| `trend_direction` | string | One of: `improving`, `worsening`, `stable` |
| `requires_escalation` | bool | True if sentiment is `very_negative` |
| `guidance` | string | Recommended response approach based on sentiment |

### Sentiment Scale
```
  +2  ██████████  positive       "Thanks!", "Great help!", "Perfect!"
   0  ██████████  neutral        "How do I...?", "What is...?"
  -1  ██████████  negative       "Still not working", "Getting frustrated"
  -2  ██████████  very_negative  "This is ridiculous!", "I want a manager NOW!"
```

### Success Criteria
- Correctly identifies `very_negative` sentiment with >= 90% accuracy
- Does not produce false positives on neutral messages (e.g., "How do I reset my password?" = neutral)
- Trend direction accurately reflects change across >= 2 consecutive messages
- Word-boundary matching for profanity (no false positives like "ass" in "password")

### Related MCP Tools
- `analyze_sentiment(message: str) -> dict`
- `get_customer_history(customer_id: str) -> str` (for historical context)

### Guardrails / Safety Rules
1. **Never tell the customer their sentiment was analyzed** -- keep it internal
2. **Do not over-escalate on single negative message** -- consider trend, not just single data point
3. **Account for cultural/language differences** -- some expressions may be normal in certain contexts
4. **Profanity detection uses word boundaries** -- avoid false positives from substring matching
5. **Sentiment trend requires minimum 2 customer messages** -- single message = "stable"

### Example Usage Scenario
```
Message 1: "hi, my slack integration stopped working this morning"
  -> sentiment: neutral, score: 0, trend: stable

Message 2: "tried disconnecting and reconnecting but still nothing"
  -> sentiment: neutral, score: 0, trend: stable

Message 3: "this is ridiculous! I have a deadline today and nobody is helping me!"
  -> sentiment: very_negative, score: -2, trend: worsening
  -> requires_escalation: true
  -> guidance: "Customer is very upset. Consider immediate escalation to human agent."
```

---

## SK-003: Escalation Decision

**Description:**  
Evaluates whether a customer interaction requires immediate handoff to a human agent. Applies configurable escalation rules based on intent, sentiment, keywords, conversation history, and safety policies. This is the most critical skill -- false negatives (failing to escalate) are far worse than false positives.

### When to Use
- After intent classification and sentiment analysis are complete
- Before generating any response to the customer
- When customer explicitly requests human assistance
- When conversation involves pricing, billing, legal, security, or data loss
- When sentiment is `very_negative` or trend is `worsening`
- When the agent cannot resolve the issue after multiple KB searches

### Trigger Conditions
- Intent is `pricing_billing`, `account_management`, or `security_legal`
- Sentiment is `very_negative`
- Customer message contains human-request keywords ("speak to manager", "real person", etc.)
- Conversation sentiment trend is `worsening`
- KB search has failed to resolve the issue after 2+ attempts
- Customer mentions churn, cancellation, legal action, or data breach

### Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | string | Yes | The customer's message text. |
| `subject` | string | No | Email subject line (if applicable). |
| `intent` | string | Yes | Classified intent category. |
| `sentiment` | string | Yes | Current sentiment analysis result. |
| `sentiment_trend` | string | No | Trend direction from SK-002. |
| `kb_searches_used` | int | Yes | Number of KB searches attempted for this issue. |
| `conversation_history` | list | No | Previous messages in this conversation. |
| `escalation_history` | list | No | Previous escalations for this customer. |

### Outputs
| Parameter | Type | Description |
|-----------|------|-------------|
| `should_escalate` | bool | True if escalation is required. |
| `reason` | string | Human-readable explanation of why escalation is needed. |
| `confidence` | float | Confidence in the escalation decision (0.0 - 1.0). |
| `rule_triggered` | string | ID of the escalation rule that was triggered (e.g., "ESC-001"). |
| `urgency` | string | One of: `immediate`, `high`, `standard`. |

### Escalation Rules Matrix
| Rule ID | Trigger | Urgency | Auto-Escalate |
|---------|---------|---------|---------------|
| ESC-001 | Pricing / Billing / Refunds / Contracts | High | Yes |
| ESC-002 | Angry Customer (very_negative sentiment) | Immediate | Yes |
| ESC-003 | Customer requests human/manager/real person | Immediate | Yes |
| ESC-004 | Security / Legal / Data Loss | Immediate | Yes |
| ESC-005 | Worsening sentiment trend across interactions | High | Yes |
| ESC-006 | KB search failed 2+ times without resolution | Standard | Yes |

### Success Criteria
- **Zero false negatives** on ESC-002, ESC-003, ESC-004 (anger, human request, security)
- Escalation reason is always clear and actionable for the human agent
- Does not escalate on standard how-to questions that KB can answer
- Handles edge cases: sarcasm, indirect requests, multi-language messages

### Related MCP Tools
- `escalate_to_human(ticket_id: str, reason: str) -> str`
- `analyze_sentiment(message: str) -> dict`
- `get_customer_history(customer_id: str) -> str`
- `create_ticket(customer_id, issue, priority, channel) -> str`

### Guardrails / Safety Rules
1. **When in doubt, escalate** -- false negatives are worse than false positives
2. **Never attempt to handle security/legal issues** -- always escalate immediately
3. **Never argue with or try to placate an angry customer beyond one attempt**
4. **Include full context in escalation handoff** -- conversation history, sentiment trend, what was already tried
5. **Do not reveal internal escalation logic to the customer**
6. **If customer was previously escalated, increase urgency**

### Example Usage Scenario
```
Customer (whatsapp): "this is ridiculous! I've been waiting for 2 hours and nobody helped me. I want to speak to a manager NOW"

Agent evaluates escalation rules:
  ESC-001 (pricing): No match
  ESC-002 (anger): MATCH -- sentiment is very_negative
  ESC-003 (human request): MATCH -- "speak to a manager"
  ESC-004 (security): No match
  ESC-005 (worsening trend): No match (first negative message)

Output:
  should_escalate: true
  reason: "Customer shows signs of significant frustration or anger AND explicitly requested to speak to a manager."
  confidence: 0.98
  rule_triggered: "ESC-002, ESC-003"
  urgency: "immediate"
```

---

## SK-004: Channel Adaptation

**Description:**  
Transforms the agent's core response into channel-appropriate formatting, tone, and length. Ensures the brand voice is consistent with the communication channel while delivering the same underlying information.

### When to Use
- After the agent has determined the content of its response
- Before sending any response back to the customer
- When the customer switches channels mid-conversation
- When formatting escalation handoff messages

### Trigger Conditions
- Response content is ready and needs channel-specific formatting
- Customer's channel is identified (email, whatsapp, web_form)
- Multi-channel conversation requires consistent tone across channels

### Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message` | string | Yes | The core response content (unformatted). |
| `channel` | string | Yes | Target channel: `email`, `whatsapp`, `web_form`. |
| `is_escalation` | bool | No | Whether this is an escalation handoff message. |
| `context_prefix` | string | No | Conversation-aware opening line (from SK-005). |
| `customer_name` | string | No | Customer's name for personalization. |

### Outputs
| Parameter | Type | Description |
|-----------|------|-------------|
| `formatted_response` | string | Channel-appropriate response with correct greeting, tone, length, and sign-off. |
| `character_count` | int | Total length of the formatted response. |
| `truncated` | bool | True if the message was truncated to fit channel limits. |

### Channel Specifications

#### EMAIL
| Attribute | Specification |
|-----------|--------------|
| **Tone** | Formal, professional, empathetic |
| **Greeting** | "Dear Valued Customer," or "Dear [Name]," |
| **Structure** | Acknowledge -> Answer -> Offer further help -> Sign-off |
| **Sign-off** | "Best regards,\nFlowSync Customer Success Team" |
| **Max Length** | No strict limit, but keep under 2000 characters |
| **Formatting** | Supports paragraphs, bullet points, numbered lists |
| **Emoji** | Avoid |

#### WHATSAPP
| Attribute | Specification |
|-----------|--------------|
| **Tone** | Casual, friendly, concise |
| **Greeting** | "Hey!" or "Hi there!" or none |
| **Structure** | Direct answer -> Quick follow-up offer |
| **Sign-off** | "Let me know if you need more help!" |
| **Max Length** | 280 characters recommended (mobile-friendly) |
| **Formatting** | Plain text only, minimal structure |
| **Emoji** | Acceptable (1 max, at end) |

#### WEB_FORM
| Attribute | Specification |
|-----------|--------------|
| **Tone** | Semi-formal, clear, solution-focused |
| **Greeting** | "Thanks for reaching out!" or "Thanks for your message!" |
| **Structure** | Answer -> Follow-up option -> Sign-off |
| **Sign-off** | "Best,\nFlowSync Support" |
| **Max Length** | 1000 characters recommended |
| **Formatting** | Supports paragraphs and bullet points |
| **Emoji** | Avoid |

### Success Criteria
- Email responses are formal and detailed with proper greeting/sign-off
- WhatsApp responses are concise (under 280 chars when possible) and casual
- Web form responses are balanced -- clear but not overly formal
- Same core information is conveyed across all channels
- Channel switch is acknowledged naturally when customer changes channels

### Related MCP Tools
- `send_response(ticket_id: str, message: str, channel: str) -> str`

### Guardrails / Safety Rules
1. **Never exceed WhatsApp character limits** -- truncate and offer to send more via email
2. **Never use casual tone in escalation messages** -- always use formal tone for escalations
3. **Preserve factual accuracy** -- formatting changes must not alter the meaning
4. **Do not mix channel styles** -- email response should never use WhatsApp-style casualness
5. **When customer switches channels, acknowledge it briefly** -- "I see you're reaching out from email now..."

### Example Usage Scenario
```
Core message: "To invite team members, go to Settings > Team > Invite Members. 
               You can invite by email or upload a CSV for bulk invites."

EMAIL output:
  "Dear Valued Customer,
   
   Thank you for your question! I'd be happy to help you with that.
   
   To invite team members, go to Settings > Team > Invite Members. You can 
   invite individuals by email or upload a CSV for bulk invites.
   
   If you need any further assistance, please don't hesitate to reach out.
   
   Best regards,
   FlowSync Customer Success Team"

WHATSAPP output:
  "Hey! Here's what you need to do:
   
   Go to Settings > Team > Invite Members. You can invite by email or 
   upload a CSV for bulk invites.
   
   Let me know if you need more help!"
```

---

## SK-005: Customer Identification & Memory

**Description:**  
Resolves customer identity across channels, retrieves conversation history, and maintains contextual awareness throughout multi-turn interactions. Ensures the agent remembers what was discussed previously, tracks topics and sentiment trends, and provides a seamless experience even when customers switch between email, WhatsApp, and web forms.

### When to Use
- On every incoming message (before any other skill)
- When a customer contacts support through a different channel than before
- When generating a response that should reference prior conversation
- When evaluating escalation based on conversation history
- When the customer asks a follow-up question referencing earlier discussion

### Trigger Conditions
- New message arrives with customer identifier (email or phone)
- Customer sends a follow-up message ("still not working", "any update?")
- Customer references prior conversation ("you mentioned earlier...")
- Agent needs to check if this customer has been seen before
- Sentiment trend analysis requires historical data

### Inputs
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `identifier` | string | Yes | Customer email or phone number. |
| `channel` | string | Yes | Current channel of contact. |
| `max_history_messages` | int | No | Maximum number of recent messages to retrieve (default: 5). |

### Outputs
| Parameter | Type | Description |
|-----------|------|-------------|
| `customer_id` | string | Resolved unique customer identifier. |
| `is_new_customer` | bool | True if this is the customer's first interaction. |
| `conversation_id` | string | Unique conversation thread ID. |
| `message_count` | int | Total messages exchanged in this conversation. |
| `topics` | list[str] | Topics discussed across the conversation. |
| `sentiment_trend` | string | Direction of sentiment change: `improving`, `worsening`, `stable`. |
| `resolution_status` | string | Current status: `open`, `in_progress`, `resolved`, `escalated`. |
| `last_channel_used` | string | Previous channel of contact. |
| `channel_switched` | bool | True if customer changed channels since last message. |
| `recent_messages` | list[dict] | Last N messages with role, content, channel, timestamp. |
| `context_summary` | string | Human-readable summary for agent context injection. |

### Customer Resolution Logic
```
Priority order for identity resolution:
  1. Exact email match in conversation store -> return existing conversation
  2. Exact phone match in conversation store -> return existing conversation
  3. Email in conversation with matching phone cross-reference -> return existing conversation
  4. No match found -> create new conversation, assign new conversation_id
```

### Success Criteria
- Same customer contacting via email then WhatsApp resolves to the same conversation
- Conversation history is accurately retrieved and presented to the agent
- Sentiment trend correctly reflects changes across multiple messages
- Channel switch is detected and reported
- New customers are correctly identified as first-time contacts

### Related MCP Tools
- `get_or_create_customer(identifier: str, channel: str) -> str`
- `get_customer_history(customer_id: str) -> str`
- `create_ticket(customer_id, issue, priority, channel) -> str`

### Guardrails / Safety Rules
1. **Never merge different customers** -- only merge when email/phone exactly matches
2. **Do not expose internal conversation IDs to customers**
3. **Limit history retrieval to last 5-10 messages** -- avoid context overflow
4. **Do not assume identity from partial information** -- require exact email or phone match
5. **Respect data privacy** -- only retrieve history for the identified customer
6. **Track channel switches but do not penalize customers** for using multiple channels

### Example Usage Scenario
```
Message 1 (email): sara@agency.com -- "AI suggestions not working"
  -> New customer created: CONV-0002
  -> is_new_customer: true
  -> topics: ["bug_report"]

Message 2 (whatsapp): sara@agency.com -- "still no AI suggestions. tried the steps."
  -> Existing customer found: CONV-0002
  -> is_new_customer: false
  -> channel_switched: true (email -> whatsapp)
  -> topics: ["bug_report", "follow_up"]
  -> sentiment_trend: stable
  -> context_summary: "Customer previously reported AI suggestions not working via email. 
                       Agent provided troubleshooting steps. Customer followed up on WhatsApp 
                       saying steps didn't work."

Message 3 (whatsapp): sara@agency.com -- "this is getting frustrating. it's been a whole day."
  -> Existing customer: CONV-0002
  -> sentiment_trend: worsening (neutral -> neutral -> negative)
  -> topics: ["bug_report", "follow_up", "general"]
  -> Agent alerted to consider escalation (SK-003)
```

---

## Skill Interaction Map

```
                    ┌──────────────────────────────────────────────┐
                    │              INCOMING MESSAGE                 │
                    └──────────────────────┬───────────────────────┘
                                           │
                              ┌────────────▼────────────┐
                              │   SK-005: Customer ID   │  ← Always first
                              │   & Memory              │     Resolve identity, get history
                              └────────────┬────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
          ┌─────────▼─────────┐  ┌────────▼────────┐  ┌─────────▼─────────┐
          │ SK-002: Sentiment │  │  Intent Class.  │  │ SK-001: Knowledge │
          │ Analysis & Trend  │  │  (part of core) │  │ Retrieval         │
          └─────────┬─────────┘  └────────┬────────┘  └─────────┬─────────┘
                    │                     │                      │
                    └─────────────────────┼──────────────────────┘
                                          │
                              ┌───────────▼───────────┐
                              │ SK-003: Escalation    │  ← Evaluates all inputs
                              │ Decision              │     Should we escalate?
                              └───────────┬───────────┘
                                          │
                          ┌───────────────┼───────────────┐
                          │                               │
                  ┌───────▼───────┐               ┌───────▼───────┐
                  │  ESCALATE     │               │  NO ESCALATE  │
                  │  (handoff)    │               │  (respond)    │
                  └───────┬───────┘               └───────┬───────┘
                          │                               │
                          │                   ┌───────────▼───────────┐
                          │                   │ SK-004: Channel       │
                          │                   │ Adaptation            │
                          │                   └───────────┬───────────┘
                          │                               │
                          │                   ┌───────────▼───────────┐
                          │                   │  Send Response        │
                          │                   │  (via MCP tool)       │
                          │                   └───────────────────────┘
                          │
                  ┌───────▼───────┐
                  │  Escalate to  │
                  │  Human Agent  │
                  │  (via MCP)    │
                  └───────────────┘
```

## Skill Execution Order

For every incoming message, the agent executes skills in this order:

1. **SK-005** -- Resolve customer identity, retrieve conversation history
2. **SK-002** -- Analyze sentiment of current message, update trend
3. **SK-001** -- Search knowledge base for relevant information
4. **SK-003** -- Evaluate escalation rules using all gathered context
5. **SK-004** -- Format response for the customer's channel

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-09 | Initial skills manifest created for Incubation Phase |

---

*End of Agent Skills Manifest*
