"""
SQLAlchemy models for the central application database.

This is NOT the Discord data schema (that's in each user's Neon branch).
This is for application-level data: users, tokens, jobs, billing.
"""
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, DateTime,
    ForeignKey, LargeBinary, Text, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """
    Application user, synced from Clerk.

    This is NOT the Discord user table - that lives in each user's database.
    Uses 'app_users' to avoid conflict with Discord 'users' table.
    """
    __tablename__ = "app_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clerk_id = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    subscription_tier = Column(String(50), default="free")  # free, pro, team
    stripe_customer_id = Column(String(255))
    neon_branch_id = Column(String(255))  # User's Neon database branch

    # Relationships
    discord_tokens = relationship("DiscordToken", back_populates="user", cascade="all, delete-orphan")
    extraction_jobs = relationship("ExtractionJob", back_populates="user", cascade="all, delete-orphan")
    usage_logs = relationship("UsageLog", back_populates="user", cascade="all, delete-orphan")


class DiscordToken(Base):
    """
    Encrypted Discord bot tokens.

    Tokens are encrypted using Fernet before storage.
    """
    __tablename__ = "discord_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False)
    encrypted_token = Column(LargeBinary, nullable=False)  # Fernet encrypted
    guild_id = Column(BigInteger)
    guild_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_sync_at = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="discord_tokens")

    # Indexes
    __table_args__ = (
        Index("idx_discord_tokens_user_guild", "user_id", "guild_id"),
    )


class ExtractionJob(Base):
    """
    Discord data extraction jobs.

    Tracks the status and progress of extraction operations.
    """
    __tablename__ = "extraction_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False)
    guild_id = Column(BigInteger)
    status = Column(String(50), default="pending")  # pending, running, completed, failed, cancelled
    sync_days = Column(Integer, default=30)
    messages_extracted = Column(Integer, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)

    # Relationships
    user = relationship("User", back_populates="extraction_jobs")

    # Indexes
    __table_args__ = (
        Index("idx_extraction_jobs_user_status", "user_id", "status"),
        Index("idx_extraction_jobs_started", "started_at"),
    )


class UsageLog(Base):
    """
    Usage tracking for billing and limits.

    Tracks queries, extractions, and storage usage.
    """
    __tablename__ = "usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(100), nullable=False)  # 'query', 'extraction'
    storage_bytes = Column(BigInteger, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="usage_logs")

    # Indexes
    __table_args__ = (
        Index("idx_usage_logs_user_action", "user_id", "action"),
        Index("idx_usage_logs_created", "created_at"),
    )
