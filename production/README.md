# FlowSync Customer Success AI Agent

## 24/7 Digital Employee for Customer Support

A production-grade, AI-powered customer success agent that handles support requests across multiple channels (Web Form, Gmail, WhatsApp) using the OpenAI Agents SDK, Kafka event streaming, and PostgreSQL.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FLOWSYNC PLATFORM                                │
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                              │
│  │ Web Form │    │  Gmail   │    │ WhatsApp │   ←── Customer Channels      │
│  │ (React)  │    │ Webhook  │    │ Webhook  │                              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘                              │
│       │               │               │                                     │
│       └───────────────┴───────────────┘                                     │
│                       │                                                     │
│              ┌────────▼────────┐                                            │
│              │  FastAPI Server  │   ←── API Layer (api/main.py)             │
│              │  :8000           │                                            │
│              └────────┬────────┘                                            │
│                       │                                                     │
│              ┌────────▼────────┐                                            │
│              │  Kafka Producer  │   ←── fte.tickets.incoming                │
│              └────────┬────────┘                                            │
│                       │                                                     │
│       ┌───────────────┴───────────────┐                                     │
│       │                               │                                     │
│  ┌────▼─────┐                  ┌─────▼──────┐                               │
│  │  Worker   │  ←── Message    │  Worker    │   ←── UnifiedMessageProcessor │
│  │  Pod 1    │      Processor  │  Pod 2-N   │       (workers/)              │
│  └────┬─────┘                  └─────┬──────┘                               │
│       │                               │                                     │
│       └───────────────┬───────────────┘                                     │
│                       │                                                     │
│          ┌────────────┼────────────┐                                        │
│          │            │            │                                        │
│     ┌────▼───┐  ┌────▼────┐  ┌────▼────┐                                   │
│     │ OpenAI │  │ Postgres│  │ Kafka   │                                   │
│     │ Agents │  │ (asyncpg)│  │ Topics  │                                   │
│     │ SDK    │  │         │  │         │                                   │
│     └────────┘  └─────────┘  └─────────┘                                   │
│                                                                             │
│  Output: AI-generated responses, escalation decisions, metrics              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Channel Support** | Web Form, Gmail, WhatsApp — all unified through Kafka |
| **AI-Powered Responses** | OpenAI Agents SDK with 7 production tools |
| **Auto-Escalation** | 5 escalation rules (pricing, anger, human request, security, sentiment) |
| **Cross-Channel Memory** | Customer identity resolved across channels |
| **Sentiment Analysis** | Real-time emotional tone detection + trend tracking |
| **Kafka Event Streaming** | All events published for downstream processing |
| **Kubernetes Ready** | Full K8s manifests with HPA, probes, resource limits |
| **In-Memory Fallback** | Works without Kafka or DB for development/testing |

## Quick Start

### Prerequisites
- Python 3.12+
- OpenAI API key
- PostgreSQL (optional — falls back to in-memory)
- Kafka (optional — falls back to direct processing)

### 1. Install Dependencies
```bash
cd production
pip install -r requirements.txt
```

### 2. Set Environment
```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

### 3. Run Tests
```bash
# All unit tests (no external services needed)
python -m pytest tests/ -v -p no:hypothesis -p no:anyio --capture=no

# E2E tests (tests the full pipeline)
python -m pytest tests/test_multichannel_e2e.py -v -p no:hypothesis -p no:anyio --capture=no
```

### 4. Run API Server
```bash
cd production
uvicorn api.main:app --reload --port 8000
```

- **API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

### 5. Run Worker (message processor)
```bash
cd production
python -m workers.message_processor
```

## Project Structure

```
production/
├── agent/                          # OpenAI Agents SDK
│   ├── customer_success_agent.py   # Main agent (Agent, Runner)
│   ├── tools.py                    # 7 tools (DB + in-memory fallback)
│   ├── prompts.py                  # System prompts & escalation rules
│   └── formatters.py               # Channel-specific formatting
│
├── api/                            # FastAPI web server
│   └── main.py                     # App with all channel endpoints
│
├── channels/                       # Channel handlers
│   ├── web_form_handler.py         # Web support form (active)
│   ├── gmail_handler.py            # Gmail webhook (active, Kafka-routed)
│   └── whatsapp_handler.py         # WhatsApp webhook (active, Kafka-routed)
│
├── database/                       # Data access layer
│   └── queries.py                  # Async PostgreSQL queries (asyncpg)
│
├── workers/                        # Background workers
│   └── message_processor.py        # UnifiedMessageProcessor (Kafka consumer)
│
├── k8s/                            # Kubernetes manifests
│   ├── namespace.yaml              # Namespace isolation
│   ├── configmap.yaml              # Environment variables
│   ├── secrets.yaml                # Secrets template
│   ├── deployment-api.yaml         # API pods (3 replicas, HPA)
│   ├── deployment-worker.yaml      # Worker pods (3 replicas, HPA)
│   ├── service.yaml                # Services (ClusterIP + LoadBalancer)
│   ├── ingress.yaml                # TLS ingress
│   ├── hpa.yaml                    # Horizontal Pod Autoscaler
│   ├── postgres.yaml               # PostgreSQL StatefulSet
│   ├── kafka.yaml                  # Strimzi Kafka template
│   ├── kustomization.yaml          # Kustomize base
│   └── deploy.sh                   # Deploy helper script
│
├── tests/                          # Test suite
│   ├── test_agent.py               # Agent unit tests (45 tests)
│   ├── test_kafka_processor.py     # Kafka + processor tests (45 tests)
│   ├── test_multichannel_e2e.py    # E2E cross-channel tests
│   ├── load_test.py                # Locust load tests
│   └── _smoke_channels.py          # Smoke tests (15 tests)
│
├── web-form/                       # React frontend
│   └── SupportForm.jsx             # Support form component (Tailwind)
│
├── kafka_client.py                 # Kafka producer/consumer classes
├── Dockerfile                      # Multi-stage production Dockerfile
├── docker-compose.yml              # Full local dev environment
├── .env.example                    # Environment template
├── requirements.txt                # Python dependencies
└── RUNBOOK.md                      # Operations guide

src/                                # Shared prototype modules
├── prototype.py                    # Sentiment analysis, intent classification
└── knowledge_base.py               # Knowledge base search
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check (DB + Kafka status) |
| `GET` | `/api/status` | Detailed API status |
| `POST` | `/support/submit` | Submit web support form |
| `GET` | `/support/ticket/{id}` | Check ticket status |
| `GET` | `/support/tickets?email=` | List tickets by email |
| `POST` | `/channels/gmail/incoming` | Gmail webhook |
| `POST` | `/channels/whatsapp/incoming` | WhatsApp webhook |
| `GET` | `/channels/gmail/status` | Gmail integration status |
| `GET` | `/channels/whatsapp/status` | WhatsApp integration status |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | Model for AI agent |
| `DATABASE_URL` | No* | — | PostgreSQL connection string |
| `KAFKA_BOOTSTRAP_SERVERS` | No* | `localhost:9092` | Kafka broker addresses |
| `KAFKA_CONSUMER_GROUP` | No | `flowsync-message-processor` | Kafka consumer group ID |
| `LOG_LEVEL` | No | `info` | Logging level |
| `API_HOST` | No | `0.0.0.0` | API bind address |
| `API_PORT` | No | `8000` | API port |
| `CORS_ORIGINS` | No | `["http://localhost:3000"]` | Allowed CORS origins |

*Optional — system falls back to in-memory mode if unavailable.

## Kafka Topics

| Topic | Purpose |
|-------|---------|
| `fte.tickets.incoming` | All incoming messages from every channel |
| `fte.tickets.responses` | AI-generated responses ready to send |
| `fte.tickets.escalations` | Escalated tickets |
| `fte.events.customer` | Customer lifecycle events |
| `fte.events.conversation` | Conversation events |
| `fte.metrics.agent` | Agent performance metrics |
| `fte.metrics.channel` | Channel metrics |

## Kubernetes Deployment

### Local (minikube)
```bash
cd production
./k8s/deploy.sh minikube
```

### Cloud (AKS/EKS/GKE)
```bash
# Set cluster context first
export OPENAI_API_KEY=sk-proj-...
export REGISTRY=ghcr.io/your-org
./k8s/deploy.sh production
```

### Verify
```bash
kubectl get pods -n flowsync
kubectl get hpa -n flowsync
kubectl port-forward -n flows svc/flowsync-api 8000:80
curl http://localhost:8000/health
```

### Teardown
```bash
./k8s/deploy.sh teardown
```

## Docker Compose

```bash
cd production
export OPENAI_API_KEY=sk-...
docker compose up -d
docker compose logs -f api
docker compose logs -f worker
```

## Test Results

```
test_agent.py:              45 passed, 4 skipped (OPENAI_API_KEY)
test_kafka_processor.py:    45 passed
test_multichannel_e2e.py:   E2E tests
_smoke_channels.py:         15 passed
─────────────────────────────────────────
Total:                      105+ passing
```

## License

Proprietary — FlowSync Customer Success Platform
