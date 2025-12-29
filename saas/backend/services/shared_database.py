"""
Shared database connection pool for multi-tenant Discord data.

This module provides a single shared PostgreSQL connection pool for all tenants.
Row-Level Security (RLS) policies at the database level enforce tenant isolation.

CRITICAL CONFIGURATION NOTES:
- statement_cache_size=0: Prevents cached prepared statements from being reused
  across tenants (which could leak data or cause incorrect tenant context)
- Connection pool is shared across all tenants for efficiency
- Each request sets its tenant context via SET LOCAL before queries
"""
import asyncio
import asyncpg
import logging
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)

# Global shared connection pool and the event loop it was created on
_shared_pool: Optional[asyncpg.Pool] = None
_pool_event_loop: Optional[asyncio.AbstractEventLoop] = None


async def init_connection(conn: asyncpg.Connection) -> None:
    """
    Initialize a new connection with secure defaults.

    Called when a new connection is created in the pool.
    Sets a restrictive default tenant that matches nothing.

    Args:
        conn: The newly created connection
    """
    # Set empty string as default - matches no tenant in RLS policies
    # This ensures that if SET LOCAL is somehow skipped, no data is exposed
    await conn.execute("SET app.current_tenant = ''")


async def get_shared_pool() -> asyncpg.Pool:
    """
    Get the shared database connection pool for Discord data.

    This pool is shared across all tenants. Tenant isolation is enforced
    via PostgreSQL RLS policies, not separate connections.

    IMPORTANT: asyncpg pools are bound to the event loop they were created on.
    If the event loop changes (e.g., in Celery workers), we must recreate the pool.

    Returns:
        The shared asyncpg connection pool

    Raises:
        ValueError: If SHARED_DATABASE_URL is not configured
    """
    global _shared_pool, _pool_event_loop

    # Get the current event loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    # Check if existing pool is bound to a different/closed event loop
    if _shared_pool is not None:
        loop_changed = _pool_event_loop is not current_loop
        loop_closed = _pool_event_loop is not None and _pool_event_loop.is_closed()

        if loop_changed or loop_closed:
            logger.warning(
                f"Pool event loop mismatch (changed={loop_changed}, closed={loop_closed}), "
                f"recreating pool"
            )
            try:
                # Try to close the old pool gracefully
                await _shared_pool.close()
            except Exception as e:
                logger.debug(f"Could not close old pool: {e}")
            _shared_pool = None
            _pool_event_loop = None

    if _shared_pool is None:
        settings = get_settings()

        if not settings.shared_database_url:
            raise ValueError(
                "SHARED_DATABASE_URL environment variable is not configured. "
                "This is required for multi-tenant database access."
            )

        logger.info("Creating shared database connection pool")

        _shared_pool = await asyncpg.create_pool(
            settings.shared_database_url,
            # Pool sizing
            min_size=5,       # Minimum connections to keep open
            max_size=50,      # Maximum concurrent connections
            # CRITICAL: Disable statement caching to prevent cross-tenant leaks
            # Prepared statements cache query plans - with RLS, the plan is
            # specific to the current_setting value, so caching could cause
            # wrong tenant context to be used
            statement_cache_size=0,
            # Timeouts
            command_timeout=60,       # Query timeout in seconds
            timeout=30,               # Connection acquisition timeout
            # Connection initialization
            init=init_connection,
        )

        # Store reference to the event loop this pool is bound to
        _pool_event_loop = current_loop

        logger.info(
            f"Shared database pool created: min={5}, max={50}, "
            f"statement_cache=disabled"
        )

    return _shared_pool


async def close_shared_pool() -> None:
    """
    Close the shared connection pool.

    Should be called during application shutdown.
    """
    global _shared_pool, _pool_event_loop

    if _shared_pool is not None:
        logger.info("Closing shared database connection pool")
        try:
            await _shared_pool.close()
        except Exception as e:
            logger.debug(f"Error closing pool: {e}")
        _shared_pool = None
        _pool_event_loop = None


async def get_pool_stats() -> dict:
    """
    Get statistics about the shared connection pool.

    Useful for monitoring and debugging.

    Returns:
        Dictionary with pool statistics
    """
    global _shared_pool

    if _shared_pool is None:
        return {"status": "not_initialized"}

    return {
        "status": "active",
        "size": _shared_pool.get_size(),
        "free_size": _shared_pool.get_idle_size(),
        "min_size": _shared_pool.get_min_size(),
        "max_size": _shared_pool.get_max_size(),
    }


async def health_check() -> bool:
    """
    Perform a health check on the shared database connection.

    Returns:
        True if healthy, False otherwise
    """
    try:
        pool = await get_shared_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            return result == 1
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
