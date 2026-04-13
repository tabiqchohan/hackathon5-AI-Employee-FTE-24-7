"use client";

import { useState } from "react";
import SupportForm from "@/components/SupportForm";
import Dashboard from "@/components/Dashboard";
import ActivityFeed from "@/components/ActivityFeed";
import { Bot, Shield, Clock, Zap } from "lucide-react";

const FEATURES = [
  {
    icon: Bot,
    title: "AI-Powered",
    description: "Instant responses powered by OpenAI's most advanced models.",
  },
  {
    icon: Clock,
    title: "24/7 Available",
    description: "Get support anytime — day, night, weekends, or holidays.",
  },
  {
    icon: Shield,
    title: "Smart Escalation",
    description: "Complex issues are automatically routed to the right specialist.",
  },
  {
    icon: Zap,
    title: "Fast Resolution",
    description: "Most issues resolved in minutes, not hours or days.",
  },
];

const SAMPLE_ACTIVITIES = [
  {
    id: "1",
    type: "created" as const,
    ticket_id: "TKT-00042",
    description: "New ticket: Slack integration sync issue",
    created_at: new Date(Date.now() - 5 * 60000).toISOString(),
  },
  {
    id: "2",
    type: "message" as const,
    ticket_id: "TKT-00038",
    description: "AI responded to team permissions question",
    created_at: new Date(Date.now() - 15 * 60000).toISOString(),
  },
  {
    id: "3",
    type: "resolved" as const,
    ticket_id: "TKT-00035",
    description: "Ticket resolved: Dashboard data display",
    created_at: new Date(Date.now() - 30 * 60000).toISOString(),
  },
  {
    id: "4",
    type: "escalation" as const,
    ticket_id: "TKT-00031",
    description: "Escalated: Enterprise pricing inquiry",
    created_at: new Date(Date.now() - 60 * 60000).toISOString(),
  },
];

export default function HomePage() {
  const [customerEmail, setCustomerEmail] = useState<string | undefined>();

  const handleTicketSuccess = (ticketId: string) => {
    // We don't know the email, but dashboard will show empty or we could track it
    void ticketId;
  };

  return (
    <div className="animate-fade-in">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-brand-600 via-brand-700 to-brand-900 dark:from-brand-900 dark:via-brand-950 dark:to-gray-950">
        {/* Background decoration */}
        <div className="absolute inset-0 animate-gradient bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-accent-500/20 via-transparent to-transparent" />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wNSI+PGNpcmNsZSBjeD0iMSIgY3k9IjEiIHI9IjEiLz48L2c+PC9nPjwvc3ZnPg==')] opacity-30" />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
          <div className="text-center max-w-3xl mx-auto mb-12">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur-sm text-sm text-white/90 mb-6">
              <Bot className="w-4 h-4" />
              AI-Powered Customer Support
            </div>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white mb-4">
              Get Instant Help from{" "}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-300 to-accent-400">
                FlowSync AI
              </span>
            </h1>
            <p className="text-lg text-white/70 max-w-2xl mx-auto">
              Submit your question and get an immediate, intelligent response.
              Our AI agent is available 24/7 across all channels.
            </p>
          </div>

          {/* Feature Pills */}
          <div className="flex flex-wrap justify-center gap-3 max-w-2xl mx-auto">
            {FEATURES.map((feature) => {
              const Icon = feature.icon;
              return (
                <div
                  key={feature.title}
                  className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 backdrop-blur-sm text-sm text-white/80"
                >
                  <Icon className="w-4 h-4 text-accent-400" />
                  {feature.title}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Main Content */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left: Support Form */}
          <div className="lg:col-span-2">
            <div className="mb-6">
              <h2 className="page-title">Submit a Request</h2>
              <p className="page-subtitle">
                Describe your issue and our AI will provide an instant response.
              </p>
            </div>
            <SupportForm onSuccess={handleTicketSuccess} />
          </div>

          {/* Right: Activity Feed */}
          <div className="lg:col-span-1">
            <div className="mb-6">
              <h2 className="section-title">Recent Activity</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                Latest support activity
              </p>
            </div>
            <ActivityFeed activities={SAMPLE_ACTIVITIES} />
          </div>
        </div>

        {/* Dashboard (shown if customer has tickets) */}
        {customerEmail && (
          <div className="mt-12">
            <h2 className="section-title mb-4">Your Support Overview</h2>
            <Dashboard email={customerEmail} />
          </div>
        )}
      </section>
    </div>
  );
}
