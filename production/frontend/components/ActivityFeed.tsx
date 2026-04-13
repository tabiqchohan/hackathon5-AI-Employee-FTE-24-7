"use client";

import { formatRelative } from "@/lib/utils";
import { getStatusConfig } from "@/lib/utils";
import {
  MessageSquare,
  ArrowUpCircle,
  CheckCircle,
  PlusCircle,
  Clock,
} from "lucide-react";

interface Activity {
  id: string;
  type: "message" | "escalation" | "resolved" | "created" | "pending";
  ticket_id: string;
  description: string;
  created_at: string;
}

const ACTIVITY_ICONS = {
  message: <MessageSquare className="w-4 h-4 text-blue-500" />,
  escalation: <ArrowUpCircle className="w-4 h-4 text-red-500" />,
  resolved: <CheckCircle className="w-4 h-4 text-green-500" />,
  created: <PlusCircle className="w-4 h-4 text-brand-500" />,
  pending: <Clock className="w-4 h-4 text-gray-400" />,
};

interface ActivityFeedProps {
  activities: Activity[];
  loading?: boolean;
}

export default function ActivityFeed({
  activities,
  loading = false,
}: ActivityFeedProps) {
  if (loading) {
    return (
      <div className="card p-5">
        <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-4">
          Recent Activity
        </h3>
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex gap-3 animate-pulse">
              <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-800" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded w-3/4" />
                <div className="h-3 bg-gray-200 dark:bg-gray-800 rounded w-1/4" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="card p-5">
      <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-4">
        Recent Activity
      </h3>
      {activities.length === 0 ? (
        <div className="text-center py-8 text-gray-400 dark:text-gray-500">
          <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No recent activity</p>
        </div>
      ) : (
        <div className="space-y-4">
          {activities.map((activity) => (
            <div key={activity.id} className="flex gap-3 group">
              <div className="w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center flex-shrink-0 group-hover:bg-gray-200 dark:group-hover:bg-gray-700 transition-colors">
                {ACTIVITY_ICONS[activity.type]}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-700 dark:text-gray-300 truncate">
                  {activity.description}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs font-mono text-gray-400 dark:text-gray-500">
                    {activity.ticket_id}
                  </span>
                  <span className="text-xs text-gray-400 dark:text-gray-500">
                    {formatRelative(activity.created_at)}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
