"""
Pytest configuration and fixtures.

Provides database setup, mock Discord data, and common test utilities.
"""
import os
import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from tests.mocks import (
    MockDiscordClient,
    MockGuild,
    create_test_server,
    create_mock_client,
    DiscordDataGenerator,
)

# =============================================================================
# TEST DATABASE CONFIGURATION
# =============================================================================

# Use SQLite in-memory for tests (fast, no external dependencies)
# For PostgreSQL-specific tests, override with TEST_DATABASE_URL env var
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite:///:memory:"
)


# =============================================================================
# ASYNCIO CONFIGURATION
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

def get_sqlite_schema():
    """
    Generate SQLite-compatible schema.

    SQLite doesn't support some PostgreSQL features, so we simplify.
    """
    return """
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            icon_hash TEXT,
            owner_id INTEGER,
            member_count INTEGER,
            created_at TIMESTAMP,
            first_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_synced_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            discriminator TEXT,
            global_name TEXT,
            avatar_hash TEXT,
            is_bot INTEGER DEFAULT 0,
            created_at TIMESTAMP,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS server_members (
            server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            nickname TEXT,
            joined_at TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            PRIMARY KEY (server_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY,
            server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            type INTEGER NOT NULL,
            parent_id INTEGER,
            topic TEXT,
            position INTEGER,
            is_nsfw INTEGER DEFAULT 0,
            created_at TIMESTAMP,
            is_archived INTEGER DEFAULT 0,
            last_synced_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
            channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
            author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            content TEXT,
            created_at TIMESTAMP NOT NULL,
            edited_at TIMESTAMP,
            message_type INTEGER DEFAULT 0,
            is_pinned INTEGER DEFAULT 0,
            is_tts INTEGER DEFAULT 0,
            reply_to_message_id INTEGER,
            reply_to_author_id INTEGER,
            thread_id INTEGER,
            mentions_everyone INTEGER DEFAULT 0,
            mention_count INTEGER DEFAULT 0,
            attachment_count INTEGER DEFAULT 0,
            embed_count INTEGER DEFAULT 0,
            has_poll INTEGER DEFAULT 0,
            word_count INTEGER,
            char_count INTEGER
        );

        CREATE TABLE IF NOT EXISTS message_mentions (
            message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
            mentioned_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY (message_id, mentioned_user_id)
        );

        CREATE TABLE IF NOT EXISTS emojis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id INTEGER,
            name TEXT NOT NULL,
            is_custom INTEGER DEFAULT 0,
            server_id INTEGER,
            is_animated INTEGER DEFAULT 0,
            UNIQUE(name, server_id)
        );

        CREATE TABLE IF NOT EXISTS reactions (
            message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
            emoji_id INTEGER REFERENCES emojis(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            reacted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_super_reaction INTEGER DEFAULT 0,
            PRIMARY KEY (message_id, emoji_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS sync_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
            channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
            sync_type TEXT NOT NULL,
            last_message_id INTEGER,
            oldest_message_id INTEGER,
            status TEXT DEFAULT 'pending',
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            message_count INTEGER DEFAULT 0,
            error_message TEXT,
            UNIQUE(server_id, channel_id, sync_type)
        );

        CREATE INDEX IF NOT EXISTS idx_messages_channel_time ON messages(channel_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_author_time ON messages(author_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_server_time ON messages(server_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_reactions_user ON reactions(user_id);
        CREATE INDEX IF NOT EXISTS idx_reactions_message ON reactions(message_id);
    """


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine, None, None]:
    """
    Create test database engine.

    Uses SQLite in-memory for fast, isolated tests.
    """
    engine = create_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False} if "sqlite" in TEST_DATABASE_URL else {},
    )

    # Create tables
    schema = get_sqlite_schema()
    with engine.connect() as conn:
        for statement in schema.split(';'):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
        conn.commit()

    yield engine

    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """
    Create database session for tests.

    Each test gets a fresh session, rolled back after the test.
    """
    SessionFactory = sessionmaker(bind=db_engine)
    session = SessionFactory()

    yield session

    session.rollback()
    session.close()


@pytest.fixture
def clean_db(db_engine: Engine) -> Generator[Engine, None, None]:
    """
    Provide a clean database for tests that need isolation.

    Truncates all tables before the test.
    """
    with db_engine.connect() as conn:
        # Delete all data (order matters for FK constraints)
        conn.execute(text("DELETE FROM reactions"))
        conn.execute(text("DELETE FROM message_mentions"))
        conn.execute(text("DELETE FROM messages"))
        conn.execute(text("DELETE FROM emojis"))
        conn.execute(text("DELETE FROM channels"))
        conn.execute(text("DELETE FROM server_members"))
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("DELETE FROM servers"))
        conn.execute(text("DELETE FROM sync_state"))
        conn.commit()

    yield db_engine


# =============================================================================
# MOCK DISCORD FIXTURES
# =============================================================================

@pytest.fixture
def mock_guild() -> MockGuild:
    """
    Create a test server with predictable data.

    Uses a fixed seed for reproducibility.
    """
    return create_test_server(
        user_count=30,
        channel_count=3,
        messages_per_channel=50,
        days=7,
        seed=12345,
    )


@pytest.fixture
def mock_client(mock_guild: MockGuild) -> MockDiscordClient:
    """Create a mock Discord client with a test server."""
    client = MockDiscordClient(guilds=[mock_guild])
    client._is_ready = True
    return client


@pytest.fixture
def small_mock_guild() -> MockGuild:
    """Create a minimal test server for focused tests."""
    return create_test_server(
        user_count=5,
        channel_count=1,
        messages_per_channel=10,
        days=1,
        seed=42,
    )


@pytest.fixture
def large_mock_guild() -> MockGuild:
    """Create a larger test server for stress tests."""
    return create_test_server(
        user_count=100,
        channel_count=10,
        messages_per_channel=500,
        days=7,
        seed=99999,
    )


@pytest.fixture
def generator() -> DiscordDataGenerator:
    """Create a data generator with fixed seed."""
    return DiscordDataGenerator(seed=42)


# =============================================================================
# HELPER FIXTURES
# =============================================================================

@pytest.fixture
def now() -> datetime:
    """Current UTC time."""
    return datetime.utcnow()


@pytest.fixture
def week_ago(now: datetime) -> datetime:
    """One week before now."""
    return now - timedelta(days=7)
