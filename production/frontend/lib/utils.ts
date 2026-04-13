import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

// ──────────────────────────────────────────────────────────────
// CN helper (className merge with Tailwind dedup)
// ──────────────────────────────────────────────────────────────

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ──────────────────────────────────────────────────────────────
// DATE FORMATTING
// ──────────────────────────────────────────────────────────────

export function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelative(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(dateStr);
}

// ──────────────────────────────────────────────────────────────
// STATUS HELPERS
// ──────────────────────────────────────────────────────────────

export type TicketStatus = "open" | "in_progress" | "resolved" | "escalated";

export const STATUS_CONFIG: Record<TicketStatus, { label: string; color: string; darkColor: string }> = {
  open: {
    label: "Open",
    color: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-400",
    darkColor: "bg-green-900/40 text-green-400",
  },
  in_progress: {
    label: "In Progress",
    color: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-400",
    darkColor: "bg-blue-900/40 text-blue-400",
  },
  resolved: {
    label: "Resolved",
    color: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-400",
    darkColor: "bg-indigo-900/40 text-indigo-400",
  },
  escalated: {
    label: "Escalated",
    color: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-400",
    darkColor: "bg-red-900/40 text-red-400",
  },
};

export function getStatusConfig(status: string): { label: string; color: string } {
  const key = status.replace(" ", "_") as TicketStatus;
  return STATUS_CONFIG[key] || { label: status, color: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300" };
}

// ──────────────────────────────────────────────────────────────
// PRIORITY HELPERS
// ──────────────────────────────────────────────────────────────

export const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  low: { label: "Low", color: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400" },
  medium: { label: "Medium", color: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400" },
  high: { label: "High", color: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400" },
  critical: { label: "Critical", color: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400" },
};

export function getPriorityConfig(priority: string): { label: string; color: string } {
  return PRIORITY_CONFIG[priority] || { label: priority, color: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400" };
}

// ──────────────────────────────────────────────────────────────
// SENTIMENT HELPERS
// ──────────────────────────────────────────────────────────────

export const SENTIMENT_CONFIG: Record<string, { label: string; color: string; emoji: string }> = {
  positive: { label: "Positive", color: "text-green-500", emoji: "😊" },
  neutral: { label: "Neutral", color: "text-gray-500", emoji: "😐" },
  negative: { label: "Negative", color: "text-orange-500", emoji: "😟" },
  very_negative: { label: "Very Negative", color: "text-red-500", emoji: "😠" },
};

export function getSentimentConfig(sentiment: string): { label: string; color: string; emoji: string } {
  return SENTIMENT_CONFIG[sentiment] || { label: sentiment, color: "text-gray-500", emoji: "❓" };
}

// ──────────────────────────────────────────────────────────────
// CATEGORIES
// ──────────────────────────────────────────────────────────────

export const CATEGORIES = [
  { value: "bug", label: "Bug Report", emoji: "🐛" },
  { value: "feature_request", label: "Feature Request", emoji: "💡" },
  { value: "integration", label: "Integration Issue", emoji: "🔗" },
  { value: "billing", label: "Billing / Account", emoji: "💳" },
  { value: "general", label: "General Question", emoji: "❓" },
];

export function getCategoryEmoji(category: string): string {
  const cat = CATEGORIES.find((c) => c.value === category);
  return cat?.emoji || "📋";
}

// ──────────────────────────────────────────────────────────────
// VALIDATION
// ──────────────────────────────────────────────────────────────

export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export type FormErrors = Partial<Record<string, string>>;

export function validateSupportForm(data: Record<string, string>): FormErrors {
  const errors: FormErrors = {};

  if (!data.name?.trim()) errors.name = "Name is required";
  else if (data.name.trim().length < 2) errors.name = "Name must be at least 2 characters";

  if (!data.email?.trim()) errors.email = "Email is required";
  else if (!isValidEmail(data.email)) errors.email = "Please enter a valid email";

  if (!data.subject?.trim()) errors.subject = "Subject is required";
  else if (data.subject.trim().length < 3) errors.subject = "Subject must be at least 3 characters";

  if (!data.message?.trim()) errors.message = "Message is required";
  else if (data.message.trim().length < 10) errors.message = "Please provide more detail (at least 10 characters)";
  else if (data.message.trim().length > 5000) errors.message = "Message must be under 5,000 characters";

  return errors;
}
