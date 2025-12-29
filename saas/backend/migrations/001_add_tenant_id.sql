-- Migration: Add tenant_id column to all Discord data tables
-- This enables multi-tenant isolation using Row-Level Security (RLS)
--
-- IMPORTANT: Run this migration BEFORE enabling RLS policies
-- The columns are created as nullable first to allow for data migration
-- After migrating existing data, run migration 002 to make them NOT NULL and enable RLS

-- ============================================================================
-- ADD tenant_id COLUMNS (nullable for migration)
-- ============================================================================

-- Servers table
ALTER TABLE servers ADD COLUMN IF NOT EXISTS tenant_id TEXT;

-- Users table (Discord users, not SaaS users)
ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id TEXT;

-- Server members table
ALTER TABLE server_members ADD COLUMN IF NOT EXISTS tenant_id TEXT;

-- Channels table
ALTER TABLE channels ADD COLUMN IF NOT EXISTS tenant_id TEXT;

-- Messages table
ALTER TABLE messages ADD COLUMN IF NOT EXISTS tenant_id TEXT;

-- Message mentions table
ALTER TABLE message_mentions ADD COLUMN IF NOT EXISTS tenant_id TEXT;

-- Emojis table
ALTER TABLE emojis ADD COLUMN IF NOT EXISTS tenant_id TEXT;

-- Reactions table
ALTER TABLE reactions ADD COLUMN IF NOT EXISTS tenant_id TEXT;

-- Sync state table
ALTER TABLE sync_state ADD COLUMN IF NOT EXISTS tenant_id TEXT;

-- ============================================================================
-- CREATE INDEXES FOR RLS PERFORMANCE
-- Using CONCURRENTLY to avoid locking tables during creation
-- ============================================================================

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_servers_tenant
    ON servers(tenant_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_tenant
    ON users(tenant_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_server_members_tenant
    ON server_members(tenant_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_channels_tenant
    ON channels(tenant_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_tenant
    ON messages(tenant_id);

-- Composite indexes for common query patterns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_tenant_channel_time
    ON messages(tenant_id, channel_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_tenant_author_time
    ON messages(tenant_id, author_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_tenant_server_time
    ON messages(tenant_id, server_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_channels_tenant_server
    ON channels(tenant_id, server_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_mentions_tenant
    ON message_mentions(tenant_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_emojis_tenant
    ON emojis(tenant_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reactions_tenant
    ON reactions(tenant_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sync_state_tenant
    ON sync_state(tenant_id);

-- ============================================================================
-- UPDATE UNIQUE CONSTRAINTS FOR MULTI-TENANCY
-- ============================================================================

-- Drop old unique constraint on emojis (name, server_id)
-- Add new one that includes tenant_id
ALTER TABLE emojis DROP CONSTRAINT IF EXISTS emojis_name_server_id_key;

-- Note: Can't add unique constraint until tenant_id is populated
-- This will be done in migration 002 after data migration

-- Drop old unique constraint on sync_state
ALTER TABLE sync_state DROP CONSTRAINT IF EXISTS sync_state_server_id_channel_id_sync_type_key;

-- ============================================================================
-- NOTES FOR DATA MIGRATION
-- ============================================================================
-- After running this migration, you need to:
-- 1. Migrate data from existing per-user Neon branches to shared database
-- 2. Set tenant_id for all rows based on the source user
-- 3. Run migration 002 to:
--    a. Make tenant_id NOT NULL
--    b. Add new unique constraints with tenant_id
--    c. Enable RLS policies
