// FlowSync API Client
// ===================
// All API calls to the FlowSync backend.

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ──────────────────────────────────────────────────────────────
// TYPES
// ──────────────────────────────────────────────────────────────

export interface TicketResponse {
  success: boolean;
  ticket_id: string;
  customer_id: string;
  status: string;
  initial_response: string;
  created_at: string;
  expected_resolution: string;
}

export interface TicketStatusResponse {
  ticket_id: string;
  subject: string;
  status: string;
  priority: string;
  channel: string;
  is_escalated: boolean;
  created_at: string;
  updated_at: string;
  latest_response: string | null;
}

export interface TicketListResponse {
  customer_id: string;
  email: string;
  total: number;
  tickets: Array<{
    ticket_id: string;
    subject: string;
    status: string;
    priority: string;
    created_at: string;
  }>;
}

export interface SupportFormSubmission {
  name: string;
  email: string;
  subject: string;
  message: string;
  category?: string;
  priority?: string;
  company_name?: string;
}

// ──────────────────────────────────────────────────────────────
// API FUNCTIONS
// ──────────────────────────────────────────────────────────────

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

export const api = {
  // Health
  health: () =>
    request<{ status: string; database: string; kafka: string }>("/health"),

  // Support form submission
  submitTicket: (data: SupportFormSubmission) =>
    request<TicketResponse>("/support/submit", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Single ticket lookup
  getTicket: (ticketId: string) =>
    request<TicketStatusResponse>(`/support/ticket/${ticketId}`),

  // List tickets by email
  listTickets: (email: string, limit = 50) =>
    request<TicketListResponse>(`/support/tickets?email=${encodeURIComponent(email)}&limit=${limit}`),

  // API status
  status: () =>
    request<Record<string, unknown>>("/api/status"),
};

export { API_BASE };
