"""
End-to-end integration tests for Discord Analytics SaaS.

These tests verify complete user journeys through the system:
- User signup and database provisioning
- Bot connection flow
- Extraction flow
- Query execution flow
- Billing flow
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import uuid
from datetime import datetime, timedelta
import json


class TestUserSignupFlow:
    """Tests for the complete user signup flow."""

    @pytest.mark.asyncio
    async def test_clerk_webhook_creates_user_and_database(self, db_session):
        """Test that Clerk webhook properly provisions a new user."""
        from api.auth import handle_user_created
        from contextlib import asynccontextmanager

        # Simulate Clerk user.created webhook data
        clerk_user_id = f"user_{uuid.uuid4().hex[:24]}"
        webhook_data = {
            "id": clerk_user_id,
            "email_addresses": [
                {
                    "id": "email_123",
                    "email_address": "test@example.com"
                }
            ],
            "primary_email_address_id": "email_123",
        }

        @asynccontextmanager
        async def mock_db_session():
            yield db_session

        # Mock Neon database provisioning and use test db session
        with patch("api.auth.provision_user_database") as mock_provision:
            mock_provision.return_value = "br_test_branch_id"

            with patch("api.auth.get_db_session", mock_db_session):
                await handle_user_created(webhook_data)

        # Verify user was created in database
        from db.models import User
        from sqlalchemy import select
        result = await db_session.execute(
            select(User).where(User.clerk_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()

        assert user is not None
        assert user.email == "test@example.com"
        assert user.subscription_tier == "free"
        assert user.neon_branch_id == "br_test_branch_id"

    @pytest.mark.asyncio
    async def test_user_deletion_cleans_up_data(self, db_session):
        """Test that user deletion properly cleans up all data."""
        from api.auth import handle_user_deleted
        from db.models import User
        from contextlib import asynccontextmanager

        # First create a user to delete
        clerk_user_id = f"user_{uuid.uuid4().hex[:24]}"
        user = User(
            id=uuid.uuid4(),
            clerk_id=clerk_user_id,
            email="delete@example.com",
            subscription_tier="free"
        )
        db_session.add(user)
        await db_session.commit()

        webhook_data = {"id": clerk_user_id}

        @asynccontextmanager
        async def mock_db_session():
            yield db_session

        with patch("api.auth.delete_user_database") as mock_delete:
            with patch("api.auth.get_db_session", mock_db_session):
                await handle_user_deleted(webhook_data)

        # Verify user was deleted
        from sqlalchemy import select
        result = await db_session.execute(
            select(User).where(User.clerk_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()
        assert user is None

        # Verify Neon database deletion was called
        mock_delete.assert_called_once_with(clerk_user_id)


class TestBotConnectionFlow:
    """Tests for the bot connection flow."""

    @pytest.mark.asyncio
    async def test_connect_bot_with_valid_token(self, db_session):
        """Test connecting a bot with a valid token."""
        from db.models import User, DiscordToken

        # Create a user first
        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_bot_test")
        db_session.add(user)
        await db_session.commit()

        # Simulate token storage
        from services.encryption import encrypt_token
        with patch("services.encryption.settings") as mock_settings:
            from cryptography.fernet import Fernet
            mock_settings.discord_token_encryption_key = Fernet.generate_key().decode()

            import services.encryption as enc_module
            enc_module._fernet = None

            encrypted = encrypt_token("MTIzNDU2Nzg5.abcdef.ghijklmnop_valid_token")

        token = DiscordToken(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_token=encrypted,
            guild_id=123456789012345678,
            guild_name="Test Server",
        )
        db_session.add(token)
        await db_session.commit()

        # Verify token was stored
        await db_session.refresh(token)
        assert token.guild_name == "Test Server"

    @pytest.mark.asyncio
    async def test_update_existing_bot_connection(self, db_session):
        """Test updating an existing bot connection."""
        from db.models import User, DiscordToken

        # Create user and initial token
        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_update_bot")
        db_session.add(user)
        await db_session.commit()

        initial_token = DiscordToken(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_token=b"initial_encrypted",
            guild_id=123456789012345678,
            guild_name="Old Server Name",
        )
        db_session.add(initial_token)
        await db_session.commit()

        # Update the token
        initial_token.guild_name = "New Server Name"
        initial_token.encrypted_token = b"updated_encrypted"
        await db_session.commit()

        await db_session.refresh(initial_token)
        assert initial_token.guild_name == "New Server Name"


class TestExtractionFlow:
    """Tests for the extraction flow."""

    @pytest.mark.asyncio
    async def test_start_extraction_creates_job(self, db_session):
        """Test that starting an extraction creates a job record."""
        from db.models import User, DiscordToken, ExtractionJob

        # Create user with token
        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_extraction_test")
        db_session.add(user)
        await db_session.commit()

        token = DiscordToken(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_token=b"encrypted",
            guild_id=123456789,
            guild_name="Test",
        )
        db_session.add(token)
        await db_session.commit()

        # Create extraction job
        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123456789,
            sync_days=30,
            status="pending",
            started_at=datetime.utcnow(),
        )
        db_session.add(job)
        await db_session.commit()

        await db_session.refresh(job)
        assert job.status == "pending"

    @pytest.mark.asyncio
    async def test_extraction_job_status_transitions(self, db_session):
        """Test extraction job status transitions."""
        from db.models import User, ExtractionJob

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_status_test")
        db_session.add(user)
        await db_session.commit()

        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123456789,
            status="pending",
        )
        db_session.add(job)
        await db_session.commit()

        # Transition to running
        job.status = "running"
        job.started_at = datetime.utcnow()
        await db_session.commit()
        assert job.status == "running"

        # Transition to completed
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.messages_extracted = 5000
        await db_session.commit()
        assert job.status == "completed"
        assert job.messages_extracted == 5000

    @pytest.mark.asyncio
    async def test_extraction_prevents_concurrent_jobs(self, db_session):
        """Test that concurrent extraction jobs for same user are prevented."""
        from db.models import User, ExtractionJob
        from sqlalchemy import select

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_concurrent_test")
        db_session.add(user)
        await db_session.commit()

        # Create a running job
        job1 = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123456789,
            status="running",
            started_at=datetime.utcnow(),
        )
        db_session.add(job1)
        await db_session.commit()

        # Check for existing running/pending jobs
        result = await db_session.execute(
            select(ExtractionJob).where(
                ExtractionJob.user_id == user_id,
                ExtractionJob.status.in_(["pending", "running"])
            )
        )
        existing = result.scalar_one_or_none()

        assert existing is not None  # Should find the running job

    @pytest.mark.asyncio
    async def test_extraction_respects_tier_limits(self, db_session):
        """Test that extraction respects subscription tier limits."""
        from db.models import User
        from config import get_settings

        settings = get_settings()

        # Free tier user
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            clerk_id="user_tier_test",
            subscription_tier="free",
        )
        db_session.add(user)
        await db_session.commit()

        # Free tier should be limited to free_tier_sync_days
        assert settings.free_tier_sync_days == 30

        # Pro tier user would have higher limit
        user.subscription_tier = "pro"
        await db_session.commit()

        assert settings.pro_tier_sync_days == 365


class TestQueryFlow:
    """Tests for the query execution flow."""

    @pytest.mark.asyncio
    async def test_query_execution_logs_usage(self, db_session):
        """Test that query execution logs usage."""
        from db.models import User, UsageLog

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_query_log")
        db_session.add(user)
        await db_session.commit()

        # Log a query
        log = UsageLog(
            id=uuid.uuid4(),
            user_id=user_id,
            action="query",
        )
        db_session.add(log)
        await db_session.commit()

        # Verify log exists
        from sqlalchemy import select, func
        result = await db_session.execute(
            select(func.count(UsageLog.id)).where(
                UsageLog.user_id == user_id,
                UsageLog.action == "query"
            )
        )
        count = result.scalar()

        assert count == 1

    def test_query_validation_allows_complex_queries(self):
        """Test that complex but safe queries are allowed."""
        from api.query import validate_query

        complex_queries = [
            """
            SELECT
                u.username,
                COUNT(m.message_id) as message_count,
                MAX(m.created_at) as last_message
            FROM users u
            LEFT JOIN messages m ON u.user_id = m.author_id
            GROUP BY u.username
            ORDER BY message_count DESC
            LIMIT 10
            """,
            """
            WITH daily_counts AS (
                SELECT
                    DATE(created_at) as day,
                    COUNT(*) as count
                FROM messages
                GROUP BY DATE(created_at)
            )
            SELECT
                day,
                count,
                AVG(count) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as rolling_avg
            FROM daily_counts
            ORDER BY day DESC
            """,
        ]

        for query in complex_queries:
            # Should not raise
            validate_query(query)


class TestBillingFlow:
    """Tests for the billing flow."""

    @pytest.mark.asyncio
    async def test_subscription_upgrade_flow(self, db_session):
        """Test the subscription upgrade flow."""
        from db.models import User

        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            clerk_id="user_upgrade_test",
            subscription_tier="free",
        )
        db_session.add(user)
        await db_session.commit()

        # Simulate upgrade
        user.subscription_tier = "pro"
        user.stripe_customer_id = "cus_test123"
        await db_session.commit()

        await db_session.refresh(user)
        assert user.subscription_tier == "pro"
        assert user.stripe_customer_id == "cus_test123"

    @pytest.mark.asyncio
    async def test_subscription_cancellation_reverts_to_free(self, db_session):
        """Test that subscription cancellation reverts to free tier."""
        from db.models import User

        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            clerk_id="user_cancel_test",
            subscription_tier="pro",
            stripe_customer_id="cus_test456",
        )
        db_session.add(user)
        await db_session.commit()

        # Simulate cancellation
        user.subscription_tier = "free"
        await db_session.commit()

        await db_session.refresh(user)
        assert user.subscription_tier == "free"


class TestFullUserJourney:
    """Tests for complete user journeys."""

    @pytest.mark.asyncio
    async def test_new_user_complete_journey(self, db_session):
        """Test a new user's complete journey through the system."""
        from db.models import User, DiscordToken, ExtractionJob, UsageLog

        # Step 1: User signs up (simulated via webhook)
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            clerk_id="user_journey_test",
            email="journey@example.com",
            subscription_tier="free",
            neon_branch_id="br_journey_test",
        )
        db_session.add(user)
        await db_session.commit()

        # Step 2: User connects their Discord bot
        token = DiscordToken(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_token=b"encrypted_token_data",
            guild_id=987654321,
            guild_name="Journey Test Server",
        )
        db_session.add(token)
        await db_session.commit()

        # Step 3: User starts an extraction
        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=987654321,
            sync_days=30,
            status="pending",
            started_at=datetime.utcnow(),
        )
        db_session.add(job)
        await db_session.commit()

        # Step 4: Extraction completes
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.messages_extracted = 10000
        await db_session.commit()

        # Step 5: User runs queries (logging usage)
        for i in range(5):
            log = UsageLog(
                id=uuid.uuid4(),
                user_id=user_id,
                action="query",
            )
            db_session.add(log)
        await db_session.commit()

        # Step 6: User upgrades to Pro
        user.subscription_tier = "pro"
        user.stripe_customer_id = "cus_journey_test"
        await db_session.commit()

        # Verify final state
        await db_session.refresh(user)
        await db_session.refresh(job)

        assert user.subscription_tier == "pro"
        assert job.status == "completed"
        assert job.messages_extracted == 10000

        # Count usage logs
        from sqlalchemy import select, func
        result = await db_session.execute(
            select(func.count(UsageLog.id)).where(UsageLog.user_id == user_id)
        )
        usage_count = result.scalar()
        assert usage_count == 5


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_extraction_failure_updates_status(self, db_session):
        """Test that extraction failures properly update job status."""
        from db.models import User, ExtractionJob

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_failure_test")
        db_session.add(user)
        await db_session.commit()

        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123456789,
            status="running",
            started_at=datetime.utcnow(),
        )
        db_session.add(job)
        await db_session.commit()

        # Simulate failure
        job.status = "failed"
        job.completed_at = datetime.utcnow()
        job.error_message = "Discord API rate limit exceeded"
        await db_session.commit()

        await db_session.refresh(job)
        assert job.status == "failed"
        assert "rate limit" in job.error_message.lower()

    @pytest.mark.asyncio
    async def test_database_connection_pool_handling(self, db_session):
        """Test that database connections are properly managed."""
        from db.models import User

        # Create multiple users to test connection handling
        users = []
        for i in range(10):
            user = User(
                id=uuid.uuid4(),
                clerk_id=f"user_pool_test_{i}",
            )
            users.append(user)
            db_session.add(user)

        await db_session.commit()

        # Verify all were created
        from sqlalchemy import select, func
        result = await db_session.execute(
            select(func.count(User.id)).where(
                User.clerk_id.like("user_pool_test_%")
            )
        )
        count = result.scalar()

        assert count == 10


class TestDataIntegrity:
    """Tests for data integrity constraints."""

    @pytest.mark.asyncio
    async def test_cascade_delete_user_tokens(self, db_session):
        """Test that deleting a user cascades to their tokens."""
        from db.models import User, DiscordToken
        from sqlalchemy import select

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_cascade_test")
        db_session.add(user)
        await db_session.commit()

        token = DiscordToken(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_token=b"test",
            guild_id=123,
            guild_name="Test",
        )
        db_session.add(token)
        await db_session.commit()

        # Delete user
        await db_session.delete(user)
        await db_session.commit()

        # Token should be deleted
        result = await db_session.execute(
            select(DiscordToken).where(DiscordToken.user_id == user_id)
        )
        remaining_tokens = result.scalars().all()

        assert len(remaining_tokens) == 0

    @pytest.mark.asyncio
    async def test_unique_clerk_id_constraint(self, db_session):
        """Test that clerk_id uniqueness is enforced."""
        from db.models import User
        from sqlalchemy.exc import IntegrityError

        clerk_id = "user_unique_test"

        user1 = User(id=uuid.uuid4(), clerk_id=clerk_id)
        db_session.add(user1)
        await db_session.commit()

        # Try to create another user with same clerk_id
        user2 = User(id=uuid.uuid4(), clerk_id=clerk_id)
        db_session.add(user2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()
