-- ============================================================================
-- FlowSync Customer Success AI Agent -- PostgreSQL Database Schema
-- ============================================================================
-- Version: 1.0
-- Date: 2026-04-09
-- Phase: Specialization -- Exercise 2.1
--
-- Migration Notes:
--   - Requires PostgreSQL 15+ with pgvector extension
--   - Run: psql -U postgres -d flowsync -f schema.sql
--   - Or via Docker: docker exec -i flowsync-db psql -U flowsync -d flowsync -f /docker-entrypoint-initdb.d/schema.sql
--   - This is a full schema creation script (not incremental migration)
--   - For production migrations, use Alembic or Flyway
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- EXTENSIONS
-- ────────────────────────────────────────────────────────────────────────────

-- pgvector for semantic knowledge base search
CREATE EXTENSION IF NOT EXISTS vector;

-- UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ────────────────────────────────────────────────────────────────────────────
-- ENUM TYPES
-- ────────────────────────────────────────────────────────────────────────────

-- Communication channels
DO $$ BEGIN
    CREATE TYPE channel_type AS ENUM ('email', 'whatsapp', 'web_form');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Ticket priority levels
DO $$ BEGIN
    CREATE TYPE ticket_priority AS ENUM ('low', 'medium', 'high', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Ticket lifecycle states
DO $$ BEGIN
    CREATE TYPE ticket_status AS ENUM ('open', 'in_progress', 'resolved', 'escalated', 'closed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Intent classification categories
DO $$ BEGIN
    CREATE TYPE intent_type AS ENUM (
        'how_to', 'bug_report', 'feature_issue', 'pricing_billing',
        'account_management', 'integration_issue', 'security_legal',
        'general', 'follow_up'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Sentiment analysis levels
DO $$ BEGIN
    CREATE TYPE sentiment_level AS ENUM ('positive', 'neutral', 'negative', 'very_negative');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Sentiment trend direction
DO $$ BEGIN
    CREATE TYPE sentiment_trend AS ENUM ('improving', 'stable', 'worsening');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Escalation urgency
DO $$ BEGIN
    CREATE TYPE urgency_level AS ENUM ('immediate', 'high', 'standard');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Message role (who sent it)
DO $$ BEGIN
    CREATE TYPE message_role AS ENUM ('customer', 'agent', 'system');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: customers
-- Unified customer record across all channels.
-- Each customer has ONE row here, regardless of how many identifiers they have.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS customers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Customer metadata
    display_name        VARCHAR(255),
    company_name        VARCHAR(255),
    -- FlowSync account info
    flowsync_plan       VARCHAR(50),              -- 'starter', 'pro', 'enterprise'
    flowsync_account_id VARCHAR(100),
    -- Support metadata
    total_tickets       INTEGER DEFAULT 0,        -- Denormalized counter
    escalated_tickets   INTEGER DEFAULT 0,
    -- Sentiment tracking
    current_sentiment   sentiment_level DEFAULT 'neutral',
    sentiment_trend     sentiment_trend DEFAULT 'stable',
    -- Lifecycle
    first_contact_at    TIMESTAMPTZ DEFAULT NOW(),
    last_contact_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    -- Soft delete
    is_deleted          BOOLEAN DEFAULT FALSE
);

COMMENT ON TABLE customers IS 'Unified customer record. One row per customer regardless of channels.';
COMMENT ON COLUMN customers.display_name IS 'Human-readable name for display purposes.';
COMMENT ON COLUMN customers.flowsync_plan IS 'Current FlowSync subscription tier: starter, pro, or enterprise.';
COMMENT ON COLUMN customers.total_tickets IS 'Denormalized count of all tickets for quick dashboard queries.';
COMMENT ON COLUMN customers.current_sentiment IS 'Most recent sentiment from any conversation.';
COMMENT ON COLUMN customers.sentiment_trend IS 'Direction of sentiment change over recent interactions.';

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: customer_identifiers
-- Cross-channel identity resolution. One customer can have multiple identifiers
-- (email, phone, etc.) that all resolve to the same customer record.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS customer_identifiers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    -- Identifier details
    identifier_type     VARCHAR(20) NOT NULL,     -- 'email', 'phone', 'slack_id', etc.
    identifier_value    VARCHAR(255) NOT NULL,    -- Normalized value (lowercase email, E.164 phone)
    -- Channel preference
    preferred_channel   channel_type DEFAULT 'email',
    -- Verification
    is_verified         BOOLEAN DEFAULT FALSE,
    verified_at         TIMESTAMPTZ,
    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    -- Unique constraint: one identifier value per type
    CONSTRAINT uq_identifier_type_value UNIQUE (identifier_type, identifier_value)
);

COMMENT ON TABLE customer_identifiers IS 'Cross-channel identity resolution. Maps emails, phones, etc. to unified customer records.';
COMMENT ON COLUMN customer_identifiers.identifier_type IS 'Type of identifier: email, phone, slack_id, etc.';
COMMENT ON COLUMN customer_identifiers.identifier_value IS 'Normalized identifier value. Emails lowercase, phones in E.164 format.';
COMMENT ON COLUMN customer_identifiers.preferred_channel IS 'The channel this identifier is primarily associated with.';

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: conversations
-- A conversation thread between a customer and the AI agent.
-- Spans multiple messages and can cross channels.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS conversations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    -- Conversation metadata
    topic_summary       TEXT,                     -- AI-generated summary of conversation topic
    topics              TEXT[],                   -- Array of topic tags: ['integration', 'slack']
    -- Status tracking
    status              VARCHAR(20) DEFAULT 'open', -- 'open', 'in_progress', 'resolved', 'escalated'
    message_count       INTEGER DEFAULT 0,        -- Denormalized message count
    -- Sentiment tracking
    initial_sentiment   sentiment_level,
    current_sentiment   sentiment_level DEFAULT 'neutral',
    sentiment_trend     sentiment_trend DEFAULT 'stable',
    -- Channel tracking
    last_channel_used   channel_type,
    -- Escalation tracking
    escalation_count    INTEGER DEFAULT 0,
    last_escalated_at   TIMESTAMPTZ,
    -- Timestamps
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE conversations IS 'Conversation thread between customer and AI agent. Can span multiple channels.';
COMMENT ON COLUMN conversations.topic_summary IS 'AI-generated one-line summary of what this conversation is about.';
COMMENT ON COLUMN conversations.topics IS 'Array of topic tags extracted from the conversation.';
COMMENT ON COLUMN conversations.sentiment_trend IS 'Direction of sentiment change across this conversation.';
COMMENT ON COLUMN conversations.last_channel_used IS 'Most recent channel used in this conversation.';

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: messages
-- Individual messages within a conversation.
-- Tracks both customer and agent messages with full metadata.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    -- Message content
    role                message_role NOT NULL,    -- 'customer', 'agent', or 'system'
    content             TEXT NOT NULL,
    content_length      INTEGER GENERATED ALWAYS AS (LENGTH(content)) STORED,
    -- Channel info
    channel             channel_type NOT NULL,
    -- AI analysis
    intent              intent_type,
    sentiment           sentiment_level,
    -- Escalation flag
    is_escalation       BOOLEAN DEFAULT FALSE,
    escalation_reason   TEXT,
    -- Metadata
    metadata            JSONB DEFAULT '{}',       -- Additional context (attachments, links, etc.)
    -- Timestamps
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE messages IS 'Individual messages within a conversation. Tracks both customer and agent messages.';
COMMENT ON COLUMN messages.role IS 'Who sent the message: customer, agent (AI), or system (automated).';
COMMENT ON COLUMN messages.content_length IS 'Auto-computed character count for analytics.';
COMMENT ON COLUMN messages.intent IS 'AI-classified intent category for the message.';
COMMENT ON COLUMN messages.sentiment IS 'AI-analyzed sentiment of this message.';
COMMENT ON COLUMN messages.is_escalation IS 'True if this message triggered or is an escalation.';
COMMENT ON COLUMN messages.metadata IS 'JSONB for additional context: attachments, links, tool call results, etc.';

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: tickets
-- Formal support tickets tracked through the support lifecycle.
-- Linked to conversations but can exist independently.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tickets (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Human-readable ticket number
    ticket_number       VARCHAR(20) UNIQUE NOT NULL, -- e.g., 'TKT-00001'
    customer_id         UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    conversation_id     UUID REFERENCES conversations(id) ON DELETE SET NULL,
    -- Ticket details
    subject             VARCHAR(500),
    description         TEXT NOT NULL,
    priority            ticket_priority DEFAULT 'medium',
    status              ticket_status DEFAULT 'open',
    channel             channel_type NOT NULL,
    -- Assignment
    assigned_to         VARCHAR(100),             -- Human agent name (NULL = AI handled)
    -- Escalation
    is_escalated        BOOLEAN DEFAULT FALSE,
    escalation_reason   TEXT,
    escalated_at        TIMESTAMPTZ,
    escalated_by        VARCHAR(100),             -- Who escalated: 'ai_agent' or human name
    -- Resolution
    resolution_summary  TEXT,
    resolved_at         TIMESTAMPTZ,
    resolved_by         VARCHAR(100),
    -- SLA tracking
    first_response_at   TIMESTAMPTZ,
    sla_deadline        TIMESTAMPTZ,
    sla_breached        BOOLEAN DEFAULT FALSE,
    -- Timestamps
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE tickets IS 'Formal support tickets tracked through the support lifecycle.';
COMMENT ON COLUMN tickets.ticket_number IS 'Human-readable ticket ID like TKT-00001.';
COMMENT ON COLUMN tickets.assigned_to IS 'Human agent assigned to this ticket. NULL means AI is handling.';
COMMENT ON COLUMN tickets.sla_deadline IS 'SLA target time for first response based on channel and priority.';
COMMENT ON COLUMN tickets.sla_breached IS 'True if first_response_at exceeded sla_deadline.';

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: knowledge_base
-- Product documentation with vector embeddings for semantic search.
-- Each row is a searchable KB article or documentation section.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS knowledge_base (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Content
    title               VARCHAR(500) NOT NULL,
    content             TEXT NOT NULL,
    content_html        TEXT,                       -- HTML-formatted version for email responses
    -- Categorization
    category            VARCHAR(100),               -- 'features', 'integrations', 'pricing', 'faq'
    tags                TEXT[],                     -- Searchable tags: ['slack', 'sync', 'troubleshooting']
    -- Vector embedding for semantic search (384-dim for all-MiniLM-L6-v2)
    embedding             vector(384),
    -- Metadata
    source_url          VARCHAR(1000),              -- Link to original documentation
    version             VARCHAR(20) DEFAULT '1.0',
    is_active           BOOLEAN DEFAULT TRUE,
    -- Usage tracking
    search_count        INTEGER DEFAULT 0,
    helpful_count       INTEGER DEFAULT 0,
    -- Timestamps
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE knowledge_base IS 'Product documentation with vector embeddings for semantic search.';
COMMENT ON COLUMN knowledge_base.embedding IS '384-dimensional vector embedding from all-MiniLM-L6-v2 model.';
COMMENT ON COLUMN knowledge_base.search_count IS 'How many times this article was returned in search results.';
COMMENT ON COLUMN knowledge_base.helpful_count IS 'How many times customers marked this article as helpful.';

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: channel_configs
-- Configuration for each communication channel.
-- Controls behavior, SLAs, formatting rules, and API credentials.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS channel_configs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel             channel_type UNIQUE NOT NULL,
    -- Behavior settings
    is_enabled          BOOLEAN DEFAULT TRUE,
    max_response_length INTEGER,                  -- Character limit for responses
    response_timeout_sec INTEGER DEFAULT 300,     -- Max time to generate response
    -- SLA settings
    sla_response_min    INTEGER,                  -- Target response time in minutes
    sla_escalation_min  INTEGER,                  -- Time before auto-escalation
    -- Formatting
    greeting_template   TEXT,
    sign_off_template   TEXT,
    tone                VARCHAR(50),              -- 'formal', 'casual', 'semi-formal'
    -- API credentials (encrypted in production)
    api_config          JSONB DEFAULT '{}',        -- Channel-specific API settings
    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE channel_configs IS 'Configuration for each communication channel: behavior, SLAs, formatting, API settings.';
COMMENT ON COLUMN channel_configs.api_config IS 'JSONB for channel-specific API credentials and settings (encrypted in production).';

-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: agent_metrics
-- Performance metrics for the AI agent, tracked per time window.
-- Used for monitoring, alerting, and continuous improvement.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_metrics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Time window
    window_start        TIMESTAMPTZ NOT NULL,
    window_end          TIMESTAMPTZ NOT NULL,
    -- Volume metrics
    total_messages      INTEGER DEFAULT 0,
    total_tickets       INTEGER DEFAULT 0,
    total_conversations INTEGER DEFAULT 0,
    -- Resolution metrics
    resolved_count      INTEGER DEFAULT 0,
    escalated_count     INTEGER DEFAULT 0,
    resolution_rate     NUMERIC(5, 2),            -- Percentage resolved without escalation
    escalation_rate     NUMERIC(5, 2),            -- Percentage escalated
    -- Response time metrics
    avg_response_time_ms NUMERIC(10, 2),          -- Average AI response generation time
    p50_response_time_ms NUMERIC(10, 2),
    p95_response_time_ms NUMERIC(10, 2),
    p99_response_time_ms NUMERIC(10, 2),
    -- Sentiment metrics
    avg_sentiment_score NUMERIC(3, 2),            -- Average sentiment score (-2 to +2)
    sentiment_improving_count INTEGER DEFAULT 0,
    sentiment_worsening_count INTEGER DEFAULT 0,
    -- Intent distribution
    intent_distribution JSONB DEFAULT '{}',        -- {'how_to': 45, 'bug_report': 20, ...}
    -- Channel distribution
    channel_distribution JSONB DEFAULT '{}',       -- {'email': 60, 'whatsapp': 30, 'web_form': 10}
    -- Quality metrics
    kb_hit_rate         NUMERIC(5, 2),            -- Percentage of queries with KB match
    avg_kb_confidence   NUMERIC(3, 2),            -- Average confidence of KB matches
    -- Timestamps
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE agent_metrics IS 'Performance metrics for the AI agent, aggregated per time window.';
COMMENT ON COLUMN agent_metrics.resolution_rate IS 'Percentage of tickets resolved without human escalation.';
COMMENT ON COLUMN agent_metrics.kb_hit_rate IS 'Percentage of queries where knowledge base returned relevant results.';
COMMENT ON COLUMN agent_metrics.intent_distribution IS 'JSONB map of intent categories to counts for this window.';

-- ────────────────────────────────────────────────────────────────────────────
-- INDEXES
-- ────────────────────────────────────────────────────────────────────────────

-- Customer lookups (most frequent query)
CREATE INDEX IF NOT EXISTS idx_customers_email
    ON customers ((SELECT identifier_value FROM customer_identifiers WHERE customer_id = customers.id AND identifier_type = 'email' LIMIT 1));

CREATE INDEX IF NOT EXISTS idx_customer_identifiers_lookup
    ON customer_identifiers (identifier_type, identifier_value);

CREATE INDEX IF NOT EXISTS idx_customer_identifiers_customer
    ON customer_identifiers (customer_id);

-- Conversation queries
CREATE INDEX IF NOT EXISTS idx_conversations_customer
    ON conversations (customer_id);

CREATE INDEX IF NOT EXISTS idx_conversations_status
    ON conversations (status);

CREATE INDEX IF NOT EXISTS idx_conversations_updated
    ON conversations (updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversations_sentiment
    ON conversations (sentiment_trend);

-- Message queries
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages (conversation_id);

CREATE INDEX IF NOT EXISTS idx_messages_created
    ON messages (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
    ON messages (conversation_id, created_at);

CREATE INDEX IF NOT EXISTS idx_messages_sentiment
    ON messages (sentiment);

CREATE INDEX IF NOT EXISTS idx_messages_intent
    ON messages (intent);

-- Ticket queries
CREATE INDEX IF NOT EXISTS idx_tickets_customer
    ON tickets (customer_id);

CREATE INDEX IF NOT EXISTS idx_tickets_status
    ON tickets (status);

CREATE INDEX IF NOT EXISTS idx_tickets_priority
    ON tickets (priority);

CREATE INDEX IF NOT EXISTS idx_tickets_created
    ON tickets (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tickets_escalated
    ON tickets (is_escalated) WHERE is_escalated = TRUE;

CREATE INDEX IF NOT EXISTS idx_tickets_sla_breached
    ON tickets (sla_breached) WHERE sla_breached = TRUE;

CREATE INDEX IF NOT EXISTS idx_tickets_number
    ON tickets (ticket_number);

-- Knowledge base vector search (HNSW index for approximate nearest neighbor)
CREATE INDEX IF NOT EXISTS idx_knowledge_base_embedding
    ON knowledge_base
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Knowledge base text search (full-text search fallback)
CREATE INDEX IF NOT EXISTS idx_knowledge_base_search
    ON knowledge_base USING GIN (
        to_tsvector('english', title || ' ' || content)
    );

CREATE INDEX IF NOT EXISTS idx_knowledge_base_category
    ON knowledge_base (category);

CREATE INDEX IF NOT EXISTS idx_knowledge_base_active
    ON knowledge_base (is_active) WHERE is_active = TRUE;

-- Channel configs
CREATE INDEX IF NOT EXISTS idx_channel_configs_channel
    ON channel_configs (channel);

-- Agent metrics
CREATE INDEX IF NOT EXISTS idx_agent_metrics_window
    ON agent_metrics (window_start, window_end);

CREATE INDEX IF NOT EXISTS idx_agent_metrics_created
    ON agent_metrics (created_at DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- FUNCTIONS & TRIGGERS
-- ────────────────────────────────────────────────────────────────────────────

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables with updated_at
CREATE TRIGGER trg_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_tickets_updated_at
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_knowledge_base_updated_at
    BEFORE UPDATE ON knowledge_base
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_channel_configs_updated_at
    BEFORE UPDATE ON channel_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-increment conversation message_count
CREATE OR REPLACE FUNCTION increment_message_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations
    SET message_count = message_count + 1,
        updated_at = NOW()
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_messages_increment_count
    AFTER INSERT ON messages
    FOR EACH ROW EXECUTE FUNCTION increment_message_count();

-- Auto-generate ticket number
CREATE OR REPLACE FUNCTION generate_ticket_number()
RETURNS TRIGGER AS $$
DECLARE
    next_num INTEGER;
BEGIN
    IF NEW.ticket_number IS NULL OR NEW.ticket_number = '' THEN
        SELECT COALESCE(MAX(CAST(SUBSTRING(ticket_number FROM 5) AS INTEGER)), 0) + 1
        INTO next_num
        FROM tickets;
        NEW.ticket_number := 'TKT-' || LPAD(next_num::TEXT, 5, '0');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tickets_generate_number
    BEFORE INSERT ON tickets
    FOR EACH ROW EXECUTE FUNCTION generate_ticket_number();

-- ────────────────────────────────────────────────────────────────────────────
-- SEED DATA
-- ────────────────────────────────────────────────────────────────────────────

-- Channel configurations
INSERT INTO channel_configs (channel, is_enabled, max_response_length, response_timeout_sec,
                              sla_response_min, sla_escalation_min, greeting_template,
                              sign_off_template, tone, api_config)
VALUES
    ('email', TRUE, 2000, 300, 240, 480,
     'Dear Valued Customer,',
     'Best regards,\nFlowSync Customer Success Team',
     'formal',
     '{"smtp_host": "smtp.flowsync.com", "from_address": "support@flowsync.com"}'::jsonb),

    ('whatsapp', TRUE, 280, 60, 15, 30,
     'Hey!',
     'Let me know if you need more help!',
     'casual',
     '{"api_version": "v17.0", "phone_number_id": ""}'::jsonb),

    ('web_form', TRUE, 1000, 120, 120, 240,
     'Thanks for your message!',
     'Best,\nFlowSync Support',
     'semi-formal',
     '{"form_endpoint": "/api/support", "max_file_size_mb": 10}'::jsonb)
ON CONFLICT (channel) DO NOTHING;

-- Knowledge base entries (FlowSync product documentation)
INSERT INTO knowledge_base (title, content, category, tags, source_url)
VALUES
    (
        'AI Task Suggestions',
        'AI Task Suggestions uses machine learning to analyze task descriptions, project context, team workload, and historical patterns to generate recommendations. It considers deadlines, dependencies, team capacity, and past completion rates. Enabled by default on Pro and Enterprise plans. To toggle: Settings > AI Features > Task Suggestions. Ensure tasks have sufficient detail (title + description) for AI to analyze. AI needs at least 3-5 tasks in a project to generate meaningful recommendations. If no suggestions appear, try refreshing the dashboard or clearing browser cache. AI suggestions may take up to 5 minutes to generate for new projects.',
        'features',
        ARRAY['ai', 'tasks', 'suggestions', 'recommendations', 'machine learning'],
        'https://docs.flowsync.com/features/ai-task-suggestions'
    ),
    (
        'Smart Dashboards',
        'Smart Dashboards provide customizable views with AI-powered insights, real-time project metrics, and team performance analytics. Features include: real-time project health scores, burndown charts and velocity tracking, AI-generated risk alerts, custom widgets and filters, export to PDF/CSV/shareable links. Navigate to Dashboards from the main menu. Click Create Dashboard to start fresh or use pre-built templates (Project Overview, Team Performance, Sprint Tracker). Drag and drop widgets to customize your view.',
        'features',
        ARRAY['dashboard', 'analytics', 'metrics', 'charts', 'insights'],
        'https://docs.flowsync.com/features/smart-dashboards'
    ),
    (
        'Team Collaboration - Inviting Members',
        'To invite team members: Go to Settings > Team > Invite Members. You can invite individuals by email or upload a CSV for bulk invites. Pro plan supports up to 50 members; Enterprise supports unlimited members. For bulk invites: Prepare a CSV with columns email and role, then upload via the Import button. Roles: Admin (full access), Member (edit + comment), Viewer (read-only). Change roles in Settings > Team > Member List > Click role dropdown next to member name.',
        'features',
        ARRAY['team', 'invite', 'members', 'roles', 'permissions', 'collaboration'],
        'https://docs.flowsync.com/features/team-collaboration'
    ),
    (
        'Slack Integration',
        'Connect FlowSync with Slack for seamless workflow automation. Get FlowSync notifications in Slack channels, create tasks from Slack messages, and sync project updates. Setup: Settings > Integrations > Slack > Connect. Authorize FlowSync in your Slack workspace. Choose which channels receive notifications and what events trigger them. Features: Task creation from Slack messages (use /flowsync task command), project status updates posted to designated channels, @mention notifications forwarded between platforms, two-way sync for task status and comments. Troubleshooting: Ensure the Slack app has been authorized by a workspace admin. Check that the integration is active in Settings > Integrations > Slack. If tasks are not syncing, verify the Slack channel is linked to a FlowSync project. Try disconnecting and reconnecting the integration.',
        'integrations',
        ARRAY['slack', 'integration', 'sync', 'notifications', 'troubleshooting'],
        'https://docs.flowsync.com/integrations/slack'
    ),
    (
        'Google Drive Integration',
        'Attach Google Drive files directly to tasks with automatic sync for document updates. Setup: Settings > Integrations > Google Drive > Connect. Authorize FlowSync to access your Google Drive. Attach files to tasks using the paperclip icon in any task view. Troubleshooting: Ensure you are logged into the correct Google account. Shared Drive files may require additional permissions.',
        'integrations',
        ARRAY['google drive', 'integration', 'files', 'attachments'],
        'https://docs.flowsync.com/integrations/google-drive'
    ),
    (
        'GitHub Integration',
        'Link GitHub repositories and issues to FlowSync tasks for unified project tracking. Setup: Settings > Integrations > GitHub > Connect. Authorize FlowSync as an OAuth app in your GitHub account. Select repositories to link and configure sync preferences. Troubleshooting: Ensure you have admin access to the GitHub repository. Webhook failures can be resolved by re-authorizing the integration.',
        'integrations',
        ARRAY['github', 'integration', 'repositories', 'issues', 'webhooks'],
        'https://docs.flowsync.com/integrations/github'
    ),
    (
        'AI Meeting Summarizer',
        'Automatically generates structured meeting summaries with action items, decisions, and follow-ups from recorded meetings. Connect your Zoom or upload a recording. The AI transcribes the audio, identifies key discussion points, extracts action items with owners, and generates a shareable summary. Available on Pro and Enterprise plans. Go to Tools > Meeting Summarizer > Upload recording or connect Zoom. Summaries are generated within 2-5 minutes depending on meeting length. Supported formats: MP3, MP4, WAV, Zoom cloud recordings. Currently supports English, Spanish, and French transcription.',
        'features',
        ARRAY['meeting', 'summarizer', 'ai', 'transcription', 'zoom', 'action items'],
        'https://docs.flowsync.com/features/meeting-summarizer'
    ),
    (
        'Custom Workflows (No-Code)',
        'Build automated workflows without writing code. Use the visual Workflow Builder to create if-this-then-that rules. Triggers include: task created, status changed, deadline approaching, etc. Actions include: assign task, send notification, update field, create subtask. Setup: Go to Automation > Workflow Builder > Create New Workflow. Choose a trigger, add conditions, and define actions. Test your workflow before activating. Available on Pro and Enterprise plans.',
        'features',
        ARRAY['workflows', 'automation', 'no-code', 'triggers', 'actions'],
        'https://docs.flowsync.com/features/custom-workflows'
    ),
    (
        'Pricing Plans Overview',
        'FlowSync offers three tiers to match your team needs. Starter: For small teams getting started. Up to 10 team members, basic task management, limited AI suggestions, 5 GB storage, email support. Pro: For growing teams that need full collaboration and AI features. Up to 50 team members, full AI Task Suggestions, Smart Dashboards, all integrations, AI Meeting Summarizer, Custom Workflows, Resource Planner, priority support. Enterprise: For large organizations with advanced security and compliance needs. Unlimited team members, all Pro features, SSO & SAML, advanced security & audit logs, dedicated account manager, custom onboarding, SLA guarantees, 24/7 phone & email support. For specific pricing details, contact our sales team.',
        'pricing',
        ARRAY['pricing', 'plans', 'starter', 'pro', 'enterprise', 'tiers'],
        'https://flowsync.com/pricing'
    ),
    (
        'Data Security and Compliance',
        'FlowSync is SOC 2 Type II certified. All data is encrypted at rest and in transit. We use AWS infrastructure with 99.99% uptime. Data is stored in US-East and EU-West regions. Customers can request data residency preferences. FlowSync complies with GDPR, CCPA, and HIPAA requirements. Regular third-party security audits are conducted annually. For specific security questions or compliance documentation, contact our security team at security@flowsync.com.',
        'faq',
        ARRAY['security', 'compliance', 'gdpr', 'soc2', 'encryption', 'data'],
        'https://docs.flowsync.com/security'
    ),
    (
        'Account Management - Password Reset',
        'To reset your password: Go to the login page and click Forgot Password. Enter your email address associated with your FlowSync account. Check your inbox for a password reset email (check spam folder if not received within 5 minutes). Click the reset link and create a new password. Password requirements: minimum 8 characters, at least one uppercase letter, one number, and one special character. If you do not receive the reset email, contact support.',
        'faq',
        ARRAY['password', 'reset', 'login', 'account'],
        'https://docs.flowsync.com/faq/password-reset'
    ),
    (
        'Resource Planner',
        'Plan and optimize team capacity with AI-powered resource allocation suggestions. Features: visual capacity heatmap, AI workload balance recommendations, time-off and availability tracking, cross-project resource allocation. Available on Pro and Enterprise plans. Go to Planning > Resource Planner. Set team member availability, assign to projects, and view capacity metrics.',
        'features',
        ARRAY['resource', 'planning', 'capacity', 'allocation', 'heatmap'],
        'https://docs.flowsync.com/features/resource-planner'
    )
ON CONFLICT DO NOTHING;

-- ────────────────────────────────────────────────────────────────────────────
-- VERIFICATION
-- ────────────────────────────────────────────────────────────────────────────

-- Verify tables created
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE';

    RAISE NOTICE 'FlowSync Database Schema: % tables created.', table_count;
END $$;

-- Verify knowledge base entries
DO $$
DECLARE
    kb_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO kb_count FROM knowledge_base;
    RAISE NOTICE 'Knowledge Base: % entries seeded.', kb_count;
END $$;

-- Verify channel configs
DO $$
DECLARE
    cc_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO cc_count FROM channel_configs;
    RAISE NOTICE 'Channel Configs: % entries created.', cc_count;
END $$;
