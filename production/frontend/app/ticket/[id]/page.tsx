"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { getStatusConfig, getPriorityConfig, formatDate, getSentimentConfig } from "@/lib/utils";
import { useToast } from "@/components/Toast";
import { SkeletonPage } from "@/components/Skeleton";
import {
  ArrowLeft,
  Clock,
  ArrowUpCircle,
  CheckCircle,
  MessageSquare,
  Bot,
  User,
  RefreshCw,
  Calendar,
} from "lucide-react";
import Link from "next/link";

export default function TicketDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { error: showError, success } = useToast();
  const ticketId = params.id as string;

  const [ticket, setTicket] = useState<Awaited<ReturnType<typeof api.getTicket>> | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchTicket = async () => {
    setLoading(true);
    try {
      const data = await api.getTicket(ticketId);
      setTicket(data);
    } catch (err) {
      showError(
        "Ticket Not Found",
        err instanceof Error ? err.message : "The ticket may not exist"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTicket();
  }, [ticketId]);

  if (loading) {
    return <SkeletonPage />;
  }

  if (!ticket) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-12 text-center animate-fade-in">
        <MessageSquare className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
          Ticket Not Found
        </h2>
        <p className="text-gray-500 dark:text-gray-400 mb-6">
          The ticket ID <span className="font-mono">{ticketId}</span> does not exist.
        </p>
        <Link href="/" className="btn btn-primary">
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </Link>
      </div>
    );
  }

  const status = getStatusConfig(ticket.status);
  const priority = getPriorityConfig(ticket.priority);

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-12 animate-fade-in">
      {/* Back + Refresh */}
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => router.back()}
          className="btn btn-ghost -ml-2"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
        <button
          onClick={fetchTicket}
          className="btn btn-ghost"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Ticket Header */}
      <div className="card p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-white font-mono">
              {ticket.ticket_id}
            </h1>
            <p className="text-base text-gray-600 dark:text-gray-400 mt-1">
              {ticket.subject}
            </p>
          </div>
          <span className={`badge ${status.color} text-sm px-3 py-1`}>
            {status.label}
          </span>
        </div>

        {/* Meta Info */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-4 border-t border-b border-gray-100 dark:border-gray-800">
          <MetaItem icon={Clock} label="Priority" value={priority.label} />
          <MetaItem icon={MessageSquare} label="Channel" value={ticket.channel} />
          <MetaItem icon={Calendar} label="Created" value={formatDate(ticket.created_at)} />
          <MetaItem icon={Calendar} label="Updated" value={formatDate(ticket.updated_at)} />
        </div>

        {/* Escalation Banner */}
        {ticket.is_escalated && (
          <div className="mt-4 bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-800/30 rounded-xl p-4 flex items-start gap-3">
            <ArrowUpCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-red-700 dark:text-red-400">
                Escalated to Specialist Team
              </p>
              <p className="text-xs text-red-600/80 dark:text-red-400/80 mt-0.5">
                A human agent is reviewing your case. You can expect a response within 2 hours.
              </p>
            </div>
          </div>
        )}

        {/* Resolved Banner */}
        {ticket.status === "resolved" && (
          <div className="mt-4 bg-green-50 dark:bg-green-900/20 border border-green-100 dark:border-green-800/30 rounded-xl p-4 flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-green-700 dark:text-green-400">
                This ticket has been resolved
              </p>
              <p className="text-xs text-green-600/80 dark:text-green-400/80 mt-0.5">
                If you still need help, please submit a new request.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Conversation / Response */}
      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Conversation
        </h2>

        {/* AI Response */}
        {ticket.latest_response ? (
          <div className="space-y-4">
            {/* Agent message */}
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-brand-100 dark:bg-brand-900/30 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    FlowSync AI Agent
                  </span>
                  <span className="text-xs text-gray-400 dark:text-gray-500">
                    {formatDate(ticket.updated_at)}
                  </span>
                </div>
                <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
                  <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-line leading-relaxed">
                    {ticket.latest_response}
                  </p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-400 dark:text-gray-500">
            <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No responses yet</p>
            <p className="text-xs mt-1">Our AI agent is processing your request</p>
          </div>
        )}
      </div>
    </div>
  );
}

function MetaItem({
  icon: Icon,
  label,
  value,
}: {
  icon: any;
  label: string;
  value: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500 mb-0.5">
        <Icon className="w-3.5 h-3.5" />
        {label}
      </div>
      <p className="text-sm font-medium text-gray-900 dark:text-white capitalize">
        {value}
      </p>
    </div>
  );
}
