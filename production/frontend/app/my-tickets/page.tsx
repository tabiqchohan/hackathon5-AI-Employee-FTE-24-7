"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import TicketCard from "@/components/TicketCard";
import { SkeletonCard } from "@/components/Skeleton";
import { useToast } from "@/components/Toast";
import { Ticket, Search, Loader2, Mail } from "lucide-react";

export default function MyTicketsPage() {
  const { error: showError } = useToast();
  const [email, setEmail] = useState("");
  const [tickets, setTickets] = useState<typeof api.listTickets extends (...args: any) => infer R ? Awaited<R>["tickets"] : never>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    setLoading(true);
    setSearched(true);

    try {
      const data = await api.listTickets(email.trim().toLowerCase());
      setTickets(data.tickets || []);
    } catch (err) {
      showError(
        "Failed to Load Tickets",
        err instanceof Error ? err.message : "Please check the email and try again"
      );
      setTickets([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 animate-fade-in">
      {/* Header */}
      <div className="mb-8">
        <h1 className="page-title">My Tickets</h1>
        <p className="page-subtitle">
          View all your support requests in one place.
        </p>
      </div>

      {/* Search */}
      <div className="card p-5 mb-8">
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="flex-1 relative">
            <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email address"
              className="input pl-10"
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
            {loading ? "Loading..." : "Search"}
          </button>
        </form>
      </div>

      {/* Results */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : searched ? (
        <>
          {tickets.length === 0 ? (
            <div className="card p-12 text-center">
              <Ticket className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                No Tickets Found
              </h3>
              <p className="text-gray-500 dark:text-gray-400 text-sm">
                No support requests found for this email address.
              </p>
            </div>
          ) : (
            <>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                {tickets.length} ticket{tickets.length !== 1 ? "s" : ""} found
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {tickets.map((ticket) => (
                  <TicketCard key={ticket.ticket_id} ticket={ticket} />
                ))}
              </div>
            </>
          )}
        </>
      ) : null}
    </div>
  );
}
