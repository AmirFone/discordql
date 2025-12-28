-- Discord Analytics Schema
-- PostgreSQL database schema for Discord message analytics

-- ============================================================================
-- CORE ENTITIES
-- ============================================================================

-- Servers (Guilds)
CREATE TABLE IF NOT EXISTS servers (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    icon_hash TEXT,
    owner_id BIGINT,
    member_count INTEGER,
    created_at TIMESTAMPTZ,
    first_synced_at TIMESTAMPTZ DEFAULT NOW(),
    last_synced_at TIMESTAMPTZ
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    username TEXT NOT NULL,
    discriminator TEXT,
    global_name TEXT,
    avatar_hash TEXT,
    is_bot BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW()
);

-- Server memberships
CREATE TABLE IF NOT EXISTS server_members (
    server_id BIGINT REFERENCES servers(id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    nickname TEXT,
    joined_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (server_id, user_id)
);

-- Channels
CREATE TABLE IF NOT EXISTS channels (
    id BIGINT PRIMARY KEY,
    server_id BIGINT REFERENCES servers(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type INTEGER NOT NULL,
    parent_id BIGINT,
    topic TEXT,
    position INTEGER,
    is_nsfw BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ,
    is_archived BOOLEAN DEFAULT FALSE,
    last_synced_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_channels_server ON channels(server_id);
CREATE INDEX IF NOT EXISTS idx_channels_parent ON channels(parent_id);

-- ============================================================================
-- MESSAGES
-- ============================================================================

CREATE TABLE IF NOT EXISTS messages (
    id BIGINT PRIMARY KEY,
    server_id BIGINT REFERENCES servers(id) ON DELETE CASCADE,
    channel_id BIGINT REFERENCES channels(id) ON DELETE CASCADE,
    author_id BIGINT REFERENCES users(id) ON DELETE SET NULL,

    content TEXT,

    created_at TIMESTAMPTZ NOT NULL,
    edited_at TIMESTAMPTZ,

    message_type INTEGER DEFAULT 0,
    is_pinned BOOLEAN DEFAULT FALSE,
    is_tts BOOLEAN DEFAULT FALSE,

    reply_to_message_id BIGINT,
    reply_to_author_id BIGINT,
    thread_id BIGINT,

    mentions_everyone BOOLEAN DEFAULT FALSE,
    mention_count INTEGER DEFAULT 0,

    attachment_count INTEGER DEFAULT 0,
    embed_count INTEGER DEFAULT 0,
    has_poll BOOLEAN DEFAULT FALSE,

    word_count INTEGER,
    char_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_messages_channel_time ON messages(channel_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_author_time ON messages(author_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_server_time ON messages(server_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_reply_to ON messages(reply_to_message_id) WHERE reply_to_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_reply_author ON messages(reply_to_author_id) WHERE reply_to_author_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC);

-- ============================================================================
-- MENTIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS message_mentions (
    message_id BIGINT REFERENCES messages(id) ON DELETE CASCADE,
    mentioned_user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (message_id, mentioned_user_id)
);

CREATE INDEX IF NOT EXISTS idx_mentions_user ON message_mentions(mentioned_user_id);

-- ============================================================================
-- EMOJIS AND REACTIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS emojis (
    id SERIAL PRIMARY KEY,
    discord_id BIGINT,
    name TEXT NOT NULL,
    is_custom BOOLEAN DEFAULT FALSE,
    server_id BIGINT,
    is_animated BOOLEAN DEFAULT FALSE,
    UNIQUE(name, server_id)
);

CREATE TABLE IF NOT EXISTS reactions (
    message_id BIGINT REFERENCES messages(id) ON DELETE CASCADE,
    emoji_id INTEGER REFERENCES emojis(id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    reacted_at TIMESTAMPTZ DEFAULT NOW(),
    is_super_reaction BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (message_id, emoji_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_reactions_user ON reactions(user_id);
CREATE INDEX IF NOT EXISTS idx_reactions_message ON reactions(message_id);
CREATE INDEX IF NOT EXISTS idx_reactions_emoji ON reactions(emoji_id);

-- ============================================================================
-- SYNC STATE
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_state (
    id SERIAL PRIMARY KEY,
    server_id BIGINT REFERENCES servers(id) ON DELETE CASCADE,
    channel_id BIGINT REFERENCES channels(id) ON DELETE CASCADE,
    sync_type TEXT NOT NULL,
    last_message_id BIGINT,
    oldest_message_id BIGINT,
    status TEXT DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0,
    error_message TEXT,
    UNIQUE(server_id, channel_id, sync_type)
);

-- ============================================================================
-- MATERIALIZED VIEWS FOR ANALYTICS
-- ============================================================================

-- User interaction matrix (replies, reactions, mentions)
CREATE MATERIALIZED VIEW IF NOT EXISTS user_interactions AS
SELECT
    m.author_id AS from_user_id,
    m.reply_to_author_id AS to_user_id,
    m.server_id,
    'reply' AS interaction_type,
    COUNT(*) AS interaction_count,
    MIN(m.created_at) AS first_interaction,
    MAX(m.created_at) AS last_interaction
FROM messages m
WHERE m.reply_to_author_id IS NOT NULL
  AND m.author_id != m.reply_to_author_id
GROUP BY m.author_id, m.reply_to_author_id, m.server_id

UNION ALL

SELECT
    r.user_id AS from_user_id,
    m.author_id AS to_user_id,
    m.server_id,
    'reaction' AS interaction_type,
    COUNT(*) AS interaction_count,
    MIN(r.reacted_at) AS first_interaction,
    MAX(r.reacted_at) AS last_interaction
FROM reactions r
JOIN messages m ON r.message_id = m.id
WHERE r.user_id != m.author_id
GROUP BY r.user_id, m.author_id, m.server_id

UNION ALL

SELECT
    m.author_id AS from_user_id,
    mm.mentioned_user_id AS to_user_id,
    m.server_id,
    'mention' AS interaction_type,
    COUNT(*) AS interaction_count,
    MIN(m.created_at) AS first_interaction,
    MAX(m.created_at) AS last_interaction
FROM messages m
JOIN message_mentions mm ON m.id = mm.message_id
WHERE m.author_id != mm.mentioned_user_id
GROUP BY m.author_id, mm.mentioned_user_id, m.server_id;

CREATE INDEX IF NOT EXISTS idx_user_interactions_from ON user_interactions(from_user_id);
CREATE INDEX IF NOT EXISTS idx_user_interactions_to ON user_interactions(to_user_id);
CREATE INDEX IF NOT EXISTS idx_user_interactions_server ON user_interactions(server_id);

-- Daily activity statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_stats AS
SELECT
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
GROUP BY 1, 2, 3, 4;

CREATE INDEX IF NOT EXISTS idx_daily_stats_day ON daily_stats(day);
CREATE INDEX IF NOT EXISTS idx_daily_stats_author ON daily_stats(author_id);
CREATE INDEX IF NOT EXISTS idx_daily_stats_server ON daily_stats(server_id);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to refresh all materialized views
CREATE OR REPLACE FUNCTION refresh_analytics_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW user_interactions;
    REFRESH MATERIALIZED VIEW daily_stats;
END;
$$ LANGUAGE plpgsql;

-- Function to extract timestamp from Discord snowflake
CREATE OR REPLACE FUNCTION snowflake_to_timestamp(snowflake BIGINT)
RETURNS TIMESTAMPTZ AS $$
BEGIN
    -- Discord epoch: 2015-01-01 00:00:00 UTC (1420070400000 ms)
    RETURN to_timestamp(((snowflake >> 22) + 1420070400000) / 1000.0);
END;
$$ LANGUAGE plpgsql IMMUTABLE;
