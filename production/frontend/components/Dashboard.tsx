"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import StatsCard from "@/components/StatsCard";
import { Ticket, MessageSquare, TrendingUp, AlertCircle, Loader2 } from "lucide-react";

interface DashboardProps {
  email?: string;
}

export default function Dashboard({ email }: DashboardProps) {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalTickets: 0,
    openTickets: 0,
    resolvedTickets: 0,
    escalatedTickets: 0,
  });

  useEffect(() => {
    if (!email) {
      setLoading(false);
      return;
    }

    const fetchStats = async () => {
      try {
        const data = await api.listTickets(email);
        const tickets = data.tickets || [];
        setStats({
          totalTickets: tickets.length,
          openTickets: tickets.filter((t) => t.status === "open").length,
          resolvedTickets: tickets.filter((t) => t.status === "resolved").length,
          escalatedTickets: tickets.filter((t) => t.status === "escalated").length,
        });
      } catch {
        // Show empty state
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, [email]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card p-5 animate-pulse">
            <div className="w-10 h-10 rounded-xl bg-gray-200 dark:bg-gray-800 mb-4" />
            <div className="h-7 bg-gray-200 dark:bg-gray-800 rounded w-12 mb-2" />
            <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded w-24" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <StatsCard
        icon={Ticket}
        label="Total Tickets"
        value={stats.totalTickets}
        trend={
          stats.totalTickets > 0
            ? { value: "This month", positive: true }
            : undefined
        }
        color="text-brand-500"
      />
      <StatsCard
        icon={MessageSquare}
        label="Open Tickets"
        value={stats.openTickets}
        color="text-accent-500"
      />
      <StatsCard
        icon={TrendingUp}
        label="Resolved"
        value={stats.resolvedTickets}
        trend={
          stats.resolvedTickets > 0
            ? { value: `${Math.round((stats.resolvedTickets / Math.max(stats.totalTickets, 1)) * 100)}% rate`, positive: true }
            : undefined
        }
        color="text-green-500"
      />
      <StatsCard
        icon={AlertCircle}
        label="Escalated"
        value={stats.escalatedTickets}
        color="text-red-500"
      />
    </div>
  );
}
