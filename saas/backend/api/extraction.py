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
    guild_id: int
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
            text("SELECT id, subscription_tier FROM users WHERE clerk_id = :clerk_id"),
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
        guild_id=guild_id,
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
            text("SELECT id FROM users WHERE clerk_id = :clerk_id"),
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
            guild_id=row[2],
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
            text("SELECT id FROM users WHERE clerk_id = :clerk_id"),
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
                guild_id=row[2],
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
            text("SELECT id FROM users WHERE clerk_id = :clerk_id"),
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
