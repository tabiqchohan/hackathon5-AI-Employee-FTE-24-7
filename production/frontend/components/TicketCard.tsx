"use client";

import Link from "next/link";
import { getStatusConfig, getPriorityConfig, formatRelative } from "@/lib/utils";
import { Clock, ArrowUpRight } from "lucide-react";

interface TicketCardProps {
  ticket: {
    ticket_id: string;
    subject: string;
    status: string;
    priority: string;
    created_at: string;
  };
}

export default function TicketCard({ ticket }: TicketCardProps) {
  const status = getStatusConfig(ticket.status);
  const priority = getPriorityConfig(ticket.priority);

  return (
    <Link
      href={`/ticket/${ticket.ticket_id}`}
      className="card card-hover p-5 block group"
    >
      {/* Header: ID + Status */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono text-gray-400 dark:text-gray-500">
          {ticket.ticket_id}
        </span>
        <span className={`badge ${status.color}`}>{status.label}</span>
      </div>

      {/* Subject */}
      <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-2 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors line-clamp-2">
        {ticket.subject}
      </h3>

      {/* Priority + Time */}
      <div className="flex items-center justify-between mt-4">
        <span className={`badge ${priority.color}`}>{priority.label}</span>
        <div className="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500">
          <Clock className="w-3.5 h-3.5" />
          {formatRelative(ticket.created_at)}
        </div>
      </div>

      {/* Hover indicator */}
      <div className="mt-3 flex items-center gap-1 text-sm text-brand-600 dark:text-brand-400 opacity-0 group-hover:opacity-100 transition-opacity">
        View details
        <ArrowUpRight className="w-3.5 h-3.5" />
      </div>
    </Link>
  );
}
