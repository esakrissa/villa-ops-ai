# VillaOps AI

An AI operations agent for villa and hotel property managers in Bali. Managers chat with an agent that looks up bookings, manages properties and guests, benchmarks prices against Booking.com, answers policy questions from the company's own documents with citations, and asks for approval before changing anything. Built with LangGraph, MCP, Pinecone, FastAPI, Next.js and Stripe.

![CI](https://github.com/esakrissa/villa-ops-ai/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.13+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.162-green)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent-purple)
![MCP](https://img.shields.io/badge/MCP_2-Streamable_HTTP-orange)
![Pinecone](https://img.shields.io/badge/RAG-Pinecone-1b17f5)
![LangSmith](https://img.shields.io/badge/Tracing-LangSmith-2f2c25)
![Next.js](https://img.shields.io/badge/Next.js-16-black)
![Stripe](https://img.shields.io/badge/Stripe-Billing-blueviolet)
![AWS](https://img.shields.io/badge/AWS-EC2_+_Caddy-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

**Live Demo:** [villaops.esakrissa.com](https://villaops.esakrissa.com) (the demo server runs on demand — it may be powered off)
&nbsp;|&nbsp;
**API Docs:** [villaops.esakrissa.com/docs](https://villaops.esakrissa.com/docs)

---

## Key Features

- **Agent that acts, not just chats** — a LangGraph agent with 26 MCP tools across 5 servers (VillaOps, Booking.com, Airbnb, Tripadvisor, Exa web search), streaming over SSE with live tool steps you can expand to see arguments and results
- **Knowledge base (RAG) with a live pipeline** — upload PDF/DOCX/Markdown and watch it extract → chunk (heading-aware, with overlap) → embed and index in Pinecone → verify, chunk by chunk. The agent searches it with `kb_search`, reranks with `bge-reranker-v2-m3`, and cites `(Document, Section)`. Delete a document and it's gone from answers immediately
- **Human-in-the-loop** — destructive tools (delete guest/property) pause the graph with `interrupt()` and show an approval card; nothing changes until you confirm
- **Fast, resilient model routing** — all models via OpenRouter (default GPT-6 Luna; Claude Haiku 5.5, Gemini Flash-Lite and five free models in the picker), an 8-second first-token deadline with automatic failover, and latency-sorted provider routing. Typical tool-using reply: ~3–6 s
- **Latency engineering backed by traces** — cached and parallel MCP tool discovery, de-duplicated conversation state, trimmed history, provider prompt caching; profiled with LangSmith (see the traces below)
- **Live market data with photo cards** — Booking.com, Airbnb and Tripadvisor MCP servers in `mcp-servers/` power rate benchmarking and recommendations rendered as cards in the chat
- **Full SaaS billing** — Stripe Checkout, Customer Portal and a webhook-driven subscription lifecycle with plan-gated usage (properties, AI queries) for Free / Pro / Business
- **Per-user tool and model controls** — turn individual tools off or pick a model from the composer
- **Auth** — email/password plus Google and GitHub OAuth with JWT
- **On-demand cloud demo** — one EC2 instance + Elastic IP + Caddy (automatic HTTPS) with a start/stop script and a 2-hour auto-stop, so it only costs money while it's on

---

## Screenshots

> Captured from the live deployment on 2026-11-24. The previous UI is kept in [`docs/images/archive/2026-02-v1`](docs/images/archive/2026-02-v1).

### Agent

| Agent answers with real data and policy citations | Expandable tool steps (arguments + JSON results) |
|:---:|:---:|
| ![Agent combining booking lookup and policy search](docs/images/chat_tool_steps.png) | ![Tool step details](docs/images/chat_tool_result.png) |

| Market research with Booking.com photo cards | Human-in-the-loop approval before deleting |
|:---:|:---:|
| ![Market comparison cards](docs/images/chat_market.png) | ![Approval card](docs/images/chat_confirm.png) |

| Model picker (OpenRouter: paid + free) | Per-user tool toggles (26 tools) |
|:---:|:---:|
| ![Model picker](docs/images/chat_models.png) | ![Tools menu](docs/images/chat_tools.png) |

### Knowledge base (RAG)

| Live ingestion pipeline with indexed chunks | Test retrieval (reranked, with scores) |
|:---:|:---:|
| ![Knowledge pipeline](docs/images/knowledge.png) | ![Knowledge search](docs/images/knowledge_search.png) |

| Pinecone index (integrated embedding) | Same query straight in Pinecone |
|:---:|:---:|
| ![Pinecone index](docs/images/pinecone_index.jpg) | ![Pinecone search](docs/images/pinecone_search.jpg) |

### Observability (LangSmith)

| Every chat is a LangGraph trace | Trace tree: agent → model → tools, with timings and tokens |
|:---:|:---:|
| ![LangSmith traces](docs/images/langsmith_traces.jpg) | ![LangSmith trace](docs/images/langsmith_trace.jpg) |

### Billing (Stripe)

| Free plan usage | Stripe Checkout (test card) |
|:---:|:---:|
| ![Billing free](docs/images/billing.png) | ![Stripe checkout](docs/images/stripe_checkout.png) |

| Payment successful | Pro plan with usage allowance |
|:---:|:---:|
| ![Checkout success](docs/images/stripe_success.png) | ![Billing pro](docs/images/billing_pro.png) |

### Dashboard and landing

| Overview | Analytics |
|:---:|:---:|
| ![Overview](docs/images/dashboard.png) | ![Analytics](docs/images/analytics.png) |

| Bookings | Properties |
|:---:|:---:|
| ![Bookings](docs/images/bookings.png) | ![Properties](docs/images/properties.png) |

| Landing page | Login (email + Google + GitHub) |
|:---:|:---:|
| ![Home](docs/images/home.png) | ![Login](docs/images/login.png) |

| Agent home | Pricing |
|:---:|:---:|
| ![Agent welcome](docs/images/chat_welcome.png) | ![Pricing](docs/images/pricing.png) |

---

## What It Does

Instead of juggling spreadsheets and dashboards, property managers can simply ask:

- *"Sarah Chen wants to cancel her Canggu booking — how much does she get back under our policy?"* (booking lookup + knowledge base, cited)
- *"Which guests are arriving in the next 7 days?"*
- *"How does my Ubud villa's rate compare with Booking.com in Ubud?"* (live market data + photo cards)
- *"What's our occupancy rate this month?"*
- *"How long do we keep guest passport copies?"* (answered from the privacy policy)
- *"Delete the guest Yuki Tanaka"* (pauses for approval)

The agent picks the right MCP tools, runs independent ones in parallel, streams each step and the answer, and cites company documents when it uses them. Sample documents for the knowledge base are in [`docs/knowledge-samples/`](docs/knowledge-samples/) (Markdown and PDF).

---

## Architecture

### Application Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    Next.js Frontend                        │
│                                                            │
│  ┌────────┐  ┌────────┐  ┌───────────┐  ┌───────────────┐  │
│  │  Auth  │  │Pricing │  │  Chat UI  │  │   Dashboard   │  │
│  │  Pages │  │  Page  │  │  (SSE)    │  │  (Bookings/   │  │
│  │        │  │        │  │           │  │   Analytics)  │  │
│  └────────┘  └────────┘  └───────────┘  └───────────────┘  │
└────────┬───────────────────────────────────────────────────┘
         │ REST + SSE
         ▼
┌────────────────────────────────────────────────────┐
│              FastAPI Backend                       │
│                                                    │
│  ┌──────────────────────────────────────────────┐  │
│  │  Auth: JWT + Google OAuth + GitHub OAuth     │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ┌──────────────────────────────────────────────┐  │
│  │  Billing: Stripe Checkout + Webhooks         │  │
│  │  Plan gating middleware (usage limits)       │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ┌──────────┐  ┌────────────────────────────────┐  │
│  │ REST API │  │  Chat API (SSE streaming)      │  │
│  │ /api/v1  │  │  /api/v1/chat                  │  │
│  └────┬─────┘  └──────────┬─────────────────────┘  │
│       │                   │                        │
│       │        ┌──────────▼─────────────────────┐  │
│       │        │   LangGraph Agent              │  │
│       │        │ + MCP Client (Streamable HTTP) │  │
│       │        └──────────┬─────────────────────┘  │
│       │                   │ Streamable HTTP        │
│       │                   ▼                        │
│  ┌────────────────────────────────────────────┐    │
│  │  MCP Servers (Streamable HTTP, 26 tools)   │    │
│  │  VillaOps: bookings, guests, properties,   │    │
│  │    analytics, notifications, kb_search     │    │
│  │  Booking.com | Airbnb | Tripadvisor | Exa  │    │
│  └────────────────────────────────────────────┘    │
│                                                    │
│  ┌────────────────────────────────────────────┐    │
│  │  LiteLLM → OpenRouter                      │    │
│  │  GPT-6 Luna (default) → retry → free model │    │
│  │  8 s first-token deadline + failover       │    │
│  └────────────────────────────────────────────┘    │
│                                                    │
│  ┌────────────────────────────────────────────┐    │
│  │  Knowledge base: extract → chunk → index   │    │
│  │  Pinecone (llama-text-embed-v2 + rerank)   │    │
│  └────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────┘

┌──────────────────┐  ┌────────────────┐  ┌─────────────┐  ┌───────────┐  ┌───────────┐
│  PostgreSQL      │  │     Redis      │  │   Stripe    │  │ Pinecone  │  │ LangSmith │
│  (10 tables)     │  │    (cache)     │  │   Payments  │  │  vectors  │  │  tracing  │
└──────────────────┘  └────────────────┘  └─────────────┘  └───────────┘  └───────────┘
```

### Deployment Architecture (current: on-demand demo server)

```
          Cloudflare DNS (villaops.esakrissa.com, DNS only)
                         │
                         ▼   Elastic IP 13.228.0.170
     ┌──────────────── EC2 t3.large · ap-southeast-1 ────────────────┐
     │  Caddy (automatic HTTPS) ── /api, /health, /docs → backend    │
     │                         └─ everything else   → frontend       │
     │                                                               │
     │  backend (FastAPI + LangGraph)   frontend (Next.js prod)      │
     │  mcp (VillaOps tools)   booking-mcp  airbnb-mcp  tripadvisor  │
     │  postgres   redis              (docker compose, one box)      │
     └───────────────────────────────────────────────────────────────┘
        ./scripts/demo.sh start | stop | status | deploy | destroy
        Auto-stop after 2 h · pay only while it runs
```

The original production setup (ECS Fargate + RDS + ElastiCache behind an Nginx service, see `.aws/`) was retired to save cost; the deploy workflow is now manual-only.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.13+, FastAPI (async), Pydantic v2 |
| **Agent** | LangGraph (checkpointed state, `interrupt()` approvals, first-token-deadline failover) |
| **Tool Protocol** | MCP (Streamable HTTP transport) |
| **LLM Gateway** | LiteLLM → OpenRouter (GPT-6 Luna default, Claude Haiku 5.5, Gemini Flash-Lite, free Nemotron/Dots/Flint) |
| **RAG** | Pinecone integrated embedding (`llama-text-embed-v2`) + `bge-reranker-v2-m3`, pypdf / python-docx extraction |
| **Observability** | LangSmith tracing |
| **Payments** | Stripe (Checkout + Webhooks + Customer Portal) |
| **Database** | PostgreSQL 16 + SQLAlchemy (async) + Alembic migrations |
| **Cache** | Redis 7 |
| **Auth** | JWT (python-jose) + Google OAuth + GitHub OAuth (authlib) |
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS v4 |
| **Charts** | Recharts |
| **Testing** | pytest, pytest-asyncio, httpx (389 tests) |
| **CI** | GitHub Actions (lint + test + build) |
| **Deployment** | AWS EC2 (on demand) + Elastic IP + Docker Compose + Cloudflare DNS |
| **Reverse Proxy** | Caddy (automatic HTTPS, SSE-friendly streaming) |

---

## Pricing

| | Free | Pro | Business |
|---|---|---|---|
| **Price** | $0/mo | $29/mo | $79/mo |
| **Properties** | 1 | 5 | Unlimited |
| **AI Queries** | 50/mo | 500/mo | Unlimited |
| **Analytics** | Basic | Full | Full + Export |
| **Notifications** | — | Yes | Yes |

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.13+
- Node.js 22+
- API keys for at least one LLM provider (Gemini, Anthropic, or OpenAI)
- Stripe account (test mode) — optional for local dev without billing

### Quick Start (Docker)

1. **Clone the repository**

   ```bash
   git clone https://github.com/esakrissa/villa-ops-ai.git
   cd villa-ops-ai
   ```

2. **Configure environment variables**

   ```bash
   cp .env.example .env
   # Edit .env with your API keys, OAuth credentials, and Stripe keys
   ```

3. **Start all services**

   ```bash
   docker-compose up --build
   ```

   This starts 8 services: FastAPI backend (:8000), VillaOps MCP server (:8001), market-data MCP servers for Booking.com (:8002), Airbnb (:8003) and Tripadvisor (:8004), Next.js frontend (:3000), PostgreSQL, and Redis. The market servers need `RAPIDAPI_KEY` / `TRIPADVISOR_API_KEY` in `.env` (see `.env.example` and each server's README in `mcp-servers/`).

4. **Run database migrations and seed data**

   ```bash
   docker-compose exec backend alembic upgrade head
   docker-compose exec backend python scripts/seed_data.py
   ```

5. **Start Stripe webhook listener** (optional, for billing features)

   ```bash
   stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
   ```

6. **Open the app**

   | Service | URL |
   |---|---|
   | Frontend | [http://localhost:3000](http://localhost:3000) |
   | API Docs (Swagger) | [http://localhost:8000/docs](http://localhost:8000/docs) |
   | MCP Server | [http://localhost:8001/mcp](http://localhost:8001/mcp) |
   | Market MCP servers | `:8002` Booking.com · `:8003` Airbnb · `:8004` Tripadvisor (each at `/mcp`, health at `/health`) |

### Running Without Docker

<details>
<summary>Backend</summary>

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Ensure PostgreSQL and Redis are running locally
alembic upgrade head
python scripts/seed_data.py
uvicorn app.main:app --reload
```

</details>

<details>
<summary>MCP Server</summary>

```bash
cd backend
source .venv/bin/activate
python -m app.mcp.server
```

</details>

<details>
<summary>Frontend</summary>

```bash
cd frontend
npm install
npm run dev
```

</details>

---

## API Overview

### Auth Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register with email/password |
| `POST` | `/api/v1/auth/login` | Login, returns JWT |
| `GET` | `/api/v1/auth/google` | Google OAuth redirect |
| `GET` | `/api/v1/auth/github` | GitHub OAuth redirect |
| `POST` | `/api/v1/auth/refresh` | Refresh JWT token |
| `GET` | `/api/v1/auth/me` | Current user profile |

### Billing Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/billing/plans` | No | List available plans (public) |
| `GET` | `/api/v1/billing/subscription` | Yes | Current plan + usage stats |
| `POST` | `/api/v1/billing/checkout` | Yes | Create Stripe Checkout session |
| `POST` | `/api/v1/billing/portal` | Yes | Get Stripe Customer Portal URL |
| `POST` | `/api/v1/webhooks/stripe` | No | Stripe webhook handler |

### REST Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/properties` | List all properties |
| `POST` | `/api/v1/properties` | Create a property (plan limit enforced) |
| `GET` | `/api/v1/bookings` | List bookings (with filters) |
| `POST` | `/api/v1/bookings` | Create a booking |
| `PATCH` | `/api/v1/bookings/{id}` | Update a booking |
| `GET` | `/api/v1/guests` | List guests |
| `GET` | `/api/v1/analytics/occupancy` | Occupancy analytics |

### Chat Endpoint

```
POST /api/v1/chat
Content-Type: application/json
Accept: text/event-stream
Authorization: Bearer <jwt-token>

{
  "message": "Show me all check-ins for tomorrow",
  "conversation_id": "optional-uuid"
}
```

Streams SSE events with agent responses and tool call results. AI query usage is counted against the plan limit.

---

## MCP Tools

The LangGraph agent connects to the MCP server over Streamable HTTP and has access to 8 tools:

| Tool | Description |
|---|---|
| `booking_search` | Search bookings by date, guest, property, or status |
| `booking_create` | Create a new booking with validation (availability + conflict checks) |
| `booking_update` | Modify or cancel existing bookings |
| `booking_analytics` | Occupancy rates, revenue, and booking trends |
| `guest_lookup` | Search guest info and booking history |
| `property_manage` | Check availability, block dates, update pricing |
| `send_notification` | Send templated emails to guests (Pro+ plans only) |
| `web_search` | Search external info via Exa (weather, local events, etc.) |

---

## Testing

```bash
cd backend

# Run all tests
pytest

# With coverage report
pytest --cov=app --cov-report=term-missing

# Specific test suites
pytest tests/test_api/         # API endpoints
pytest tests/test_auth/        # Authentication (JWT + OAuth)
pytest tests/test_billing/     # Stripe billing lifecycle
pytest tests/test_agent/       # Agent reasoning + tool selection
pytest tests/test_mcp/         # MCP tool edge cases
pytest tests/test_services/    # Business logic
```

**Current stats:** 389 tests (backend), plus fixture-based tests for each market-data MCP server.

---

## Deployment

The live demo runs on **one EC2 instance that is off by default** and is started only when needed (`scripts/demo.sh`).

### Infrastructure

| Resource | Service |
|---|---|
| Compute | EC2 `t3.large`, Ubuntu 24.04, ap-southeast-1 (Singapore), 30 GB gp3 + 4 GB swap |
| Network | Elastic IP (stable across stop/start), security group: 80/443 public, 22 from the operator's IP only |
| HTTPS | Caddy with automatic Let's Encrypt certificates (`Caddyfile`) |
| Stack | `docker compose -f docker-compose.yml -f docker-compose.prod.yml` (Next.js prod build, no source mounts, no reload) |
| DNS | Cloudflare A record `villaops` → Elastic IP (DNS only) |
| External | Pinecone (vectors), OpenRouter (models), Stripe (billing, sandbox), LangSmith (tracing) |
| Cost | ~$0.11/h while running + ~$0.29/day for IP and disk when stopped |

```bash
./scripts/demo.sh create     # one-time: key pair, firewall, instance, Elastic IP
./scripts/demo.sh deploy     # rsync code + .env, build, migrate, seed
./scripts/demo.sh start      # power on, auto-stop in 2 h, wait for https health
./scripts/demo.sh stop       # power off (disk + IP kept)
./scripts/demo.sh status     # state, DNS, health, auto-stop time
./scripts/demo.sh destroy    # delete everything
```

### CI

`ci.yml` runs lint, tests and builds on pushes and pull requests to `main`. The previous ECS Fargate deployment (`deploy.yml`, `.aws/`) is kept for reference and can only be run manually.

---

## Project Structure

```
villa-ops-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # Async SQLAlchemy engine + sessions
│   │   ├── models/              # 10 SQLAlchemy models (incl. knowledge documents/chunks)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── api/v1/              # REST + Chat + Auth + Billing + Webhook routers
│   │   ├── auth/                # JWT + OAuth (Google, GitHub)
│   │   ├── billing/             # Stripe (checkout, webhooks, plan gating)
│   │   ├── agent/               # LangGraph agent, MCP client (cached), model routing + failover
│   │   ├── knowledge/           # RAG: extract, chunk, Pinecone client, ingestion pipeline, search
│   │   ├── mcp/                 # MCP server (Streamable HTTP)
│   │   │   ├── server.py
│   │   │   └── tools/           # 6 tool modules (16 tools incl. kb_search)
│   │   └── services/            # Business logic layer
│   ├── tests/                   # 389 tests
│   │   ├── conftest.py
│   │   ├── test_api/
│   │   ├── test_auth/
│   │   ├── test_billing/
│   │   ├── test_agent/
│   │   ├── test_mcp/
│   │   ├── test_knowledge/
│   │   └── test_services/
│   ├── scripts/
│   │   └── seed_data.py         # Idempotent demo data seeder
│   ├── alembic/                 # Database migrations
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/          # Login, register, OAuth callbacks
│   │   │   ├── pricing/         # Public pricing page
│   │   │   ├── chat/            # Chat interface (SSE streaming)
│   │   │   └── dashboard/       # Bookings, analytics, properties, knowledge, billing
│   │   ├── components/
│   │   │   ├── auth/            # OAuthButtons, LoginForm, RegisterForm
│   │   │   ├── chat/            # ChatWindow, MessageBubble, ToolCallCard
│   │   │   ├── dashboard/       # BookingTable, OccupancyChart, PropertyCard
│   │   │   ├── billing/         # PricingCard, UsageMeter, PlanBadge
│   │   │   ├── knowledge/       # DropZone, PipelineView, SearchPanel
│   │   │   └── ui/              # Header, Sidebar, LoadingSkeleton
│   │   └── lib/                 # API client, auth helpers, hooks
│   ├── Dockerfile
│   └── package.json
├── .aws/                        # Retired ECS infrastructure (reference)
│   ├── backend-task-def.json
│   ├── frontend-task-def.json
│   ├── mcp-task-def.json
│   ├── nginx-task-def.json
│   ├── setup-infra.sh
│   └── nginx/                   # Nginx config + Dockerfile
├── .github/workflows/
│   ├── ci.yml                   # CI: lint (ruff+mypy) + test + build
│   └── deploy.yml               # Retired ECS deploy (manual trigger only)
├── mcp-servers/                 # Booking.com, Airbnb, Tripadvisor MCP servers
├── scripts/demo.sh              # On-demand EC2 demo server: create/deploy/start/stop/status/destroy
├── docs/images/                 # README screenshots (archive/ = previous UI)
├── docs/knowledge-samples/      # Sample knowledge-base documents (Markdown + PDF)
├── docker-compose.yml           # Dev: 8 services (frontend, backend, MCP, 3 market MCPs, postgres, redis)
├── docker-compose.prod.yml      # Production overrides + Caddy
├── Caddyfile                    # HTTPS reverse proxy
├── .env.example                 # Environment variable template
└── README.md
```

---

## Environment Variables

All variables are configured via `.env` (see [`.env.example`](.env.example) for the template).

| Variable | Required | Description |
|---|---|---|
| **App** | | |
| `APP_NAME` | No | Application name (default: `VillaOps AI`) |
| `DEBUG` | No | Enable debug mode (default: `true`) |
| `ENVIRONMENT` | No | `development` or `production` |
| **Database** | | |
| `DATABASE_URL` | Yes | PostgreSQL async connection string |
| **Cache** | | |
| `REDIS_URL` | Yes | Redis connection string |
| **Auth** | | |
| `JWT_SECRET_KEY` | Yes | Secret key for JWT token signing |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | Access token TTL (default: `30`) |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | No | Refresh token TTL (default: `7`) |
| `GOOGLE_CLIENT_ID` | No | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | No | Google OAuth client secret |
| `GITHUB_CLIENT_ID` | No | GitHub OAuth client ID |
| `GITHUB_CLIENT_SECRET` | No | GitHub OAuth client secret |
| **Stripe** | | |
| `STRIPE_SECRET_KEY` | No* | Stripe secret key (*required for billing features) |
| `STRIPE_PUBLISHABLE_KEY` | No* | Stripe publishable key |
| `STRIPE_WEBHOOK_SECRET` | No* | Stripe webhook signing secret(s), comma-separated (e.g. dashboard endpoint + `stripe listen`) |
| `STRIPE_PRO_PRICE_ID` | No* | Stripe Price ID for Pro plan |
| `STRIPE_BUSINESS_PRICE_ID` | No* | Stripe Price ID for Business plan |
| **LLM** | | |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key — all picker models run through OpenRouter |
| `DEFAULT_LLM_MODEL` | No | Default model (default: `openrouter/openai/gpt-6-luna`) |
| `LLM_FALLBACK_MODELS` | No | JSON list tried after the primary stalls/errors (default: Nemotron 3.5 Lightning free, Gemini 3.1 Flash-Lite) |
| `TITLE_LLM_MODEL` | No | Model for conversation titles (default: `openrouter/google/gemini-3.1-flash-lite`) |
| `MCP_TOOLS_CACHE_TTL` | No | Seconds to cache each MCP server's tool list (default: `600`) |
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | No | Optional direct provider keys |
| **Knowledge base** | | |
| `PINECONE_API_KEY` | No* | Pinecone API key (*required for the Knowledge page and `kb_search`) |
| `PINECONE_INDEX` | No | Index name, created on first use (default: `villaops-kb`) |
| `PINECONE_EMBED_MODEL` / `PINECONE_RERANK_MODEL` | No | Defaults: `llama-text-embed-v2` / `bge-reranker-v2-m3` (empty rerank = off) |
| **Observability** | | |
| `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` | No | LangSmith tracing for every LangGraph run |
| **Web Search** | | |
| `EXA_API_KEY` | No | Exa API key for the `web_search` tool |
| **Services** | | |
| `MCP_SERVER_URL` | Yes | MCP server URL (default: `http://localhost:8001/mcp`) |
| `FRONTEND_URL` | Yes | Frontend URL for CORS and OAuth redirects |

---

## License

MIT
