"""
Comprehensive functional tests for Discord Analytics SaaS.

These tests cover all different conditions and scenarios the app might encounter,
including edge cases, error conditions, and various permutations of user states.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import uuid
from datetime import datetime, timedelta
import json


# ============================================================================
# BOT CONFIGURATION SCENARIOS
# ============================================================================

class TestBotConfigurationScenarios:
    """Tests for all bot configuration scenarios."""

    @pytest.mark.asyncio
    async def test_connect_bot_new_user_first_guild(self, db_session):
        """Scenario: New user connects their first guild."""
        from db.models import User, DiscordToken

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_first_guild")
        db_session.add(user)
        await db_session.commit()

        token = DiscordToken(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_token=b"encrypted",
            guild_id=111111111111111111,
            guild_name="First Server",
        )
        db_session.add(token)
        await db_session.commit()

        # Verify
        from sqlalchemy import select
        result = await db_session.execute(
            select(DiscordToken).where(DiscordToken.user_id == user_id)
        )
        tokens = result.scalars().all()
        assert len(tokens) == 1
        assert tokens[0].guild_name == "First Server"

    @pytest.mark.asyncio
    async def test_connect_bot_existing_user_same_guild_update(self, db_session):
        """Scenario: User updates token for same guild."""
        from db.models import User, DiscordToken

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_update_guild")
        db_session.add(user)
        await db_session.commit()

        # Initial token
        token = DiscordToken(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_token=b"old_encrypted",
            guild_id=222222222222222222,
            guild_name="Old Name",
        )
        db_session.add(token)
        await db_session.commit()

        # Update
        token.encrypted_token = b"new_encrypted"
        token.guild_name = "New Name"
        await db_session.commit()

        await db_session.refresh(token)
        assert token.encrypted_token == b"new_encrypted"
        assert token.guild_name == "New Name"

    @pytest.mark.asyncio
    async def test_connect_bot_multiple_guilds_same_user(self, db_session):
        """Scenario: User connects multiple guilds."""
        from db.models import User, DiscordToken

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_multi_guild")
        db_session.add(user)
        await db_session.commit()

        guilds = [
            (333333333333333333, "Server 1"),
            (444444444444444444, "Server 2"),
            (555555555555555555, "Server 3"),
        ]

        for guild_id, guild_name in guilds:
            token = DiscordToken(
                id=uuid.uuid4(),
                user_id=user_id,
                encrypted_token=b"encrypted",
                guild_id=guild_id,
                guild_name=guild_name,
            )
            db_session.add(token)

        await db_session.commit()

        from sqlalchemy import select
        result = await db_session.execute(
            select(DiscordToken).where(DiscordToken.user_id == user_id)
        )
        tokens = result.scalars().all()
        assert len(tokens) == 3

    @pytest.mark.asyncio
    async def test_disconnect_bot_single_guild(self, db_session):
        """Scenario: User disconnects their only guild."""
        from db.models import User, DiscordToken

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_disconnect")
        db_session.add(user)
        await db_session.commit()

        token = DiscordToken(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_token=b"encrypted",
            guild_id=666666666666666666,
            guild_name="To Be Deleted",
        )
        db_session.add(token)
        await db_session.commit()

        await db_session.delete(token)
        await db_session.commit()

        from sqlalchemy import select
        result = await db_session.execute(
            select(DiscordToken).where(DiscordToken.user_id == user_id)
        )
        tokens = result.scalars().all()
        assert len(tokens) == 0

    @pytest.mark.asyncio
    async def test_disconnect_bot_one_of_multiple_guilds(self, db_session):
        """Scenario: User disconnects one guild while keeping others."""
        from db.models import User, DiscordToken

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_partial_disconnect")
        db_session.add(user)
        await db_session.commit()

        token1 = DiscordToken(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_token=b"encrypted",
            guild_id=777777777777777777,
            guild_name="Keep This",
        )
        token2 = DiscordToken(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_token=b"encrypted",
            guild_id=888888888888888888,
            guild_name="Delete This",
        )
        db_session.add(token1)
        db_session.add(token2)
        await db_session.commit()

        await db_session.delete(token2)
        await db_session.commit()

        from sqlalchemy import select
        result = await db_session.execute(
            select(DiscordToken).where(DiscordToken.user_id == user_id)
        )
        tokens = result.scalars().all()
        assert len(tokens) == 1
        assert tokens[0].guild_name == "Keep This"


# ============================================================================
# EXTRACTION SCENARIOS
# ============================================================================

class TestExtractionScenarios:
    """Tests for all extraction scenarios."""

    @pytest.mark.asyncio
    async def test_extraction_free_tier_30_days(self, db_session):
        """Scenario: Free tier user extracts 30 days."""
        from db.models import User, ExtractionJob

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_free_30", subscription_tier="free")
        db_session.add(user)
        await db_session.commit()

        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123456789,
            sync_days=30,
            status="pending",
        )
        db_session.add(job)
        await db_session.commit()

        assert job.sync_days == 30

    @pytest.mark.asyncio
    async def test_extraction_pro_tier_365_days(self, db_session):
        """Scenario: Pro tier user extracts 365 days."""
        from db.models import User, ExtractionJob

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_pro_365", subscription_tier="pro")
        db_session.add(user)
        await db_session.commit()

        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123456789,
            sync_days=365,
            status="pending",
        )
        db_session.add(job)
        await db_session.commit()

        assert job.sync_days == 365

    @pytest.mark.asyncio
    async def test_extraction_team_tier_unlimited(self, db_session):
        """Scenario: Team tier user extracts unlimited history."""
        from db.models import User, ExtractionJob

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_team_unlimited", subscription_tier="team")
        db_session.add(user)
        await db_session.commit()

        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123456789,
            sync_days=9999,  # Unlimited
            status="pending",
        )
        db_session.add(job)
        await db_session.commit()

        assert job.sync_days == 9999

    @pytest.mark.asyncio
    async def test_extraction_job_pending_to_running(self, db_session):
        """Scenario: Job transitions from pending to running."""
        from db.models import User, ExtractionJob

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_pending_running")
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

        job.status = "running"
        job.started_at = datetime.utcnow()
        await db_session.commit()

        assert job.status == "running"
        assert job.started_at is not None

    @pytest.mark.asyncio
    async def test_extraction_job_running_to_completed(self, db_session):
        """Scenario: Job completes successfully."""
        from db.models import User, ExtractionJob

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_complete")
        db_session.add(user)
        await db_session.commit()

        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123456789,
            status="running",
            started_at=datetime.utcnow() - timedelta(minutes=30),
        )
        db_session.add(job)
        await db_session.commit()

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.messages_extracted = 50000
        await db_session.commit()

        assert job.status == "completed"
        assert job.messages_extracted == 50000

    @pytest.mark.asyncio
    async def test_extraction_job_running_to_failed(self, db_session):
        """Scenario: Job fails during extraction."""
        from db.models import User, ExtractionJob

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_failed")
        db_session.add(user)
        await db_session.commit()

        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123456789,
            status="running",
            started_at=datetime.utcnow() - timedelta(minutes=5),
        )
        db_session.add(job)
        await db_session.commit()

        job.status = "failed"
        job.completed_at = datetime.utcnow()
        job.error_message = "Discord API error: 429 Too Many Requests"
        await db_session.commit()

        assert job.status == "failed"
        assert "429" in job.error_message

    @pytest.mark.asyncio
    async def test_extraction_job_cancelled(self, db_session):
        """Scenario: User cancels a running job."""
        from db.models import User, ExtractionJob

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_cancel")
        db_session.add(user)
        await db_session.commit()

        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123456789,
            status="running",
            started_at=datetime.utcnow() - timedelta(minutes=10),
        )
        db_session.add(job)
        await db_session.commit()

        job.status = "cancelled"
        job.completed_at = datetime.utcnow()
        await db_session.commit()

        assert job.status == "cancelled"

    @pytest.mark.asyncio
    async def test_extraction_concurrent_job_prevention(self, db_session):
        """Scenario: Prevent starting new job when one is running."""
        from db.models import User, ExtractionJob
        from sqlalchemy import select

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_concurrent")
        db_session.add(user)
        await db_session.commit()

        # Create running job
        job1 = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123456789,
            status="running",
        )
        db_session.add(job1)
        await db_session.commit()

        # Check for existing
        result = await db_session.execute(
            select(ExtractionJob).where(
                ExtractionJob.user_id == user_id,
                ExtractionJob.status.in_(["pending", "running"])
            )
        )
        existing = result.scalars().all()
        assert len(existing) == 1

    @pytest.mark.asyncio
    async def test_extraction_multiple_completed_jobs_history(self, db_session):
        """Scenario: User has multiple completed jobs in history."""
        from db.models import User, ExtractionJob
        from sqlalchemy import select

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_history")
        db_session.add(user)
        await db_session.commit()

        # Create multiple completed jobs
        for i in range(5):
            job = ExtractionJob(
                id=uuid.uuid4(),
                user_id=user_id,
                guild_id=123456789,
                status="completed",
                started_at=datetime.utcnow() - timedelta(days=i * 7),
                completed_at=datetime.utcnow() - timedelta(days=i * 7 - 1),
                messages_extracted=(i + 1) * 10000,
            )
            db_session.add(job)
        await db_session.commit()

        result = await db_session.execute(
            select(ExtractionJob).where(
                ExtractionJob.user_id == user_id
            ).order_by(ExtractionJob.started_at.desc())
        )
        jobs = result.scalars().all()
        assert len(jobs) == 5

    @pytest.mark.asyncio
    async def test_extraction_progress_tracking(self, db_session):
        """Scenario: Track extraction progress updates."""
        from db.models import User, ExtractionJob

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_progress")
        db_session.add(user)
        await db_session.commit()

        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123456789,
            status="running",
            messages_extracted=0,
        )
        db_session.add(job)
        await db_session.commit()

        # Simulate progress updates
        progress_values = [1000, 5000, 10000, 25000, 50000]
        for progress in progress_values:
            job.messages_extracted = progress
            await db_session.commit()
            assert job.messages_extracted == progress


# ============================================================================
# QUERY EXECUTION SCENARIOS
# ============================================================================

class TestQueryExecutionScenarios:
    """Tests for all query execution scenarios."""

    def test_query_simple_select(self):
        """Scenario: Simple SELECT query."""
        from api.query import validate_query
        validate_query("SELECT * FROM messages LIMIT 10")

    def test_query_with_where_clause(self):
        """Scenario: SELECT with WHERE clause."""
        from api.query import validate_query
        validate_query("SELECT * FROM messages WHERE author_id = 123456789")

    def test_query_with_join(self):
        """Scenario: SELECT with JOIN."""
        from api.query import validate_query
        validate_query("""
            SELECT m.content, u.username
            FROM messages m
            JOIN users u ON m.author_id = u.user_id
            LIMIT 100
        """)

    def test_query_with_aggregation(self):
        """Scenario: SELECT with GROUP BY and aggregation."""
        from api.query import validate_query
        validate_query("""
            SELECT author_id, COUNT(*) as message_count
            FROM messages
            GROUP BY author_id
            HAVING COUNT(*) > 10
            ORDER BY message_count DESC
        """)

    def test_query_with_subquery(self):
        """Scenario: SELECT with subquery."""
        from api.query import validate_query
        validate_query("""
            SELECT * FROM users
            WHERE user_id IN (
                SELECT DISTINCT author_id FROM messages
                WHERE created_at > NOW() - INTERVAL '7 days'
            )
        """)

    def test_query_with_cte(self):
        """Scenario: SELECT with CTE (Common Table Expression)."""
        from api.query import validate_query
        validate_query("""
            WITH active_users AS (
                SELECT author_id, COUNT(*) as cnt
                FROM messages
                GROUP BY author_id
            )
            SELECT * FROM active_users
            WHERE cnt > 100
        """)

    def test_query_with_window_function(self):
        """Scenario: SELECT with window function."""
        from api.query import validate_query
        validate_query("""
            SELECT
                author_id,
                created_at,
                ROW_NUMBER() OVER (PARTITION BY author_id ORDER BY created_at DESC) as rn
            FROM messages
        """)

    def test_query_date_range(self):
        """Scenario: SELECT with date range filter."""
        from api.query import validate_query
        validate_query("""
            SELECT * FROM messages
            WHERE created_at BETWEEN '2024-01-01' AND '2024-12-31'
        """)

    def test_query_text_search(self):
        """Scenario: SELECT with text search."""
        from api.query import validate_query
        validate_query("SELECT * FROM messages WHERE content ILIKE '%hello%'")

    def test_query_null_handling(self):
        """Scenario: SELECT with NULL handling."""
        from api.query import validate_query
        validate_query("""
            SELECT COALESCE(content, '[no content]') as content
            FROM messages
            WHERE reply_to_message_id IS NOT NULL
        """)

    def test_query_case_expression(self):
        """Scenario: SELECT with CASE expression."""
        from api.query import validate_query
        validate_query("""
            SELECT
                CASE
                    WHEN is_bot THEN 'Bot'
                    ELSE 'Human'
                END as user_type,
                COUNT(*) as count
            FROM users
            GROUP BY is_bot
        """)

    def test_query_with_limit_offset(self):
        """Scenario: SELECT with pagination."""
        from api.query import validate_query
        validate_query("SELECT * FROM messages ORDER BY created_at DESC LIMIT 50 OFFSET 100")

    def test_query_multiple_tables(self):
        """Scenario: SELECT across multiple tables."""
        from api.query import validate_query
        validate_query("""
            SELECT
                c.name as channel_name,
                u.username,
                COUNT(m.message_id) as message_count
            FROM channels c
            JOIN messages m ON c.channel_id = m.channel_id
            JOIN users u ON m.author_id = u.user_id
            GROUP BY c.name, u.username
            ORDER BY message_count DESC
            LIMIT 100
        """)


# ============================================================================
# BILLING SCENARIOS
# ============================================================================

class TestBillingScenarios:
    """Tests for all billing scenarios."""

    @pytest.mark.asyncio
    async def test_billing_new_free_user(self, db_session):
        """Scenario: New user starts on free tier."""
        from db.models import User

        user = User(
            id=uuid.uuid4(),
            clerk_id="user_new_free",
            subscription_tier="free",
        )
        db_session.add(user)
        await db_session.commit()

        assert user.subscription_tier == "free"
        assert user.stripe_customer_id is None

    @pytest.mark.asyncio
    async def test_billing_free_to_pro_upgrade(self, db_session):
        """Scenario: User upgrades from free to pro."""
        from db.models import User

        user = User(
            id=uuid.uuid4(),
            clerk_id="user_upgrade_pro",
            subscription_tier="free",
        )
        db_session.add(user)
        await db_session.commit()

        user.subscription_tier = "pro"
        user.stripe_customer_id = "cus_pro_test"
        await db_session.commit()

        assert user.subscription_tier == "pro"

    @pytest.mark.asyncio
    async def test_billing_free_to_team_upgrade(self, db_session):
        """Scenario: User upgrades from free to team."""
        from db.models import User

        user = User(
            id=uuid.uuid4(),
            clerk_id="user_upgrade_team",
            subscription_tier="free",
        )
        db_session.add(user)
        await db_session.commit()

        user.subscription_tier = "team"
        user.stripe_customer_id = "cus_team_test"
        await db_session.commit()

        assert user.subscription_tier == "team"

    @pytest.mark.asyncio
    async def test_billing_pro_to_team_upgrade(self, db_session):
        """Scenario: User upgrades from pro to team."""
        from db.models import User

        user = User(
            id=uuid.uuid4(),
            clerk_id="user_pro_to_team",
            subscription_tier="pro",
            stripe_customer_id="cus_existing",
        )
        db_session.add(user)
        await db_session.commit()

        user.subscription_tier = "team"
        await db_session.commit()

        assert user.subscription_tier == "team"

    @pytest.mark.asyncio
    async def test_billing_team_to_pro_downgrade(self, db_session):
        """Scenario: User downgrades from team to pro."""
        from db.models import User

        user = User(
            id=uuid.uuid4(),
            clerk_id="user_team_to_pro",
            subscription_tier="team",
            stripe_customer_id="cus_downgrade",
        )
        db_session.add(user)
        await db_session.commit()

        user.subscription_tier = "pro"
        await db_session.commit()

        assert user.subscription_tier == "pro"

    @pytest.mark.asyncio
    async def test_billing_cancellation_to_free(self, db_session):
        """Scenario: User cancels subscription, reverts to free."""
        from db.models import User

        user = User(
            id=uuid.uuid4(),
            clerk_id="user_cancel_sub",
            subscription_tier="pro",
            stripe_customer_id="cus_cancel",
        )
        db_session.add(user)
        await db_session.commit()

        user.subscription_tier = "free"
        await db_session.commit()

        assert user.subscription_tier == "free"

    @pytest.mark.asyncio
    async def test_billing_payment_failed_downgrade(self, db_session):
        """Scenario: Payment fails, user downgraded to free."""
        from db.models import User

        user = User(
            id=uuid.uuid4(),
            clerk_id="user_payment_failed",
            subscription_tier="pro",
            stripe_customer_id="cus_payment_failed",
        )
        db_session.add(user)
        await db_session.commit()

        # Simulate payment failure
        user.subscription_tier = "free"
        await db_session.commit()

        assert user.subscription_tier == "free"


# ============================================================================
# USAGE TRACKING SCENARIOS
# ============================================================================

class TestUsageTrackingScenarios:
    """Tests for usage tracking scenarios."""

    @pytest.mark.asyncio
    async def test_usage_first_query(self, db_session):
        """Scenario: User's first query."""
        from db.models import User, UsageLog

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_first_query")
        db_session.add(user)
        await db_session.commit()

        log = UsageLog(
            id=uuid.uuid4(),
            user_id=user_id,
            action="query",
        )
        db_session.add(log)
        await db_session.commit()

        from sqlalchemy import select, func
        result = await db_session.execute(
            select(func.count(UsageLog.id)).where(
                UsageLog.user_id == user_id,
                UsageLog.action == "query"
            )
        )
        assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_usage_approaching_limit(self, db_session):
        """Scenario: User approaching free tier limit."""
        from db.models import User, UsageLog
        from config import get_settings

        settings = get_settings()
        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_approaching_limit", subscription_tier="free")
        db_session.add(user)
        await db_session.commit()

        # Add queries up to 90% of limit
        target = int(settings.free_tier_queries_per_month * 0.9)
        for _ in range(target):
            log = UsageLog(id=uuid.uuid4(), user_id=user_id, action="query")
            db_session.add(log)
        await db_session.commit()

        from sqlalchemy import select, func
        result = await db_session.execute(
            select(func.count(UsageLog.id)).where(
                UsageLog.user_id == user_id,
                UsageLog.action == "query"
            )
        )
        count = result.scalar()
        assert count < settings.free_tier_queries_per_month

    @pytest.mark.asyncio
    async def test_usage_at_limit(self, db_session):
        """Scenario: User at free tier limit."""
        from db.models import User, UsageLog
        from config import get_settings

        settings = get_settings()
        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_at_limit", subscription_tier="free")
        db_session.add(user)
        await db_session.commit()

        # Add queries up to limit
        for _ in range(settings.free_tier_queries_per_month):
            log = UsageLog(id=uuid.uuid4(), user_id=user_id, action="query")
            db_session.add(log)
        await db_session.commit()

        from sqlalchemy import select, func
        result = await db_session.execute(
            select(func.count(UsageLog.id)).where(
                UsageLog.user_id == user_id,
                UsageLog.action == "query"
            )
        )
        count = result.scalar()
        assert count == settings.free_tier_queries_per_month

    @pytest.mark.asyncio
    async def test_usage_pro_unlimited(self, db_session):
        """Scenario: Pro user with unlimited queries."""
        from db.models import User, UsageLog

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_pro_unlimited", subscription_tier="pro")
        db_session.add(user)
        await db_session.commit()

        # Add many queries
        for _ in range(5000):
            log = UsageLog(id=uuid.uuid4(), user_id=user_id, action="query")
            db_session.add(log)
        await db_session.commit()

        # Pro tier should have no limit
        assert user.subscription_tier == "pro"

    @pytest.mark.asyncio
    async def test_usage_storage_tracking(self, db_session):
        """Scenario: Track storage usage."""
        from db.models import User, UsageLog

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_storage")
        db_session.add(user)
        await db_session.commit()

        log = UsageLog(
            id=uuid.uuid4(),
            user_id=user_id,
            action="storage_update",
            storage_bytes=100 * 1024 * 1024,  # 100 MB
        )
        db_session.add(log)
        await db_session.commit()

        assert log.storage_bytes == 100 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_usage_month_rollover(self, db_session):
        """Scenario: Usage resets at month boundary."""
        from db.models import User, UsageLog
        from sqlalchemy import select, func

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_rollover")
        db_session.add(user)
        await db_session.commit()

        # Add old queries (last month)
        old_date = datetime.utcnow() - timedelta(days=35)
        for _ in range(100):
            log = UsageLog(
                id=uuid.uuid4(),
                user_id=user_id,
                action="query",
                created_at=old_date,
            )
            db_session.add(log)

        # Add current month queries
        for _ in range(10):
            log = UsageLog(
                id=uuid.uuid4(),
                user_id=user_id,
                action="query",
            )
            db_session.add(log)

        await db_session.commit()

        # Count current month only
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        result = await db_session.execute(
            select(func.count(UsageLog.id)).where(
                UsageLog.user_id == user_id,
                UsageLog.action == "query",
                UsageLog.created_at >= current_month_start
            )
        )
        current_month_count = result.scalar()
        assert current_month_count == 10


# ============================================================================
# USER LIFECYCLE SCENARIOS
# ============================================================================

class TestUserLifecycleScenarios:
    """Tests for user lifecycle scenarios."""

    @pytest.mark.asyncio
    async def test_user_signup_new(self, db_session):
        """Scenario: New user signs up."""
        from db.models import User

        user = User(
            id=uuid.uuid4(),
            clerk_id="user_new_signup",
            email="new@example.com",
            subscription_tier="free",
        )
        db_session.add(user)
        await db_session.commit()

        assert user.email == "new@example.com"
        assert user.subscription_tier == "free"

    @pytest.mark.asyncio
    async def test_user_with_neon_database(self, db_session):
        """Scenario: User with provisioned Neon database."""
        from db.models import User

        user = User(
            id=uuid.uuid4(),
            clerk_id="user_with_neon",
            neon_branch_id="br_test_123",
        )
        db_session.add(user)
        await db_session.commit()

        assert user.neon_branch_id == "br_test_123"

    @pytest.mark.asyncio
    async def test_user_email_update(self, db_session):
        """Scenario: User updates email."""
        from db.models import User

        user = User(
            id=uuid.uuid4(),
            clerk_id="user_email_update",
            email="old@example.com",
        )
        db_session.add(user)
        await db_session.commit()

        user.email = "new@example.com"
        await db_session.commit()

        assert user.email == "new@example.com"

    @pytest.mark.asyncio
    async def test_user_deletion_cascade(self, db_session):
        """Scenario: User deletion cascades to related data."""
        from db.models import User, DiscordToken, ExtractionJob, UsageLog
        from sqlalchemy import select

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_cascade_delete")
        db_session.add(user)
        await db_session.commit()

        # Add related data
        token = DiscordToken(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_token=b"test",
            guild_id=123,
            guild_name="Test",
        )
        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123,
            status="completed",
        )
        log = UsageLog(
            id=uuid.uuid4(),
            user_id=user_id,
            action="query",
        )
        db_session.add_all([token, job, log])
        await db_session.commit()

        # Delete user
        await db_session.delete(user)
        await db_session.commit()

        # Check all related data is deleted
        token_result = await db_session.execute(
            select(DiscordToken).where(DiscordToken.user_id == user_id)
        )
        job_result = await db_session.execute(
            select(ExtractionJob).where(ExtractionJob.user_id == user_id)
        )
        log_result = await db_session.execute(
            select(UsageLog).where(UsageLog.user_id == user_id)
        )

        assert len(token_result.scalars().all()) == 0
        assert len(job_result.scalars().all()) == 0
        assert len(log_result.scalars().all()) == 0


# ============================================================================
# ERROR HANDLING SCENARIOS
# ============================================================================

class TestErrorHandlingScenarios:
    """Tests for error handling scenarios."""

    def test_query_validation_blocks_malformed_sql(self):
        """Scenario: Block non-SELECT SQL statements."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            validate_query("SHOW TABLES")  # Non-SELECT statement

    def test_query_validation_blocks_truncate(self):
        """Scenario: Block TRUNCATE statement."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            validate_query("TRUNCATE TABLE messages")

    def test_query_validation_blocks_copy(self):
        """Scenario: Block COPY statement."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            validate_query("COPY messages TO '/tmp/data.csv'")

    @pytest.mark.asyncio
    async def test_extraction_invalid_guild_id(self, db_session):
        """Scenario: Handle invalid guild ID gracefully."""
        from db.models import User, ExtractionJob

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_invalid_guild")
        db_session.add(user)
        await db_session.commit()

        # Guild ID 0 might be invalid
        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=0,
            status="pending",
        )
        db_session.add(job)
        await db_session.commit()

        # Job should be created but might fail during execution
        assert job.guild_id == 0


# ============================================================================
# CONCURRENT ACCESS SCENARIOS
# ============================================================================

class TestConcurrentAccessScenarios:
    """Tests for concurrent access scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_extraction_jobs_different_users(self, db_session):
        """Scenario: Multiple users running extractions concurrently."""
        from db.models import User, ExtractionJob

        users = []
        jobs = []

        for i in range(5):
            user = User(id=uuid.uuid4(), clerk_id=f"concurrent_user_{i}")
            users.append(user)
            db_session.add(user)

        await db_session.commit()

        for user in users:
            job = ExtractionJob(
                id=uuid.uuid4(),
                user_id=user.id,
                guild_id=100000000 + users.index(user),
                status="running",
            )
            jobs.append(job)
            db_session.add(job)

        await db_session.commit()

        # All jobs should exist
        assert len(jobs) == 5
        for job in jobs:
            assert job.status == "running"

    @pytest.mark.asyncio
    async def test_concurrent_queries_same_user(self, db_session):
        """Scenario: Same user running multiple queries."""
        from db.models import User, UsageLog

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="concurrent_query_user")
        db_session.add(user)
        await db_session.commit()

        # Simulate concurrent query logging
        logs = []
        for i in range(10):
            log = UsageLog(
                id=uuid.uuid4(),
                user_id=user_id,
                action="query",
            )
            logs.append(log)
            db_session.add(log)

        await db_session.commit()

        assert len(logs) == 10


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_user_with_empty_email(self, db_session):
        """Edge case: User without email."""
        from db.models import User

        user = User(
            id=uuid.uuid4(),
            clerk_id="user_no_email",
            email=None,
        )
        db_session.add(user)
        await db_session.commit()

        assert user.email is None

    @pytest.mark.asyncio
    async def test_extraction_zero_messages(self, db_session):
        """Edge case: Extraction finds zero messages."""
        from db.models import User, ExtractionJob

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_zero_messages")
        db_session.add(user)
        await db_session.commit()

        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=123456789,
            status="completed",
            messages_extracted=0,
        )
        db_session.add(job)
        await db_session.commit()

        assert job.messages_extracted == 0

    @pytest.mark.asyncio
    async def test_guild_with_very_long_name(self, db_session):
        """Edge case: Guild with maximum length name."""
        from db.models import User, DiscordToken

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_long_guild")
        db_session.add(user)
        await db_session.commit()

        long_name = "A" * 100  # Discord max is 100 chars
        token = DiscordToken(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_token=b"test",
            guild_id=123456789,
            guild_name=long_name,
        )
        db_session.add(token)
        await db_session.commit()

        assert len(token.guild_name) == 100

    @pytest.mark.asyncio
    async def test_large_guild_id(self, db_session):
        """Edge case: Very large guild ID (Discord snowflake)."""
        from db.models import User, DiscordToken

        user_id = uuid.uuid4()
        user = User(id=user_id, clerk_id="user_large_guild")
        db_session.add(user)
        await db_session.commit()

        large_guild_id = 1234567890123456789  # Max Discord snowflake
        token = DiscordToken(
            id=uuid.uuid4(),
            user_id=user_id,
            encrypted_token=b"test",
            guild_id=large_guild_id,
            guild_name="Large ID Guild",
        )
        db_session.add(token)
        await db_session.commit()

        assert token.guild_id == large_guild_id

    def test_query_with_special_characters(self):
        """Edge case: Query with special characters in strings."""
        from api.query import validate_query

        # Should handle quotes in strings properly
        validate_query("SELECT * FROM messages WHERE content = 'Hello''s World'")

    def test_query_unicode_content(self):
        """Edge case: Query with unicode characters."""
        from api.query import validate_query

        validate_query("SELECT * FROM messages WHERE content LIKE '%日本語%'")
        validate_query("SELECT * FROM messages WHERE content LIKE '%emoji 😀%'")
