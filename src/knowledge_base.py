"""
FlowSync Product Knowledge Base
Used by the AI agent to ground responses in factual product information.
"""

KNOWLEDGE_BASE = {
    "ai_task_suggestions": {
        "name": "AI Task Suggestions",
        "description": "AI-powered feature that analyzes your project tasks and provides smart recommendations for prioritization, assignment, and next steps.",
        "how_it_works": (
            "AI Task Suggestions uses machine learning to analyze task descriptions, "
            "project context, team workload, and historical patterns to generate recommendations. "
            "It considers deadlines, dependencies, team capacity, and past completion rates."
        ),
        "setup": (
            "AI Task Suggestions is enabled by default on Pro and Enterprise plans. "
            "To toggle: Go to Settings > AI Features > Task Suggestions > Toggle On/Off. "
            "Starter plan users can access basic suggestions; advanced insights require Pro or Enterprise."
        ),
        "troubleshooting": [
            "Ensure AI features are enabled in Settings > AI Features.",
            "Check that tasks have sufficient detail (title + description) for AI to analyze.",
            "AI needs at least 3-5 tasks in a project to generate meaningful recommendations.",
            "If no suggestions appear, try refreshing the dashboard or clearing browser cache.",
            "AI suggestions may take up to 5 minutes to generate for new projects.",
            "Check your plan tier — Starter plan has limited AI capabilities.",
        ],
        "limitations": [
            "AI suggestions are recommendations only — they do not auto-modify tasks.",
            "Accuracy improves over time as the AI learns your team's patterns.",
            "Currently supports English language tasks only.",
        ],
    },
    "smart_dashboards": {
        "name": "Smart Dashboards",
        "description": "Customizable dashboards with AI-powered insights, real-time project metrics, and team performance analytics.",
        "features": [
            "Real-time project health scores",
            "Burndown charts and velocity tracking",
            "AI-generated risk alerts",
            "Custom widgets and filters",
            "Export to PDF, CSV, or shareable links",
        ],
        "setup": (
            "Navigate to Dashboards from the main menu. Click 'Create Dashboard' to start fresh, "
            "or use one of our pre-built templates (Project Overview, Team Performance, Sprint Tracker). "
            "Drag and drop widgets to customize your view."
        ),
        "troubleshooting": [
            "If data appears stale, click the refresh icon in the top-right corner.",
            "Ensure you have view permissions for the projects displayed.",
            "Custom filters may exclude data — check your filter settings.",
        ],
    },
    "team_collaboration": {
        "name": "Team Collaboration",
        "description": "Real-time collaboration features including comments, @mentions, shared views, and team chat.",
        "features": [
            "Inline comments on tasks",
            "@mentions to notify specific team members",
            "Real-time team chat channels",
            "Shared project views (Kanban, List, Timeline, Calendar)",
            "File attachments and version history",
        ],
        "inviting_members": (
            "To invite team members: Go to Settings > Team > Invite Members. "
            "You can invite individuals by email or upload a CSV for bulk invites. "
            "Pro plan supports up to 50 members; Enterprise supports unlimited members. "
            "For bulk invites: Prepare a CSV with columns 'email' and 'role', then upload via the Import button."
        ),
        "permissions": (
            "Roles: Admin (full access), Member (edit + comment), Viewer (read-only). "
            "Change roles in Settings > Team > Member List > Click role dropdown next to member name."
        ),
        "troubleshooting": [
            "If @mentions aren't sending notifications, check the user's notification preferences.",
            "Ensure invited members have accepted their email invitation.",
            "Real-time chat requires all users to be on the same workspace.",
        ],
    },
    "integrations": {
        "name": "Integrations",
        "description": "Connect FlowSync with your favorite tools for seamless workflow automation.",
        "available_integrations": {
            "slack": {
                "name": "Slack",
                "description": "Get FlowSync notifications in Slack channels, create tasks from Slack messages, and sync project updates.",
                "setup": (
                    "Go to Settings > Integrations > Slack > Connect. "
                    "Authorize FlowSync in your Slack workspace. "
                    "Choose which channels receive notifications and what events trigger them."
                ),
                "sync_features": [
                    "Task creation from Slack messages (use /flowsync task command)",
                    "Project status updates posted to designated channels",
                    "@mention notifications forwarded between platforms",
                    "Two-way sync for task status and comments",
                ],
                "troubleshooting": [
                    "Ensure the Slack app has been authorized by a workspace admin.",
                    "Check that the integration is active in Settings > Integrations > Slack.",
                    "If tasks aren't syncing, verify the Slack channel is linked to a FlowSync project.",
                    "Try disconnecting and reconnecting the integration.",
                    "Check for any Slack API outages at status.slack.com.",
                    "Rate limits: Slack API allows 1 request per second for free workspaces.",
                ],
            },
            "google_drive": {
                "name": "Google Drive",
                "description": "Attach Google Drive files directly to tasks, with automatic sync for document updates.",
                "setup": (
                    "Go to Settings > Integrations > Google Drive > Connect. "
                    "Authorize FlowSync to access your Google Drive. "
                    "Attach files to tasks using the paperclip icon in any task view."
                ),
                "troubleshooting": [
                    "Ensure you're logged into the correct Google account.",
                    "Shared Drive files may require additional permissions.",
                ],
            },
            "github": {
                "name": "GitHub",
                "description": "Link GitHub repositories and issues to FlowSync tasks for unified project tracking.",
                "setup": (
                    "Go to Settings > Integrations > GitHub > Connect. "
                    "Authorize FlowSync as an OAuth app in your GitHub account. "
                    "Select repositories to link and configure sync preferences."
                ),
                "troubleshooting": [
                    "Ensure you have admin access to the GitHub repository.",
                    "Webhook failures can be resolved by re-authorizing the integration.",
                ],
            },
            "figma": {
                "name": "Figma",
                "description": "Embed Figma designs directly into FlowSync tasks for design-to-development workflow.",
                "setup": (
                    "Go to Settings > Integrations > Figma > Connect. "
                    "Authorize FlowSync in your Figma account settings."
                ),
            },
            "zoom": {
                "name": "Zoom",
                "description": "Schedule Zoom meetings from FlowSync tasks and auto-attach meeting recordings.",
                "setup": (
                    "Go to Settings > Integrations > Zoom > Connect. "
                    "Authorize FlowSync in your Zoom account."
                ),
            },
        },
    },
    "ai_meeting_summarizer": {
        "name": "AI Meeting Summarizer",
        "description": "Automatically generates structured meeting summaries with action items, decisions, and follow-ups from recorded meetings.",
        "how_it_works": (
            "Connect your Zoom or upload a recording. The AI transcribes the audio, "
            "identifies key discussion points, extracts action items with owners, "
            "and generates a shareable summary."
        ),
        "setup": (
            "Available on Pro and Enterprise plans. "
            "Go to Tools > Meeting Summarizer > Upload recording or connect Zoom. "
            "Summaries are generated within 2-5 minutes depending on meeting length."
        ),
        "supported_formats": ["MP3", "MP4", "WAV", "Zoom cloud recordings"],
        "troubleshooting": [
            "Ensure audio quality is clear — background noise affects transcription accuracy.",
            "Meetings longer than 2 hours may be split into multiple summaries.",
            "Currently supports English, Spanish, and French transcription.",
        ],
    },
    "resource_planner": {
        "name": "Resource Planner",
        "description": "Plan and optimize team capacity with AI-powered resource allocation suggestions.",
        "features": [
            "Visual capacity heatmap",
            "AI workload balance recommendations",
            "Time-off and availability tracking",
            "Cross-project resource allocation",
        ],
        "setup": (
            "Available on Pro and Enterprise plans. "
            "Go to Planning > Resource Planner. "
            "Set team member availability, assign to projects, and view capacity metrics."
        ),
    },
    "custom_workflows": {
        "name": "Custom Workflows (No-Code)",
        "description": "Build automated workflows without writing code. Trigger actions based on events, conditions, and schedules.",
        "how_it_works": (
            "Use the visual Workflow Builder to create if-this-then-haven't rules. "
            "Triggers include: task created, status changed, deadline approaching, etc. "
            "Actions include: assign task, send notification, update field, create subtask."
        ),
        "setup": (
            "Go to Automation > Workflow Builder > Create New Workflow. "
            "Choose a trigger, add conditions, and define actions. "
            "Test your workflow before activating."
        ),
        "available_on": ["Pro", "Enterprise"],
    },
    "pricing_plans": {
        "name": "Pricing Plans",
        "description": "FlowSync offers three tiers to match your team's needs.",
        "plans": {
            "starter": {
                "name": "Starter",
                "description": "For small teams getting started with project management.",
                "features": [
                    "Up to 10 team members",
                    "Basic task management",
                    "Limited AI suggestions",
                    "5 GB storage",
                    "Email support",
                ],
            },
            "pro": {
                "name": "Pro",
                "description": "For growing teams that need full collaboration and AI features.",
                "features": [
                    "Up to 50 team members",
                    "Full AI Task Suggestions",
                    "Smart Dashboards",
                    "All integrations",
                    "AI Meeting Summarizer",
                    "Custom Workflows",
                    "Resource Planner",
                    "Priority support",
                ],
            },
            "enterprise": {
                "name": "Enterprise",
                "description": "For large organizations with advanced security and compliance needs.",
                "features": [
                    "Unlimited team members",
                    "All Pro features",
                    "SSO & SAML",
                    "Advanced security & audit logs",
                    "Dedicated account manager",
                    "Custom onboarding",
                    "SLA guarantees",
                    "24/7 phone & email support",
                ],
            },
        },
        "note": "For specific pricing details, please contact our sales team or visit our pricing page.",
    },
    "general_faq": {
        "account_creation": "Sign up at flowsync.com/signup with your work email. Free 14-day trial on all plans.",
        "password_reset": "Go to login page > Forgot Password > Enter your email > Follow the reset link.",
        "data_export": "Go to Settings > Data > Export All Data. Available in CSV and JSON formats.",
        "data_security": "FlowSync is SOC 2 Type II certified. All data is encrypted at rest and in transit. We use AWS infrastructure with 99.99% uptime.",
        "supported_browsers": "Chrome, Firefox, Safari, Edge (latest 2 versions).",
        "mobile_app": "iOS and Android apps available. Go to Settings > Mobile Apps for download links.",
        "cancellation": "You can cancel anytime from Settings > Billing > Cancel Subscription. No long-term contracts required.",
    },
}


def get_kb_as_text():
    """Return the entire knowledge base as a formatted text string for embedding/search."""
    text = ""
    for section_key, section in KNOWLEDGE_BASE.items():
        text += f"\n## {section.get('name', section_key)}\n"
        text += f"{section.get('description', '')}\n"
        if "how_it_works" in section:
            text += f"\nHow it works: {section['how_it_works']}\n"
        if "setup" in section:
            text += f"\nSetup: {section['setup']}\n"
        if "features" in section:
            text += f"\nFeatures:\n"
            for f in section["features"]:
                text += f"  - {f}\n"
        if "troubleshooting" in section:
            text += f"\nTroubleshooting:\n"
            for t in section["troubleshooting"]:
                text += f"  - {t}\n"
        if "limitations" in section:
            text += f"\nLimitations:\n"
            for l in section["limitations"]:
                text += f"  - {l}\n"
        if "available_integrations" in section:
            for int_key, int_data in section["available_integrations"].items():
                text += f"\n  ### {int_data['name']}\n"
                text += f"  {int_data.get('description', '')}\n"
                if "setup" in int_data:
                    text += f"  Setup: {int_data['setup']}\n"
                if "troubleshooting" in int_data:
                    text += f"  Troubleshooting:\n"
                    for t in int_data["troubleshooting"]:
                        text += f"    - {t}\n"
        if "plans" in section:
            for plan_key, plan in section["plans"].items():
                text += f"\n  ### {plan['name']} Plan\n"
                text += f"  {plan.get('description', '')}\n"
                if "features" in plan:
                    text += f"  Features:\n"
                    for f in plan["features"]:
                        text += f"    - {f}\n"
        if section_key == "general_faq":
            for q_key, answer in section.items():
                if q_key != "name" and q_key != "description":
                    text += f"\n{q_key.replace('_', ' ').title()}: {answer}\n"
    return text


def search_kb(query: str) -> str:
    """
    Simple keyword-based KB search.
    Returns the most relevant KB section as text.
    In production, this would be a vector similarity search.
    """
    query_lower = query.lower()
    results = []

    # Keyword mapping to sections
    keyword_map = {
        "ai task": "ai_task_suggestions",
        "task suggestion": "ai_task_suggestions",
        "ai suggestion": "ai_task_suggestions",
        "ai recommend": "ai_task_suggestions",
        "ai not working": "ai_task_suggestions",
        "dashboard": "smart_dashboards",
        "insight": "smart_dashboards",
        "metric": "smart_dashboards",
        "invite": "team_collaboration",
        "team member": "team_collaboration",
        "collaborat": "team_collaboration",
        "mention": "team_collaboration",
        "comment": "team_collaboration",
        "permission": "team_collaboration",
        "role": "team_collaboration",
        "slack": "integrations",
        "sync": "integrations",
        "integration": "integrations",
        "google drive": "integrations",
        "github": "integrations",
        "figma": "integrations",
        "zoom": "integrations",
        "connect": "integrations",
        "meeting summar": "ai_meeting_summarizer",
        "meeting summary": "ai_meeting_summarizer",
        "transcri": "ai_meeting_summarizer",
        "resource": "resource_planner",
        "capacity": "resource_planner",
        "workflow": "custom_workflows",
        "automation": "custom_workflows",
        "no-code": "custom_workflows",
        "no code": "custom_workflows",
        "pricing": "pricing_plans",
        "price": "pricing_plans",
        "plan": "pricing_plans",
        "starter": "pricing_plans",
        "pro plan": "pricing_plans",
        "enterprise": "pricing_plans",
        "cost": "pricing_plans",
        "billing": "pricing_plans",
        "refund": "pricing_plans",
        "payment": "pricing_plans",
        "contract": "pricing_plans",
        "signup": "general_faq",
        "password": "general_faq",
        "export": "general_faq",
        "security": "general_faq",
        "data": "general_faq",
        "mobile": "general_faq",
        "cancel": "general_faq",
        "subscription": "general_faq",
    }

    for keyword, section_key in keyword_map.items():
        if keyword in query_lower:
            if section_key not in results:
                results.append(section_key)

    if not results:
        # Fallback: search all text for matching words
        full_text = get_kb_as_text().lower()
        query_words = query_lower.split()
        for word in query_words:
            if len(word) > 3 and word in full_text:
                # Return general info if partial match
                results = ["general_faq"]
                break

    # Build response from matched sections
    if results:
        response_parts = []
        for section_key in results[:3]:  # Max 3 sections
            section = KNOWLEDGE_BASE.get(section_key, {})
            response_parts.append(f"### {section.get('name', section_key)}")
            response_parts.append(section.get("description", ""))
            if "setup" in section:
                response_parts.append(f"Setup: {section['setup']}")
            if "how_it_works" in section:
                response_parts.append(f"How it works: {section['how_it_works']}")
            if "troubleshooting" in section:
                response_parts.append("Troubleshooting steps:")
                for t in section["troubleshooting"]:
                    response_parts.append(f"- {t}")
            if "features" in section:
                response_parts.append("Features:")
                for f in section["features"]:
                    response_parts.append(f"- {f}")
            if "available_integrations" in section:
                for int_key, int_data in section["available_integrations"].items():
                    if int_key in query_lower:
                        response_parts.append(f"\n**{int_data['name']}**:")
                        response_parts.append(f"  {int_data.get('description', '')}")
                        if "setup" in int_data:
                            response_parts.append(f"  Setup: {int_data['setup']}")
                        if "troubleshooting" in int_data:
                            response_parts.append(f"  Troubleshooting:")
                            for t in int_data["troubleshooting"]:
                                response_parts.append(f"    - {t}")
            if "plans" in section:
                for plan_key, plan in section["plans"].items():
                    response_parts.append(f"\n**{plan['name']} Plan**: {plan.get('description', '')}")
                    if "features" in plan:
                        for f in plan["features"]:
                            response_parts.append(f"  - {f}")
                response_parts.append(f"\n{section.get('note', '')}")
            response_parts.append("")
        return "\n".join(response_parts)

    return "No specific product documentation found for this query. Please provide general guidance based on FlowSync's capabilities."
