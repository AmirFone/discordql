"""
Neon database provisioning and connection service.

Handles creating database branches for users and managing connections.

NOTE: This module is being deprecated in favor of shared_database.py
The new architecture uses a single shared database with Row-Level Security (RLS)
instead of per-user Neon branches.

Functions marked as DEPRECATED should be replaced with shared_database.py equivalents:
- provision_user_database() -> No longer needed (single shared DB)
- get_user_database_connection() -> Use shared_database.get_shared_pool() + tenant.tenant_connection()
- delete_user_database() -> No longer needed
"""
import logging
from typing import Optional, Dict

import httpx
import asyncpg

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Connection pool cache: clerk_id -> connection pool (DEPRECATED - use shared pool)
_connection_pools: Dict[str, asyncpg.Pool] = {}


class NeonClient:
    """Client for Neon API operations."""

    BASE_URL = "https://console.neon.tech/api/v2"

    def __init__(self):
        self.api_key = settings.neon_api_key
        self.project_id = settings.neon_project_id

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_branch(self, branch_name: str) -> dict:
        """
        Create a new database branch for a user.

        Args:
            branch_name: Unique name for the branch (use clerk_id)

        Returns:
            Branch details including connection string
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/projects/{self.project_id}/branches",
                headers=self.headers,
                json={
                    "branch": {
                        "name": branch_name,
                    },
                    "endpoints": [
                        {
                            "type": "read_write",
                        }
                    ],
                },
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_branch(self, branch_id: str) -> dict:
        """Get branch details."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/projects/{self.project_id}/branches/{branch_id}",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def delete_branch(self, branch_id: str) -> None:
        """Delete a database branch."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.BASE_URL}/projects/{self.project_id}/branches/{branch_id}",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()

    async def get_connection_string(self, branch_id: str) -> str:
        """
        Get the connection string for a branch.

        Args:
            branch_id: The Neon branch ID

        Returns:
            PostgreSQL connection string
        """
        async with httpx.AsyncClient() as client:
            # Get endpoints for the branch
            response = await client.get(
                f"{self.BASE_URL}/projects/{self.project_id}/branches/{branch_id}/endpoints",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            endpoints = response.json()

            if not endpoints.get("endpoints"):
                raise ValueError(f"No endpoints found for branch {branch_id}")

            endpoint = endpoints["endpoints"][0]
            host = endpoint["host"]

            # Get connection URI
            response = await client.get(
                f"{self.BASE_URL}/projects/{self.project_id}/connection_uri",
                headers=self.headers,
                params={
                    "branch_id": branch_id,
                    "database_name": "neondb",
                    "role_name": "neondb_owner",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()["uri"]

    async def list_branches(self) -> list:
        """List all branches in the project."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/projects/{self.project_id}/branches",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json().get("branches", [])


# Global Neon client instance
neon_client = NeonClient()


async def provision_user_database(clerk_id: str) -> str:
    """
    DEPRECATED: Provision a new database branch for a user.

    This function is deprecated. The new architecture uses a single shared
    database with Row-Level Security (RLS) instead of per-user branches.

    New users don't need individual branches - their data is stored in the
    shared database with tenant_id = clerk_id.

    Args:
        clerk_id: The user's Clerk ID

    Returns:
        The Neon branch ID (returns empty string for new architecture)
    """
    logger.warning(
        f"provision_user_database() is deprecated. "
        f"User {clerk_id} will use shared database with RLS."
    )
    # In the new architecture, we don't provision individual branches
    # Return empty string to indicate shared database usage
    return ""


async def initialize_user_schema(connection_string: str) -> None:
    """
    Initialize the Discord analytics schema in a user's database.

    Args:
        connection_string: PostgreSQL connection string
    """
    # Read the schema from the existing schema.sql file
    import os
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "..", "schema.sql"
    )

    # Fallback to embedded schema if file not found
    if os.path.exists(schema_path):
        with open(schema_path, "r") as f:
            schema_sql = f.read()
    else:
        # Embedded minimal schema
        schema_sql = get_discord_schema()

    conn = await asyncpg.connect(connection_string)
    try:
        await conn.execute(schema_sql)
    finally:
        await conn.close()


async def get_user_database_connection(clerk_id: str) -> asyncpg.Pool:
    """
    DEPRECATED: Get a connection pool for a user's database.

    This function is deprecated. Use the following pattern instead:

        from services.shared_database import get_shared_pool
        from services.tenant import tenant_connection

        pool = await get_shared_pool()
        async with tenant_connection(pool, clerk_id) as conn:
            result = await conn.fetch("SELECT * FROM messages")

    The new architecture uses a single shared pool with RLS for isolation.

    Args:
        clerk_id: The user's Clerk ID

    Returns:
        asyncpg connection pool (from shared pool for new architecture)
    """
    logger.warning(
        f"get_user_database_connection() is deprecated. "
        f"Use shared_database.get_shared_pool() + tenant.tenant_connection() instead."
    )

    # For backward compatibility, return the shared pool
    # Callers should migrate to use tenant_connection() for proper RLS
    from services.shared_database import get_shared_pool
    return await get_shared_pool()


async def delete_user_database(clerk_id: str) -> None:
    """
    DEPRECATED: Delete a user's database branch.

    This function is deprecated. In the new architecture with RLS,
    user data is deleted by running DELETE statements with the
    tenant context set, not by deleting branches.

    To delete user data:
        from services.shared_database import get_shared_pool
        from services.tenant import tenant_connection

        pool = await get_shared_pool()
        async with tenant_connection(pool, clerk_id) as conn:
            # RLS ensures only this user's data is deleted
            await conn.execute("DELETE FROM messages")
            await conn.execute("DELETE FROM channels")
            # ... etc for all tables

    Args:
        clerk_id: The user's Clerk ID
    """
    logger.warning(
        f"delete_user_database() is deprecated. "
        f"Use DELETE statements with tenant_connection() for data deletion."
    )
    # No-op in new architecture
    pass


def get_discord_schema() -> str:
    """Get the Discord analytics schema SQL."""
    return """
-- Discord Analytics Schema for User Database

-- Servers (Discord Guilds)
CREATE TABLE IF NOT EXISTS servers (
    server_id BIGINT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    owner_id BIGINT,
    icon_hash VARCHAR(255),
    member_count INT,
    created_at TIMESTAMPTZ,
    last_synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(32) NOT NULL,
    discriminator VARCHAR(4),
    global_name VARCHAR(32),
    avatar_hash VARCHAR(255),
    is_bot BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ
);

-- Server Members (many-to-many)
CREATE TABLE IF NOT EXISTS server_members (
    server_id BIGINT REFERENCES servers(server_id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    nickname VARCHAR(32),
    joined_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (server_id, user_id)
);

-- Channels
CREATE TABLE IF NOT EXISTS channels (
    channel_id BIGINT PRIMARY KEY,
    server_id BIGINT REFERENCES servers(server_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    channel_type SMALLINT DEFAULT 0,
    topic TEXT,
    position INT,
    is_nsfw BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ
);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
    message_id BIGINT PRIMARY KEY,
    server_id BIGINT REFERENCES servers(server_id) ON DELETE CASCADE,
    channel_id BIGINT REFERENCES channels(channel_id) ON DELETE CASCADE,
    author_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    content TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    edited_at TIMESTAMPTZ,
    message_type SMALLINT DEFAULT 0,
    is_pinned BOOLEAN DEFAULT FALSE,
    is_tts BOOLEAN DEFAULT FALSE,
    reply_to_message_id BIGINT,
    reply_to_author_id BIGINT,
    mentions_everyone BOOLEAN DEFAULT FALSE,
    mention_count SMALLINT DEFAULT 0,
    attachment_count SMALLINT DEFAULT 0,
    embed_count SMALLINT DEFAULT 0,
    word_count INT DEFAULT 0,
    char_count INT DEFAULT 0
);

-- Message Mentions
CREATE TABLE IF NOT EXISTS message_mentions (
    message_id BIGINT REFERENCES messages(message_id) ON DELETE CASCADE,
    mentioned_user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    PRIMARY KEY (message_id, mentioned_user_id)
);

-- Emojis
CREATE TABLE IF NOT EXISTS emojis (
    emoji_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    discord_id BIGINT,
    is_custom BOOLEAN DEFAULT FALSE,
    server_id BIGINT,
    is_animated BOOLEAN DEFAULT FALSE,
    UNIQUE(name, discord_id)
);

-- Reactions
CREATE TABLE IF NOT EXISTS reactions (
    id SERIAL PRIMARY KEY,
    message_id BIGINT REFERENCES messages(message_id) ON DELETE CASCADE,
    emoji_id INT REFERENCES emojis(emoji_id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(message_id, emoji_id, user_id)
);

-- Sync State
CREATE TABLE IF NOT EXISTS sync_state (
    id SERIAL PRIMARY KEY,
    server_id BIGINT REFERENCES servers(server_id) ON DELETE CASCADE,
    channel_id BIGINT REFERENCES channels(channel_id) ON DELETE CASCADE,
    last_message_id BIGINT,
    last_sync_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(server_id, channel_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_messages_channel_created ON messages(channel_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_author ON messages(author_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reactions_user ON reactions(user_id);
CREATE INDEX IF NOT EXISTS idx_mentions_user ON message_mentions(mentioned_user_id);
"""
