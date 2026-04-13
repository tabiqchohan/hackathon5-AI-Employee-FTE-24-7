"use client";

import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatsCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  trend?: { value: string; positive: boolean };
  color?: string;
}

export default function StatsCard({
  icon: Icon,
  label,
  value,
  trend,
  color = "text-brand-500",
}: StatsCardProps) {
  return (
    <div className="card p-5 card-hover">
      <div className="flex items-start justify-between">
        <div className={`p-2.5 rounded-xl bg-brand-50 dark:bg-brand-900/20 ${color}`}>
          <Icon className="w-5 h-5" />
        </div>
        {trend && (
          <span
            className={cn(
              "text-xs font-medium px-2 py-0.5 rounded-full",
              trend.positive
                ? "text-green-700 bg-green-100 dark:text-green-400 dark:bg-green-900/30"
                : "text-red-700 bg-red-100 dark:text-red-400 dark:bg-red-900/30"
            )}
          >
            {trend.value}
          </span>
        )}
      </div>
      <div className="mt-4">
        <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{label}</p>
      </div>
    </div>
  );
}
