# VillaOps AI

An AI-powered operations assistant for villa and hotel property managers in Bali. Chat with an AI that can query bookings, manage properties, contact guests, and provide analytics — all through natural language.

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent-purple)
![MCP](https://img.shields.io/badge/MCP-Tools-orange)
![Next.js](https://img.shields.io/badge/Next.js-15-black)
![Stripe](https://img.shields.io/badge/Stripe-Payments-blueviolet)
![AWS](https://img.shields.io/badge/AWS-ECS%20Fargate-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

## What It Does

Instead of juggling spreadsheets and dashboards, property managers can simply ask:

- *"Show me all check-ins for tomorrow"*
- *"Book Villa Sunset for John, Feb 10-15"*
- *"What's our occupancy rate this month?"*
- *"Send check-in instructions to tomorrow's arrivals"*
- *"Cancel booking #1234"*

The AI agent understands the intent, picks the right tool, executes it, and responds with the results — streamed in real-time through a chat interface.

## Pricing

| | Free | Pro | Business |
|---|---|---|---|
| **Price** | $0/mo | $29/mo | $79/mo |
| **Properties** | 1 | 5 | Unlimited |
| **AI Queries** | 50/mo | 500/mo | Unlimited |
| **Analytics** | Basic | Full | Full + Export |
| **Notifications** | — | Yes | Yes |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Next.js Frontend                         │
│                                                             │
│  ┌────────┐ ┌────────┐ ┌───────────┐ ┌──────────────────┐   │
│  │  Auth  │ │Pricing │ │  Chat UI  │ │    Dashboard     │   │
│  │  Pages │ │  Page  │ │  (SSE)    │ │   (Bookings/     │   │
│  │        │ │        │ │           │ │   Analytics)     │   │
│  └────────┘ └────────┘ └───────────┘ └──────────────────┘   │
└────────┬────────────────────────────────────────────────────┘
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
│       │        │   + MCP Client (SSE transport) │  │
│       │        └──────────┬─────────────────────┘  │
│       │                   │ SSE/Streamable HTTP    │
│       │                   ▼                        │
│  ┌────────────────────────────────────────────┐    │
│  │  MCP Server (remote, SSE transport)        │    │
│  │  booking_search | booking_create           │    │
│  │  booking_update | booking_analytics        │    │
│  │  guest_lookup   | property_manage          │    │
│  │  send_notification | web_search            │    │
│  └────────────────────────────────────────────┘    │
│                                                    │
│  ┌────────────────────────────────────────────┐    │
│  │  LiteLLM Gateway                           │    │
│  │  Gemini (default) → Claude → GPT           │    │
│  │  + caching + cost tracking + fallback      │    │
│  └────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────┘

┌──────────────────┐  ┌────────────────┐  ┌─────────────┐
│  AWS RDS         │  │ AWS ElastiCache│  │   Stripe    │
│  PostgreSQL      │  │ Redis          │  │   Payments  │
└──────────────────┘  └────────────────┘  └─────────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12+, FastAPI (async) |
| **Agent** | LangGraph |
| **Tool Protocol** | MCP (SSE/Streamable HTTP transport) |
| **LLM Gateway** | LiteLLM (Gemini default, Anthropic + OpenAI fallback) |
| **Payments** | Stripe (Checkout + Webhooks + Customer Portal) |
| **Database** | PostgreSQL + Alembic migrations |
| **Cache** | Redis |
| **Auth** | JWT + Google OAuth + GitHub OAuth |
| **Frontend** | Next.js 15, TypeScript, Tailwind CSS |
| **Testing** | pytest, pytest-asyncio, httpx (>80% coverage) |
| **CI/CD** | GitHub Actions |
| **Deployment** | AWS (ECS Fargate + ECR + RDS + ElastiCache) |

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 18+
- API keys for at least one LLM provider (Gemini, Anthropic, or OpenAI)
- Stripe account (test mode)

### Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/esakrissa/villa-ops-ai.git
   cd villa-ops-ai
   ```

2. **Configure environment variables**

   ```bash
   cp .env.example .env
   # Edit .env with your API keys, OAuth credentials, Stripe keys, and database settings
   ```

3. **Start with Docker Compose**

   ```bash
   docker-compose up --build
   ```

   This starts the FastAPI backend, MCP server, PostgreSQL, Redis, and the Next.js frontend.

4. **Seed the database**

   ```bash
   docker-compose exec backend python seed_data.py
   ```

5. **Start Stripe webhook listener (for local dev)**

   ```bash
   stripe listen --forward-to localhost:8000/api/v1/billing/webhook
   ```

6. **Open the app**

   - Frontend: http://localhost:3000
   - API docs: http://localhost:8000/docs
   - MCP Server: http://localhost:8001/sse

### Running Without Docker

<details>
<summary>Backend</summary>

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python seed_data.py
uvicorn app.main:app --reload
```

</details>

<details>
<summary>MCP Server</summary>

```bash
cd backend
uvicorn app.mcp.server:app --port 8001
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

## API Overview

### Auth Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register with email/password |
| `POST` | `/api/v1/auth/login` | Login, returns JWT |
| `GET` | `/api/v1/auth/google` | Google OAuth login |
| `GET` | `/api/v1/auth/github` | GitHub OAuth login |
| `POST` | `/api/v1/auth/refresh` | Refresh JWT token |
| `GET` | `/api/v1/auth/me` | Current user profile |

### Billing Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/billing/subscription` | Current plan + usage stats |
| `POST` | `/api/v1/billing/checkout` | Create Stripe Checkout session |
| `POST` | `/api/v1/billing/portal` | Get Stripe Customer Portal URL |
| `POST` | `/api/v1/billing/webhook` | Stripe webhook handler |

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

Streams SSE events with agent responses and tool call results. AI query usage counted against plan limit.

## MCP Tools

The LangGraph agent connects to the MCP server over SSE/Streamable HTTP and has access to:

| Tool | Description |
|---|---|
| `booking_search` | Search bookings by date, guest, property, or status |
| `booking_create` | Create a new booking with validation |
| `booking_update` | Modify or cancel existing bookings |
| `booking_analytics` | Occupancy rates, revenue, and trends |
| `guest_lookup` | Search guest info and booking history |
| `property_manage` | Check availability, block dates, update pricing |
| `send_notification` | Send templated emails to guests (Pro+ only) |
| `web_search` | Search external info (weather, local events) |

## Testing

```bash
cd backend

# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=term-missing

# Specific test suites
pytest tests/test_api/         # API endpoints
pytest tests/test_auth/        # Authentication
pytest tests/test_billing/     # Stripe billing
pytest tests/test_agent/       # Agent reasoning
pytest tests/test_mcp/         # MCP tools
pytest tests/test_services/    # Business logic
```

## Deployment

### AWS Architecture

```
GitHub Actions CI/CD
    │
    ├── Build & push Docker images → AWS ECR
    │
    └── Deploy to:
        ├── AWS ECS Fargate (backend + MCP server)
        ├── Vercel or ECS (Next.js frontend)
        ├── AWS RDS (PostgreSQL)
        └── AWS ElastiCache (Redis)
```

### Deploy

```bash
# Build and push images
docker build -t villa-ops-backend ./backend
docker tag villa-ops-backend:latest <account>.dkr.ecr.<region>.amazonaws.com/villa-ops-backend
docker push <account>.dkr.ecr.<region>.amazonaws.com/villa-ops-backend
```

CI/CD handles this automatically on push to `main`.

## Project Structure

```
villa-ops-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # Async SQLAlchemy setup
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── api/v1/              # REST + Chat + Auth + Billing routers
│   │   ├── auth/                # JWT + OAuth (Google, GitHub)
│   │   ├── billing/             # Stripe (checkout, webhooks, plan gating)
│   │   ├── agent/               # LangGraph agent
│   │   ├── mcp/                 # MCP server (SSE transport)
│   │   └── services/            # Business logic
│   ├── tests/
│   ├── alembic/
│   ├── seed_data.py
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js pages
│   │   │   ├── (auth)/          # Login, register, OAuth callbacks
│   │   │   ├── pricing/         # Public pricing page
│   │   │   ├── chat/            # Chat interface
│   │   │   └── dashboard/       # Bookings, analytics, properties, billing
│   │   ├── components/          # Reusable UI components
│   │   └── lib/                 # API client, auth helpers, hooks
│   └── package.json
├── infra/                       # AWS infrastructure (Terraform/CDK)
├── docker-compose.yml
├── .github/workflows/ci.yml
└── .env.example
```

## License

MIT
