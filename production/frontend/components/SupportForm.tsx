"use client";

import React, { useState } from 'react';
import { Loader2, CheckCircle, Send } from 'lucide-react';

const CATEGORIES = [
  { value: 'general', label: 'General / Questions' },
  { value: 'technical', label: 'Technical Support' },
  { value: 'integration', label: 'Integration Issue' },
  { value: 'bug_report', label: 'Bug Report' },
  { value: 'feature_request', label: 'Feature Request' },
  { value: 'billing', label: 'Billing / Account Issue' },
];

const PRIORITIES = [
  { value: 'low', label: 'Low – General inquiry' },
  { value: 'medium', label: 'Medium – Standard issue' },
  { value: 'high', label: 'High – Workflow affected' },
  { value: 'critical', label: 'Critical – System down' },
];

interface SupportFormProps {
  onSuccess?: (ticketId: string) => void;   // ← Yeh line add ki
}

export default function SupportForm({ onSuccess }: SupportFormProps) {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    company_name: "",
    subject: "",
    category: "general",
    priority: "medium",
    message: ""
  });

  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [ticketId, setTicketId] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [responseMessage, setResponseMessage] = useState('');

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('submitting');
    setErrorMsg('');

    if (!formData.name.trim() || !formData.email.trim() || !formData.subject.trim() || !formData.message.trim()) {
      setErrorMsg("Please fill all required fields.");
      setStatus('error');
      return;
    }

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/support/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Submission failed');
      }

      setTicketId(data.ticket_id || 'N/A');
      setResponseMessage(data.message || "Thank you! Our AI assistant will respond shortly.");
      setStatus('success');

      // Call onSuccess if provided
      onSuccess?.(data.ticket_id);

    } catch (err: any) {
      setErrorMsg(err.message || 'Something went wrong. Please try again.');
      setStatus('error');
    }
  };

  // Success Screen
  if (status === 'success') {
    return (
      <div className="max-w-2xl mx-auto p-8 bg-white dark:bg-gray-900 rounded-2xl shadow-xl text-center">
        <CheckCircle className="w-20 h-20 text-green-500 mx-auto mb-6" />
        <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Thank You!</h2>
        <p className="text-gray-600 dark:text-gray-400 mb-6">{responseMessage}</p>
        
        <div className="bg-gray-50 dark:bg-gray-800 p-6 rounded-xl mb-8">
          <p className="text-sm text-gray-500">Your Ticket ID</p>
          <p className="text-2xl font-mono font-bold text-gray-900 dark:text-white mt-1 break-all">{ticketId}</p>
        </div>

        <button
          onClick={() => window.location.reload()}
          className="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl font-medium transition-colors"
        >
          Submit Another Request
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-8 bg-white dark:bg-gray-900 rounded-2xl shadow-xl">
      <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Contact Support</h2>
      <p className="text-gray-600 dark:text-gray-400 mb-8">
        Our AI assistant is ready to help you 24/7.
      </p>

      {errorMsg && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl">
          {errorMsg}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium mb-1">Full Name *</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-blue-500"
              placeholder="Ahmed Khan"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Company Name (Optional)</label>
            <input
              type="text"
              name="company_name"
              value={formData.company_name}
              onChange={handleChange}
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-blue-500"
              placeholder="Your Company Name"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Email Address *</label>
          <input
            type="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            required
            className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-blue-500"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Subject *</label>
          <input
            type="text"
            name="subject"
            value={formData.subject}
            onChange={handleChange}
            required
            className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-blue-500"
            placeholder="Brief description of your issue"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium mb-1">Category *</label>
            <select
              name="category"
              value={formData.category}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-blue-500"
            >
              {CATEGORIES.map(cat => (
                <option key={cat.value} value={cat.value}>
                  {cat.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Priority</label>
            <select
              name="priority"
              value={formData.priority}
              onChange={handleChange}
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-blue-500"
            >
              {PRIORITIES.map(p => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">How can we help? *</label>
          <textarea
            name="message"
            value={formData.message}
            onChange={handleChange}
            required
            rows={6}
            className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-blue-500 resize-none"
            placeholder="Please describe your issue or question in detail..."
          />
        </div>

        <button
          type="submit"
          disabled={status === 'submitting'}
          className="w-full py-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-2xl font-semibold text-lg transition-all flex items-center justify-center gap-2"
        >
          {status === 'submitting' ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Submitting...
            </>
          ) : (
            <>
              <Send className="w-5 h-5" />
              Submit Support Request
            </>
          )}
        </button>
      </form>
    </div>
  );
}