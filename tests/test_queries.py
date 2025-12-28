"""
Edge case tests for database query functions.

Tests upsert, insert, and data handling edge cases.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.db.queries import (
    upsert_server,
    upsert_user,
    upsert_server_member,
    upsert_channel,
    insert_message,
    insert_mention,
    upsert_emoji,
    insert_reaction,
)


class TestUpsertServer:
    """Tests for server upsert functionality."""

    def test_insert_new_server(self, db_session):
        """Should insert a new server."""
        server = upsert_server(
            db_session,
            server_id=123456789,
            name="Test Server",
            owner_id=111,
            member_count=100,
        )
        db_session.commit()

        assert server is not None
        assert server.id == 123456789
        assert server.name == "Test Server"
        assert server.owner_id == 111
        assert server.member_count == 100

    def test_update_existing_server(self, db_session):
        """Should update existing server on conflict."""
        # Insert first
        upsert_server(
            db_session,
            server_id=100,
            name="Original Name",
            member_count=50,
        )
        db_session.commit()

        # Update
        server = upsert_server(
            db_session,
            server_id=100,
            name="Updated Name",
            member_count=100,
        )
        db_session.commit()

        assert server.name == "Updated Name"
        assert server.member_count == 100

    def test_server_with_null_owner(self, db_session):
        """Server can have null owner."""
        server = upsert_server(
            db_session,
            server_id=200,
            name="Orphan Server",
            owner_id=None,
        )
        db_session.commit()

        assert server.owner_id is None

    def test_server_with_unicode_name(self, db_session):
        """Server can have unicode name."""
        server = upsert_server(
            db_session,
            server_id=300,
            name="日本語サーバー 🎮",
        )
        db_session.commit()

        assert server.name == "日本語サーバー 🎮"

    def test_server_with_very_long_name(self, db_session):
        """Server with maximum length name."""
        long_name = "A" * 100
        server = upsert_server(
            db_session,
            server_id=400,
            name=long_name,
        )
        db_session.commit()

        assert server.name == long_name


class TestUpsertUser:
    """Tests for user upsert functionality."""

    def test_insert_new_user(self, db_session):
        """Should insert a new user."""
        user = upsert_user(
            db_session,
            user_id=111222333,
            username="testuser",
            discriminator="1234",
            global_name="Test User",
        )
        db_session.commit()

        assert user.id == 111222333
        assert user.username == "testuser"
        assert user.global_name == "Test User"

    def test_update_existing_user(self, db_session):
        """Should update username on conflict."""
        upsert_user(
            db_session,
            user_id=500,
            username="old_name",
        )
        db_session.commit()

        user = upsert_user(
            db_session,
            user_id=500,
            username="new_name",
            global_name="New Display",
        )
        db_session.commit()

        assert user.username == "new_name"
        assert user.global_name == "New Display"

    def test_bot_user(self, db_session):
        """Bot flag should be stored correctly."""
        user = upsert_user(
            db_session,
            user_id=600,
            username="BotUser",
            is_bot=True,
        )
        db_session.commit()

        assert user.is_bot is True

    def test_user_with_special_characters(self, db_session):
        """Username with special characters."""
        user = upsert_user(
            db_session,
            user_id=700,
            username="user'with\"special<chars>",
        )
        db_session.commit()

        assert user.username == "user'with\"special<chars>"


class TestUpsertChannel:
    """Tests for channel upsert functionality."""

    def test_insert_channel(self, db_session):
        """Should insert a new channel."""
        # Need a server first
        upsert_server(db_session, server_id=1, name="Server")
        db_session.commit()

        channel = upsert_channel(
            db_session,
            channel_id=1001,
            server_id=1,
            name="general",
            channel_type=0,
            topic="Welcome to general!",
        )
        db_session.commit()

        assert channel.id == 1001
        assert channel.name == "general"
        assert channel.topic == "Welcome to general!"

    def test_update_channel_topic(self, db_session):
        """Should update topic on conflict."""
        upsert_server(db_session, server_id=2, name="Server")
        upsert_channel(
            db_session,
            channel_id=2001,
            server_id=2,
            name="channel",
            channel_type=0,
            topic="Old topic",
        )
        db_session.commit()

        channel = upsert_channel(
            db_session,
            channel_id=2001,
            server_id=2,
            name="channel",
            channel_type=0,
            topic="New topic",
        )
        db_session.commit()

        assert channel.topic == "New topic"

    def test_nsfw_channel(self, db_session):
        """NSFW flag should be stored."""
        upsert_server(db_session, server_id=3, name="Server")
        channel = upsert_channel(
            db_session,
            channel_id=3001,
            server_id=3,
            name="nsfw-channel",
            channel_type=0,
            is_nsfw=True,
        )
        db_session.commit()

        assert channel.is_nsfw is True


class TestInsertMessage:
    """Tests for message insertion."""

    def test_insert_message(self, db_session):
        """Should insert a new message."""
        # Setup
        upsert_server(db_session, server_id=10, name="Server")
        upsert_user(db_session, user_id=20, username="author")
        upsert_channel(db_session, channel_id=30, server_id=10, name="ch", channel_type=0)
        db_session.commit()

        msg = insert_message(
            db_session,
            message_id=1000,
            server_id=10,
            channel_id=30,
            author_id=20,
            content="Hello world!",
            created_at=datetime.utcnow(),
        )
        db_session.commit()

        assert msg.id == 1000
        assert msg.content == "Hello world!"
        assert msg.word_count == 2
        assert msg.char_count == 12

    def test_message_with_empty_content(self, db_session):
        """Message can have empty content."""
        upsert_server(db_session, server_id=11, name="Server")
        upsert_user(db_session, user_id=21, username="author")
        upsert_channel(db_session, channel_id=31, server_id=11, name="ch", channel_type=0)
        db_session.commit()

        msg = insert_message(
            db_session,
            message_id=1001,
            server_id=11,
            channel_id=31,
            author_id=21,
            content="",
            created_at=datetime.utcnow(),
        )
        db_session.commit()

        assert msg.content == ""
        assert msg.word_count == 0
        assert msg.char_count == 0

    def test_message_duplicate_ignored(self, db_session):
        """Duplicate message ID should be ignored."""
        upsert_server(db_session, server_id=12, name="Server")
        upsert_user(db_session, user_id=22, username="author")
        upsert_channel(db_session, channel_id=32, server_id=12, name="ch", channel_type=0)
        db_session.commit()

        # Insert first
        insert_message(
            db_session,
            message_id=1002,
            server_id=12,
            channel_id=32,
            author_id=22,
            content="First",
            created_at=datetime.utcnow(),
        )
        db_session.commit()

        # Try to insert duplicate (should be ignored)
        msg = insert_message(
            db_session,
            message_id=1002,
            server_id=12,
            channel_id=32,
            author_id=22,
            content="Second",
            created_at=datetime.utcnow(),
        )
        db_session.commit()

        # Should still have first content
        assert msg.content == "First"

    def test_message_with_reply(self, db_session):
        """Message can reference a reply."""
        upsert_server(db_session, server_id=13, name="Server")
        upsert_user(db_session, user_id=23, username="author")
        upsert_channel(db_session, channel_id=33, server_id=13, name="ch", channel_type=0)
        db_session.commit()

        # Original message
        insert_message(
            db_session,
            message_id=1003,
            server_id=13,
            channel_id=33,
            author_id=23,
            content="Original",
            created_at=datetime.utcnow() - timedelta(hours=1),
        )

        # Reply
        reply = insert_message(
            db_session,
            message_id=1004,
            server_id=13,
            channel_id=33,
            author_id=23,
            content="Reply",
            created_at=datetime.utcnow(),
            message_type=19,
            reply_to_message_id=1003,
            reply_to_author_id=23,
        )
        db_session.commit()

        assert reply.reply_to_message_id == 1003
        assert reply.reply_to_author_id == 23

    def test_message_with_unicode(self, db_session):
        """Message with unicode content."""
        upsert_server(db_session, server_id=14, name="Server")
        upsert_user(db_session, user_id=24, username="author")
        upsert_channel(db_session, channel_id=34, server_id=14, name="ch", channel_type=0)
        db_session.commit()

        content = "Hello 👋 World 🌍 日本語"
        msg = insert_message(
            db_session,
            message_id=1005,
            server_id=14,
            channel_id=34,
            author_id=24,
            content=content,
            created_at=datetime.utcnow(),
        )
        db_session.commit()

        assert msg.content == content


class TestInsertMention:
    """Tests for mention insertion."""

    def test_insert_mention(self, db_session):
        """Should insert a mention."""
        upsert_server(db_session, server_id=50, name="Server")
        upsert_user(db_session, user_id=51, username="author")
        upsert_user(db_session, user_id=52, username="mentioned")
        upsert_channel(db_session, channel_id=53, server_id=50, name="ch", channel_type=0)
        insert_message(
            db_session, message_id=5000, server_id=50, channel_id=53,
            author_id=51, content="Hey @mentioned", created_at=datetime.utcnow()
        )
        db_session.commit()

        insert_mention(db_session, message_id=5000, mentioned_user_id=52)
        db_session.commit()

        # Verify via raw query
        result = db_session.execute(
            text("SELECT * FROM message_mentions WHERE message_id = 5000")
        )
        rows = result.fetchall()
        assert len(rows) == 1

    def test_duplicate_mention_ignored(self, db_session):
        """Duplicate mention should be ignored."""
        upsert_server(db_session, server_id=60, name="Server")
        upsert_user(db_session, user_id=61, username="author")
        upsert_user(db_session, user_id=62, username="mentioned")
        upsert_channel(db_session, channel_id=63, server_id=60, name="ch", channel_type=0)
        insert_message(
            db_session, message_id=6000, server_id=60, channel_id=63,
            author_id=61, content="@mentioned @mentioned", created_at=datetime.utcnow()
        )
        db_session.commit()

        # Insert twice
        insert_mention(db_session, message_id=6000, mentioned_user_id=62)
        db_session.commit()
        insert_mention(db_session, message_id=6000, mentioned_user_id=62)
        db_session.commit()

        # Should only have one
        result = db_session.execute(
            text("SELECT COUNT(*) FROM message_mentions WHERE message_id = 6000")
        )
        assert result.scalar() == 1


class TestUpsertEmoji:
    """Tests for emoji upsert functionality."""

    def test_insert_unicode_emoji(self, db_session):
        """Should insert unicode emoji."""
        emoji_id = upsert_emoji(
            db_session,
            name="👍",
            is_custom=False,
        )
        db_session.commit()

        assert emoji_id is not None

    def test_same_emoji_returns_same_id(self, db_session):
        """Same emoji should return same ID."""
        id1 = upsert_emoji(db_session, name="❤️", is_custom=False)
        db_session.commit()

        id2 = upsert_emoji(db_session, name="❤️", is_custom=False)
        db_session.commit()

        assert id1 == id2

    def test_different_emojis_different_ids(self, db_session):
        """Different emojis should have different IDs."""
        id1 = upsert_emoji(db_session, name="😀", is_custom=False)
        id2 = upsert_emoji(db_session, name="😢", is_custom=False)
        db_session.commit()

        assert id1 != id2

    def test_custom_emoji(self, db_session):
        """Custom emoji with server ID."""
        upsert_server(db_session, server_id=70, name="Server")
        db_session.commit()

        emoji_id = upsert_emoji(
            db_session,
            name="custom_emoji",
            discord_id=123456,
            is_custom=True,
            server_id=70,
        )
        db_session.commit()

        assert emoji_id is not None


class TestInsertReaction:
    """Tests for reaction insertion."""

    def test_insert_reaction(self, db_session):
        """Should insert a reaction."""
        upsert_server(db_session, server_id=80, name="Server")
        upsert_user(db_session, user_id=81, username="author")
        upsert_user(db_session, user_id=82, username="reactor")
        upsert_channel(db_session, channel_id=83, server_id=80, name="ch", channel_type=0)
        insert_message(
            db_session, message_id=8000, server_id=80, channel_id=83,
            author_id=81, content="React!", created_at=datetime.utcnow()
        )
        emoji_id = upsert_emoji(db_session, name="👍", is_custom=False)
        db_session.commit()

        insert_reaction(
            db_session,
            message_id=8000,
            emoji_id=emoji_id,
            user_id=82,
        )
        db_session.commit()

        result = db_session.execute(
            text("SELECT COUNT(*) FROM reactions WHERE message_id = 8000")
        )
        assert result.scalar() == 1

    def test_duplicate_reaction_ignored(self, db_session):
        """Same user, same emoji, same message - duplicate ignored."""
        upsert_server(db_session, server_id=90, name="Server")
        upsert_user(db_session, user_id=91, username="author")
        upsert_user(db_session, user_id=92, username="reactor")
        upsert_channel(db_session, channel_id=93, server_id=90, name="ch", channel_type=0)
        insert_message(
            db_session, message_id=9000, server_id=90, channel_id=93,
            author_id=91, content="React!", created_at=datetime.utcnow()
        )
        emoji_id = upsert_emoji(db_session, name="👍", is_custom=False)
        db_session.commit()

        # Insert twice
        insert_reaction(db_session, message_id=9000, emoji_id=emoji_id, user_id=92)
        db_session.commit()
        insert_reaction(db_session, message_id=9000, emoji_id=emoji_id, user_id=92)
        db_session.commit()

        result = db_session.execute(
            text("SELECT COUNT(*) FROM reactions WHERE message_id = 9000")
        )
        assert result.scalar() == 1

    def test_same_user_different_emojis(self, db_session):
        """Same user can react with different emojis."""
        upsert_server(db_session, server_id=100, name="Server")
        upsert_user(db_session, user_id=101, username="author")
        upsert_user(db_session, user_id=102, username="reactor")
        upsert_channel(db_session, channel_id=103, server_id=100, name="ch", channel_type=0)
        insert_message(
            db_session, message_id=10000, server_id=100, channel_id=103,
            author_id=101, content="React!", created_at=datetime.utcnow()
        )
        emoji_id1 = upsert_emoji(db_session, name="👍", is_custom=False)
        emoji_id2 = upsert_emoji(db_session, name="❤️", is_custom=False)
        db_session.commit()

        insert_reaction(db_session, message_id=10000, emoji_id=emoji_id1, user_id=102)
        insert_reaction(db_session, message_id=10000, emoji_id=emoji_id2, user_id=102)
        db_session.commit()

        result = db_session.execute(
            text("SELECT COUNT(*) FROM reactions WHERE message_id = 10000")
        )
        assert result.scalar() == 2


class TestServerMember:
    """Tests for server member functionality."""

    def test_insert_member(self, db_session):
        """Should insert server member."""
        upsert_server(db_session, server_id=110, name="Server")
        upsert_user(db_session, user_id=111, username="user")
        db_session.commit()

        upsert_server_member(
            db_session,
            server_id=110,
            user_id=111,
            nickname="Cool Nick",
            joined_at=datetime.utcnow(),
        )
        db_session.commit()

        result = db_session.execute(
            text("SELECT nickname FROM server_members WHERE server_id = 110 AND user_id = 111")
        )
        assert result.scalar() == "Cool Nick"

    def test_update_member_nickname(self, db_session):
        """Should update nickname on conflict."""
        upsert_server(db_session, server_id=120, name="Server")
        upsert_user(db_session, user_id=121, username="user")
        db_session.commit()

        upsert_server_member(db_session, server_id=120, user_id=121, nickname="Old")
        db_session.commit()

        upsert_server_member(db_session, server_id=120, user_id=121, nickname="New")
        db_session.commit()

        result = db_session.execute(
            text("SELECT nickname FROM server_members WHERE server_id = 120 AND user_id = 121")
        )
        assert result.scalar() == "New"

    def test_member_null_nickname(self, db_session):
        """Member can have null nickname."""
        upsert_server(db_session, server_id=130, name="Server")
        upsert_user(db_session, user_id=131, username="user")
        db_session.commit()

        upsert_server_member(db_session, server_id=130, user_id=131, nickname=None)
        db_session.commit()

        result = db_session.execute(
            text("SELECT nickname FROM server_members WHERE server_id = 130 AND user_id = 131")
        )
        assert result.scalar() is None
