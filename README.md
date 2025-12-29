# Discord SQL Analytics

We built this because Discord's built-in analytics are useless for understanding how communities actually work. Who replies to whom? Who reacts to whose messages? Which users drive conversations vs. just lurk? Discord won't tell you. So we extract the raw message data, store it in PostgreSQL, and let you query it however you want.

This is a data extraction and analytics pipeline for Discord servers. It pulls messages, reactions, mentions, and user data through the Discord API, stores everything in a properly normalized schema, and gives you SQL access to answer questions Discord can't.

## Features

- Extracts messages, reactions, mentions, and reply chains from any Discord server you have bot access to
- Stores data in PostgreSQL with a schema designed for analytics queries
- Multi-tenant SaaS version with Row-Level Security (RLS) for tenant isolation
- Stripe billing integration with free/pro/team tiers
- Mock Discord client for testing without hitting the real API
- Realistic data generator that mimics actual Discord usage patterns (60% lurkers, 3% power users, peak-hour activity bias)
- Materialized views for expensive analytics queries (user interaction matrices, daily stats)
- Idempotent sync: run it twice, get the same data (no duplicates)

## Architecture

```
+------------------+      +------------------+      +------------------+
|   Discord API    | ---> |    Extractor     | ---> |   PostgreSQL     |
|   (or Mock)      |      | (src/extractor)  |      |   (schema.sql)   |
+------------------+      +------------------+      +------------------+
        |                         |                         |
        |                         |                         v
        |                         |              +---------------------+
        |                         |              | Materialized Views  |
        |                         |              | - user_interactions |
        |                         |              | - daily_stats       |
        |                         |              +---------------------+
        |                         |
        v                         v
+------------------+      +------------------+
| MockDiscordClient|      | SQLAlchemy       |
| (tests/mocks)    |      | Models + Queries |
+------------------+      +------------------+
```

The extractor uses Python protocols to define what it expects from Discord objects. Both the real `discord.py` client and our `MockDiscordClient` implement these protocols. The extractor doesn't know or care which one it's talking to. This lets us test the full extraction pipeline without touching Discord's API.

### Why SQLAlchemy AND raw SQL?

We use SQLAlchemy for CRUD operations (upserts, inserts) because it handles connection pooling and transactions cleanly. We use raw SQL for analytics queries because SQLAlchemy's ORM makes complex aggregations painful. Pick the right tool for the job.

### Why materialized views?

Queries like "who interacts with whom" require joining messages, reactions, and mentions, then aggregating. On a busy server, that's slow. Materialized views precompute the answer. The tradeoff: data is stale until you refresh. We refresh on sync completion.

### Why RLS instead of separate databases?

Row-Level Security lets us put all tenants in one database while guaranteeing they can't see each other's data. PostgreSQL enforces this at the query level. Simpler than managing N databases. The schema adds `tenant_id` to every table, and RLS policies filter based on `current_setting('app.current_tenant')`.

## Data Schema

The extractor captures six types of data:

| Table | Primary Key | Description |
|-------|-------------|-------------|
| `servers` | Discord snowflake | Server name, icon, owner, member count |
| `users` | Discord snowflake | Username, discriminator, avatar, bot flag |
| `server_members` | server_id + user_id | Nickname, join date, active status |
| `channels` | Discord snowflake | Name, type, topic, position, NSFW flag |
| `messages` | Discord snowflake | Content, timestamps, reply chain, attachment/embed counts |
| `message_mentions` | message_id + user_id | Links messages to mentioned users |
| `emojis` | Internal ID | Custom and unicode emojis |
| `reactions` | message_id + emoji_id + user_id | Who reacted with what |

### Key Message Fields

```sql
id BIGINT PRIMARY KEY          -- Discord snowflake
server_id BIGINT               -- Foreign key to servers
channel_id BIGINT              -- Foreign key to channels
author_id BIGINT               -- Foreign key to users
content TEXT                   -- Full message text
created_at TIMESTAMPTZ         -- When posted
edited_at TIMESTAMPTZ          -- Last edit time (nullable)
message_type INTEGER           -- 0=normal, 19=reply
reply_to_message_id BIGINT     -- Original message (for replies)
reply_to_author_id BIGINT      -- Who they replied to
mention_count INTEGER          -- Number of @mentions
attachment_count INTEGER       -- Files attached
word_count INTEGER             -- Computed from content
```

### Relationships

```
servers (1) ─────< channels (many)
servers (1) ─────< messages (many)
servers (1) ─────< server_members (many)
users (1) ─────< server_members (many)
users (1) ─────< messages (many)
messages (1) ─────< reactions (many)
messages (1) ─────< message_mentions (many)
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ (for RLS support)
- A Discord bot token (or use mock data for testing)

### Installation

```bash
git clone https://github.com/yourusername/discord-sql.git
cd discord-sql

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Database Setup

```bash
createdb discord_analytics
psql discord_analytics < schema.sql
```

### Run a Simulation (No Discord Required)

This generates fake Discord data and runs the full extraction pipeline:

```bash
python scripts/run_simulation.py --users 50 --channels 5 --messages 200 --days 7
```

### Run With Real Discord

```bash
export DISCORD_BOT_TOKEN="your-token-here"
export DATABASE_URL="postgresql://localhost/discord_analytics"
```

Then use the extractor in your bot code:

```python
from src.extractor import run_extraction

stats = await run_extraction(
    client=discord_client,
    engine=engine,
    guild_id=123456789012345678,
    sync_days=30,
    fetch_reactions=True,
)
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | (required) | Your Discord bot token |
| `DATABASE_URL` | `postgresql://localhost/discord_analytics` | PostgreSQL connection string |
| `SYNC_DAYS` | `7` | How many days of history to sync |
| `FETCH_REACTIONS` | `true` | Whether to fetch reaction details |

## SQL Query Examples

### Who replies to whom the most?

```sql
SELECT
    u1.username AS replier,
    u2.username AS replied_to,
    COUNT(*) AS reply_count
FROM messages m
JOIN users u1 ON m.author_id = u1.id
JOIN users u2 ON m.reply_to_author_id = u2.id
WHERE m.reply_to_author_id IS NOT NULL
  AND m.author_id != m.reply_to_author_id
GROUP BY u1.username, u2.username
ORDER BY reply_count DESC
LIMIT 10;
```

### Power users vs lurkers

```sql
SELECT
    u.username,
    COUNT(*) AS messages,
    CASE
        WHEN COUNT(*) > 500 THEN 'power_user'
        WHEN COUNT(*) > 100 THEN 'active'
        WHEN COUNT(*) > 20 THEN 'casual'
        ELSE 'lurker'
    END AS activity_level
FROM messages m
JOIN users u ON m.author_id = u.id
WHERE m.created_at > NOW() - INTERVAL '30 days'
GROUP BY u.id, u.username
ORDER BY messages DESC;
```

### Daily activity trends

```sql
SELECT
    date_trunc('day', created_at) AS day,
    COUNT(*) AS messages,
    COUNT(DISTINCT author_id) AS active_users
FROM messages
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY day
ORDER BY day;
```

### Top reaction givers

```sql
SELECT u.username, COUNT(*) AS reactions_given
FROM reactions r
JOIN users u ON r.user_id = u.id
GROUP BY u.username
ORDER BY reactions_given DESC
LIMIT 10;
```

## Testing

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Just extraction tests
pytest tests/test_extraction.py -v
```

Tests use SQLite in-memory by default. Set `TEST_DATABASE_URL` for PostgreSQL-specific tests.

### Mock Data Testing

```python
from tests.mocks import create_mock_client

client = create_mock_client(
    user_count=100,
    channel_count=10,
    messages_per_channel=500,
    days=14,
    seed=42,  # Reproducible
)

# Run extraction exactly as with real Discord
stats = await run_extraction(client=client, engine=engine, guild_id=client.guilds[0].id)
```

The mock generator creates realistic patterns: 60% lurkers, 3% power users, messages biased toward daytime hours, 35% replies, 20% get reactions.

---

# SaaS Platform

The `saas/` directory contains a multi-tenant web application built on this extraction engine.

## SaaS Architecture

```
+------------------+     +------------------+     +------------------+
|   Next.js        | --> |   FastAPI        | --> |   PostgreSQL     |
|   Frontend       |     |   Backend        |     |   (with RLS)     |
+------------------+     +------------------+     +------------------+
        |                        |                        |
        v                        v                        v
+------------------+     +------------------+     +------------------+
|   Clerk Auth     |     |   Celery Workers |     |   Neon (shared)  |
+------------------+     +------------------+     +------------------+
        |                        |
        v                        v
+------------------+     +------------------+
|   Stripe Billing |     |   Redis Queue    |
+------------------+     +------------------+
```

### Multi-Tenant Isolation

Every table has a `tenant_id` column. RLS policies enforce isolation:

```sql
CREATE POLICY tenant_isolation_messages ON messages
    USING (tenant_id = current_setting('app.current_tenant', TRUE))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', TRUE));
```

Before each query, the app sets the tenant context:

```python
await conn.execute("SET LOCAL app.current_tenant = $1", user.clerk_id)
```

`SET LOCAL` is transaction-scoped, so tenant context never leaks between requests in the connection pool.

### Authentication Flow

1. User signs in via Clerk (frontend)
2. Frontend sends `Authorization: Bearer <jwt>` to backend
3. Backend fetches Clerk's JWKS and validates the RS256 signature
4. The `sub` claim becomes the tenant ID for RLS

## SaaS Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose
- Clerk account
- Stripe account (for billing)
- Neon account (for shared database)

### Backend Setup

```bash
cd saas/backend

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env from example
cp .env.example .env
# Edit .env with your credentials
```

Required environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost/discord_analytics
SHARED_DATABASE_URL=postgresql://user:pass@neon-host/shared_data

# Authentication
CLERK_SECRET_KEY=sk_live_...
CLERK_JWT_ISSUER=https://your-app.clerk.accounts.dev
CLERK_WEBHOOK_SECRET=whsec_...

# Encryption (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
DISCORD_TOKEN_ENCRYPTION_KEY=...

# Billing
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_TEAM=price_...

# Task Queue
REDIS_URL=redis://localhost:6379
```

Run the backend:

```bash
python main.py  # Starts on http://localhost:8000
```

Run Celery workers (separate terminal):

```bash
celery -A workers.celery_app worker --loglevel=info
```

### Frontend Setup

```bash
cd saas/frontend
npm install

# Create .env.local
cp .env.example .env.local
# Edit with your Clerk keys
```

Required frontend variables:

```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Run the frontend:

```bash
npm run dev  # Starts on http://localhost:3000
```

### Docker Compose

For a complete local setup:

```bash
cd saas
docker-compose up
```

This starts PostgreSQL, Redis, the FastAPI backend, and Celery workers.

## Subscription Tiers

| Feature | Free | Pro ($9/mo) | Team ($29/mo) |
|---------|------|-------------|---------------|
| Storage | 500 MB | 5 GB | 25 GB |
| History | 30 days | 365 days | Unlimited |
| Queries/month | 1,000 | Unlimited | Unlimited |

## API Endpoints

### Bot Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/bot/connect` | Connect Discord bot (encrypted token storage) |
| GET | `/api/bot/status` | Get bot connection status |
| DELETE | `/api/bot/disconnect` | Remove bot connection |

### Data Extraction

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/extraction/start` | Start extraction job |
| GET | `/api/extraction/status/{job_id}` | Get job status |
| GET | `/api/extraction/history` | List past extractions |
| POST | `/api/extraction/cancel/{job_id}` | Cancel running job |

### SQL Queries

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/query/execute` | Run SQL query (SELECT only) |
| GET | `/api/query/schema` | Get table schemas |
| GET | `/api/query/tables` | List available tables |

### Billing

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/billing/subscription` | Current subscription |
| POST | `/api/billing/checkout/{plan}` | Start Stripe checkout |
| POST | `/api/billing/portal` | Open billing portal |
| GET | `/api/billing/usage` | Current usage stats |

## Security

### SQL Injection Prevention

The query endpoint blocks dangerous operations:

**Blocked keywords:** DROP, CREATE, ALTER, INSERT, UPDATE, DELETE, GRANT, SET, PG_SLEEP, CURRENT_SETTING, SET_CONFIG

**Blocked patterns:** Statement stacking (`; DROP`), SQL comments (`--`, `/*`), RLS bypass attempts (`app.current_tenant`)

Only SELECT and WITH (CTE) queries are allowed. Results capped at 10,000 rows. 30-second timeout.

### Token Encryption

Discord bot tokens are encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256). Tokens are never stored in plaintext.

### Webhook Verification

Both Clerk and Stripe webhooks require valid signatures. Invalid signatures return 400. Missing webhook secrets cause 500 (fail-closed).

### Security Headers

Both frontend and backend set: X-Frame-Options: DENY, X-Content-Type-Options: nosniff, Strict-Transport-Security (production), Content-Security-Policy

## Project Structure

```
.
├── schema.sql                 # PostgreSQL schema with RLS
├── requirements.txt
├── src/
│   ├── config.py              # Environment loading
│   ├── extractor.py           # Extraction logic
│   └── db/
│       ├── models.py          # SQLAlchemy models
│       └── queries.py         # CRUD operations
├── tests/
│   ├── test_extraction.py     # Pipeline tests
│   └── mocks/                 # Mock Discord client
├── scripts/
│   └── run_simulation.py      # Demo script
└── saas/
    ├── backend/
    │   ├── api/               # FastAPI routes
    │   ├── services/          # Business logic
    │   ├── workers/           # Celery tasks
    │   └── tests/             # Backend tests (198 passing)
    ├── frontend/
    │   └── src/               # Next.js app
    └── docker-compose.yml
```

## Running Tests

```bash
# Root project tests
pytest

# SaaS backend tests
cd saas/backend && pytest

# With coverage
pytest --cov=. --cov-report=html
```

## License

MIT
