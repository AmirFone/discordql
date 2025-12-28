"""
Edge case tests for mock Discord objects.

Validates that mock objects behave exactly like real discord.py objects.
"""
import pytest
import calendar
from datetime import datetime, timedelta, timezone

from tests.mocks import (
    MockUser,
    MockMember,
    MockMessage,
    MockChannel,
    MockGuild,
    MockReaction,
    MockEmoji,
    MockMessageReference,
    MockDiscordClient,
    snowflake_to_datetime,
    DISCORD_EPOCH,
    DiscordDataGenerator,
)


class TestMockUser:
    """Tests for MockUser edge cases."""

    def test_user_equality_by_id(self):
        """Two users with same ID should be equal."""
        user1 = MockUser(id=123, name="user1")
        user2 = MockUser(id=123, name="different_name")
        assert user1 == user2

    def test_user_inequality_different_id(self):
        """Users with different IDs should not be equal."""
        user1 = MockUser(id=123, name="same_name")
        user2 = MockUser(id=456, name="same_name")
        assert user1 != user2

    def test_user_hash_for_sets(self):
        """Users should be hashable for use in sets."""
        user1 = MockUser(id=123, name="user1")
        user2 = MockUser(id=123, name="user1")
        user3 = MockUser(id=456, name="user2")

        user_set = {user1, user2, user3}
        assert len(user_set) == 2  # user1 and user2 are same

    def test_display_name_fallback(self):
        """Display name should fallback to username if global_name is None."""
        user = MockUser(id=1, name="username", global_name=None)
        assert user.display_name == "username"

        user_with_global = MockUser(id=2, name="username", global_name="Display")
        assert user_with_global.display_name == "Display"

    def test_mention_format(self):
        """Mention should return proper Discord format."""
        user = MockUser(id=123456789, name="user")
        assert user.mention == "<@123456789>"

    def test_created_at_from_snowflake(self):
        """Created at should be derived from snowflake ID."""
        # Snowflake with known timestamp
        # 2023-01-01 00:00:00 UTC = 1672531200000 ms since Unix epoch
        # Discord epoch = 1420070400000 ms
        # Difference = 252460800000 ms = timestamp in snowflake
        # Snowflake = (252460800000 << 22) | 0
        known_timestamp = datetime(2023, 1, 1, 0, 0, 0)
        # Use calendar.timegm to treat naive datetime as UTC
        discord_ts = int(calendar.timegm(known_timestamp.timetuple()) * 1000) - DISCORD_EPOCH
        snowflake = discord_ts << 22

        user = MockUser(id=snowflake, name="test")
        # Allow 1 second tolerance for rounding
        assert abs((user.created_at - known_timestamp).total_seconds()) < 1

    def test_bot_flag(self):
        """Bot flag should be correctly set."""
        human = MockUser(id=1, name="human", bot=False)
        bot = MockUser(id=2, name="bot", bot=True)

        assert not human.bot
        assert bot.bot


class TestMockMember:
    """Tests for MockMember edge cases."""

    def test_member_inherits_user_properties(self):
        """Member should inherit all User properties."""
        member = MockMember(
            id=123,
            name="user",
            global_name="Global",
            nick="Nickname",
        )
        assert member.id == 123
        assert member.name == "user"
        assert member.global_name == "Global"

    def test_member_display_name_priority(self):
        """Member display name: nick > global_name > username."""
        # Nick takes priority
        member1 = MockMember(id=1, name="user", global_name="Global", nick="Nick")
        assert member1.display_name == "Nick"

        # Global name second
        member2 = MockMember(id=2, name="user", global_name="Global", nick=None)
        assert member2.display_name == "Global"

        # Username fallback
        member3 = MockMember(id=3, name="user", global_name=None, nick=None)
        assert member3.display_name == "user"


class TestMockEmoji:
    """Tests for MockEmoji edge cases."""

    def test_unicode_emoji(self):
        """Unicode emoji should have None id."""
        emoji = MockEmoji(id=None, name="👍")
        assert emoji.is_unicode_emoji
        assert not emoji.is_custom_emoji
        assert str(emoji) == "👍"

    def test_custom_emoji(self):
        """Custom emoji should have snowflake id."""
        emoji = MockEmoji(id=123456789, name="custom_emoji")
        assert emoji.is_custom_emoji
        assert not emoji.is_unicode_emoji
        assert str(emoji) == "<:custom_emoji:123456789>"

    def test_animated_custom_emoji(self):
        """Animated emoji should have 'a' prefix."""
        emoji = MockEmoji(id=123456789, name="animated", animated=True)
        assert str(emoji) == "<a:animated:123456789>"

    def test_emoji_equality(self):
        """Emoji equality based on id and name."""
        emoji1 = MockEmoji(id=123, name="test")
        emoji2 = MockEmoji(id=123, name="test")
        emoji3 = MockEmoji(id=123, name="different")

        assert emoji1 == emoji2
        assert emoji1 != emoji3

    def test_emoji_hash_for_sets(self):
        """Emojis should be hashable."""
        emoji1 = MockEmoji(id=None, name="👍")
        emoji2 = MockEmoji(id=None, name="👍")
        emoji3 = MockEmoji(id=None, name="👎")

        emoji_set = {emoji1, emoji2, emoji3}
        assert len(emoji_set) == 2


class TestMockMessage:
    """Tests for MockMessage edge cases."""

    def test_message_without_reference(self):
        """Message without reply reference."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockUser(id=1, name="user")

        msg = MockMessage(
            id=1,
            channel=channel,
            author=user,
            content="Hello",
            created_at=datetime.now(timezone.utc),
        )

        assert msg.reference is None
        assert msg.type == 0  # Default message type

    def test_message_reply(self):
        """Message that is a reply."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockUser(id=1, name="user")

        msg = MockMessage(
            id=2,
            channel=channel,
            author=user,
            content="Reply",
            created_at=datetime.now(timezone.utc),
            type=19,  # Reply type
            reference=MockMessageReference(message_id=1, channel_id=1, guild_id=1),
        )

        assert msg.reference is not None
        assert msg.reference.message_id == 1
        assert msg.type == 19

    def test_message_with_mentions(self):
        """Message with user mentions."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        author = MockUser(id=1, name="author")
        mentioned = MockUser(id=2, name="mentioned")

        msg = MockMessage(
            id=1,
            channel=channel,
            author=author,
            content="Hey @mentioned!",
            created_at=datetime.now(timezone.utc),
            mentions=[mentioned],
        )

        assert len(msg.mentions) == 1
        assert msg.mentions[0].id == 2

    def test_message_jump_url(self):
        """Jump URL should be correctly formatted."""
        guild = MockGuild(id=111, name="Guild", owner_id=1)
        channel = MockChannel(id=222, name="channel", guild=guild)
        user = MockUser(id=1, name="user")

        msg = MockMessage(
            id=333,
            channel=channel,
            author=user,
            content="Test",
            created_at=datetime.now(timezone.utc),
        )

        assert msg.jump_url == "https://discord.com/channels/111/222/333"

    def test_message_empty_content(self):
        """Message with empty content (e.g., image-only)."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockUser(id=1, name="user")

        msg = MockMessage(
            id=1,
            channel=channel,
            author=user,
            content="",
            created_at=datetime.now(timezone.utc),
        )

        assert msg.content == ""


class TestMockChannel:
    """Tests for MockChannel edge cases."""

    @pytest.mark.asyncio
    async def test_history_with_limit(self):
        """History should respect limit parameter."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockUser(id=1, name="user")

        # Add 10 messages
        for i in range(10):
            channel._messages.append(MockMessage(
                id=i,
                channel=channel,
                author=user,
                content=f"Message {i}",
                created_at=datetime.now(timezone.utc) - timedelta(hours=10-i),
            ))

        # Fetch with limit
        messages = [m async for m in channel.history(limit=5)]
        assert len(messages) == 5

    @pytest.mark.asyncio
    async def test_history_no_limit(self):
        """History with limit=None should return all messages."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockUser(id=1, name="user")

        for i in range(20):
            channel._messages.append(MockMessage(
                id=i,
                channel=channel,
                author=user,
                content=f"Message {i}",
                created_at=datetime.now(timezone.utc),
            ))

        messages = [m async for m in channel.history(limit=None)]
        assert len(messages) == 20

    @pytest.mark.asyncio
    async def test_history_after_filter(self):
        """History should filter messages after date."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockUser(id=1, name="user")

        now = datetime.now(timezone.utc)
        for i in range(10):
            channel._messages.append(MockMessage(
                id=i,
                channel=channel,
                author=user,
                content=f"Message {i}",
                created_at=now - timedelta(days=10-i),
            ))

        # Get messages from last 5 days
        cutoff = now - timedelta(days=5)
        messages = [m async for m in channel.history(after=cutoff, limit=None)]

        for msg in messages:
            assert msg.created_at > cutoff

    @pytest.mark.asyncio
    async def test_history_before_filter(self):
        """History should filter messages before date."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockUser(id=1, name="user")

        now = datetime.now(timezone.utc)
        for i in range(10):
            channel._messages.append(MockMessage(
                id=i,
                channel=channel,
                author=user,
                content=f"Message {i}",
                created_at=now - timedelta(days=10-i),
            ))

        cutoff = now - timedelta(days=5)
        messages = [m async for m in channel.history(before=cutoff, limit=None)]

        for msg in messages:
            assert msg.created_at < cutoff

    @pytest.mark.asyncio
    async def test_history_empty_channel(self):
        """History on empty channel should return empty."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)

        messages = [m async for m in channel.history()]
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_history_oldest_first(self):
        """History with oldest_first should reverse order."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        user = MockUser(id=1, name="user")

        now = datetime.now(timezone.utc)
        for i in range(5):
            channel._messages.append(MockMessage(
                id=i,
                channel=channel,
                author=user,
                content=f"Message {i}",
                created_at=now - timedelta(hours=5-i),
            ))

        # Default: newest first
        newest_first = [m async for m in channel.history(limit=None, oldest_first=False)]
        assert newest_first[0].created_at > newest_first[-1].created_at

        # oldest_first=True
        oldest_first = [m async for m in channel.history(limit=None, oldest_first=True)]
        assert oldest_first[0].created_at < oldest_first[-1].created_at


class TestMockReaction:
    """Tests for MockReaction edge cases."""

    @pytest.mark.asyncio
    async def test_reaction_users_iterator(self):
        """Reaction users() should return async iterator."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        author = MockUser(id=1, name="author")
        reactor1 = MockUser(id=2, name="reactor1")
        reactor2 = MockUser(id=3, name="reactor2")

        msg = MockMessage(
            id=1,
            channel=channel,
            author=author,
            content="React to me",
            created_at=datetime.now(timezone.utc),
        )

        reaction = MockReaction(
            message=msg,
            emoji=MockEmoji(id=None, name="👍"),
            count=2,
            _users=[reactor1, reactor2],
        )

        users = [u async for u in reaction.users()]
        assert len(users) == 2
        assert reactor1 in users
        assert reactor2 in users

    @pytest.mark.asyncio
    async def test_reaction_users_with_limit(self):
        """Reaction users() should respect limit."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        author = MockUser(id=1, name="author")
        msg = MockMessage(
            id=1,
            channel=channel,
            author=author,
            content="React to me",
            created_at=datetime.now(timezone.utc),
        )

        reactors = [MockUser(id=i, name=f"reactor{i}") for i in range(10)]
        reaction = MockReaction(
            message=msg,
            emoji=MockEmoji(id=None, name="👍"),
            count=10,
            _users=reactors,
        )

        users = [u async for u in reaction.users(limit=5)]
        assert len(users) == 5

    @pytest.mark.asyncio
    async def test_reaction_empty_users(self):
        """Reaction with no users."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=1, name="channel", guild=guild)
        author = MockUser(id=1, name="author")
        msg = MockMessage(
            id=1,
            channel=channel,
            author=author,
            content="React to me",
            created_at=datetime.now(timezone.utc),
        )

        reaction = MockReaction(
            message=msg,
            emoji=MockEmoji(id=None, name="👍"),
            count=0,
            _users=[],
        )

        users = [u async for u in reaction.users()]
        assert len(users) == 0


class TestMockGuild:
    """Tests for MockGuild edge cases."""

    @pytest.mark.asyncio
    async def test_fetch_members(self):
        """Fetch members should return all members."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        for i in range(10):
            guild._members.append(MockMember(id=i, name=f"member{i}", guild=guild))

        members = [m async for m in guild.fetch_members()]
        assert len(members) == 10

    @pytest.mark.asyncio
    async def test_fetch_members_with_limit(self):
        """Fetch members should respect limit."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        for i in range(10):
            guild._members.append(MockMember(id=i, name=f"member{i}", guild=guild))

        members = [m async for m in guild.fetch_members(limit=5)]
        assert len(members) == 5

    def test_get_member(self):
        """Get member by ID."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        member = MockMember(id=123, name="target", guild=guild)
        guild._members.append(member)
        guild._members.append(MockMember(id=456, name="other", guild=guild))

        found = guild.get_member(123)
        assert found is not None
        assert found.name == "target"

        not_found = guild.get_member(999)
        assert not_found is None

    def test_get_channel(self):
        """Get channel by ID."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        channel = MockChannel(id=123, name="target", guild=guild)
        guild._channels.append(channel)
        guild._channels.append(MockChannel(id=456, name="other", guild=guild))

        found = guild.get_channel(123)
        assert found is not None
        assert found.name == "target"

        not_found = guild.get_channel(999)
        assert not_found is None

    def test_text_channels_property(self):
        """Text channels should return all channels."""
        guild = MockGuild(id=1, name="Guild", owner_id=1)
        for i in range(5):
            guild._channels.append(MockChannel(id=i, name=f"channel{i}", guild=guild))

        assert len(guild.text_channels) == 5


class TestMockDiscordClient:
    """Tests for MockDiscordClient edge cases."""

    def test_get_guild_exists(self):
        """Get guild that exists."""
        guild = MockGuild(id=123, name="Test", owner_id=1)
        client = MockDiscordClient(guilds=[guild])

        found = client.get_guild(123)
        assert found is not None
        assert found.name == "Test"

    def test_get_guild_not_exists(self):
        """Get guild that doesn't exist."""
        client = MockDiscordClient(guilds=[])
        assert client.get_guild(123) is None

    def test_get_channel_across_guilds(self):
        """Get channel searches across all guilds."""
        guild1 = MockGuild(id=1, name="Guild1", owner_id=1)
        guild2 = MockGuild(id=2, name="Guild2", owner_id=1)

        channel1 = MockChannel(id=100, name="channel1", guild=guild1)
        channel2 = MockChannel(id=200, name="channel2", guild=guild2)

        guild1._channels.append(channel1)
        guild2._channels.append(channel2)

        client = MockDiscordClient(guilds=[guild1, guild2])

        found1 = client.get_channel(100)
        assert found1 is not None
        assert found1.name == "channel1"

        found2 = client.get_channel(200)
        assert found2 is not None
        assert found2.name == "channel2"

        not_found = client.get_channel(999)
        assert not_found is None

    @pytest.mark.asyncio
    async def test_client_ready_states(self):
        """Client ready/closed states."""
        client = MockDiscordClient()

        assert not client.is_ready
        assert not client.is_closed

        await client.wait_until_ready()
        assert client.is_ready

        await client.close()
        assert client.is_closed


class TestSnowflakeConversion:
    """Tests for snowflake ID conversion."""

    def test_known_snowflake(self):
        """Test conversion of known snowflake."""
        # Discord's first snowflake (approximately)
        # January 1, 2015 00:00:00 UTC
        first_snowflake = 0  # Timestamp bits are 0
        dt = snowflake_to_datetime(first_snowflake)

        # Should be close to Discord epoch
        expected = datetime(2015, 1, 1, 0, 0, 0)
        assert abs((dt - expected).total_seconds()) < 1

    def test_recent_snowflake(self):
        """Test conversion of recent snowflake."""
        # Create a snowflake for a known recent time
        known_time = datetime(2024, 6, 15, 12, 0, 0)
        # Use calendar.timegm to treat naive datetime as UTC
        timestamp_ms = int(calendar.timegm(known_time.timetuple()) * 1000) - DISCORD_EPOCH
        snowflake = timestamp_ms << 22

        converted = snowflake_to_datetime(snowflake)
        assert abs((converted - known_time).total_seconds()) < 1

    def test_snowflake_ordering(self):
        """Later snowflakes should have later timestamps."""
        older_snowflake = (100000000 << 22) | 1
        newer_snowflake = (200000000 << 22) | 1

        older_dt = snowflake_to_datetime(older_snowflake)
        newer_dt = snowflake_to_datetime(newer_snowflake)

        assert newer_dt > older_dt
