"""
Discord data extraction endpoints.
Handles triggering and monitoring extraction jobs.
"""
from typing import Optional, List
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from api.auth import User, get_current_user
from db.connection import get_db_session
from config import get_settings

router = APIRouter()
settings = get_settings()


class ExtractionStartRequest(BaseModel):
    """Request to start a Discord extraction."""
    guild_id: str  # Accept as string to preserve precision for large Discord IDs
    sync_days: int = 30


class ExtractionJobResponse(BaseModel):
    """Response with extraction job details."""
    id: str
    status: str  # pending, running, completed, failed
    guild_id: str  # Use string to preserve precision for large Discord snowflake IDs
    sync_days: int
    messages_extracted: int = 0  # Default to 0 for NULL values
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ExtractionProgressResponse(BaseModel):
    """Real-time extraction progress."""
    job_id: str
    status: str
    progress_percent: int
    messages_extracted: int
    current_channel: Optional[str] = None
    eta_seconds: Optional[int] = None


@router.post("/start", response_model=ExtractionJobResponse)
async def start_extraction(
    request: ExtractionStartRequest,
    user: User = Depends(get_current_user),
):
    """
    Start a Discord data extraction job.

    This creates a background job that:
    1. Fetches the user's encrypted Discord token
    2. Connects to Discord and extracts message history
    3. Stores data in the user's Neon database branch
    """
    # Convert guild_id from string to int (preserves precision for large Discord IDs)
    try:
        guild_id = int(request.guild_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid guild_id format"
        )

    async with get_db_session() as session:
        # Get user record with UUID and subscription tier
        result = await session.execute(
            text("SELECT id, subscription_tier FROM app_users WHERE clerk_id = :clerk_id"),
            {"clerk_id": user.clerk_id}
        )
        user_row = result.fetchone()

        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please log out and log in again."
            )

        user_uuid = str(user_row[0])
        tier = user_row[1] or "free"

        # Validate sync_days against tier limits
        max_sync_days = {
            "free": settings.free_tier_sync_days,
            "pro": settings.pro_tier_sync_days,
            "team": 9999,  # Unlimited
        }.get(tier, settings.free_tier_sync_days)

        if request.sync_days > max_sync_days:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your plan allows up to {max_sync_days} days of history. Upgrade for more."
            )

        # Check for existing running job
        existing = await session.execute(
            text("""
            SELECT id FROM extraction_jobs
            WHERE user_id = :user_id AND status IN ('pending', 'running')
            """),
            {"user_id": user_uuid}
        )
        if existing.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An extraction is already in progress"
            )

        # Verify bot is connected
        token_result = await session.execute(
            text("""
            SELECT id FROM discord_tokens
            WHERE user_id = :user_id AND guild_id = :guild_id
            """),
            {"user_id": user_uuid, "guild_id": guild_id}
        )
        if not token_result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No Discord bot connected for this guild"
            )

        # Create extraction job
        job_id = str(uuid.uuid4())
        await session.execute(
            text("""
            INSERT INTO extraction_jobs (id, user_id, guild_id, sync_days, status, started_at)
            VALUES (:id, :user_id, :guild_id, :sync_days, 'pending', :started_at)
            """),
            {
                "id": job_id,
                "user_id": user_uuid,
                "guild_id": guild_id,
                "sync_days": request.sync_days,
                "started_at": datetime.utcnow(),
            }
        )
        await session.commit()

    # Queue the extraction task (Celery)
    try:
        from workers.tasks import run_extraction
        run_extraction.delay(job_id, user.clerk_id, guild_id, request.sync_days)
    except Exception as e:
        # If Celery/Redis is not available, return error with job created
        # The job is created but won't run until Celery is available
        import logging
        logging.warning(f"Celery task queue unavailable: {e}. Job created but not started.")
        # Update job status to indicate it needs manual processing
        async with get_db_session() as session:
            await session.execute(
                text("""
                UPDATE extraction_jobs SET status = 'failed', error_message = :error
                WHERE id = :job_id
                """),
                {"job_id": job_id, "error": "Task queue unavailable. Please ensure Redis is running."}
            )
            await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Extraction service unavailable. Redis/Celery is not running. Start Redis with: brew install redis && brew services start redis"
        )

    return ExtractionJobResponse(
        id=job_id,
        status="pending",
        guild_id=str(guild_id),  # Convert to string for JSON precision
        sync_days=request.sync_days,
        messages_extracted=0,
        started_at=datetime.utcnow(),
    )


@router.get("/status/{job_id}", response_model=ExtractionJobResponse)
async def get_extraction_status(
    job_id: str,
    user: User = Depends(get_current_user),
):
    """Get the status of an extraction job."""
    async with get_db_session() as session:
        # Get user UUID
        user_result = await session.execute(
            text("SELECT id FROM app_users WHERE clerk_id = :clerk_id"),
            {"clerk_id": user.clerk_id}
        )
        user_row = user_result.fetchone()
        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user_uuid = str(user_row[0])

        result = await session.execute(
            text("""
            SELECT id, status, guild_id, sync_days, messages_extracted,
                   started_at, completed_at, error_message
            FROM extraction_jobs
            WHERE id = :job_id AND user_id = :user_id
            """),
            {"job_id": job_id, "user_id": user_uuid}
        )
        row = result.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Extraction job not found"
            )

        return ExtractionJobResponse(
            id=str(row[0]),
            status=row[1],
            guild_id=str(row[2]),  # Convert to string for JSON precision
            sync_days=row[3],
            messages_extracted=row[4] or 0,  # Handle NULL
            started_at=row[5],
            completed_at=row[6],
            error_message=row[7],
        )


@router.get("/history", response_model=List[ExtractionJobResponse])
async def get_extraction_history(
    limit: int = 10,
    user: User = Depends(get_current_user),
):
    """Get the user's extraction job history."""
    async with get_db_session() as session:
        # Get user UUID
        user_result = await session.execute(
            text("SELECT id FROM app_users WHERE clerk_id = :clerk_id"),
            {"clerk_id": user.clerk_id}
        )
        user_row = user_result.fetchone()
        if not user_row:
            return []  # No user, no history
        user_uuid = str(user_row[0])

        result = await session.execute(
            text("""
            SELECT id, status, guild_id, sync_days, messages_extracted,
                   started_at, completed_at, error_message
            FROM extraction_jobs
            WHERE user_id = :user_id
            ORDER BY started_at DESC
            LIMIT :limit
            """),
            {"user_id": user_uuid, "limit": limit}
        )

        jobs = []
        for row in result.fetchall():
            jobs.append(ExtractionJobResponse(
                id=str(row[0]),
                status=row[1],
                guild_id=str(row[2]),  # Convert to string for JSON precision
                sync_days=row[3],
                messages_extracted=row[4] or 0,  # Handle NULL
                started_at=row[5],
                completed_at=row[6],
                error_message=row[7],
            ))

        return jobs


@router.post("/cancel/{job_id}")
async def cancel_extraction(
    job_id: str,
    user: User = Depends(get_current_user),
):
    """Cancel a pending or running extraction job."""
    async with get_db_session() as session:
        # Get user UUID
        user_result = await session.execute(
            text("SELECT id FROM app_users WHERE clerk_id = :clerk_id"),
            {"clerk_id": user.clerk_id}
        )
        user_row = user_result.fetchone()
        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user_uuid = str(user_row[0])

        result = await session.execute(
            text("""
            UPDATE extraction_jobs
            SET status = 'cancelled', completed_at = :completed_at
            WHERE id = :job_id AND user_id = :user_id AND status IN ('pending', 'running')
            RETURNING id
            """),
            {
                "job_id": job_id,
                "user_id": user_uuid,
                "completed_at": datetime.utcnow(),
            }
        )
        cancelled = result.fetchone()
        await session.commit()

        if not cancelled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found or already completed"
            )

    return {"status": "cancelled", "job_id": job_id}


# =============================================================================
# DEV-ONLY ENDPOINTS - For local testing without Celery
# =============================================================================

import os

_host = os.getenv("HOST", "127.0.0.1")
_is_local = _host in ("127.0.0.1", "localhost", "0.0.0.0")


class DevExtractionRequest(BaseModel):
    """Request for dev extraction (bypasses Celery)."""
    clerk_id: str
    guild_id: str
    sync_days: int = 7


if _is_local:
    import logging
    _logger = logging.getLogger(__name__)

    @router.post("/dev/run-sync", tags=["dev"])
    async def dev_run_extraction_sync(request: DevExtractionRequest):
        """
        DEV ONLY: Run extraction synchronously without Celery.
        This is for testing the extraction flow directly.

        WARNING: This blocks the request until extraction completes.
        Only use for testing with small sync_days values.
        """
        _logger.warning(f"DEV: Running sync extraction for {request.clerk_id}")

        try:
            guild_id = int(request.guild_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid guild_id format"
            )

        # Create job record
        job_id = str(uuid.uuid4())

        async with get_db_session() as session:
            # Get user UUID
            user_result = await session.execute(
                text("SELECT id FROM app_users WHERE clerk_id = :clerk_id"),
                {"clerk_id": request.clerk_id}
            )
            user_row = user_result.fetchone()

            if not user_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found. Create user first with /api/auth/dev/create-test-user"
                )

            user_uuid = str(user_row[0])

            # Verify bot token exists
            token_result = await session.execute(
                text("""
                SELECT id FROM discord_tokens
                WHERE user_id = :user_id AND guild_id = :guild_id
                """),
                {"user_id": user_uuid, "guild_id": guild_id}
            )
            if not token_result.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No Discord bot connected for this guild. Connect bot first."
                )

            # Create job
            await session.execute(
                text("""
                INSERT INTO extraction_jobs (id, user_id, guild_id, sync_days, status, started_at)
                VALUES (:id, :user_id, :guild_id, :sync_days, 'running', :started_at)
                """),
                {
                    "id": job_id,
                    "user_id": user_uuid,
                    "guild_id": guild_id,
                    "sync_days": request.sync_days,
                    "started_at": datetime.utcnow(),
                }
            )
            await session.commit()

        # Run extraction directly (synchronous for testing)
        try:
            from services.discord_extractor import run_extraction
            stats = await run_extraction(
                clerk_id=request.clerk_id,
                job_id=job_id,
                guild_id=guild_id,
                sync_days=request.sync_days,
            )

            return {
                "status": "completed",
                "job_id": job_id,
                "stats": stats,
            }

        except Exception as e:
            _logger.error(f"DEV extraction failed: {e}")
            import traceback
            traceback.print_exc()

            # Update job to failed
            async with get_db_session() as session:
                await session.execute(
                    text("""
                    UPDATE extraction_jobs
                    SET status = 'failed', error_message = :error, completed_at = :completed_at
                    WHERE id = :job_id
                    """),
                    {
                        "job_id": job_id,
                        "error": str(e),
                        "completed_at": datetime.utcnow(),
                    }
                )
                await session.commit()

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Extraction failed: {str(e)}"
            )

    @router.get("/dev/test-discord-connection", tags=["dev"])
    async def dev_test_discord_connection(clerk_id: str, guild_id: str):
        """
        DEV ONLY: Test Discord bot connection without extracting data.
        Verifies the bot can connect and access the guild.
        """
        _logger.warning(f"DEV: Testing Discord connection for {clerk_id}")

        try:
            guild_id_int = int(guild_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid guild_id format"
            )

        # Get token
        from services.encryption import decrypt_token

        async with get_db_session() as session:
            result = await session.execute(
                text("""
                SELECT dt.encrypted_token, dt.guild_name
                FROM discord_tokens dt
                JOIN app_users u ON dt.user_id = u.id
                WHERE u.clerk_id = :clerk_id AND dt.guild_id = :guild_id
                """),
                {"clerk_id": clerk_id, "guild_id": guild_id_int}
            )
            row = result.fetchone()

            if not row:
                return {
                    "status": "error",
                    "message": "No Discord token found for this user/guild",
                    "suggestions": [
                        "Connect bot first via /api/bot/connect",
                        "Verify clerk_id and guild_id are correct"
                    ]
                }

            encrypted_token = row[0]
            stored_guild_name = row[1]

        # Decrypt and test connection
        try:
            token = decrypt_token(encrypted_token)
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to decrypt token: {e}",
            }

        # Test Discord connection
        import discord

        intents = discord.Intents.default()
        client = discord.Client(intents=intents)

        connection_result = {"status": "unknown"}

        @client.event
        async def on_ready():
            nonlocal connection_result
            try:
                _logger.info(f"Connected as {client.user}")
                guild = await client.fetch_guild(guild_id_int)
                connection_result = {
                    "status": "success",
                    "bot_user": str(client.user),
                    "guild_name": guild.name,
                    "guild_id": guild.id,
                    "member_count": guild.member_count,
                    "stored_guild_name": stored_guild_name,
                }
            except discord.NotFound:
                connection_result = {
                    "status": "error",
                    "message": f"Guild {guild_id_int} not found - bot may not be a member",
                }
            except discord.Forbidden:
                connection_result = {
                    "status": "error",
                    "message": f"Bot lacks permission to access guild {guild_id_int}",
                }
            except Exception as e:
                connection_result = {
                    "status": "error",
                    "message": str(e),
                }
            finally:
                await client.close()

        import asyncio

        try:
            # Run with timeout
            await asyncio.wait_for(client.start(token), timeout=30)
        except asyncio.TimeoutError:
            connection_result = {
                "status": "error",
                "message": "Connection timed out after 30 seconds",
            }
        except discord.LoginFailure as e:
            connection_result = {
                "status": "error",
                "message": f"Invalid Discord token: {e}",
            }
        except Exception as e:
            if connection_result["status"] == "unknown":
                connection_result = {
                    "status": "error",
                    "message": str(e),
                }

        return connection_result

    _logger.info("DEV EXTRACTION ENDPOINTS ENABLED: /api/extraction/dev/* endpoints are available")
