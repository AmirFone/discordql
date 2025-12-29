# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Test Commands

### Root Project (Discord Extraction Engine)
```bash
# Run all tests
pytest

# Run single test file
pytest tests/test_extraction.py -v

# Run with coverage
pytest --cov=src --cov-report=html

# Run simulation (no Discord required)
python scripts/run_simulation.py --users 50 --channels 5 --messages 200 --days 7
```

### SaaS Backend (saas/backend/)
```bash
cd saas/backend

# Run all backend tests
pytest

# Run single test
pytest tests/test_api.py::test_query_execution -v

# Run backend server
python main.py

# Run Celery workers
celery -A workers.celery_app worker --loglevel=info
```

### SaaS Frontend (saas/frontend/)
```bash
cd saas/frontend

# Install dependencies
npm install

# Run dev server
npm run dev

# Build
npm run build

# Lint
npm run lint
```

### Docker (Full Stack)
```bash
cd saas
docker-compose up
```

## Architecture Overview

### Two-Part System

1. **Core Extraction Engine** (`src/`, `tests/`) - Standalone Python library that extracts Discord data to PostgreSQL. Uses Protocol types so the same code works with real `discord.py` or `MockDiscordClient`.

2. **SaaS Platform** (`saas/`) - Multi-tenant web app wrapping the extraction engine. FastAPI backend + Next.js frontend.

### Core Extraction Flow

`src/extractor.py` defines Protocol interfaces (`UserProtocol`, `MessageProtocol`, etc.) that abstract Discord objects. The `DiscordExtractor` class accepts any client implementing `ClientProtocol`. This enables testing without Discord API access.

```
ClientProtocol (real or mock) → DiscordExtractor → SQLAlchemy → PostgreSQL
```

### SaaS Multi-Tenancy

Tenant isolation uses PostgreSQL Row-Level Security (RLS), not separate databases:

- Every table has `tenant_id` column
- RLS policies filter by `current_setting('app.current_tenant')`
- `services/tenant.py` sets tenant context with `SET LOCAL` (transaction-scoped)
- `services/shared_database.py` manages connection pool with `statement_cache_size=0` (required for RLS safety)

### Key Backend Services

- `api/auth.py` - Clerk JWT validation with JWKS caching (5-min TTL)
- `api/query.py` - SQL execution with injection prevention (keyword blocklist + regex patterns)
- `services/tenant.py` - `tenant_connection()` context manager sets/clears RLS context
- `services/encryption.py` - Fernet encryption for Discord bot tokens at rest
- `workers/tasks.py` - Celery tasks for async extraction jobs

### SQL Injection Prevention

`api/query.py` blocks dangerous operations through:
1. Keyword blocklist (DROP, INSERT, SET, CURRENT_SETTING, etc.)
2. Pattern matching (statement stacking, comments, RLS bypass attempts)
3. Only SELECT/WITH queries allowed
4. Materialized views blocked (must use `*_secure` view wrappers)

### Frontend Auth Flow

1. Clerk handles sign-in (`src/app/sign-in/`)
2. `middleware.ts` protects routes
3. `lib/api.ts` adds `Authorization: Bearer <jwt>` to all API calls
4. Backend validates JWT against Clerk's JWKS endpoint

## Database Schema

Primary tables: `servers`, `users`, `channels`, `messages`, `reactions`, `message_mentions`, `emojis`, `server_members`

All use Discord snowflake IDs as primary keys. Materialized views `user_interactions` and `daily_stats` precompute analytics (must use `*_secure` wrappers in SaaS).

Schema defined in `schema.sql` (root) with RLS migrations in `saas/backend/migrations/`.
