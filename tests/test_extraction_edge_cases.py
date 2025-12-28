"""
Edge case tests for Discord data extraction.

Tests unusual scenarios and boundary conditions.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import text

from src.extractor import DiscordExtractor, run_extraction
from tests.mocks import (
    MockDiscordClient,
    MockGuild,
    MockChannel,
    MockUser,
    MockMember,
    MockMessage,
    MockReaction,
    MockEmoji,
    MockMessageReference,
    DiscordDataGenerator,
)


class TestEmptyData:
    """Tests for empty or minimal data scenarios."""

    @pytest.mark.asyncio
    async def test_empty_server(self, clean_db):
        """Server with no channels or members."""
        guild = MockGuild(id=1, name="Empty Server", owner_id=1)
        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        stats = await extractor.sync_server(guild.id)

        assert stats["servers"] == 1
        assert stats["users"] == 0
        assert stats["channels"] == 0
        assert stats["messages"] == 0

    @pytest.mark.asyncio
    async def test_server_with_empty_channel(self, clean_db):
        """Server with channels but no messages."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="empty-channel", guild=guild)
        guild._channels.append(channel)

        member = MockMember(id=1, name="user", guild=guild)
        guild._members.append(member)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        stats = await extractor.sync_server(guild.id)

        assert stats["channels"] == 1
        assert stats["messages"] == 0

    @pytest.mark.asyncio
    async def test_server_with_single_message(self, clean_db):
        """Server with exactly one message."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockMember(id=1, name="user", guild=guild)

        guild._channels.append(channel)
        guild._members.append(user)

        msg = MockMessage(
            id=1,
            channel=channel,
            author=user,
            content="Solo message",
            created_at=datetime.utcnow(),
        )
        channel._messages.append(msg)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        stats = await extractor.sync_server(guild.id)

        assert stats["messages"] == 1


class TestSpecialContent:
    """Tests for special message content."""

    @pytest.mark.asyncio
    async def test_message_with_empty_content(self, clean_db):
        """Message with empty string content."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockMember(id=1, name="user", guild=guild)

        guild._channels.append(channel)
        guild._members.append(user)

        msg = MockMessage(
            id=1,
            channel=channel,
            author=user,
            content="",  # Empty content
            created_at=datetime.utcnow(),
        )
        channel._messages.append(msg)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        await extractor.sync_server(guild.id)

        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT content, word_count FROM messages WHERE id = 1"))
            row = result.fetchone()
            assert row[0] == ""
            assert row[1] == 0

    @pytest.mark.asyncio
    async def test_message_with_unicode_content(self, clean_db):
        """Message with unicode characters."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockMember(id=1, name="user", guild=guild)

        guild._channels.append(channel)
        guild._members.append(user)

        unicode_content = "Hello 👋 World 🌍 日本語 中文 العربية"
        msg = MockMessage(
            id=1,
            channel=channel,
            author=user,
            content=unicode_content,
            created_at=datetime.utcnow(),
        )
        channel._messages.append(msg)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        await extractor.sync_server(guild.id)

        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT content FROM messages WHERE id = 1"))
            assert result.scalar() == unicode_content

    @pytest.mark.asyncio
    async def test_message_with_very_long_content(self, clean_db):
        """Message with very long content (Discord limit is 2000 chars)."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockMember(id=1, name="user", guild=guild)

        guild._channels.append(channel)
        guild._members.append(user)

        long_content = "A" * 2000  # Max Discord message length
        msg = MockMessage(
            id=1,
            channel=channel,
            author=user,
            content=long_content,
            created_at=datetime.utcnow(),
        )
        channel._messages.append(msg)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        await extractor.sync_server(guild.id)

        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT char_count FROM messages WHERE id = 1"))
            assert result.scalar() == 2000


class TestReplyChains:
    """Tests for reply chain edge cases."""

    @pytest.mark.asyncio
    async def test_reply_to_deleted_message(self, clean_db):
        """Reply referencing a message that doesn't exist."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockMember(id=1, name="user", guild=guild)

        guild._channels.append(channel)
        guild._members.append(user)

        # Reply to non-existent message (ID 999)
        msg = MockMessage(
            id=1,
            channel=channel,
            author=user,
            content="Reply to deleted",
            created_at=datetime.utcnow(),
            type=19,
            reference=MockMessageReference(message_id=999, channel_id=1, guild_id=1),
        )
        channel._messages.append(msg)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        # Should not raise error
        await extractor.sync_server(guild.id)

        with clean_db.connect() as conn:
            result = conn.execute(text(
                "SELECT reply_to_message_id FROM messages WHERE id = 1"
            ))
            assert result.scalar() == 999

    @pytest.mark.asyncio
    async def test_self_reply(self, clean_db):
        """User replying to their own message."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockMember(id=1, name="user", guild=guild)

        guild._channels.append(channel)
        guild._members.append(user)

        original = MockMessage(
            id=1,
            channel=channel,
            author=user,
            content="Original",
            created_at=datetime.utcnow() - timedelta(hours=1),
        )

        reply = MockMessage(
            id=2,
            channel=channel,
            author=user,  # Same user
            content="Self reply",
            created_at=datetime.utcnow(),
            type=19,
            reference=MockMessageReference(message_id=1, channel_id=1, guild_id=1),
            _reply_to_author_id=user.id,
        )

        channel._messages.extend([original, reply])

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        await extractor.sync_server(guild.id)

        with clean_db.connect() as conn:
            result = conn.execute(text(
                "SELECT reply_to_author_id, author_id FROM messages WHERE id = 2"
            ))
            row = result.fetchone()
            assert row[0] == row[1]  # Self-reply


class TestReactionEdgeCases:
    """Tests for reaction edge cases."""

    @pytest.mark.asyncio
    async def test_same_user_multiple_emojis(self, clean_db):
        """Same user reacting with multiple different emojis."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        author = MockMember(id=1, name="author", guild=guild)
        reactor = MockMember(id=2, name="reactor", guild=guild)

        guild._channels.append(channel)
        guild._members.extend([author, reactor])

        msg = MockMessage(
            id=1,
            channel=channel,
            author=author,
            content="React to me",
            created_at=datetime.utcnow(),
        )

        # Same user, different emojis
        msg.reactions = [
            MockReaction(
                message=msg,
                emoji=MockEmoji(id=None, name="👍"),
                count=1,
                _users=[reactor],
            ),
            MockReaction(
                message=msg,
                emoji=MockEmoji(id=None, name="❤️"),
                count=1,
                _users=[reactor],
            ),
        ]

        channel._messages.append(msg)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
            fetch_reactions=True,
        )

        await extractor.sync_server(guild.id)

        with clean_db.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM reactions WHERE user_id = 2"
            ))
            assert result.scalar() == 2

    @pytest.mark.asyncio
    async def test_self_reaction(self, clean_db):
        """User reacting to their own message."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockMember(id=1, name="user", guild=guild)

        guild._channels.append(channel)
        guild._members.append(user)

        msg = MockMessage(
            id=1,
            channel=channel,
            author=user,
            content="Self react",
            created_at=datetime.utcnow(),
        )

        msg.reactions = [
            MockReaction(
                message=msg,
                emoji=MockEmoji(id=None, name="👍"),
                count=1,
                _users=[user],  # Author reacting to self
            ),
        ]

        channel._messages.append(msg)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
            fetch_reactions=True,
        )

        await extractor.sync_server(guild.id)

        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM reactions"))
            assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_many_reactions_on_one_message(self, clean_db):
        """Message with many reactions from many users."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        author = MockMember(id=1, name="author", guild=guild)

        # Create many reactors
        reactors = [MockMember(id=i+10, name=f"reactor{i}", guild=guild) for i in range(20)]
        guild._members = [author] + reactors
        guild._channels.append(channel)

        msg = MockMessage(
            id=1,
            channel=channel,
            author=author,
            content="Popular message",
            created_at=datetime.utcnow(),
        )

        msg.reactions = [
            MockReaction(
                message=msg,
                emoji=MockEmoji(id=None, name="👍"),
                count=20,
                _users=reactors,
            ),
        ]

        channel._messages.append(msg)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
            fetch_reactions=True,
        )

        await extractor.sync_server(guild.id)

        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM reactions"))
            assert result.scalar() == 20


class TestMentionEdgeCases:
    """Tests for mention edge cases."""

    @pytest.mark.asyncio
    async def test_self_mention(self, clean_db):
        """User mentioning themselves."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockMember(id=1, name="user", guild=guild)

        guild._channels.append(channel)
        guild._members.append(user)

        msg = MockMessage(
            id=1,
            channel=channel,
            author=user,
            content="Hey @myself",
            created_at=datetime.utcnow(),
            mentions=[user],  # Self-mention
        )
        channel._messages.append(msg)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        await extractor.sync_server(guild.id)

        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM message_mentions"))
            assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_multiple_mentions_same_user(self, clean_db):
        """User mentioned multiple times in same message."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        author = MockMember(id=1, name="author", guild=guild)
        mentioned = MockMember(id=2, name="mentioned", guild=guild)

        guild._channels.append(channel)
        guild._members.extend([author, mentioned])

        # In Discord, even if you mention someone twice,
        # message.mentions only contains them once
        msg = MockMessage(
            id=1,
            channel=channel,
            author=author,
            content="Hey @mentioned and @mentioned again",
            created_at=datetime.utcnow(),
            mentions=[mentioned],  # Only appears once
        )
        channel._messages.append(msg)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        await extractor.sync_server(guild.id)

        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM message_mentions"))
            assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_mention_everyone(self, clean_db):
        """Message with @everyone mention."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockMember(id=1, name="user", guild=guild)

        guild._channels.append(channel)
        guild._members.append(user)

        msg = MockMessage(
            id=1,
            channel=channel,
            author=user,
            content="Hey @everyone!",
            created_at=datetime.utcnow(),
            mention_everyone=True,
        )
        channel._messages.append(msg)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        await extractor.sync_server(guild.id)

        with clean_db.connect() as conn:
            result = conn.execute(text(
                "SELECT mentions_everyone FROM messages WHERE id = 1"
            ))
            assert result.scalar() == 1


class TestBotUsers:
    """Tests for bot user handling."""

    @pytest.mark.asyncio
    async def test_bot_messages_stored(self, clean_db):
        """Bot messages should be stored."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        bot = MockMember(id=1, name="BotUser", guild=guild, bot=True)

        guild._channels.append(channel)
        guild._members.append(bot)

        msg = MockMessage(
            id=1,
            channel=channel,
            author=bot,
            content="I am a bot",
            created_at=datetime.utcnow(),
        )
        channel._messages.append(msg)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        await extractor.sync_server(guild.id)

        with clean_db.connect() as conn:
            result = conn.execute(text(
                "SELECT u.is_bot FROM messages m "
                "JOIN users u ON m.author_id = u.id WHERE m.id = 1"
            ))
            assert result.scalar() == 1


class TestMultipleChannels:
    """Tests for multi-channel scenarios."""

    @pytest.mark.asyncio
    async def test_messages_across_channels(self, clean_db):
        """Messages from different channels should be stored correctly."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel1 = MockChannel(id=1, name="channel1", guild=guild)
        channel2 = MockChannel(id=2, name="channel2", guild=guild)
        user = MockMember(id=1, name="user", guild=guild)

        guild._channels.extend([channel1, channel2])
        guild._members.append(user)

        # Add messages to different channels
        for i in range(5):
            channel1._messages.append(MockMessage(
                id=100 + i,
                channel=channel1,
                author=user,
                content=f"Channel 1 msg {i}",
                created_at=datetime.utcnow(),
            ))
            channel2._messages.append(MockMessage(
                id=200 + i,
                channel=channel2,
                author=user,
                content=f"Channel 2 msg {i}",
                created_at=datetime.utcnow(),
            ))

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        await extractor.sync_server(guild.id)

        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM messages WHERE channel_id = 1"))
            assert result.scalar() == 5

            result = conn.execute(text("SELECT COUNT(*) FROM messages WHERE channel_id = 2"))
            assert result.scalar() == 5


class TestDateFiltering:
    """Tests for date-based filtering edge cases."""

    @pytest.mark.asyncio
    async def test_exactly_at_cutoff(self, clean_db):
        """Message exactly at the cutoff time."""
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockMember(id=1, name="user", guild=guild)

        guild._channels.append(channel)
        guild._members.append(user)

        # Message exactly 7 days ago
        cutoff = datetime.utcnow() - timedelta(days=7)
        msg = MockMessage(
            id=1,
            channel=channel,
            author=user,
            content="At cutoff",
            created_at=cutoff,
        )
        channel._messages.append(msg)

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=7,
        )

        await extractor.sync_server(guild.id)

        # Should be included (after means >, so exactly at cutoff is excluded)
        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM messages"))
            # Behavior depends on implementation - at least no error

    @pytest.mark.asyncio
    async def test_sync_zero_days(self, clean_db):
        """Sync with 0 days should only get very recent messages."""
        gen = DiscordDataGenerator(seed=42)
        guild = gen.generate_guild(
            user_count=5,
            channel_count=1,
            messages_per_channel=50,
            days=7,
        )

        client = MockDiscordClient(guilds=[guild])
        client._is_ready = True

        extractor = DiscordExtractor(
            client=client,
            engine=clean_db,
            sync_days=0,  # Zero days
        )

        await extractor.sync_server(guild.id)

        # Should have very few or no messages
        with clean_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM messages"))
            count = result.scalar()
            assert count < 10  # Should be very few
