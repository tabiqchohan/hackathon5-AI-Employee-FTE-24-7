import { useState } from "react";

// ──────────────────────────────────────────────────────────────
// CONSTANTS
// ──────────────────────────────────────────────────────────────

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const CATEGORIES = [
  { value: "bug", label: "Bug Report" },
  { value: "feature_request", label: "Feature Request" },
  { value: "integration", label: "Integration Issue" },
  { value: "billing", label: "Billing / Account" },
  { value: "general", label: "General Question" },
];

const PRIORITIES = [
  { value: "low", label: "Low – General inquiry", color: "text-gray-500" },
  { value: "medium", label: "Medium – Standard issue", color: "text-blue-500" },
  { value: "high", label: "High – Workflow affected", color: "text-orange-500" },
  { value: "critical", label: "Critical – System down", color: "text-red-500" },
];

// ──────────────────────────────────────────────────────────────
// SUPPORT FORM COMPONENT
// ──────────────────────────────────────────────────────────────

export default function SupportForm() {
  const [step, setStep] = useState("form"); // "form" | "submitting" | "success"
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    subject: "",
    category: "",
    priority: "medium",
    message: "",
    company_name: "",
  });
  const [errors, setErrors] = useState({});
  const [ticketResult, setTicketResult] = useState(null);

  // ── Handlers ──

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    // Clear error on change
    if (errors[name]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const validate = () => {
    const newErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = "Name is required";
    } else if (formData.name.trim().length < 2) {
      newErrors.name = "Name must be at least 2 characters";
    }

    if (!formData.email.trim()) {
      newErrors.email = "Email is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = "Please enter a valid email address";
    }

    if (!formData.subject.trim()) {
      newErrors.subject = "Subject is required";
    } else if (formData.subject.trim().length < 3) {
      newErrors.subject = "Subject must be at least 3 characters";
    }

    if (!formData.message.trim()) {
      newErrors.message = "Message is required";
    } else if (formData.message.trim().length < 10) {
      newErrors.message = "Please provide more detail (at least 10 characters)";
    } else if (formData.message.trim().length > 5000) {
      newErrors.message = "Message must be under 5,000 characters";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    setStep("submitting");

    try {
      const payload = {
        name: formData.name.trim(),
        email: formData.email.trim().toLowerCase(),
        subject: formData.subject.trim(),
        message: formData.message.trim(),
        category: formData.category || null,
        priority: formData.priority,
        company_name: formData.company_name.trim() || null,
      };

      const response = await fetch(`${API_BASE_URL}/support/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const result = await response.json();
      setTicketResult(result);
      setStep("success");
    } catch (err) {
      setErrors({ submit: err.message || "Failed to submit form. Please try again." });
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

  // ── Render ──

  if (step === "success" && ticketResult) {
    return <SuccessScreen result={ticketResult} onNewRequest={handleReset} />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-600 text-white mb-4">
            <svg
              className="w-8 h-8"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-gray-900">
            FlowSync Support
          </h1>
          <p className="mt-2 text-gray-600">
            Describe your issue and we'll get back to you with a solution.
          </p>
        </div>

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8"
        >
          {/* Submit error banner */}
          {errors.submit && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {errors.submit}
            </div>
          )}

          <div className="space-y-6">
            {/* Name + Email row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField label="Full Name" error={errors.name} required>
                <input
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleChange}
                  placeholder="John Doe"
                  className={`input-field ${errors.name ? "input-error" : ""}`}
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
                  className={`input-field ${errors.email ? "input-error" : ""}`}
                  disabled={step === "submitting"}
                />
              </FormField>
            </div>

            {/* Company (optional) */}
            <FormField label="Company Name" optional>
              <input
                type="text"
                name="company_name"
                value={formData.company_name}
                onChange={handleChange}
                placeholder="Acme Inc. (optional)"
                className="input-field"
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
                className={`input-field ${errors.subject ? "input-error" : ""}`}
                disabled={step === "submitting"}
              />
            </FormField>

            {/* Category + Priority row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField label="Category" optional>
                <select
                  name="category"
                  value={formData.category}
                  onChange={handleChange}
                  className="input-field"
                  disabled={step === "submitting"}
                >
                  <option value="">Select a category...</option>
                  {CATEGORIES.map((cat) => (
                    <option key={cat.value} value={cat.value}>
                      {cat.label}
                    </option>
                  ))}
                </select>
              </FormField>

              <FormField label="Priority" error={errors.priority}>
                <select
                  name="priority"
                  value={formData.priority}
                  onChange={handleChange}
                  className="input-field"
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
                className={`input-field resize-y ${errors.message ? "input-error" : ""}`}
                disabled={step === "submitting"}
              />
            </FormField>
          </div>

          {/* Submit button */}
          <div className="mt-8">
            <button
              type="submit"
              disabled={step === "submitting"}
              className="w-full btn-primary disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {step === "submitting" ? (
                <span className="flex items-center justify-center gap-2">
                  <LoadingSpinner />
                  Submitting...
                </span>
              ) : (
                "Submit Support Request"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// SUB-COMPONENTS
// ──────────────────────────────────────────────────────────────

function FormField({ label, error, required, optional, counter, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
        {optional && <span className="text-gray-400 ml-1">(optional)</span>}
      </label>
      {children}
      {counter && (
        <p className="mt-1 text-xs text-gray-400 text-right">
          {counter.current}/{counter.max}
        </p>
      )}
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  );
}

function LoadingSpinner() {
  return (
    <svg
      className="animate-spin h-4 w-4"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

function SuccessScreen({ result, onNewRequest }) {
  const priorityColors = {
    low: "bg-gray-100 text-gray-700",
    medium: "bg-blue-100 text-blue-700",
    high: "bg-orange-100 text-orange-700",
    critical: "bg-red-100 text-red-700",
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Success card */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 text-green-600 mb-4">
            <svg
              className="w-8 h-8"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>

          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Request Submitted!
          </h2>
          <p className="text-gray-600 mb-6">
            We've received your support request and are working on it.
          </p>

          {/* Ticket details */}
          <div className="bg-gray-50 rounded-xl p-6 text-left space-y-4 mb-6">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">Ticket ID</span>
              <span className="font-mono font-bold text-lg text-gray-900">
                {result.ticket_id}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">Status</span>
              <span
                className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wide ${
                  result.status === "open"
                    ? "bg-green-100 text-green-700"
                    : result.status === "escalated"
                    ? "bg-red-100 text-red-700"
                    : "bg-blue-100 text-blue-700"
                }`}
              >
                {result.status.replace("_", " ")}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">Expected Response</span>
              <span className="text-sm font-medium text-gray-700">
                {result.expected_resolution || "within 24 hours"}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">Submitted At</span>
              <span className="text-sm text-gray-600">
                {new Date(result.created_at).toLocaleString()}
              </span>
            </div>
          </div>

          {/* AI Response */}
          {result.initial_response && (
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-6 text-left mb-6">
              <h3 className="text-sm font-semibold text-blue-800 mb-2 flex items-center gap-2">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm1 11H9v-2h2v2zm0-4H9V5h2v4z" />
                </svg>
                Initial Response from FlowSync AI
              </h3>
              <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-line">
                {result.initial_response}
              </p>
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() =>
                navigator.clipboard?.writeText(result.ticket_id)
              }
              className="btn-secondary"
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              Copy Ticket ID
            </button>
            <button onClick={onNewRequest} className="btn-primary">
              Submit Another Request
            </button>
          </div>
        </div>

        {/* Info footer */}
        <p className="text-center text-sm text-gray-400 mt-6">
          Save your Ticket ID to check status later.
        </p>
      </div>
    </div>
  );
}
