"""
Bot configuration endpoints.
Handles Discord bot token storage and management.
"""
from typing import Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from api.auth import User, get_current_user
from services.encryption import encrypt_token, decrypt_token
from db.connection import get_db_session
from db.models import DiscordToken

router = APIRouter()


class BotConnectRequest(BaseModel):
    """Request to connect a Discord bot."""
    token: str
    guild_id: str  # Accept as string to preserve precision for large Discord IDs
    guild_name: str


class BotConnectResponse(BaseModel):
    """Response after connecting a Discord bot."""
    id: str
    guild_id: int
    guild_name: str
    connected_at: datetime
    last_sync_at: Optional[datetime] = None


class BotStatusResponse(BaseModel):
    """Bot connection status."""
    connected: bool
    guild_id: Optional[int] = None
    guild_name: Optional[str] = None
    last_sync_at: Optional[datetime] = None


@router.post("/connect", response_model=BotConnectResponse)
async def connect_bot(
    request: BotConnectRequest,
    user: User = Depends(get_current_user),
):
    """
    Connect a Discord bot by saving the encrypted token.

    The token is encrypted using Fernet before storage.
    """
    # Validate token format (basic check)
    if not request.token or len(request.token) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Discord token format"
        )

    # Convert guild_id from string to int (preserves precision for large Discord IDs)
    try:
        guild_id = int(request.guild_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid guild_id format"
        )

    # Encrypt the token
    encrypted_token = encrypt_token(request.token)

    # Store in database
    async with get_db_session() as session:
        # Get user UUID from clerk_id
        user_result = await session.execute(
            text("SELECT id FROM users WHERE clerk_id = :clerk_id"),
            {"clerk_id": user.clerk_id}
        )
        user_row = user_result.fetchone()

        if not user_row:
            # Auto-create user if not exists (first time setup)
            user_uuid = str(uuid.uuid4())
            await session.execute(
                text("""
                INSERT INTO users (id, clerk_id, email, created_at, subscription_tier)
                VALUES (:id, :clerk_id, :email, :created_at, 'free')
                """),
                {
                    "id": user_uuid,
                    "clerk_id": user.clerk_id,
                    "email": user.email,
                    "created_at": datetime.utcnow(),
                }
            )
        else:
            user_uuid = str(user_row[0])

        # Check if user already has a token for this guild
        existing = await session.execute(
            text("""
            SELECT id FROM discord_tokens
            WHERE user_id = :user_id AND guild_id = :guild_id
            """),
            {"user_id": user_uuid, "guild_id": guild_id}
        )
        existing_row = existing.fetchone()

        if existing_row:
            # Update existing token
            await session.execute(
                text("""
                UPDATE discord_tokens
                SET encrypted_token = :token, guild_name = :guild_name, created_at = :created_at
                WHERE id = :id
                """),
                {
                    "id": str(existing_row[0]),
                    "token": encrypted_token,
                    "guild_name": request.guild_name,
                    "created_at": datetime.utcnow(),
                }
            )
            token_id = str(existing_row[0])
        else:
            # Create new token entry
            token_id = str(uuid.uuid4())
            await session.execute(
                text("""
                INSERT INTO discord_tokens (id, user_id, encrypted_token, guild_id, guild_name, created_at)
                VALUES (:id, :user_id, :token, :guild_id, :guild_name, :created_at)
                """),
                {
                    "id": token_id,
                    "user_id": user_uuid,
                    "token": encrypted_token,
                    "guild_id": guild_id,
                    "guild_name": request.guild_name,
                    "created_at": datetime.utcnow(),
                }
            )

        await session.commit()

    return BotConnectResponse(
        id=token_id,
        guild_id=guild_id,
        guild_name=request.guild_name,
        connected_at=datetime.utcnow(),
    )


@router.get("/status", response_model=BotStatusResponse)
async def get_bot_status(user: User = Depends(get_current_user)):
    """Get the current bot connection status."""
    async with get_db_session() as session:
        # Get user UUID
        user_result = await session.execute(
            text("SELECT id FROM users WHERE clerk_id = :clerk_id"),
            {"clerk_id": user.clerk_id}
        )
        user_row = user_result.fetchone()

        if not user_row:
            return BotStatusResponse(connected=False)

        user_uuid = str(user_row[0])

        result = await session.execute(
            text("""
            SELECT guild_id, guild_name, last_sync_at
            FROM discord_tokens
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 1
            """),
            {"user_id": user_uuid}
        )
        row = result.fetchone()

        if row:
            return BotStatusResponse(
                connected=True,
                guild_id=row[0],
                guild_name=row[1],
                last_sync_at=row[2],
            )
        else:
            return BotStatusResponse(connected=False)


@router.delete("/disconnect")
async def disconnect_bot(
    guild_id: int,
    user: User = Depends(get_current_user),
):
    """Disconnect a Discord bot by removing the stored token."""
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
            DELETE FROM discord_tokens
            WHERE user_id = :user_id AND guild_id = :guild_id
            RETURNING id
            """),
            {"user_id": user_uuid, "guild_id": guild_id}
        )
        deleted = result.fetchone()
        await session.commit()

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot connection not found"
            )

    return {"status": "disconnected", "guild_id": guild_id}
