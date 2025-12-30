"""
User service for common user operations.

This module consolidates duplicated user lookup patterns across API endpoints.
"""
from typing import Tuple

from fastapi import HTTPException, status
from sqlalchemy import text

from db.connection import get_db_session


async def get_user_with_tier(clerk_id: str) -> Tuple[str, str]:
    """
    Get user UUID and subscription tier from clerk_id.

    Args:
        clerk_id: The Clerk user ID

    Returns:
        Tuple of (user_uuid, subscription_tier)

    Raises:
        HTTPException 404 if user not found
    """
    async with get_db_session() as session:
        result = await session.execute(
            text("""
            SELECT id, subscription_tier FROM app_users WHERE clerk_id = :clerk_id
            """),
            {"clerk_id": clerk_id}
        )
        row = result.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Please log out and log in again."
            )

        return str(row[0]), row[1] or "free"


async def get_user_uuid(clerk_id: str) -> str:
    """
    Get user UUID from clerk_id.

    Args:
        clerk_id: The Clerk user ID

    Returns:
        The user's UUID as a string

    Raises:
        HTTPException 404 if user not found
    """
    user_uuid, _ = await get_user_with_tier(clerk_id)
    return user_uuid
