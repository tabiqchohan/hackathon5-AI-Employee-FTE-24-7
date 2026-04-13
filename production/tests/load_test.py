"""
FlowSync Customer Success AI Agent -- Load Test (Locust)
=========================================================
Load testing script using Locust for the FlowSync support API.

Tests:
  - Web form submission endpoint
  - Ticket status lookup
  - Ticket listing
  - Health check

Usage:
  # Web UI (recommended):
  cd production
  locust -f tests/load_test.py --host=http://localhost:8000

  # Then open http://localhost:8089 in browser

  # Headless (CI/CD):
  locust -f tests/load_test.py --host=http://localhost:8000 \
    --headless -u 50 -r 10 --run-time 60s --csv=locust_results

  # Parameters:
  #   -u NUM   : Number of concurrent users
  #   -r NUM   : Spawn rate (users per second)
  #   --run-time : Duration of test

Requirements:
  pip install locust

Architecture:
  The load test simulates real-world traffic patterns:
  - 60% web form submissions (new support requests)
  - 20% ticket status checks (customers checking progress)
  - 15% health checks (monitoring/external)
  - 5% ticket listing (admin/bulk lookups)
"""

from __future__ import annotations

import json
import random
import time

from locust import HttpUser, task, between, events


# ──────────────────────────────────────────────────────────────
# TEST DATA
# ──────────────────────────────────────────────────────────────

SAMPLE_ISSUES = [
    "How do I invite team members to my workspace?",
    "Slack integration is not syncing tasks to my dashboard.",
    "I need help setting up custom workflows for my team.",
    "The AI Task Suggestions feature is not working correctly.",
    "How do I upgrade from Starter to Pro plan?",
    "My Google Drive integration shows an error when connecting.",
    "I can't find the Resource Planner in my dashboard.",
    "How do I set up the AI Meeting Summarizer for my team?",
    "Tasks created in Figma are not appearing in FlowSync.",
    "I need to change my team's permissions and roles.",
    "The Smart Dashboard is showing incorrect data.",
    "How do I export my project data to CSV?",
    "Zoom integration keeps disconnecting every few hours.",
    "I accidentally deleted an important task, can I recover it?",
    "How do I create a custom workflow without code?",
]

SAMPLE_NAMES = [
    "Ahmed Hassan", "Sarah Chen", "Mike Johnson", "Priya Patel",
    "Lars Mueller", "Yuki Tanaka", "Emma Wilson", "Carlos Rivera",
    "Fatima Al-Rashid", "David Kim", "Anna Kowalski", "James Brown",
]

SAMPLE_COMPANIES = [
    "StartupIO", "TechFlow Inc", "DataDriven Co", "CloudFirst LLC",
    "InnovateLab", "ScaleUp Corp", "RemoteFirst Inc", "AgileWorks",
]


# ──────────────────────────────────────────────────────────────
# LOCUST USER CLASS
# ──────────────────────────────────────────────────────────────

class FlowSyncUser(HttpUser):
    """
    Simulates a FlowSync customer support user.

    Wait between 2-8 seconds between tasks (realistic user behavior).
    """
    wait_time = between(2, 8)

    # Track created tickets for follow-up tests
    created_tickets: list[dict] = []

    def on_start(self):
        """Called when a simulated user starts."""
        self.user_name = random.choice(SAMPLE_NAMES)
        self.company = random.choice(SAMPLE_COMPANIES)
        # Generate unique email per user
        user_id = int(time.time() * 1000) % 100000
        self.email = f"loadtest-{user_id}@example.com"

    @task(6)
    def submit_support_form(self):
        """
        Submit a web support form (60% of traffic).

        This is the most common action -- customers submitting new requests.
        """
        issue = random.choice(SAMPLE_ISSUES)
        priority = random.choices(
            ["low", "medium", "high", "critical"],
            weights=[20, 50, 25, 5],
        )[0]

        payload = {
            "name": self.user_name,
            "email": self.email,
            "subject": issue[:60],
            "message": issue,
            "category": random.choice(["bug", "feature_request", "integration", "general"]),
            "priority": priority,
            "company_name": self.company,
        }

        with self.client.post(
            "/support/submit",
            json=payload,
            name="/support/submit",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    # Store for follow-up
                    self.created_tickets.append({
                        "ticket_id": data.get("ticket_id", ""),
                        "email": self.email,
                    })
                    response.success()
                except Exception:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Status {response.status_code}")

    @task(2)
    def check_ticket_status(self):
        """
        Check ticket status (20% of traffic).

        Customers looking up their existing tickets.
        """
        if not self.created_tickets:
            return

        ticket = random.choice(self.created_tickets)
        ticket_id = ticket.get("ticket_id", "")

        if not ticket_id:
            return

        with self.client.get(
            f"/support/ticket/{ticket_id}",
            name="/support/ticket/[id]",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 404):
                response.success()  # 404 is acceptable (ticket not found yet)
            else:
                response.failure(f"Status {response.status_code}")

    @task(1)
    def list_my_tickets(self):
        """
        List all tickets for a customer (10% of traffic).

        Admin-style bulk lookup.
        """
        with self.client.get(
            f"/support/tickets?email={self.email}",
            name="/support/tickets",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    @task(1)
    def health_check(self):
        """
        Health check (10% of traffic).

        Simulates external monitoring pinging the health endpoint.
        """
        with self.client.get(
            "/health",
            name="/health",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("status") == "healthy":
                        response.success()
                    else:
                        response.failure("Unhealthy status")
                except Exception:
                    response.failure("Invalid JSON")
            else:
                response.failure(f"Status {response.status_code}")


# ──────────────────────────────────────────────────────────────
# CUSTOM LOCUST EVENTS
# ──────────────────────────────────────────────────────────────

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the load test starts."""
    print("\n" + "=" * 60)
    print("  FlowSync Load Test Starting")
    print("=" * 60)
    print(f"  Target: {environment.host}")
    print(f"  Users: {environment.parsed_options.num_users if environment.parsed_options else 'N/A'}")
    print(f"  Spawn rate: {environment.parsed_options.spawn_rate if environment.parsed_options else 'N/A'}")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the load test stops."""
    stats = environment.runner.stats

    print("\n" + "=" * 60)
    print("  FlowSync Load Test Results")
    print("=" * 60)
    print(f"  Total requests: {stats.total.num_requests}")
    print(f"  Failed requests: {stats.total.num_failures}")
    print(f"  Success rate: {((stats.total.num_requests - stats.total.num_failures) / max(stats.total.num_requests, 1) * 100):.1f}%")

    if stats.total.avg_response_time:
        print(f"  Avg response time: {stats.total.avg_response_time:.0f}ms")
        print(f"  Median response time: {stats.total.median_response_time:.0f}ms")
        print(f"  95th percentile: {stats.total.get_response_time_percentile(0.95):.0f}ms")
        print(f"  99th percentile: {stats.total.get_response_time_percentile(0.99):.0f}ms")

    print(f"  Requests/sec: {stats.total.current_rps:.1f}")
    print("=" * 60)

    # Fail the test if error rate > 10%
    if stats.total.num_requests > 0:
        error_rate = stats.total.num_failures / stats.total.num_requests * 100
        if error_rate > 10:
            print(f"\n  FAIL: Error rate {error_rate:.1f}% exceeds 10% threshold")
        else:
            print(f"\n  PASS: Error rate {error_rate:.1f}% within acceptable range")
