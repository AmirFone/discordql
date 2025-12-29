"""
Tenant context management for Row-Level Security (RLS).

This module provides utilities for setting PostgreSQL session variables
that RLS policies use to enforce tenant isolation.

SECURITY NOTES:
- Uses SET LOCAL (transaction-scoped) which is safe for connection pools
- SET LOCAL automatically resets when the transaction ends
- Never use SET SESSION in a pooled environment (would leak to other requests)
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import re
import asyncpg


class TenantContextError(Exception):
    """Raised when there's an error with tenant context operations."""
    pass


def validate_tenant_id(tenant_id: str) -> bool:
    """
    Validate that a tenant_id matches the expected Clerk user ID format.

    Clerk user IDs follow the pattern: user_XXXXXXXXXXXXXXXXXXXXXXXXX
    where X is alphanumeric.

    Args:
        tenant_id: The tenant identifier to validate

    Returns:
        True if valid, False otherwise
    """
    if not tenant_id:
        return False

    # Clerk user IDs: user_ followed by alphanumeric characters
    # Typically 25-30 chars total, but we allow flexibility
    pattern = r'^user_[a-zA-Z0-9]{10,50}$'
    return bool(re.match(pattern, tenant_id))


async def set_tenant_context(conn: asyncpg.Connection, tenant_id: str) -> None:
    """
    Set the tenant context for RLS policies.

    Uses SET LOCAL which is transaction-scoped - the setting is automatically
    cleared when the transaction ends. This is CRITICAL for connection pool
    safety - if we used SET SESSION, the tenant context would persist and
    could leak to other requests using the same pooled connection.

    Args:
        conn: An asyncpg database connection
        tenant_id: The Clerk user ID to set as the current tenant

    Raises:
        TenantContextError: If tenant_id is invalid
    """
    if not validate_tenant_id(tenant_id):
        raise TenantContextError(
            f"Invalid tenant_id format. Expected Clerk user ID (user_xxx), got: {tenant_id}"
        )

    # Use set_config() instead of SET LOCAL because SET doesn't support $1 parameters
    # set_config(name, value, is_local) - is_local=TRUE makes it transaction-scoped like SET LOCAL
    await conn.execute(
        "SELECT set_config('app.current_tenant', $1, TRUE)",
        tenant_id
    )


async def clear_tenant_context(conn: asyncpg.Connection) -> None:
    """
    Clear the tenant context.

    This is defensive - SET LOCAL automatically clears at transaction end.
    But explicit clearing provides an additional safety layer.

    Args:
        conn: An asyncpg database connection
    """
    await conn.execute("RESET app.current_tenant")


async def get_current_tenant(conn: asyncpg.Connection) -> str | None:
    """
    Get the current tenant context from the connection.

    Args:
        conn: An asyncpg database connection

    Returns:
        The current tenant_id or None if not set
    """
    result = await conn.fetchval(
        "SELECT current_setting('app.current_tenant', TRUE)"
    )
    return result if result else None


@asynccontextmanager
async def tenant_connection(
    pool: asyncpg.Pool,
    tenant_id: str
) -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Context manager that provides a connection with tenant context set.

    This is the primary way to interact with the database in a multi-tenant
    context. It ensures:
    1. A connection is acquired from the pool
    2. A transaction is started (required for SET LOCAL)
    3. The tenant context is set before any queries
    4. The context is automatically cleared when done

    Usage:
        async with tenant_connection(pool, user.clerk_id) as conn:
            result = await conn.fetch("SELECT * FROM messages")
            # RLS automatically filters to tenant's data

    Args:
        pool: An asyncpg connection pool
        tenant_id: The Clerk user ID for the tenant

    Yields:
        An asyncpg connection with tenant context set

    Raises:
        TenantContextError: If tenant_id is invalid
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await set_tenant_context(conn, tenant_id)
            try:
                yield conn
            finally:
                # Defensive: Clear context explicitly
                # (SET LOCAL auto-clears at transaction end, but be safe)
                try:
                    await clear_tenant_context(conn)
                except Exception:
                    # Don't raise on cleanup - transaction end handles it
                    pass


@asynccontextmanager
async def tenant_transaction(
    conn: asyncpg.Connection,
    tenant_id: str
) -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Context manager for setting tenant context on an existing connection.

    Use this when you already have a connection and want to set tenant
    context within a transaction.

    Args:
        conn: An existing asyncpg connection
        tenant_id: The Clerk user ID for the tenant

    Yields:
        The same connection with tenant context set
    """
    async with conn.transaction():
        await set_tenant_context(conn, tenant_id)
        try:
            yield conn
        finally:
            try:
                await clear_tenant_context(conn)
            except Exception:
                pass
