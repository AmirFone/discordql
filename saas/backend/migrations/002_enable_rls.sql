-- Migration: Enable Row-Level Security (RLS) on all Discord data tables
--
-- PREREQUISITES:
-- 1. Migration 001 must be run first (adds tenant_id columns)
-- 2. All existing data must have tenant_id populated
--
-- This migration:
-- 1. Makes tenant_id NOT NULL on all tables
-- 2. Adds multi-tenant unique constraints
-- 3. Enables RLS and creates isolation policies
-- 4. Creates secure views for materialized views

-- ============================================================================
-- MAKE tenant_id NOT NULL
-- ============================================================================

ALTER TABLE servers ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE users ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE server_members ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE channels ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE messages ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE message_mentions ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE emojis ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE reactions ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE sync_state ALTER COLUMN tenant_id SET NOT NULL;

-- ============================================================================
-- ADD MULTI-TENANT UNIQUE CONSTRAINTS
-- ============================================================================

-- Emojis: unique per (tenant, name, server) - replaces old (name, server_id)
ALTER TABLE emojis
    ADD CONSTRAINT emojis_tenant_name_server_key
    UNIQUE (tenant_id, name, server_id);

-- Sync state: unique per (tenant, server, channel, sync_type)
ALTER TABLE sync_state
    ADD CONSTRAINT sync_state_tenant_unique
    UNIQUE (tenant_id, server_id, channel_id, sync_type);

-- ============================================================================
-- ENABLE ROW-LEVEL SECURITY ON ALL TABLES
-- ============================================================================

ALTER TABLE servers ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE server_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_mentions ENABLE ROW LEVEL SECURITY;
ALTER TABLE emojis ENABLE ROW LEVEL SECURITY;
ALTER TABLE reactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_state ENABLE ROW LEVEL SECURITY;

-- FORCE RLS for table owners too (critical - prevents bypass via superuser)
ALTER TABLE servers FORCE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE server_members FORCE ROW LEVEL SECURITY;
ALTER TABLE channels FORCE ROW LEVEL SECURITY;
ALTER TABLE messages FORCE ROW LEVEL SECURITY;
ALTER TABLE message_mentions FORCE ROW LEVEL SECURITY;
ALTER TABLE emojis FORCE ROW LEVEL SECURITY;
ALTER TABLE reactions FORCE ROW LEVEL SECURITY;
ALTER TABLE sync_state FORCE ROW LEVEL SECURITY;

-- ============================================================================
-- CREATE RLS POLICIES
-- Uses current_setting('app.current_tenant', TRUE) which:
-- - Returns the session variable app.current_tenant
-- - Returns NULL (not error) if not set (TRUE = missing_ok)
-- - Application sets this via: SET LOCAL app.current_tenant = 'user_xxx'
-- ============================================================================

-- Drop existing policies if they exist (for idempotency)
DROP POLICY IF EXISTS tenant_isolation_servers ON servers;
DROP POLICY IF EXISTS tenant_isolation_users ON users;
DROP POLICY IF EXISTS tenant_isolation_server_members ON server_members;
DROP POLICY IF EXISTS tenant_isolation_channels ON channels;
DROP POLICY IF EXISTS tenant_isolation_messages ON messages;
DROP POLICY IF EXISTS tenant_isolation_message_mentions ON message_mentions;
DROP POLICY IF EXISTS tenant_isolation_emojis ON emojis;
DROP POLICY IF EXISTS tenant_isolation_reactions ON reactions;
DROP POLICY IF EXISTS tenant_isolation_sync_state ON sync_state;

-- Create policies
-- USING clause: Filters rows for SELECT, UPDATE, DELETE
-- WITH CHECK clause: Validates new rows for INSERT, UPDATE

CREATE POLICY tenant_isolation_servers ON servers
    USING (tenant_id = current_setting('app.current_tenant', TRUE))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', TRUE));

CREATE POLICY tenant_isolation_users ON users
    USING (tenant_id = current_setting('app.current_tenant', TRUE))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', TRUE));

CREATE POLICY tenant_isolation_server_members ON server_members
    USING (tenant_id = current_setting('app.current_tenant', TRUE))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', TRUE));

CREATE POLICY tenant_isolation_channels ON channels
    USING (tenant_id = current_setting('app.current_tenant', TRUE))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', TRUE));

CREATE POLICY tenant_isolation_messages ON messages
    USING (tenant_id = current_setting('app.current_tenant', TRUE))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', TRUE));

CREATE POLICY tenant_isolation_message_mentions ON message_mentions
    USING (tenant_id = current_setting('app.current_tenant', TRUE))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', TRUE));

CREATE POLICY tenant_isolation_emojis ON emojis
    USING (tenant_id = current_setting('app.current_tenant', TRUE))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', TRUE));

CREATE POLICY tenant_isolation_reactions ON reactions
    USING (tenant_id = current_setting('app.current_tenant', TRUE))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', TRUE));

CREATE POLICY tenant_isolation_sync_state ON sync_state
    USING (tenant_id = current_setting('app.current_tenant', TRUE))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', TRUE));

-- ============================================================================
-- RECREATE MATERIALIZED VIEWS WITH tenant_id
-- ============================================================================

-- Drop and recreate user_interactions with tenant_id
DROP MATERIALIZED VIEW IF EXISTS user_interactions CASCADE;

CREATE MATERIALIZED VIEW user_interactions AS
SELECT
    m.tenant_id,
    m.author_id AS from_user_id,
    m.reply_to_author_id AS to_user_id,
    m.server_id,
    'reply'::text AS interaction_type,
    COUNT(*) AS interaction_count,
    MIN(m.created_at) AS first_interaction,
    MAX(m.created_at) AS last_interaction
FROM messages m
WHERE m.reply_to_author_id IS NOT NULL
  AND m.author_id != m.reply_to_author_id
GROUP BY m.tenant_id, m.author_id, m.reply_to_author_id, m.server_id

UNION ALL

SELECT
    m.tenant_id,
    r.user_id AS from_user_id,
    m.author_id AS to_user_id,
    m.server_id,
    'reaction'::text AS interaction_type,
    COUNT(*) AS interaction_count,
    MIN(r.reacted_at) AS first_interaction,
    MAX(r.reacted_at) AS last_interaction
FROM reactions r
JOIN messages m ON r.message_id = m.id
WHERE r.user_id != m.author_id
GROUP BY m.tenant_id, r.user_id, m.author_id, m.server_id

UNION ALL

SELECT
    m.tenant_id,
    m.author_id AS from_user_id,
    mm.mentioned_user_id AS to_user_id,
    m.server_id,
    'mention'::text AS interaction_type,
    COUNT(*) AS interaction_count,
    MIN(m.created_at) AS first_interaction,
    MAX(m.created_at) AS last_interaction
FROM messages m
JOIN message_mentions mm ON m.id = mm.message_id
WHERE m.author_id != mm.mentioned_user_id
GROUP BY m.tenant_id, m.author_id, mm.mentioned_user_id, m.server_id;

-- Create indexes on materialized view
CREATE INDEX idx_user_interactions_tenant ON user_interactions(tenant_id);
CREATE INDEX idx_user_interactions_from ON user_interactions(from_user_id);
CREATE INDEX idx_user_interactions_to ON user_interactions(to_user_id);
CREATE INDEX idx_user_interactions_server ON user_interactions(server_id);

-- Drop and recreate daily_stats with tenant_id
DROP MATERIALIZED VIEW IF EXISTS daily_stats CASCADE;

CREATE MATERIALIZED VIEW daily_stats AS
SELECT
    m.tenant_id,
    date_trunc('day', m.created_at) AS day,
    m.server_id,
    m.channel_id,
    m.author_id,
    COUNT(*) AS message_count,
    COUNT(DISTINCT m.reply_to_author_id) AS unique_users_replied_to,
    SUM(CASE WHEN m.reply_to_message_id IS NOT NULL THEN 1 ELSE 0 END) AS reply_count,
    SUM(COALESCE(m.word_count, 0)) AS total_words,
    AVG(COALESCE(m.word_count, 0)) AS avg_words_per_message
FROM messages m
GROUP BY m.tenant_id, date_trunc('day', m.created_at), m.server_id, m.channel_id, m.author_id;

-- Create indexes on materialized view
CREATE INDEX idx_daily_stats_tenant ON daily_stats(tenant_id);
CREATE INDEX idx_daily_stats_day ON daily_stats(day);
CREATE INDEX idx_daily_stats_author ON daily_stats(author_id);
CREATE INDEX idx_daily_stats_server ON daily_stats(server_id);

-- ============================================================================
-- CREATE SECURE VIEWS FOR MATERIALIZED VIEWS
-- Materialized views don't support RLS, so we wrap them in views
-- that filter by the current tenant
-- ============================================================================

CREATE OR REPLACE VIEW user_interactions_secure AS
SELECT * FROM user_interactions
WHERE tenant_id = current_setting('app.current_tenant', TRUE);

CREATE OR REPLACE VIEW daily_stats_secure AS
SELECT * FROM daily_stats
WHERE tenant_id = current_setting('app.current_tenant', TRUE);

-- ============================================================================
-- UPDATE refresh_analytics_views FUNCTION
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_analytics_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW user_interactions;
    REFRESH MATERIALIZED VIEW daily_stats;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VERIFICATION QUERIES (run manually to verify RLS is working)
-- ============================================================================

-- To test RLS is enabled:
-- SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';

-- To test policies:
-- SET LOCAL app.current_tenant = 'user_test123';
-- SELECT COUNT(*) FROM messages; -- Should only show tenant's data

-- To verify no data leaks:
-- SET LOCAL app.current_tenant = '';
-- SELECT COUNT(*) FROM messages; -- Should return 0
