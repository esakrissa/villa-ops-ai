# VillaOps AI — Backend

The FastAPI backend powering VillaOps AI. Provides a fully async REST API for managing villa/hotel properties, bookings, guests, and analytics with JWT + OAuth authentication.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Framework** | FastAPI 0.128+ (fully async) |
| **Python** | 3.13+ |
| **ORM** | SQLAlchemy 2.0 (async) + asyncpg |
| **Migrations** | Alembic |
| **Database** | PostgreSQL 16 |
| **Cache** | Redis 7 |
| **Auth** | JWT (python-jose) + Google/GitHub OAuth (authlib) |
| **Password Hashing** | bcrypt |
| **Config** | pydantic-settings |
| **Validation** | Pydantic v2 |
| **Testing** | pytest + pytest-asyncio + httpx |
| **Linting** | ruff |
| **Type Checking** | mypy (strict mode) |

## Quick Start

### With Docker (recommended)

From the **project root** (`villa-ops-ai/`):

```bash
# Start backend + PostgreSQL + Redis
docker-compose up --build

# Run migrations
docker-compose exec backend alembic upgrade head

# Seed the database
docker-compose exec backend python scripts/seed_data.py
```

The API will be available at **http://localhost:8000**.

### Without Docker

Prerequisites: Python 3.13+, a running PostgreSQL instance, and a running Redis instance.

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install with dev dependencies
pip install -e ".[dev]"

# Configure your environment
cp ../.env.example ../.env
# Edit ../.env — set DATABASE_URL, REDIS_URL, JWT_SECRET_KEY, etc.

# Run migrations
alembic upgrade head

# Seed with demo data
python scripts/seed_data.py

# Start the server (with hot-reload)
uvicorn app.main:app --reload
```

### Verify It's Running

```bash
# Health check
curl http://localhost:8000/health
# → {"status": "healthy", "service": "VillaOps AI"}

# Swagger docs
open http://localhost:8000/docs
```

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, middleware, router registration
│   ├── config.py               # Settings via pydantic-settings (env vars)
│   ├── database.py             # Async SQLAlchemy engine + session factory
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py             # Shared dependencies (get_db session)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── auth.py         # Register, login, refresh, me, OAuth
│   │       ├── properties.py   # CRUD for properties
│   │       ├── bookings.py     # CRUD for bookings (with conflict detection)
│   │       ├── guests.py       # CRUD for guests
│   │       └── analytics.py    # Occupancy analytics
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── jwt.py              # Token creation + validation
│   │   ├── oauth.py            # Google + GitHub OAuth client setup
│   │   ├── passwords.py        # bcrypt hash + verify
│   │   └── dependencies.py     # get_current_user FastAPI dependency
│   ├── models/
│   │   ├── __init__.py         # Re-exports all models
│   │   ├── user.py             # User model (email, hashed_password, role)
│   │   ├── subscription.py     # Subscription (plan, status, usage tracking)
│   │   ├── property.py         # Property (name, type, location, pricing)
│   │   ├── booking.py          # Booking (check-in/out, status, total_price)
│   │   ├── guest.py            # Guest (name, email, nationality, notes)
│   │   ├── conversation.py     # Conversation (for AI chat — schema ready)
│   │   └── llm_usage.py        # LLM usage tracking (schema ready)
│   └── schemas/
│       ├── __init__.py
│       ├── auth.py             # Register, Login, Token, UserResponse schemas
│       ├── property.py         # PropertyCreate, PropertyUpdate, PropertyResponse
│       ├── booking.py          # BookingCreate, BookingUpdate, BookingResponse
│       ├── guest.py            # GuestCreate, GuestUpdate, GuestResponse
│       └── analytics.py        # OccupancyRequest, OccupancyResponse
├── alembic/
│   ├── env.py                  # Async Alembic environment config
│   ├── script.py.mako
│   └── versions/
│       └── d026dfaf7c4d_initial_tables_users_subscriptions_.py
├── scripts/
│   ├── __init__.py
│   └── seed_data.py            # Idempotent seed script (690 lines)
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Session-scoped async fixtures, test DB setup
│   ├── test_auth/
│   │   ├── __init__.py
│   │   └── test_auth_endpoints.py  # 13 tests
│   └── test_api/
│       ├── __init__.py
│       ├── test_properties.py      # 18 tests
│       ├── test_bookings.py        # 26 tests
│       ├── test_guests.py          # 25 tests
│       └── test_analytics.py       # 10 tests
├── alembic.ini
├── Dockerfile
├── pyproject.toml
└── README.md                   # ← You are here
```

## Database Models

### Entity Relationship

```
┌──────────┐     1:1      ┌──────────────┐
│  User    │─────────────▶│ Subscription │
│          │              │              │
│ id       │              │ plan         │
│ email    │              │ status       │
│ name     │              │ ai_queries_  │
│ role     │              │   used       │
│ provider │              │ current_     │
└────┬─────┘              │   period_end │
     │                    └──────────────┘
     │ 1:N
     ▼
┌──────────┐
│ Property │     N:1
│          │◀────────────┐
│ name     │             │
│ type     │      ┌──────┴───┐     N:1    ┌───────┐
│ location │      │ Booking  │───────────▶│ Guest │
│ status   │      │          │            │       │
│ price_   │      │ check_in │            │ name  │
│  per_    │      │ check_out│            │ email │
│  night   │      │ status   │            │ phone │
└──────────┘      │ total_   │            │ nat.  │
                  │  price   │            └───────┘
                  └──────────┘
```

### Models Detail

| Model | Key Fields | Notes |
|-------|-----------|-------|
| **User** | `email`, `name`, `hashed_password`, `role` (manager/staff/admin), `provider` (local/google/github) | Unique email, nullable password for OAuth users |
| **Subscription** | `plan` (free/pro/business), `status`, `ai_queries_used`, `properties_count`, `current_period_end` | 1:1 with User, auto-created on registration |
| **Property** | `name`, `property_type` (villa/hotel/guesthouse/apartment), `location`, `max_guests`, `price_per_night`, `status` (active/inactive) | Owned by user, cascades bookings on delete |
| **Booking** | `check_in_date`, `check_out_date`, `status` (pending/confirmed/checked_in/checked_out/cancelled), `total_price`, `num_guests`, `special_requests` | FK to property + guest, date conflict validation |
| **Guest** | `name`, `email`, `phone`, `nationality`, `notes` | Unique email per user scope |
| **Conversation** | `title`, `message_count` | Ready for Week 2 (AI chat) |
| **LLMUsage** | `model`, `input_tokens`, `output_tokens`, `cost`, `tool_calls` | Ready for Week 2 (usage tracking) |

## API Reference

All endpoints (except auth) require a JWT Bearer token: `Authorization: Bearer <token>`

### Authentication — `/api/v1/auth`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/register` | No | Create account (returns tokens) |
| `POST` | `/login` | No | Login with email/password (returns tokens) |
| `GET` | `/me` | Yes | Get current user profile |
| `POST` | `/refresh` | No | Refresh access token (send refresh token in body) |
| `GET` | `/google` | No | Redirect to Google OAuth |
| `GET` | `/google/callback` | No | Google OAuth callback |
| `GET` | `/github` | No | Redirect to GitHub OAuth |
| `GET` | `/github/callback` | No | GitHub OAuth callback |

**Register example:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "email": "alice@example.com", "password": "securepass123"}'
```

**Login example:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@villaops.ai", "password": "demo1234"}'
```

Response:

```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

### Properties — `/api/v1/properties`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | List your properties (query: `property_type`, `status`, `skip`, `limit`) |
| `POST` | `/` | Create a property |
| `GET` | `/{id}` | Get property by ID (must be yours) |
| `PATCH` | `/{id}` | Partial update |
| `DELETE` | `/{id}` | Delete property (cascades all bookings) |

**Property types:** `villa`, `hotel`, `guesthouse`, `apartment`
**Statuses:** `active`, `inactive`

### Bookings — `/api/v1/bookings`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | List bookings (query: `status`, `property_id`, `start_date`, `end_date`, `skip`, `limit`) |
| `POST` | `/` | Create booking (validates date conflicts automatically) |
| `GET` | `/{id}` | Get booking with nested property + guest data |
| `PATCH` | `/{id}` | Update status, dates, notes (re-validates conflicts on date change) |
| `DELETE` | `/{id}` | Delete booking |

**Booking statuses:** `pending`, `confirmed`, `checked_in`, `checked_out`, `cancelled`

**Date conflict detection:** The API automatically rejects bookings that overlap with existing non-cancelled bookings for the same property.

### Guests — `/api/v1/guests`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | List guests (query: `search` for name/email, `skip`, `limit`) |
| `POST` | `/` | Create guest (unique email enforced) |
| `GET` | `/{id}` | Get guest by ID |
| `PATCH` | `/{id}` | Update guest info |
| `DELETE` | `/{id}` | Delete guest |

### Analytics — `/api/v1/analytics`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/occupancy` | Occupancy rate (query: `start_date`, `end_date`, `property_id`) |

Returns the occupancy percentage for your properties over the specified date range. Cancelled bookings are excluded from calculations.

## Configuration

All configuration is managed through environment variables, loaded via `pydantic-settings`. You can set them in a `.env` file at the project root.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/villaops` | PostgreSQL connection URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `ENVIRONMENT` | `development` | `development`, `staging`, or `production` |
| `DEBUG` | `false` | Enable debug mode |
| `JWT_SECRET_KEY` | `change-me-in-production` | **Must** be changed in production |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token TTL |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `GOOGLE_CLIENT_ID` | — | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | — | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | `http://localhost:8000/api/v1/auth/google/callback` | Google OAuth redirect |
| `GITHUB_CLIENT_ID` | — | GitHub OAuth client ID |
| `GITHUB_CLIENT_SECRET` | — | GitHub OAuth client secret |
| `GITHUB_REDIRECT_URI` | `http://localhost:8000/api/v1/auth/github/callback` | GitHub OAuth redirect |
| `FRONTEND_URL` | `http://localhost:3000` | Frontend URL (for OAuth redirects) |
| `CORS_ORIGINS` | `["http://localhost:3000", "http://localhost:8000"]` | Allowed CORS origins |

> **Security note:** In production, `JWT_SECRET_KEY` must be set to a strong random value. The app will refuse to start with the default value when `ENVIRONMENT=production`. Generate one with: `python -c "import secrets; print(secrets.token_urlsafe(64))"`

## Seed Data

The seed script populates the database with realistic Bali villa data for development and demos:

```bash
python scripts/seed_data.py
```

| Entity | Count | Details |
|--------|-------|---------|
| **Demo user** | 1 | `demo@villaops.ai` / `demo1234`, role: manager |
| **Subscription** | 1 | Free plan, active |
| **Properties** | 5 | Real Bali villas with descriptions, amenities, pricing |
| **Guests** | 15 | Diverse nationalities (AU, GB, US, DE, FR, JP, IN, SE, etc.) |
| **Bookings** | 22 | Mix of all 5 statuses, past/current/future dates |

### Seeded Properties

| Name | Location | Type | Max Guests | Price/Night |
|------|----------|------|-----------|-------------|
| Le Ayu Villa Canggu | Canggu, Bali | Villa | 4 | $129 |
| Pitu Village Escape | Sangeh, Ubud, Bali | Villa | 2 | $86 |
| Da Vinci Villa by Nagisa | Canggu, Bali | Villa | 8 | $350 |
| Umah Anyar Villas Ubud | Ubud, Bali | Villa | 2 | $163 |
| Capung Asri Eco Resort | Ubud, Bali | Guesthouse | 4 | $122 |

The script is **idempotent** — it deletes existing seed data and re-creates it cleanly. Safe to run multiple times.

## Testing

### Running Tests

```bash
# All tests (92 total)
pytest

# With verbose output
pytest -v

# With coverage report
pytest --cov=app --cov-report=term-missing

# Individual test suites
pytest tests/test_auth/                     # 13 auth tests
pytest tests/test_api/test_properties.py    # 18 property tests
pytest tests/test_api/test_bookings.py      # 26 booking tests
pytest tests/test_api/test_guests.py        # 25 guest tests
pytest tests/test_api/test_analytics.py     # 10 analytics tests
```

### Test Architecture

- **Database:** Tests use a separate `villa_ops_test` PostgreSQL database
- **Isolation:** Each test runs inside a transaction that is rolled back after the test
- **Fixtures:** Session-scoped engine, function-scoped DB sessions with dependency override
- **Async:** All tests are fully async via `pytest-asyncio` with `asyncio_mode = "auto"`
- **HTTP client:** `httpx.AsyncClient` bound to the FastAPI app (no real HTTP calls)

### Test Coverage by Module

| Module | Tests | What's Covered |
|--------|-------|----------------|
| `auth` | 13 | Register, login, token refresh, profile, OAuth, validation errors |
| `properties` | 18 | CRUD, filters, pagination, authorization, cascade deletes |
| `bookings` | 26 | CRUD, date conflicts, overlaps, status changes, date range filters |
| `guests` | 25 | CRUD, search, email uniqueness, cascade behavior |
| `analytics` | 10 | Occupancy calc, date ranges, property filters, edge cases |
| **Total** | **92** | |

### Known Test Behaviors

1. **HTTPBearer 401 vs 403:** Unauthenticated tests accept either `401` or `403` for compatibility across FastAPI versions.
2. **JWT same-second tokens:** Tokens created in the same second are identical (second-resolution `iat`). The refresh test does not assert token uniqueness.
3. **Guest cascade:** Guests with bookings must have bookings deleted first (ORM-level cascade not configured on `Guest.bookings`).

## Database Migrations

Migrations are managed with Alembic:

```bash
# Apply all migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "description of changes"

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## Docker

The backend includes a production-ready Dockerfile:

- **Base:** `python:3.13-slim`
- **Non-root user:** Runs as `appuser` (UID 1000)
- **Health check:** `GET /health` every 30 seconds
- **Port:** 8000

Build standalone:

```bash
docker build -t villa-ops-backend .
docker run -p 8000:8000 --env-file ../.env villa-ops-backend
```

## Code Quality

```bash
# Linting
ruff check .

# Auto-fix lint issues
ruff check --fix .

# Formatting
ruff format .

# Type checking
mypy app/
```

Configuration for ruff and mypy is in `pyproject.toml`.

