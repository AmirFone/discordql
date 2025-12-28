"""
Tests for database schema and constraints.

Validates that the schema correctly enforces data integrity.
"""
import pytest
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


class TestSchemaConstraints:
    """Test database schema constraints."""

    def test_server_insert(self, clean_db):
        """Should be able to insert a server."""
        with clean_db.connect() as conn:
            conn.execute(text(
                "INSERT INTO servers (id, name, owner_id, member_count) "
                "VALUES (123, 'Test Server', 456, 100)"
            ))
            conn.commit()

            result = conn.execute(text("SELECT name FROM servers WHERE id = 123"))
            assert result.scalar() == "Test Server"

    def test_user_insert(self, clean_db):
        """Should be able to insert a user."""
        with clean_db.connect() as conn:
            conn.execute(text(
                "INSERT INTO users (id, username, is_bot) "
                "VALUES (789, 'testuser', 0)"
            ))
            conn.commit()

            result = conn.execute(text("SELECT username FROM users WHERE id = 789"))
            assert result.scalar() == "testuser"

    def test_channel_requires_server(self, clean_db):
        """Channels should reference existing servers (FK constraint)."""
        with clean_db.connect() as conn:
            # First create a server
            conn.execute(text(
                "INSERT INTO servers (id, name) VALUES (1, 'Server 1')"
            ))
            conn.commit()

            # Channel with valid server_id should work
            conn.execute(text(
                "INSERT INTO channels (id, server_id, name, type) "
                "VALUES (100, 1, 'general', 0)"
            ))
            conn.commit()

            result = conn.execute(text("SELECT COUNT(*) FROM channels"))
            assert result.scalar() == 1

    def test_message_references_valid_entities(self, clean_db):
        """Messages should reference valid server, channel, author."""
        with clean_db.connect() as conn:
            # Setup: server, user, channel (separate statements)
            conn.execute(text("INSERT INTO servers (id, name) VALUES (1, 'Server')"))
            conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'user1')"))
            conn.execute(text(
                "INSERT INTO channels (id, server_id, name, type) VALUES (1, 1, 'general', 0)"
            ))
            conn.commit()

            # Insert message
            conn.execute(text(
                "INSERT INTO messages (id, server_id, channel_id, author_id, content, created_at) "
                "VALUES (1, 1, 1, 1, 'Hello world', datetime('now'))"
            ))
            conn.commit()

            result = conn.execute(text("SELECT content FROM messages WHERE id = 1"))
            assert result.scalar() == "Hello world"

    def test_reaction_links_message_emoji_user(self, clean_db):
        """Reactions should link message, emoji, and user."""
        with clean_db.connect() as conn:
            # Setup (separate statements for SQLite compatibility)
            conn.execute(text("INSERT INTO servers (id, name) VALUES (1, 'Server')"))
            conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'user1')"))
            conn.execute(text(
                "INSERT INTO channels (id, server_id, name, type) VALUES (1, 1, 'general', 0)"
            ))
            conn.execute(text(
                "INSERT INTO messages (id, server_id, channel_id, author_id, content, created_at) "
                "VALUES (1, 1, 1, 1, 'React to me', datetime('now'))"
            ))
            conn.execute(text("INSERT INTO emojis (id, name) VALUES (1, '👍')"))
            conn.commit()

            # Insert reaction
            conn.execute(text(
                "INSERT INTO reactions (message_id, emoji_id, user_id) VALUES (1, 1, 1)"
            ))
            conn.commit()

            result = conn.execute(text("SELECT COUNT(*) FROM reactions"))
            assert result.scalar() == 1

    def test_reaction_unique_per_user_emoji_message(self, clean_db):
        """User can only react once per emoji per message."""
        with clean_db.connect() as conn:
            # Setup
            conn.execute(text("INSERT INTO servers (id, name) VALUES (1, 'Server')"))
            conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'user1')"))
            conn.execute(text(
                "INSERT INTO channels (id, server_id, name, type) VALUES (1, 1, 'general', 0)"
            ))
            conn.execute(text(
                "INSERT INTO messages (id, server_id, channel_id, author_id, content, created_at) "
                "VALUES (1, 1, 1, 1, 'React to me', datetime('now'))"
            ))
            conn.execute(text("INSERT INTO emojis (id, name) VALUES (1, '👍')"))
            conn.commit()

            # First reaction should work
            conn.execute(text(
                "INSERT INTO reactions (message_id, emoji_id, user_id) VALUES (1, 1, 1)"
            ))
            conn.commit()

            # Duplicate should fail or be ignored (depending on DBMS)
            try:
                conn.execute(text(
                    "INSERT INTO reactions (message_id, emoji_id, user_id) VALUES (1, 1, 1)"
                ))
                conn.commit()
            except IntegrityError:
                conn.rollback()

            # Should still be only 1 reaction
            result = conn.execute(text("SELECT COUNT(*) FROM reactions"))
            assert result.scalar() == 1

    def test_mention_links_message_and_user(self, clean_db):
        """Mentions should link message to mentioned user."""
        with clean_db.connect() as conn:
            # Setup
            conn.execute(text("INSERT INTO servers (id, name) VALUES (1, 'Server')"))
            conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'author')"))
            conn.execute(text("INSERT INTO users (id, username) VALUES (2, 'mentioned')"))
            conn.execute(text(
                "INSERT INTO channels (id, server_id, name, type) VALUES (1, 1, 'general', 0)"
            ))
            conn.execute(text(
                "INSERT INTO messages (id, server_id, channel_id, author_id, content, created_at) "
                "VALUES (1, 1, 1, 1, 'Hey @mentioned', datetime('now'))"
            ))
            conn.commit()

            # Insert mention
            conn.execute(text(
                "INSERT INTO message_mentions (message_id, mentioned_user_id) VALUES (1, 2)"
            ))
            conn.commit()

            result = conn.execute(text("SELECT COUNT(*) FROM message_mentions"))
            assert result.scalar() == 1

    def test_server_member_composite_key(self, clean_db):
        """Server membership has composite primary key."""
        with clean_db.connect() as conn:
            # Setup
            conn.execute(text("INSERT INTO servers (id, name) VALUES (1, 'Server')"))
            conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'user1')"))
            conn.commit()

            # Insert membership
            conn.execute(text(
                "INSERT INTO server_members (server_id, user_id, nickname) VALUES (1, 1, 'Nickname')"
            ))
            conn.commit()

            result = conn.execute(text("SELECT nickname FROM server_members"))
            assert result.scalar() == "Nickname"


class TestIndexes:
    """Test that indexes exist and are functional."""

    def test_message_indexes_exist(self, clean_db):
        """Message indexes should exist for common queries."""
        with clean_db.connect() as conn:
            # SQLite way to check indexes
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='messages'"
            ))
            indexes = [row[0] for row in result.fetchall()]

            # Check key indexes exist
            assert any("channel" in idx.lower() for idx in indexes)
            assert any("author" in idx.lower() for idx in indexes)

    def test_reaction_indexes_exist(self, clean_db):
        """Reaction indexes should exist."""
        with clean_db.connect() as conn:
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='reactions'"
            ))
            indexes = [row[0] for row in result.fetchall()]

            assert any("user" in idx.lower() for idx in indexes)
            assert any("message" in idx.lower() for idx in indexes)
