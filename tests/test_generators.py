"""
Edge case tests for the Discord data generator.

Validates realistic data generation patterns and edge cases.
"""
import pytest
from datetime import datetime, timedelta, timezone
from collections import Counter

from tests.mocks import (
    DiscordDataGenerator,
    MockGuild,
    MockChannel,
    create_test_server,
)
from tests.mocks.generators import (
    ACTIVITY_PATTERNS,
    REPLY_PROBABILITY,
    REACTION_PROBABILITY,
    MENTION_PROBABILITY,
    COMMON_EMOJIS,
)


class TestGeneratorSeeding:
    """Tests for reproducible random generation."""

    def test_same_seed_same_output(self):
        """Same seed should produce identical output."""
        gen1 = DiscordDataGenerator(seed=12345)
        gen2 = DiscordDataGenerator(seed=12345)

        users1 = gen1.generate_users(10)
        users2 = gen2.generate_users(10)

        for u1, u2 in zip(users1, users2):
            assert u1.id == u2.id
            assert u1.name == u2.name

    def test_different_seed_different_output(self):
        """Different seeds should produce different output."""
        gen1 = DiscordDataGenerator(seed=12345)
        gen2 = DiscordDataGenerator(seed=54321)

        users1 = gen1.generate_users(10)
        users2 = gen2.generate_users(10)

        # At least some should be different
        different = sum(1 for u1, u2 in zip(users1, users2) if u1.name != u2.name)
        assert different > 0

    def test_no_seed_varies(self):
        """Without seed, output should vary (statistically)."""
        gen1 = DiscordDataGenerator(seed=None)
        gen2 = DiscordDataGenerator(seed=None)

        # Generate with time gap to ensure different random state
        users1 = gen1.generate_users(100)
        users2 = gen2.generate_users(100)

        # Names should mostly differ
        same_names = sum(1 for u1, u2 in zip(users1, users2) if u1.name == u2.name)
        assert same_names < 50  # Most should differ


class TestSnowflakeGeneration:
    """Tests for Discord snowflake ID generation."""

    def test_snowflakes_are_unique(self):
        """Generated snowflakes should all be unique."""
        gen = DiscordDataGenerator(seed=42)
        snowflakes = [gen._next_snowflake() for _ in range(1000)]
        assert len(snowflakes) == len(set(snowflakes))

    def test_snowflakes_are_increasing(self):
        """Snowflakes should be monotonically increasing."""
        gen = DiscordDataGenerator(seed=42)
        prev = 0
        for _ in range(100):
            current = gen._next_snowflake()
            assert current > prev
            prev = current

    def test_snowflake_with_timestamp(self):
        """Snowflake should encode provided timestamp."""
        gen = DiscordDataGenerator(seed=42)
        known_time = datetime(2024, 1, 15, 12, 0, 0)
        snowflake = gen._next_snowflake(created_at=known_time)

        # Extract timestamp from snowflake
        from tests.mocks import snowflake_to_datetime
        extracted = snowflake_to_datetime(snowflake)

        # Should be within 1 second
        assert abs((extracted - known_time).total_seconds()) < 1


class TestUserGeneration:
    """Tests for user generation edge cases."""

    def test_generates_correct_count(self):
        """Should generate exact number of users requested."""
        gen = DiscordDataGenerator(seed=42)
        for count in [1, 5, 10, 100]:
            users = gen.generate_users(count)
            assert len(users) == count

    def test_zero_users(self):
        """Should handle zero users gracefully."""
        gen = DiscordDataGenerator(seed=42)
        users = gen.generate_users(0)
        assert len(users) == 0

    def test_activity_levels_assigned(self):
        """All users should have activity levels."""
        gen = DiscordDataGenerator(seed=42)
        users = gen.generate_users(100)

        for user in users:
            assert hasattr(user, '_activity_level')
            assert user._activity_level in ACTIVITY_PATTERNS.keys()

    def test_activity_distribution_approximate(self):
        """Activity distribution should roughly match expected."""
        gen = DiscordDataGenerator(seed=42)
        users = gen.generate_users(1000)

        activity_counts = Counter(u._activity_level for u in users)

        # Check distribution is roughly correct (within 10% tolerance)
        for level, expected_pct in ACTIVITY_PATTERNS.items():
            actual_pct = activity_counts[level] / 1000
            assert abs(actual_pct - expected_pct) < 0.1, \
                f"{level}: expected ~{expected_pct}, got {actual_pct}"

    def test_bot_percentage(self):
        """About 2% of users should be bots."""
        gen = DiscordDataGenerator(seed=42)
        users = gen.generate_users(1000)

        bot_count = sum(1 for u in users if u.bot)
        bot_pct = bot_count / 1000

        # Should be around 2% (±2%)
        assert 0.0 < bot_pct < 0.05

    def test_unique_user_ids(self):
        """All user IDs should be unique."""
        gen = DiscordDataGenerator(seed=42)
        users = gen.generate_users(100)

        ids = [u.id for u in users]
        assert len(ids) == len(set(ids))


class TestMessageGeneration:
    """Tests for message generation edge cases."""

    def test_generates_correct_count(self):
        """Should generate exact number of messages."""
        gen = DiscordDataGenerator(seed=42)
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="general", guild=guild)
        users = gen.generate_users(10)

        for count in [1, 10, 50, 100]:
            messages = gen.generate_messages(
                channel=channel,
                users=users,
                count=count,
                start_date=datetime.now(timezone.utc) - timedelta(days=7),
                end_date=datetime.now(timezone.utc),
            )
            assert len(messages) == count

    def test_zero_messages(self):
        """Should handle zero messages."""
        gen = DiscordDataGenerator(seed=42)
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="general", guild=guild)
        users = gen.generate_users(5)

        messages = gen.generate_messages(
            channel=channel,
            users=users,
            count=0,
            start_date=datetime.now(timezone.utc) - timedelta(days=1),
            end_date=datetime.now(timezone.utc),
        )
        assert len(messages) == 0

    def test_messages_sorted_by_time(self):
        """Messages should be sorted by creation time."""
        gen = DiscordDataGenerator(seed=42)
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="general", guild=guild)
        users = gen.generate_users(10)

        messages = gen.generate_messages(
            channel=channel,
            users=users,
            count=100,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc),
        )

        for i in range(len(messages) - 1):
            assert messages[i].created_at <= messages[i + 1].created_at

    def test_messages_within_date_range(self):
        """All messages should be within specified date range."""
        gen = DiscordDataGenerator(seed=42)
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="general", guild=guild)
        users = gen.generate_users(10)

        start = datetime.now(timezone.utc) - timedelta(days=3)
        end = datetime.now(timezone.utc)

        messages = gen.generate_messages(
            channel=channel,
            users=users,
            count=50,
            start_date=start,
            end_date=end,
        )

        for msg in messages:
            # Allow small tolerance for timezone issues
            assert msg.created_at >= start - timedelta(seconds=1)
            assert msg.created_at <= end + timedelta(seconds=1)

    def test_reply_probability_approximate(self):
        """About 35% of messages should be replies."""
        gen = DiscordDataGenerator(seed=42)
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="general", guild=guild)
        users = gen.generate_users(20)

        messages = gen.generate_messages(
            channel=channel,
            users=users,
            count=1000,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc),
        )

        reply_count = sum(1 for m in messages if m.reference is not None)
        reply_pct = reply_count / 1000

        # Should be around 35% (±10% tolerance)
        assert abs(reply_pct - REPLY_PROBABILITY) < 0.1

    def test_replies_reference_earlier_messages(self):
        """Replies should reference messages that come before them."""
        gen = DiscordDataGenerator(seed=42)
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="general", guild=guild)
        users = gen.generate_users(10)

        messages = gen.generate_messages(
            channel=channel,
            users=users,
            count=100,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc),
        )

        message_ids = {m.id for m in messages}

        for msg in messages:
            if msg.reference is not None:
                # Reference should be to a message that exists
                assert msg.reference.message_id in message_ids or \
                       msg.reference.message_id < msg.id

    def test_mention_probability_approximate(self):
        """About 15% of messages should have mentions."""
        gen = DiscordDataGenerator(seed=42)
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="general", guild=guild)
        users = gen.generate_users(20)

        messages = gen.generate_messages(
            channel=channel,
            users=users,
            count=1000,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc),
        )

        mention_count = sum(1 for m in messages if len(m.mentions) > 0)
        mention_pct = mention_count / 1000

        # Should be around 15% (±10% tolerance)
        assert abs(mention_pct - MENTION_PROBABILITY) < 0.1

    def test_unique_message_ids(self):
        """All message IDs should be unique."""
        gen = DiscordDataGenerator(seed=42)
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="general", guild=guild)
        users = gen.generate_users(10)

        messages = gen.generate_messages(
            channel=channel,
            users=users,
            count=500,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc),
        )

        ids = [m.id for m in messages]
        assert len(ids) == len(set(ids))


class TestReactionGeneration:
    """Tests for reaction generation edge cases."""

    def test_reaction_probability_approximate(self):
        """About 20% of messages should have reactions."""
        gen = DiscordDataGenerator(seed=42)
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="general", guild=guild)
        users = gen.generate_users(30)

        messages = gen.generate_messages(
            channel=channel,
            users=users,
            count=500,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc),
        )

        reaction_count = sum(1 for m in messages if len(m.reactions) > 0)
        reaction_pct = reaction_count / 500

        # Should be around 20% (±10% tolerance)
        assert abs(reaction_pct - REACTION_PROBABILITY) < 0.1

    def test_reactions_use_common_emojis(self):
        """Reactions should use emojis from the common set."""
        gen = DiscordDataGenerator(seed=42)
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="general", guild=guild)
        users = gen.generate_users(20)

        messages = gen.generate_messages(
            channel=channel,
            users=users,
            count=200,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc),
        )

        common_emoji_names = {e[0] for e in COMMON_EMOJIS}

        for msg in messages:
            for reaction in msg.reactions:
                assert reaction.emoji.name in common_emoji_names

    def test_reaction_user_count_matches(self):
        """Reaction count should match number of users."""
        gen = DiscordDataGenerator(seed=42)
        guild = MockGuild(id=1, name="Test", owner_id=1)
        channel = MockChannel(id=1, name="general", guild=guild)
        users = gen.generate_users(30)

        messages = gen.generate_messages(
            channel=channel,
            users=users,
            count=100,
            start_date=datetime.now(timezone.utc) - timedelta(days=7),
            end_date=datetime.now(timezone.utc),
        )

        for msg in messages:
            for reaction in msg.reactions:
                assert reaction.count == len(reaction._users)


class TestGuildGeneration:
    """Tests for complete guild generation."""

    def test_generate_guild_all_components(self):
        """Guild should have all expected components."""
        gen = DiscordDataGenerator(seed=42)
        guild = gen.generate_guild(
            name="Test Guild",
            user_count=10,
            channel_count=3,
            messages_per_channel=20,
            days=7,
        )

        assert guild.name == "Test Guild"
        assert len(guild._members) == 10
        assert len(guild._channels) == 3
        assert guild.member_count == 10

        # Each channel should have messages
        for channel in guild._channels:
            assert len(channel._messages) > 0

    def test_guild_owner_is_first_member(self):
        """Guild owner should be first generated user."""
        gen = DiscordDataGenerator(seed=42)
        guild = gen.generate_guild(user_count=10)

        assert guild.owner_id == guild._members[0].id

    def test_members_belong_to_guild(self):
        """All members should reference the guild."""
        gen = DiscordDataGenerator(seed=42)
        guild = gen.generate_guild(user_count=10)

        for member in guild._members:
            assert member.guild == guild

    def test_channels_belong_to_guild(self):
        """All channels should reference the guild."""
        gen = DiscordDataGenerator(seed=42)
        guild = gen.generate_guild(channel_count=5)

        for channel in guild._channels:
            assert channel.guild == guild

    def test_messages_reference_correct_channel(self):
        """Messages should reference their containing channel."""
        gen = DiscordDataGenerator(seed=42)
        guild = gen.generate_guild(
            channel_count=3,
            messages_per_channel=10,
        )

        for channel in guild._channels:
            for message in channel._messages:
                assert message.channel == channel


class TestCreateTestServer:
    """Tests for the convenience factory function."""

    def test_creates_valid_guild(self):
        """Should create a valid guild with all components."""
        guild = create_test_server(
            user_count=20,
            channel_count=4,
            messages_per_channel=30,
            days=5,
            seed=42,
        )

        assert isinstance(guild, MockGuild)
        assert len(guild._members) == 20
        assert len(guild._channels) == 4

    def test_reproducible_with_seed(self):
        """Same seed should produce servers with same structure."""
        guild1 = create_test_server(seed=12345)
        guild2 = create_test_server(seed=12345)

        # Names and counts should match (IDs differ due to real-time timestamps)
        assert guild1.name == guild2.name
        assert len(guild1._members) == len(guild2._members)
        assert len(guild1._channels) == len(guild2._channels)

        # Member names should match in same order
        for m1, m2 in zip(guild1._members, guild2._members):
            assert m1.name == m2.name

        # Channel names should match
        for c1, c2 in zip(guild1._channels, guild2._channels):
            assert c1.name == c2.name

    def test_default_parameters(self):
        """Default parameters should work."""
        guild = create_test_server()

        # Defaults from function signature
        assert len(guild._members) == 50
        assert len(guild._channels) == 5
