# FlowSync Customer Success AI Agent -- Multi-Stage Production Dockerfile
# ==========================================================================
# Stage 1: Build dependencies
# Stage 2: Production runtime (minimal image)
#
# Build:
#   docker build -t flowsync/flowsync-api:latest -f Dockerfile .
#   docker build -t flowsync/flowsync-worker:latest -f Dockerfile --target worker .
#
# Test:
#   docker run --rm -p 8000:8000 flowsync/flowsync-api:latest

# ──────────────────────────────────────────────────────────────
# STAGE 1: Build dependencies
# ──────────────────────────────────────────────────────────────

FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ──────────────────────────────────────────────────────────────
# STAGE 2: Production runtime (API)
# ──────────────────────────────────────────────────────────────

FROM python:3.12-slim AS api

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY agent/ ./agent/
COPY api/ ./api/
COPY channels/ ./channels/
COPY database/ ./database/
COPY workers/ ./workers/
COPY kafka_client.py .
COPY src/ ./src/

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run FastAPI
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# ──────────────────────────────────────────────────────────────
# STAGE 3: Production runtime (Worker)
# ──────────────────────────────────────────────────────────────

FROM python:3.12-slim AS worker

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code (worker needs all modules)
COPY agent/ ./agent/
COPY channels/ ./channels/
COPY database/ ./database/
COPY workers/ ./workers/
COPY kafka_client.py .
COPY src/ ./src/

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

# No exposed ports (worker is background process)

# Health check (process-based)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "message_processor" || exit 1

# Run message processor
CMD ["python", "-m", "workers.message_processor"]
