"""Database query functions for Discord analytics."""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from .models import Server, User, ServerMember, Channel, Message, MessageMention, Emoji, Reaction


def upsert_server(
    session: Session,
    server_id: int,
    name: str,
    owner_id: Optional[int] = None,
    icon_hash: Optional[str] = None,
    member_count: Optional[int] = None,
    created_at: Optional[datetime] = None,
) -> Server:
    """Insert or update a server."""
    stmt = insert(Server).values(
        id=server_id,
        name=name,
        owner_id=owner_id,
        icon_hash=icon_hash,
        member_count=member_count,
        created_at=created_at,
        last_synced_at=datetime.utcnow(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "name": stmt.excluded.name,
            "owner_id": stmt.excluded.owner_id,
            "icon_hash": stmt.excluded.icon_hash,
            "member_count": stmt.excluded.member_count,
            "last_synced_at": stmt.excluded.last_synced_at,
        },
    )
    session.execute(stmt)
    return session.query(Server).get(server_id)


def upsert_user(
    session: Session,
    user_id: int,
    username: str,
    discriminator: Optional[str] = None,
    global_name: Optional[str] = None,
    avatar_hash: Optional[str] = None,
    is_bot: bool = False,
    created_at: Optional[datetime] = None,
) -> User:
    """Insert or update a user."""
    stmt = insert(User).values(
        id=user_id,
        username=username,
        discriminator=discriminator,
        global_name=global_name,
        avatar_hash=avatar_hash,
        is_bot=is_bot,
        created_at=created_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "username": stmt.excluded.username,
            "discriminator": stmt.excluded.discriminator,
            "global_name": stmt.excluded.global_name,
            "avatar_hash": stmt.excluded.avatar_hash,
        },
    )
    session.execute(stmt)
    return session.query(User).get(user_id)


def upsert_server_member(
    session: Session,
    server_id: int,
    user_id: int,
    nickname: Optional[str] = None,
    joined_at: Optional[datetime] = None,
) -> None:
    """Insert or update a server member."""
    stmt = insert(ServerMember).values(
        server_id=server_id,
        user_id=user_id,
        nickname=nickname,
        joined_at=joined_at,
        is_active=True,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["server_id", "user_id"],
        set_={
            "nickname": stmt.excluded.nickname,
            "is_active": True,
        },
    )
    session.execute(stmt)


def upsert_channel(
    session: Session,
    channel_id: int,
    server_id: int,
    name: str,
    channel_type: int,
    parent_id: Optional[int] = None,
    topic: Optional[str] = None,
    position: Optional[int] = None,
    is_nsfw: bool = False,
    created_at: Optional[datetime] = None,
) -> Channel:
    """Insert or update a channel."""
    stmt = insert(Channel).values(
        id=channel_id,
        server_id=server_id,
        name=name,
        type=channel_type,
        parent_id=parent_id,
        topic=topic,
        position=position,
        is_nsfw=is_nsfw,
        created_at=created_at,
        last_synced_at=datetime.utcnow(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "name": stmt.excluded.name,
            "topic": stmt.excluded.topic,
            "position": stmt.excluded.position,
            "last_synced_at": stmt.excluded.last_synced_at,
        },
    )
    session.execute(stmt)
    return session.query(Channel).get(channel_id)


def insert_message(
    session: Session,
    message_id: int,
    server_id: int,
    channel_id: int,
    author_id: int,
    content: str,
    created_at: datetime,
    edited_at: Optional[datetime] = None,
    message_type: int = 0,
    is_pinned: bool = False,
    is_tts: bool = False,
    reply_to_message_id: Optional[int] = None,
    reply_to_author_id: Optional[int] = None,
    mentions_everyone: bool = False,
    mention_count: int = 0,
    attachment_count: int = 0,
    embed_count: int = 0,
) -> Message:
    """Insert a message (no update on conflict - messages are immutable)."""
    # Calculate word and char count
    word_count = len(content.split()) if content else 0
    char_count = len(content) if content else 0

    stmt = insert(Message).values(
        id=message_id,
        server_id=server_id,
        channel_id=channel_id,
        author_id=author_id,
        content=content,
        created_at=created_at,
        edited_at=edited_at,
        message_type=message_type,
        is_pinned=is_pinned,
        is_tts=is_tts,
        reply_to_message_id=reply_to_message_id,
        reply_to_author_id=reply_to_author_id,
        mentions_everyone=mentions_everyone,
        mention_count=mention_count,
        attachment_count=attachment_count,
        embed_count=embed_count,
        word_count=word_count,
        char_count=char_count,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
    session.execute(stmt)
    return session.query(Message).get(message_id)


def insert_mention(
    session: Session,
    message_id: int,
    mentioned_user_id: int,
) -> None:
    """Insert a message mention."""
    stmt = insert(MessageMention).values(
        message_id=message_id,
        mentioned_user_id=mentioned_user_id,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["message_id", "mentioned_user_id"])
    session.execute(stmt)


def upsert_emoji(
    session: Session,
    name: str,
    discord_id: Optional[int] = None,
    is_custom: bool = False,
    server_id: Optional[int] = None,
    is_animated: bool = False,
) -> int:
    """Insert or get emoji, return emoji ID."""
    # Check if emoji exists
    existing = session.query(Emoji).filter(
        Emoji.name == name,
        Emoji.server_id == server_id,
    ).first()

    if existing:
        return existing.id

    emoji = Emoji(
        discord_id=discord_id,
        name=name,
        is_custom=is_custom,
        server_id=server_id,
        is_animated=is_animated,
    )
    session.add(emoji)
    session.flush()
    return emoji.id


def insert_reaction(
    session: Session,
    message_id: int,
    emoji_id: int,
    user_id: int,
    is_super_reaction: bool = False,
) -> None:
    """Insert a reaction."""
    stmt = insert(Reaction).values(
        message_id=message_id,
        emoji_id=emoji_id,
        user_id=user_id,
        reacted_at=datetime.utcnow(),
        is_super_reaction=is_super_reaction,
    )
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["message_id", "emoji_id", "user_id"]
    )
    session.execute(stmt)


# =============================================================================
# ANALYTICS QUERIES
# =============================================================================

def get_user_interactions(
    session: Session,
    server_id: int,
    days: int = 7,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Get top user-to-user interactions in the past N days.

    Returns aggregated reply, reaction, and mention counts.
    """
    sql = text("""
        SELECT
            u1.username AS from_user,
            u2.username AS to_user,
            SUM(interaction_count) AS total_interactions,
            jsonb_object_agg(interaction_type, interaction_count) AS breakdown
        FROM user_interactions ui
        JOIN users u1 ON ui.from_user_id = u1.id
        JOIN users u2 ON ui.to_user_id = u2.id
        WHERE ui.server_id = :server_id
          AND ui.last_interaction > NOW() - INTERVAL :days DAY
        GROUP BY u1.username, u2.username
        ORDER BY total_interactions DESC
        LIMIT :limit
    """)
    result = session.execute(sql, {"server_id": server_id, "days": days, "limit": limit})
    return [dict(row) for row in result]


def get_reaction_patterns(
    session: Session,
    server_id: int,
    days: int = 7,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Get who reacts to whom patterns."""
    sql = text("""
        SELECT
            reactor.username AS reactor,
            author.username AS message_author,
            COUNT(*) AS reaction_count,
            array_agg(DISTINCT e.name) AS emojis_used
        FROM reactions r
        JOIN messages m ON r.message_id = m.id
        JOIN users reactor ON r.user_id = reactor.id
        JOIN users author ON m.author_id = author.id
        JOIN emojis e ON r.emoji_id = e.id
        WHERE m.server_id = :server_id
          AND r.reacted_at > NOW() - INTERVAL :days DAY
          AND r.user_id != m.author_id
        GROUP BY reactor.username, author.username
        ORDER BY reaction_count DESC
        LIMIT :limit
    """)
    result = session.execute(sql, {"server_id": server_id, "days": days, "limit": limit})
    return [dict(row) for row in result]


def get_message_count_by_user(
    session: Session,
    server_id: int,
    days: int = 7,
) -> List[Dict[str, Any]]:
    """Get message counts by user."""
    sql = text("""
        SELECT
            u.username,
            u.global_name,
            COUNT(*) AS message_count,
            COUNT(DISTINCT m.channel_id) AS channels_active,
            SUM(CASE WHEN m.reply_to_message_id IS NOT NULL THEN 1 ELSE 0 END) AS reply_count
        FROM messages m
        JOIN users u ON m.author_id = u.id
        WHERE m.server_id = :server_id
          AND m.created_at > NOW() - INTERVAL :days DAY
        GROUP BY u.id, u.username, u.global_name
        ORDER BY message_count DESC
    """)
    result = session.execute(sql, {"server_id": server_id, "days": days})
    return [dict(row) for row in result]


def refresh_materialized_views(session: Session) -> None:
    """Refresh all materialized views."""
    session.execute(text("SELECT refresh_analytics_views()"))
