"""
Database model tests for Discord Analytics SaaS.
"""
import pytest
from datetime import datetime
import uuid


class TestUserModel:
    """Tests for User model."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session):
        """Test creating a user."""
        from db.models import User

        user = User(
            id=uuid.uuid4(),
            clerk_id="user_test123",
            email="test@example.com",
            subscription_tier="free",
        )

        db_session.add(user)
        await db_session.commit()

        # Query back
        await db_session.refresh(user)
        assert user.clerk_id == "user_test123"
        assert user.email == "test@example.com"
        assert user.subscription_tier == "free"
        assert user.created_at is not None

    @pytest.mark.asyncio
    async def test_user_default_tier(self, db_session):
        """Test user defaults to free tier."""
        from db.models import User

        user = User(
            id=uuid.uuid4(),
            clerk_id="user_test456",
        )

        db_session.add(user)
        await db_session.commit()

        await db_session.refresh(user)
        assert user.subscription_tier == "free"


class TestDiscordTokenModel:
    """Tests for DiscordToken model."""

    @pytest.mark.asyncio
    async def test_create_token(self, db_session):
        """Test creating a Discord token."""
        from db.models import User, DiscordToken

        # Create user first
        user = User(
            id=uuid.uuid4(),
            clerk_id="user_token_test",
        )
        db_session.add(user)
        await db_session.commit()

        # Create token
        token = DiscordToken(
            id=uuid.uuid4(),
            user_id=user.id,
            encrypted_token=b"encrypted_data_here",
            guild_id=123456789012345678,
            guild_name="Test Server",
        )

        db_session.add(token)
        await db_session.commit()

        await db_session.refresh(token)
        assert token.guild_id == 123456789012345678
        assert token.guild_name == "Test Server"
        assert token.encrypted_token == b"encrypted_data_here"


class TestExtractionJobModel:
    """Tests for ExtractionJob model."""

    @pytest.mark.asyncio
    async def test_create_job(self, db_session):
        """Test creating an extraction job."""
        from db.models import User, ExtractionJob

        # Create user
        user = User(
            id=uuid.uuid4(),
            clerk_id="user_job_test",
        )
        db_session.add(user)
        await db_session.commit()

        # Create job
        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user.id,
            guild_id=123456789,
            sync_days=30,
            status="pending",
        )

        db_session.add(job)
        await db_session.commit()

        await db_session.refresh(job)
        assert job.status == "pending"
        assert job.sync_days == 30
        assert job.messages_extracted == 0

    @pytest.mark.asyncio
    async def test_job_status_transitions(self, db_session):
        """Test job status can be updated."""
        from db.models import User, ExtractionJob

        user = User(id=uuid.uuid4(), clerk_id="user_status_test")
        db_session.add(user)
        await db_session.commit()

        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user.id,
            guild_id=123456789,
            status="pending",
        )
        db_session.add(job)
        await db_session.commit()

        # Update status
        job.status = "running"
        job.started_at = datetime.utcnow()
        await db_session.commit()

        await db_session.refresh(job)
        assert job.status == "running"
        assert job.started_at is not None


class TestUsageLogModel:
    """Tests for UsageLog model."""

    @pytest.mark.asyncio
    async def test_create_usage_log(self, db_session):
        """Test creating a usage log."""
        from db.models import User, UsageLog

        user = User(id=uuid.uuid4(), clerk_id="user_usage_test")
        db_session.add(user)
        await db_session.commit()

        log = UsageLog(
            id=uuid.uuid4(),
            user_id=user.id,
            action="query",
            storage_bytes=1024,
        )
        db_session.add(log)
        await db_session.commit()

        await db_session.refresh(log)
        assert log.action == "query"
        assert log.storage_bytes == 1024
        assert log.created_at is not None
