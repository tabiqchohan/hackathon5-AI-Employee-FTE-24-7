"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { getStatusConfig, getPriorityConfig, formatDate } from "@/lib/utils";
import { useToast } from "@/components/Toast";
import {
  Search,
  Loader2,
  Ticket,
  Clock,
  ArrowUpCircle,
  ArrowRight,
  CheckCircle,
} from "lucide-react";
import Link from "next/link";

export default function StatusPage() {
  const { error: showError, success } = useToast();
  const [ticketId, setTicketId] = useState("");
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.getTicket>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticketId.trim()) return;

    setLoading(true);
    setSearched(true);

    try {
      const data = await api.getTicket(ticketId.trim().toUpperCase());
      setResult(data);
      success("Ticket Found", `Status: ${data.status}`);
    } catch (err) {
      showError(
        "Ticket Not Found",
        err instanceof Error ? err.message : "Please check the Ticket ID"
      );
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8 sm:py-12 animate-fade-in">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-brand-100 dark:bg-brand-900/30 text-brand-600 dark:text-brand-400 mb-4">
          <Search className="w-7 h-7" />
        </div>
        <h1 className="page-title">Track Your Ticket</h1>
        <p className="page-subtitle">
          Enter your Ticket ID to check the current status.
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="card p-5 mb-8">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Ticket className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={ticketId}
              onChange={(e) => setTicketId(e.target.value.toUpperCase())}
              placeholder="Enter Ticket ID (e.g. TKT-00001)"
              className="input pl-10 font-mono"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary disabled:opacity-60"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Search className="w-4 h-4" />
            )}
            Track
          </button>
        </div>
      </form>

      {/* Loading */}
      {loading && (
        <div className="card p-8 animate-pulse">
          <div className="skeleton h-6 w-32 mb-4" />
          <div className="skeleton h-4 w-full mb-2" />
          <div className="skeleton h-4 w-2/3" />
        </div>
      )}

      {/* Result */}
      {!loading && result && (
        <div className="card p-6 animate-slide-up">
          {/* Status Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-bold text-gray-900 dark:text-white font-mono">
                {result.ticket_id}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                {result.subject}
              </p>
            </div>
            <span className={`badge ${getStatusConfig(result.status).color} text-sm px-3 py-1`}>
              {getStatusConfig(result.status).label}
            </span>
          </div>

          {/* Details Grid */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <DetailItem label="Priority" value={result.priority} />
            <DetailItem label="Channel" value={result.channel} />
            <DetailItem label="Created" value={formatDate(result.created_at)} />
            <DetailItem label="Last Updated" value={formatDate(result.updated_at)} />
          </div>

          {/* Escalation Notice */}
          {result.is_escalated && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-800/30 rounded-xl p-4 mb-6 flex items-start gap-3">
              <ArrowUpCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-700 dark:text-red-400">
                  This ticket has been escalated
                </p>
                <p className="text-xs text-red-600/80 dark:text-red-400/80 mt-0.5">
                  A specialist team is reviewing your case and will respond shortly.
                </p>
              </div>
            </div>
          )}

          {/* Resolution Notice */}
          {result.status === "resolved" && (
            <div className="bg-green-50 dark:bg-green-900/20 border border-green-100 dark:border-green-800/30 rounded-xl p-4 mb-6 flex items-start gap-3">
              <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-green-700 dark:text-green-400">
                  This ticket has been resolved
                </p>
                <p className="text-xs text-green-600/80 dark:text-green-400/80 mt-0.5">
                  If your issue persists, feel free to submit a new request.
                </p>
              </div>
            </div>
          )}

          {/* Latest Response */}
          {result.latest_response && (
            <div className="border-t border-gray-100 dark:border-gray-800 pt-5">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Latest Response
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-line">
                {result.latest_response}
              </p>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 mt-6 pt-5 border-t border-gray-100 dark:border-gray-800">
            <button
              onClick={() => {
                setTicketId(result.ticket_id);
                handleSearch(new Event("submit") as any);
              }}
              className="btn btn-outline flex-1"
            >
              <Clock className="w-4 h-4" />
              Refresh Status
            </button>
            <Link href="/" className="btn btn-primary flex-1">
              New Request
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && searched && !result && (
        <div className="card p-12 text-center">
          <Ticket className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
            Ticket Not Found
          </h3>
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            Check the Ticket ID and try again.
          </p>
        </div>
      )}
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-0.5">
        {label}
      </p>
      <p className="text-sm font-medium text-gray-900 dark:text-white capitalize">
        {value}
      </p>
    </div>
  );
}
