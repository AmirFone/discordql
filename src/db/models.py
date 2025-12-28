"""SQLAlchemy models matching the database schema."""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Server(Base):
    """Discord server (guild) model."""

    __tablename__ = "servers"

    id = Column(BigInteger, primary_key=True)
    name = Column(Text, nullable=False)
    icon_hash = Column(Text)
    owner_id = Column(BigInteger)
    member_count = Column(Integer)
    created_at = Column(DateTime(timezone=True))
    first_synced_at = Column(DateTime(timezone=True), default=func.now())
    last_synced_at = Column(DateTime(timezone=True))

    # Relationships
    channels = relationship("Channel", back_populates="server", cascade="all, delete-orphan")
    members = relationship("ServerMember", back_populates="server", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="server", cascade="all, delete-orphan")


class User(Base):
    """Discord user model."""

    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    username = Column(Text, nullable=False)
    discriminator = Column(Text)
    global_name = Column(Text)
    avatar_hash = Column(Text)
    is_bot = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True))
    first_seen_at = Column(DateTime(timezone=True), default=func.now())

    # Relationships
    memberships = relationship("ServerMember", back_populates="user")
    messages = relationship("Message", back_populates="author")
    reactions = relationship("Reaction", back_populates="user")


class ServerMember(Base):
    """Server membership (user in a specific server)."""

    __tablename__ = "server_members"

    server_id = Column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    nickname = Column(Text)
    joined_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    # Relationships
    server = relationship("Server", back_populates="members")
    user = relationship("User", back_populates="memberships")


class Channel(Base):
    """Discord channel model."""

    __tablename__ = "channels"

    id = Column(BigInteger, primary_key=True)
    server_id = Column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"))
    name = Column(Text, nullable=False)
    type = Column(Integer, nullable=False)
    parent_id = Column(BigInteger)
    topic = Column(Text)
    position = Column(Integer)
    is_nsfw = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True))
    is_archived = Column(Boolean, default=False)
    last_synced_at = Column(DateTime(timezone=True))

    # Relationships
    server = relationship("Server", back_populates="channels")
    messages = relationship("Message", back_populates="channel", cascade="all, delete-orphan")


class Message(Base):
    """Discord message model."""

    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True)
    server_id = Column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"))
    channel_id = Column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"))
    author_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))

    content = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False)
    edited_at = Column(DateTime(timezone=True))

    message_type = Column(Integer, default=0)
    is_pinned = Column(Boolean, default=False)
    is_tts = Column(Boolean, default=False)

    reply_to_message_id = Column(BigInteger)
    reply_to_author_id = Column(BigInteger)
    thread_id = Column(BigInteger)

    mentions_everyone = Column(Boolean, default=False)
    mention_count = Column(Integer, default=0)

    attachment_count = Column(Integer, default=0)
    embed_count = Column(Integer, default=0)
    has_poll = Column(Boolean, default=False)

    word_count = Column(Integer)
    char_count = Column(Integer)

    # Relationships
    server = relationship("Server", back_populates="messages")
    channel = relationship("Channel", back_populates="messages")
    author = relationship("User", back_populates="messages")
    mentions = relationship("MessageMention", back_populates="message", cascade="all, delete-orphan")
    reactions = relationship("Reaction", back_populates="message", cascade="all, delete-orphan")


class MessageMention(Base):
    """User mention in a message."""

    __tablename__ = "message_mentions"

    message_id = Column(BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True)
    mentioned_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    # Relationships
    message = relationship("Message", back_populates="mentions")


class Emoji(Base):
    """Emoji model (unicode or custom)."""

    __tablename__ = "emojis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_id = Column(BigInteger)
    name = Column(Text, nullable=False)
    is_custom = Column(Boolean, default=False)
    server_id = Column(BigInteger)
    is_animated = Column(Boolean, default=False)

    # Relationships
    reactions = relationship("Reaction", back_populates="emoji")


class Reaction(Base):
    """Reaction on a message."""

    __tablename__ = "reactions"

    message_id = Column(BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True)
    emoji_id = Column(Integer, ForeignKey("emojis.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    reacted_at = Column(DateTime(timezone=True), default=func.now())
    is_super_reaction = Column(Boolean, default=False)

    # Relationships
    message = relationship("Message", back_populates="reactions")
    emoji = relationship("Emoji", back_populates="reactions")
    user = relationship("User", back_populates="reactions")


class SyncState(Base):
    """Track sync progress for incremental updates."""

    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(BigInteger, ForeignKey("servers.id", ondelete="CASCADE"))
    channel_id = Column(BigInteger, ForeignKey("channels.id", ondelete="CASCADE"))
    sync_type = Column(Text, nullable=False)
    last_message_id = Column(BigInteger)
    oldest_message_id = Column(BigInteger)
    status = Column(Text, default="pending")
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    message_count = Column(Integer, default=0)
    error_message = Column(Text)
