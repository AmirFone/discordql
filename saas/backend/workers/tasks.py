"""
Celery tasks for Discord Analytics SaaS.
"""
import asyncio
import logging

from .celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run an async function in a new event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3)
def run_extraction(self, job_id: str, clerk_id: str, guild_id: int, sync_days: int = 30):
    """
    Run Discord data extraction as a background task.

    Args:
        job_id: The extraction job ID
        clerk_id: The user's Clerk ID
        guild_id: Discord server ID
        sync_days: Number of days of history to extract
    """
    logger.info(f"Starting extraction job {job_id} for user {clerk_id}")

    try:
        # Ensure backend directory is in path for forked workers
        import sys
        from pathlib import Path
        backend_dir = str(Path(__file__).resolve().parent.parent)
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        from services.discord_extractor import run_extraction as async_run_extraction

        stats = run_async(async_run_extraction(
            clerk_id=clerk_id,
            job_id=job_id,
            guild_id=guild_id,
            sync_days=sync_days,
        ))

        logger.info(f"Extraction job {job_id} completed: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Extraction job {job_id} failed: {e}")
        raise self.retry(exc=e, countdown=60)  # Retry in 1 minute


@celery_app.task
def cleanup_old_jobs():
    """
    Clean up old extraction jobs and logs.

    Runs periodically to remove jobs older than 30 days.
    """
    logger.info("Running job cleanup")

    async def cleanup():
        from db.connection import get_db_session
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(days=30)

        async with get_db_session() as session:
            result = await session.execute(
                """
                DELETE FROM extraction_jobs
                WHERE completed_at < :cutoff
                RETURNING id
                """,
                {"cutoff": cutoff}
            )
            deleted = result.fetchall()
            await session.commit()

            logger.info(f"Cleaned up {len(deleted)} old jobs")
            return len(deleted)

    return run_async(cleanup())


@celery_app.task
def update_storage_usage(clerk_id: str):
    """
    Update storage usage for a user.

    Queries the Neon database to calculate actual storage used.
    """
    logger.info(f"Updating storage usage for user {clerk_id}")

    async def update():
        from services.neon import get_user_database_connection
        from db.connection import get_db_session
        from datetime import datetime

        try:
            db = await get_user_database_connection(clerk_id)

            async with db.acquire() as conn:
                # Get database size
                result = await conn.fetchval(
                    "SELECT pg_database_size(current_database())"
                )
                storage_bytes = result or 0

            # Log usage
            async with get_db_session() as session:
                await session.execute(
                    """
                    INSERT INTO usage_logs (user_id, action, storage_bytes, created_at)
                    SELECT id, 'storage_update', :storage, :created_at
                    FROM users WHERE clerk_id = :clerk_id
                    """,
                    {
                        "storage": storage_bytes,
                        "created_at": datetime.utcnow(),
                        "clerk_id": clerk_id,
                    }
                )
                await session.commit()

            logger.info(f"Storage for {clerk_id}: {storage_bytes} bytes")
            return storage_bytes

        except Exception as e:
            logger.error(f"Failed to update storage for {clerk_id}: {e}")
            raise

    return run_async(update())
