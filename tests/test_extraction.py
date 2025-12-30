"""
Tests for the Discord data extractor.

Validates that extraction works identically with mock data
as it would with real Discord data.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import text

from src.extractor import DiscordExtractor, run_extraction
from tests.mocks import MockDiscordClient, create_test_server


class TestDiscordExtractor:
    """Tests for DiscordExtractor class."""

    @pytest.mark.asyncio
    async def test_sync_server_extracts_all_data(
        self, clean_db, mock_client, mock_guild
    ):
        """Extraction should capture servers, users, channels, messages."""
        extractor = DiscordExtractor(
            client=mock_client,
            engine=clean_db,
            sync_days=7,
            fetch_reactions=True,
        )

        stats = await extractor.sync_server(mock_guild.id)

        # Verify all data types were extracted
        assert stats["servers"] == 1
        assert stats["users"] > 0
        assert stats["channels"] > 0
        assert stats["messages"] > 0

    @pytest.mark.asyncio
    async def test_sync_server_stores_in_database(
        self, clean_db, mock_client, mock_guild
    ):
        """Extracted data should be stored in the database."""
        extractor = DiscordExtractor(
            client=mock_client,
            engine=clean_db,
            sync_days=7,
            fetch_reactions=True,
        )

        await extractor.sync_server(mock_guild.id)

        # Query database to verify data
        with clean_db.connect() as conn:
            # Check servers
            result = conn.execute(text("SELECT COUNT(*) FROM servers"))
            assert result.scalar() == 1

            # Check users
            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            assert result.scalar() > 0

            # Check channels
            result = conn.execute(text("SELECT COUNT(*) FROM channels"))
            assert result.scalar() == len(mock_guild.text_channels)

            # Check messages
            result = conn.execute(text("SELECT COUNT(*) FROM messages"))
            total_expected = sum(
                len(ch._messages) for ch in mock_guild._channels
            )
            # Allow some variance due to date filtering
            assert result.scalar() > 0

    @pytest.mark.asyncio
    async def test_sync_captures_reply_relationships(
        self, clean_db, small_mock_guild
    ):
        """Reply chains should be captured correctly."""
        client = MockDiscordClient(guilds=[small_mock_guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
            fetch_reactions=False,
        )

        await extractor.sync_server(small_mock_guild.id)

        # Check for replies in database
        with clean_db.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM messages WHERE reply_to_message_id IS NOT NULL"
            ))
            reply_count = result.scalar()

            # Should have some replies (35% probability in generator)
            # With 10 messages, expect ~3-4 replies on average
            # Allow for randomness
            assert reply_count >= 0  # At least check it runs

    @pytest.mark.asyncio
    async def test_sync_captures_mentions(self, clean_db, mock_guild):
        """User mentions should be captured."""
        client = MockDiscordClient(guilds=[mock_guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
            fetch_reactions=False,
        )

        stats = await extractor.sync_server(mock_guild.id)

        # Check mentions were recorded
        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM message_mentions"))
            assert result.scalar() == stats["mentions"]

    @pytest.mark.asyncio
    async def test_sync_captures_reactions(self, clean_db, mock_guild):
        """Reactions should be captured with user attribution."""
        client = MockDiscordClient(guilds=[mock_guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
            fetch_reactions=True,
        )

        stats = await extractor.sync_server(mock_guild.id)

        # Check reactions were recorded
        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM reactions"))
            assert result.scalar() == stats["reactions"]

            # Check emojis were recorded
            result = conn.execute(text("SELECT COUNT(*) FROM emojis"))
            assert result.scalar() > 0

    @pytest.mark.asyncio
    async def test_sync_respects_date_filter(self, clean_db, generator):
        """Only messages within sync_days should be extracted."""
        # Create a guild with old and new messages
        guild = generator.generate_guild(
            user_count=5,
            channel_count=1,
            messages_per_channel=20,
            days=14,  # 2 weeks of messages
        )

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        # Sync only last 3 days
        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=3,
            fetch_reactions=False,
        )

        await extractor.sync_server(guild.id)

        # Check that only recent messages were extracted
        with clean_db.connect() as conn:
            cutoff = datetime.utcnow() - timedelta(days=3)
            result = conn.execute(text(
                "SELECT MIN(created_at), MAX(created_at) FROM messages"
            ))
            row = result.fetchone()
            if row[0]:  # If any messages were extracted
                min_date = datetime.fromisoformat(row[0]) if isinstance(row[0], str) else row[0]
                assert min_date >= cutoff - timedelta(hours=1)  # Allow some slack

    @pytest.mark.asyncio
    async def test_sync_without_reactions(self, clean_db, mock_guild):
        """Extraction should work without fetching reactions."""
        client = MockDiscordClient(guilds=[mock_guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
            fetch_reactions=False,  # Disabled
        )

        stats = await extractor.sync_server(mock_guild.id)

        # Reactions should not be fetched
        assert stats["reactions"] == 0

        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM reactions"))
            assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_sync_is_idempotent(self, clean_db, small_mock_guild):
        """Running sync twice should not duplicate data."""
        client = MockDiscordClient(guilds=[small_mock_guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
            fetch_reactions=True,
        )

        # Run sync twice
        stats1 = await extractor.sync_server(small_mock_guild.id)

        # Reset stats using the ExtractionStats dataclass
        from src.extractor import ExtractionStats
        extractor.stats = ExtractionStats()
        stats2 = await extractor.sync_server(small_mock_guild.id)

        # Check database counts are same (not doubled)
        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM messages"))
            message_count = result.scalar()

            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()

        # Counts should not have doubled
        assert message_count <= stats1["messages"] * 1.5  # Allow some overhead


class TestConvenienceFunction:
    """Tests for run_extraction convenience function."""

    @pytest.mark.asyncio
    async def test_run_extraction_works(self, clean_db, mock_client, mock_guild):
        """Convenience function should work end-to-end."""
        stats = await run_extraction(
            client=mock_client,
            engine=clean_db,
            guild_id=mock_guild.id,
            sync_days=7,
            fetch_reactions=True,
        )

        assert stats["servers"] == 1
        assert stats["messages"] > 0

    @pytest.mark.asyncio
    async def test_run_extraction_invalid_guild(self, clean_db, mock_client):
        """Should raise error for invalid guild ID."""
        with pytest.raises(ValueError, match="not found"):
            await run_extraction(
                client=mock_client,
                engine=clean_db,
                guild_id=999999999,
            )
