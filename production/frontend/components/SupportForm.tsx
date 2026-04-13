"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, type SupportFormSubmission } from "@/lib/api";
import { validateSupportForm, type FormErrors, CATEGORIES } from "@/lib/utils";
import { useToast } from "@/components/Toast";
import {
  Loader2,
  Send,
  CheckCircle,
  Copy,
  ArrowRight,
} from "lucide-react";

const PRIORITIES = [
  { value: "low", label: "Low – General inquiry" },
  { value: "medium", label: "Medium – Standard issue", default: true },
  { value: "high", label: "High – Workflow affected" },
  { value: "critical", label: "Critical – System down" },
];

interface SupportFormProps {
  onSuccess?: (ticketId: string) => void;
}

export default function SupportForm({ onSuccess }: SupportFormProps) {
  const router = useRouter();
  const { success, error: showError } = useToast();
  const [step, setStep] = useState<"form" | "submitting" | "success">("form");
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    subject: "",
    category: "",
    priority: "medium",
    message: "",
    company_name: "",
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [ticketResult, setTicketResult] = useState<{
    ticket_id: string;
    status: string;
    expected_resolution: string;
    created_at: string;
    initial_response: string;
  } | null>(null);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationErrors = validateSupportForm(formData);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setStep("submitting");

    try {
      const payload: SupportFormSubmission = {
        name: formData.name.trim(),
        email: formData.email.trim().toLowerCase(),
        subject: formData.subject.trim(),
        message: formData.message.trim(),
        category: formData.category || undefined,
        priority: formData.priority,
        company_name: formData.company_name.trim() || undefined,
      };

      const result = await api.submitTicket(payload);
      setTicketResult(result);
      setStep("success");
      success("Ticket Created!", `Your ticket ID is ${result.ticket_id}`);
      onSuccess?.(result.ticket_id);
    } catch (err) {
      showError(
        "Submission Failed",
        err instanceof Error ? err.message : "Please try again later"
      );
      setStep("form");
    }
  };

  const handleReset = () => {
    setFormData({
      name: "",
      email: "",
      subject: "",
      category: "",
      priority: "medium",
      message: "",
      company_name: "",
    });
    setErrors({});
    setTicketResult(null);
    setStep("form");
  };

  const copyTicketId = () => {
    if (ticketResult?.ticket_id) {
      navigator.clipboard.writeText(ticketResult.ticket_id);
      success("Copied!", "Ticket ID copied to clipboard");
    }
  };

  // ── Success Screen ──
  if (step === "success" && ticketResult) {
    return (
      <div className="card p-6 sm:p-8 animate-bounce-in">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400 mb-4">
            <CheckCircle className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-1">
            Request Submitted!
          </h2>
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            We&apos;ve received your request and are working on it.
          </p>
        </div>

        {/* Ticket Details */}
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-5 space-y-3 mb-5">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500 dark:text-gray-400">Ticket ID</span>
            <span className="font-mono font-bold text-lg text-gray-900 dark:text-white">
              {ticketResult.ticket_id}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500 dark:text-gray-400">Status</span>
            <span className="badge bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400">
              {ticketResult.status.replace("_", " ")}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Expected Response
            </span>
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {ticketResult.expected_resolution}
            </span>
          </div>
        </div>

        {/* AI Response Preview */}
        {ticketResult.initial_response && (
          <div className="bg-brand-50 dark:bg-brand-900/20 border border-brand-100 dark:border-brand-800/30 rounded-xl p-5 mb-5">
            <h3 className="text-sm font-semibold text-brand-700 dark:text-brand-400 mb-2">
              AI Initial Response
            </h3>
            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-line leading-relaxed">
              {ticketResult.initial_response}
            </p>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={copyTicketId}
            className="btn btn-secondary flex-1"
          >
            <Copy className="w-4 h-4" />
            Copy Ticket ID
          </button>
          <button
            onClick={() => router.push(`/ticket/${ticketResult.ticket_id}`)}
            className="btn btn-primary flex-1"
          >
            View Ticket
            <ArrowRight className="w-4 h-4" />
          </button>
          <button onClick={handleReset} className="btn btn-outline flex-1">
            New Request
          </button>
        </div>
      </div>
    );
  }

  // ── Form ──
  return (
    <form onSubmit={handleSubmit} className="card p-6 sm:p-8">
      <div className="space-y-5">
        {/* Name + Email */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label="Full Name" error={errors.name} required>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              placeholder="John Doe"
              className={`input ${errors.name ? "input-error" : ""}`}
              disabled={step === "submitting"}
            />
          </FormField>

          <FormField label="Email Address" error={errors.email} required>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="john@company.com"
              className={`input ${errors.email ? "input-error" : ""}`}
              disabled={step === "submitting"}
            />
          </FormField>
        </div>

        {/* Company */}
        <FormField label="Company Name" optional>
          <input
            type="text"
            name="company_name"
            value={formData.company_name}
            onChange={handleChange}
            placeholder="Acme Inc. (optional)"
            className="input"
            disabled={step === "submitting"}
          />
        </FormField>

        {/* Subject */}
        <FormField label="Subject" error={errors.subject} required>
          <input
            type="text"
            name="subject"
            value={formData.subject}
            onChange={handleChange}
            placeholder="Brief description of your issue"
            className={`input ${errors.subject ? "input-error" : ""}`}
            disabled={step === "submitting"}
          />
        </FormField>

        {/* Category + Priority */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label="Category" optional>
            <select
              name="category"
              value={formData.category}
              onChange={handleChange}
              className="select"
              disabled={step === "submitting"}
            >
              <option value="">Select a category...</option>
              {CATEGORIES.map((cat) => (
                <option key={cat.value} value={cat.value}>
                  {cat.emoji} {cat.label}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label="Priority">
            <select
              name="priority"
              value={formData.priority}
              onChange={handleChange}
              className="select"
              disabled={step === "submitting"}
            >
              {PRIORITIES.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </FormField>
        </div>

        {/* Message */}
        <FormField
          label="Message"
          error={errors.message}
          required
          counter={{ current: formData.message.length, max: 5000 }}
        >
          <textarea
            name="message"
            value={formData.message}
            onChange={handleChange}
            placeholder="Please describe your issue in detail. Include steps to reproduce if it's a bug."
            rows={5}
            className={`textarea ${errors.message ? "input-error" : ""}`}
            disabled={step === "submitting"}
          />
        </FormField>
      </div>

      {/* Submit */}
      <div className="mt-6">
        <button
          type="submit"
          disabled={step === "submitting"}
          className="btn btn-primary w-full disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {step === "submitting" ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Submitting...
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              Submit Support Request
            </>
          )}
        </button>
      </div>
    </form>
  );
}

// ──────────────────────────────────────────────────────────────
// SUB-COMPONENTS
// ──────────────────────────────────────────────────────────────

function FormField({
  label,
  error,
  required,
  optional,
  counter,
  children,
}: {
  label: string;
  error?: string;
  required?: boolean;
  optional?: boolean;
  counter?: { current: number; max: number };
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
        {optional && <span className="text-gray-400 ml-1">(optional)</span>}
      </label>
      {children}
      {counter && (
        <p className="mt-1 text-xs text-gray-400 dark:text-gray-500 text-right">
          {counter.current}/{counter.max}
        </p>
      )}
      {error && <p className="mt-1 text-sm text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}
