# Discovery Log — Hackathon 5: Customer Success Digital FTE

**Project:** FlowSync Customer Success AI Agent  
**Company:** TechCorp  
**Date:** 2026-04-08  
**Exercise:** 1.1 — Initial Exploration  

---

## 1. Context Analysis

### 1.1 Company Profile
| Attribute | Detail |
|-----------|--------|
| **Company** | TechCorp |
| **Product** | FlowSync — AI-powered project management & team collaboration |
| **Founded** | 2022 |
| **Customer Base** | 8,500+ teams |
| **Target Segments** | Product managers, engineering teams, marketing agencies, remote-first companies |
| **Pricing Tiers** | Starter, Pro, Enterprise (no exact pricing disclosed) |

**Implications:**
- Large customer base → high ticket volume expected → automation is critical
- B2B SaaS → customers expect professional, timely responses
- Multiple target segments → questions will vary by use case (engineering vs. marketing workflows)
- Pricing tiers exist but are abstracted → agent must deflect exact pricing questions and escalate

### 1.2 Product Feature Map
| Feature | Category | Support Implications |
|---------|----------|---------------------|
| AI Task Suggestions | AI/ML | May have accuracy issues, false positives, or "no recommendations" scenarios |
| Smart Dashboards | UI/Analytics | Questions about setup, customization, data interpretation |
| Team Collaboration | Core Feature | Permissions, invites, @mentions, real-time chat issues |
| Integrations (Slack, Google Drive, GitHub, Figma, Zoom) | Ecosystem | Sync failures, auth issues, webhook errors, rate limits |
| AI Meeting Summarizer | AI/ML | Quality concerns, transcription errors, language support |
| Resource Planner | Planning | Capacity questions, allocation conflicts |
| Custom Workflows (no-code) | Automation | Setup help, debugging, best practices |

### 1.3 Brand Voice Requirements
| Channel | Tone | Style |
|---------|------|-------|
| **Email** | Formal, professional | Detailed, structured, empathetic |
| **WhatsApp** | Casual, friendly | Concise, direct, conversational |
| **Web Form** | Balanced | Clear, solution-focused, moderate length |

### 1.4 Escalation Rules (Non-Negotiable)
The agent **MUST** escalate immediately when:
1. Pricing, billing, refunds, contracts are mentioned
2. Customer shows anger (profanity, repeated frustration)
3. Cannot resolve after 2 knowledge base searches
4. Customer explicitly requests human/manager/real person
5. Legal, security, or data loss issues arise

---

## 2. Sample Ticket Analysis

### 2.1 Ticket Breakdown

| # | Channel | Customer | Topic | Type | Urgency |
|---|---------|----------|-------|------|---------|
| 1 | Email | ahmed@startup.io | Team invitation (25 members) | How-to / Onboarding | Medium |
| 2 | WhatsApp | +923001234567 | Slack sync not working | Bug / Integration | High |
| 3 | Web Form | sara@agency.com | AI suggestions not working | Bug / Feature Issue | Medium |
| 4 | Email | mike@techflow.dev | Enterprise pricing inquiry | Pricing (ESCALATE) | High |

### 2.2 Channel-Specific Patterns

#### Email
- **Structure:** Formal greeting, context provided, clear question
- **Length:** Longer, more detailed
- **Customer Info:** Always includes email, often includes subject line
- **Common Topics:** Onboarding, billing, feature inquiries, account management
- **Response Style:** Formal greeting → Acknowledge → Detailed steps → Offer further help → Professional sign-off
- **Metadata Available:** `customer_email`, `subject`, `content`

#### WhatsApp
- **Structure:** Casual, no greeting, direct problem statement
- **Length:** Very short, often fragmented sentences
- **Customer Info:** Phone number only
- **Common Topics:** Urgent bugs, sync issues, quick how-to questions
- **Response Style:** Friendly acknowledgment → Quick fix/steps → "Let me know if that helps!"
- **Metadata Available:** `customer_phone` only
- **Special Considerations:** May include typos, abbreviations ("pls", "u"), lowercase

#### Web Form
- **Structure:** Semi-formal, structured but less formal than email
- **Length:** Moderate
- **Customer Info:** Email + subject + content
- **Common Topics:** Feature issues, feedback, bug reports
- **Response Style:** Acknowledge → Explain → Provide solution → Follow-up option
- **Metadata Available:** `customer_email`, `subject`, `content`

### 2.3 Common Question Types (Taxonomy)

| Category | Description | Example | Resolution Path |
|----------|-------------|---------|-----------------|
| **How-To** | Step-by-step guidance | "How do I invite 25 team members?" | Knowledge base lookup → Structured response |
| **Bug Report** | Feature not working | "Tasks not syncing with Slack" | Diagnose → Troubleshoot → Escalate if unresolved |
| **Feature Issue** | Feature underperforming | "AI suggestions not giving recommendations" | Check known issues → Troubleshoot → Escalate |
| **Pricing/Billing** | Cost, plans, payments | "What's Enterprise pricing?" | **ESCALATE IMMEDIATELY** |
| **Account Management** | Plan changes, cancellations | "How to downgrade?" | **ESCALATE** |
| **Integration** | Third-party connectivity | "GitHub not connecting" | Troubleshoot → Escalate |
| **Security/Legal** | Data, compliance | "Where is my data stored?" | **ESCALATE IMMEDIATELY** |

---

## 3. Hidden Requirements Discovery

### 3.1 Explicit Requirements (Given)
- [x] Handle Gmail, WhatsApp, Web Form
- [x] Follow brand voice per channel
- [x] Follow escalation rules
- [x] Use knowledge base for answers

### 3.2 Implicit Requirements (Discovered)

| # | Requirement | Justification |
|---|-------------|---------------|
| H1 | **Multi-channel message routing** | Each channel has different input formats, APIs, and response styles |
| H2 | **Channel-aware response formatting** | Email needs HTML formatting; WhatsApp needs plain text with character limits |
| H3 | **Customer identity resolution** | Same customer may reach out via email AND WhatsApp — need unified customer profile |
| H4 | **Conversation state management** | Multi-turn conversations require memory of previous messages |
| H5 | **Knowledge base search & retrieval** | Agent needs RAG (Retrieval-Augmented Generation) over product docs |
| H6 | **Sentiment analysis** | Detect anger/frustration for escalation triggers |
| H7 | **Intent classification** | Route to correct resolution path (how-to vs. bug vs. pricing) |
| H8 | **Ticket lifecycle management** | Open → In Progress → Resolved → Closed with timestamps |
| H9 | **SLA tracking** | Response time targets per channel (email: 4hrs, WhatsApp: 15min, web: 2hrs) |
| H10 | **Fallback handling** | When KB search fails twice, escalate gracefully |
| H11 | **Rate limiting & abuse prevention** | Prevent spam or repeated identical queries |
| H12 | **Audit logging** | Every action, decision, and escalation must be logged for compliance |
| H13 | **Human handoff protocol** | Smooth transfer with full context when escalating |
| H14 | **Multi-language support** | Customer phone numbers suggest international base (e.g., +92 Pakistan) |
| H15 | **Attachment handling** | Emails may include screenshots; web forms may allow file uploads |
| H16 | **Template management** | Pre-built response templates for common scenarios |
| H17 | **Analytics & reporting** | Track resolution rate, escalation rate, CSAT, response times |
| H18 | **Testing harness** | Ability to replay sample tickets and validate responses |
| H19 | **Configuration management** | Escalation rules, brand voice, KB content should be configurable without code changes |
| H20 | **Graceful degradation** | If LLM is unavailable, fall back to template-based responses |

---

## 4. Edge Cases

| # | Edge Case | Impact | Mitigation |
|---|-----------|--------|------------|
| E1 | Customer sends blank message | Low | Prompt: "Could you please describe your issue?" |
| E2 | Customer sends gibberish/spam | Low | Detect & respond: "I didn't understand. Can you rephrase?" |
| E3 | Customer switches mid-conversation from WhatsApp to email | Medium | Identity resolution needed; merge conversation threads |
| E4 | Customer asks multiple questions in one message | Medium | Parse & address each; or ask to prioritize |
| E5 | Customer provides incorrect info (wrong email, phone) | Medium | Validate before acting |
| E6 | Knowledge base has outdated/contradictory info | High | Version control KB; flag conflicts |
| E7 | LLM hallucinates incorrect product info | Critical | Ground responses in KB; add validation layer |
| E8 | Customer uses sarcasm ("Great, another broken feature") | Medium | Sentiment analysis must detect negative tone |
| E9 | Escalation during off-hours | High | Define after-hours protocol; queue for human team |
| E10 | Customer demands immediate response on non-urgent issue | Low | Set expectations: "I'll help you within X minutes" |
| E11 | Integration outage (Slack API down) | High | Detect via status page; inform customer proactively |
| E12 | Customer shares sensitive data (passwords, API keys) | Critical | Auto-redact; warn customer; log securely |
| E13 | Repeated same question from same customer | Low | Detect loop; offer escalation |
| E14 | Customer asks about competitor features | Low | Deflect politely; focus on FlowSync strengths |
| E15 | Web form submission with extremely long description | Medium | Summarize; extract key issue |
| E16 | Customer asks "Are you a bot?" | Medium | Transparent response per brand voice |
| E17 | Timezone confusion in responses | Low | Use customer's local timezone when possible |
| E18 | Customer references old conversation | Medium | Access conversation history |
| E19 | Multiple customers reporting same bug simultaneously | High | Detect pattern; link tickets; bulk update |
| E20 | Customer threatens to cancel/churn | Critical | Escalate immediately; flag as retention risk |

---

## 5. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CUSTOMER SUCCESS AI FTE                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐                     │
│  │  Gmail   │  │  WhatsApp    │  │  Web Form │  ← CHANNEL LAYER    │
│  │  API     │  │  Business    │  │  Endpoint │                     │
│  └────┬─────┘  └──────┬───────┘  └─────┬─────┘                     │
│       │               │                │                            │
│       └───────────────┼────────────────┘                            │
│                       │                                             │
│              ┌────────▼────────┐                                    │
│              │  Ingestion &    │  ← Normalize all channels to       │
│              │  Normalization  │    unified Ticket schema           │
│              └────────┬────────┘                                    │
│                       │                                             │
│       ┌───────────────▼───────────────┐                             │
│       │        ORCHESTRATOR           │                             │
│       │  (LangGraph / State Machine)  │                             │
│       ├───────────────────────────────┤                             │
│       │  1. Parse & Classify Intent   │                             │
│       │  2. Analyze Sentiment         │                             │
│       │  3. Check Escalation Rules    │                             │
│       │  4. Search Knowledge Base     │                             │
│       │  5. Generate Response         │                             │
│       │  6. Format for Channel        │                             │
│       │  7. Log & Track               │                             │
│       └───────────────┬───────────────┘                             │
│                       │                                             │
│       ┌───────────────┼───────────────┐                             │
│       │               │               │                             │
│  ┌────▼────┐   ┌──────▼──────┐  ┌────▼─────┐                      │
│  │ Intent  │   │  Sentiment  │  │Escalation│                      │
│  │ Classifier│  │  Analyzer   │  │  Engine  │                      │
│  └────┬────┘   └──────┬──────┘  └────┬─────┘                      │
│       │               │               │                             │
│  ┌────▼───────────────▼───────────────▼────┐                       │
│  │          KNOWLEDGE LAYER                │                       │
│  │  ┌─────────────┐  ┌──────────────────┐ │                       │
│  │  │ Vector DB   │  │  Product Docs    │ │                       │
│  │  │ (Chroma/    │  │  KB Articles     │ │                       │
│  │  │  FAISS)     │  │  FAQ Database    │ │                       │
│  │  └─────────────┘  └──────────────────┘ │                       │
│  └────────────────────┬────────────────────┘                       │
│                       │                                             │
│  ┌────────────────────▼────────────────────┐                       │
│  │          RESPONSE GENERATION            │                       │
│  │  ┌─────────────┐  ┌──────────────────┐ │                       │
│  │  │ LLM Engine  │  │  Template Engine │ │                       │
│  │  │ (GPT-4/     │  │  (Fallback &     │ │                       │
│  │  │  Claude)    │  │   Common Cases)  │ │                       │
│  │  └─────────────┘  └──────────────────┘ │                       │
│  └────────────────────┬────────────────────┘                       │
│                       │                                             │
│  ┌────────────────────▼────────────────────┐                       │
│  │          OUTPUT & DELIVERY              │                       │
│  │  ┌─────────────┐  ┌──────────────────┐ │                       │
│  │  │ Channel     │  │  Response        │ │                       │
│  │  │ Formatter   │  │  Dispatcher      │ │                       │
│  │  └─────────────┘  └──────────────────┘ │                       │
│  └────────────────────┬────────────────────┘                       │
│                       │                                             │
│  ┌────────────────────▼────────────────────┐                       │
│  │          PERSISTENCE & LOGGING          │                       │
│  │  ┌─────────────┐  ┌──────────────────┐ │                       │
│  │  │ Ticket DB   │  │  Audit Log       │ │                       │
│  │  │ (SQLite/    │  │  Analytics       │ │                       │
│  │  │  Postgres)  │  │  Dashboard       │ │                       │
│  │  └─────────────┘  └──────────────────┘ │                       │
│  └─────────────────────────────────────────┘                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Architecture Components

| Layer | Component | Technology Options |
|-------|-----------|-------------------|
| **Channel Layer** | Gmail API, WhatsApp Business API, Web Form endpoint | `google-api-python-client`, `twilio`, FastAPI endpoint |
| **Ingestion** | Message normalizer | Pydantic models for unified schema |
| **Orchestrator** | State machine / workflow | LangGraph, LangChain Agents, or custom state machine |
| **Intent Classifier** | Categorize ticket type | LLM-based classification or lightweight ML model |
| **Sentiment Analyzer** | Detect frustration/anger | LLM prompt or dedicated sentiment model |
| **Escalation Engine** | Rule-based decision engine | Configurable rule evaluator |
| **Knowledge Layer** | RAG pipeline | ChromaDB / FAISS + embedding model |
| **Response Generation** | LLM + templates | OpenAI GPT-4 / Claude + Jinja2 templates |
| **Output Layer** | Channel-specific formatter | HTML for email, plain text for WhatsApp |
| **Persistence** | Ticket & audit storage | SQLite (dev) → PostgreSQL (prod) |

---

## 6. Recommended Next Steps (Exercise 1.2)

### Phase 1: Foundation (Day 1-2)
1. **Set up project structure** — Create modular directory layout
2. **Define data models** — Ticket, Customer, Response, Escalation schemas (Pydantic)
3. **Build knowledge base** — Create product docs as searchable vector store
4. **Create sample test harness** — Load `sample-tickets.json` for testing

### Phase 2: Core Agent (Day 2-3)
5. **Build intent classifier** — Categorize tickets (how-to, bug, pricing, etc.)
6. **Build sentiment analyzer** — Detect escalation triggers
7. **Implement escalation engine** — Rule-based routing
8. **Build RAG pipeline** — KB search → context → response generation

### Phase 3: Channel Integration (Day 3-4)
9. **Build channel normalizer** — Unified ticket ingestion
10. **Build response formatters** — Email (HTML), WhatsApp (plain text), Web Form (markdown)
11. **Implement brand voice** — Channel-aware prompt engineering
12. **Build dispatcher** — Route responses back to correct channel

### Phase 4: Polish & Demo (Day 4-5)
13. **Add conversation memory** — Multi-turn support
14. **Build demo UI** — Simple dashboard to view tickets & responses
15. **Add analytics** — Resolution rate, escalation rate, response times
16. **Test with sample tickets** — Validate all scenarios
17. **Prepare hackathon demo** — Live demo script + slides

---

## 7. Open Questions

| # | Question | Priority |
|---|----------|----------|
| Q1 | Should we use a specific LLM provider (OpenAI, Anthropic, open-source)? | High |
| Q2 | Do we need real-time channel integration or simulated channels for the hackathon? | High |
| Q3 | What is the expected demo format — live, recorded, or CLI-based? | Medium |
| Q4 | Should we build a UI dashboard or keep it CLI/API-based? | Medium |
| Q5 | Do we have access to actual FlowSync product docs for the KB? | Medium |
| Q6 | Are there any existing customer support workflows to replicate? | Low |
| Q7 | Should we support languages other than English? | Low |

---

*End of Discovery Log — Exercise 1.1*

---

## 8. Exercise 1.3 Completion Notes

**Date:** 2026-04-08  
**Status:** Complete

### What Was Added
- `src/memory.py` — Conversation memory module with:
  - `Message` — Individual message with role, content, channel, intent, sentiment
  - `Conversation` — Full conversation thread with metadata (ID, topics, status, sentiment trend)
  - `SentimentTrend` — Tracks sentiment direction over time (improving/worsening/stable)
  - `ConversationStore` — Central registry with cross-channel customer resolution
  - `build_context_for_agent()` — Builds context string for response generation

- `src/prototype.py` v2.0 — Updated with:
  - Conversation lookup/creation on every ticket
  - Follow-up intent detection (references to prior context)
  - Context-aware response prefixes ("Following up on your earlier question...")
  - Channel switch detection and acknowledgment
  - Sentiment trend tracking (customer-only, excluding agent messages)
  - Worsening sentiment escalation rule (ESC-005)
  - New CLI commands: `conversations` to view all active conversations

### Test Results — 3 Multi-Turn Scenarios

| Scenario | Customer | Messages | Key Behavior | Result |
|----------|----------|----------|-------------|--------|
| 1. Multi-turn email | ahmed@startup.io | 3 turns (how-to -> roles -> CSV) | Follow-up detection, sentiment improving (neutral -> positive -> positive) | Pass |
| 2. Cross-channel | sara@agency.com | email -> whatsapp -> whatsapp | Channel switch detected, sentiment worsening (neutral -> neutral -> negative) | Pass |
| 3. Worsening escalation | +14155551234 | 3 whatsapp messages | Sentiment worsening (neutral -> neutral -> very_negative), auto-escalation | Pass |

### Next Steps (Exercise 1.4)
- MCP Server integration for external tool access
- Real channel API connections (Gmail, WhatsApp Business)
- Vector-based KB search (ChromaDB/FAISS)
- LLM-powered response generation (OpenAI/Claude)
