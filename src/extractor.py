"""
Discord data extractor.

Extracts messages, reactions, and user data from Discord servers.
Works identically with real discord.py client or MockDiscordClient.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Protocol, Optional, AsyncIterator, List, Any, TYPE_CHECKING

from sqlalchemy.orm import Session

from .db.queries import (
    upsert_server,
    upsert_user,
    upsert_server_member,
    upsert_channel,
    insert_message,
    insert_mention,
    upsert_emoji,
    insert_reaction,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# =============================================================================
# PROTOCOL DEFINITIONS
# =============================================================================
# These protocols define the interface we expect from Discord objects.
# Both real discord.py objects and our mocks implement these interfaces.


class UserProtocol(Protocol):
    """Protocol for User objects."""
    id: int
    name: str
    discriminator: str
    global_name: Optional[str]
    avatar: Optional[str]
    bot: bool
    created_at: datetime


class MemberProtocol(UserProtocol, Protocol):
    """Protocol for Member objects."""
    nick: Optional[str]
    joined_at: Optional[datetime]


class EmojiProtocol(Protocol):
    """Protocol for Emoji objects."""
    id: Optional[int]
    name: str
    animated: bool


class ReactionProtocol(Protocol):
    """Protocol for Reaction objects."""
    emoji: EmojiProtocol
    count: int

    async def users(self, limit: Optional[int] = None) -> AsyncIterator[UserProtocol]:
        ...


class MessageReferenceProtocol(Protocol):
    """Protocol for MessageReference objects."""
    message_id: Optional[int]
    channel_id: int


class MessageProtocol(Protocol):
    """Protocol for Message objects."""
    id: int
    author: UserProtocol
    content: str
    created_at: datetime
    edited_at: Optional[datetime]
    tts: bool
    mention_everyone: bool
    mentions: List[UserProtocol]
    pinned: bool
    type: int
    reference: Optional[MessageReferenceProtocol]
    reactions: List[ReactionProtocol]
    attachments: List[Any]
    embeds: List[Any]


class ChannelProtocol(Protocol):
    """Protocol for Channel objects."""
    id: int
    name: str
    topic: Optional[str]
    position: int
    nsfw: bool
    created_at: datetime

    async def history(
        self,
        limit: Optional[int] = None,
        after: Optional[datetime] = None,
    ) -> AsyncIterator[MessageProtocol]:
        ...


class GuildProtocol(Protocol):
    """Protocol for Guild objects."""
    id: int
    name: str
    owner_id: int
    icon: Optional[str]
    member_count: int
    text_channels: List[ChannelProtocol]
    created_at: datetime

    async def fetch_members(self, limit: Optional[int] = None) -> AsyncIterator[MemberProtocol]:
        ...


class ClientProtocol(Protocol):
    """Protocol for Discord client."""
    guilds: List[GuildProtocol]

    def get_guild(self, guild_id: int) -> Optional[GuildProtocol]:
        ...


# =============================================================================
# EXTRACTOR CLASS
# =============================================================================


class DiscordExtractor:
    """
    Extracts Discord data and stores it in PostgreSQL.

    Works with either real discord.py client or MockDiscordClient.
    """

    def __init__(
        self,
        client: ClientProtocol,
        engine: "Engine",
        sync_days: int = 7,
        fetch_reactions: bool = True,
    ):
        """
        Initialize the extractor.

        Args:
            client: Discord client (real or mock)
            engine: SQLAlchemy database engine
            sync_days: Number of days of history to sync
            fetch_reactions: Whether to fetch detailed reaction data
        """
        self.client = client
        self.engine = engine
        self.sync_days = sync_days
        self.fetch_reactions = fetch_reactions

        # Statistics
        self.stats = {
            "servers": 0,
            "users": 0,
            "channels": 0,
            "messages": 0,
            "reactions": 0,
            "mentions": 0,
        }

    async def sync_server(self, guild_id: int) -> dict:
        """
        Sync all data for a server.

        Args:
            guild_id: Discord server (guild) ID

        Returns:
            Statistics dictionary
        """
        guild = self.client.get_guild(guild_id)
        if guild is None:
            raise ValueError(f"Guild {guild_id} not found")

        logger.info(f"Starting sync for server: {guild.name} ({guild.id})")

        # Import here to avoid circular imports
        from .db.connection import get_session

        with get_session(self.engine) as session:
            # 1. Sync server metadata
            await self._sync_server_metadata(session, guild)

            # 2. Sync members
            await self._sync_members(session, guild)

            # 3. Sync channels and messages
            await self._sync_channels(session, guild)

        logger.info(f"Sync complete. Stats: {self.stats}")
        return self.stats

    async def _sync_server_metadata(
        self,
        session: Session,
        guild: GuildProtocol,
    ) -> None:
        """Sync server metadata."""
        # Convert Asset to string hash if present
        icon_hash = str(guild.icon.key) if guild.icon else None

        upsert_server(
            session=session,
            server_id=guild.id,
            name=guild.name,
            owner_id=guild.owner_id,
            icon_hash=icon_hash,
            member_count=guild.member_count,
            created_at=guild.created_at,
        )
        self.stats["servers"] += 1
        logger.debug(f"Synced server: {guild.name}")

    async def _sync_members(
        self,
        session: Session,
        guild: GuildProtocol,
    ) -> None:
        """Sync all guild members."""
        member_count = 0
        async for member in guild.fetch_members():
            # Convert Asset to string hash if present
            avatar_hash = str(member.avatar.key) if member.avatar else None

            # Upsert user first
            upsert_user(
                session=session,
                user_id=member.id,
                username=member.name,
                discriminator=member.discriminator,
                global_name=member.global_name,
                avatar_hash=avatar_hash,
                is_bot=member.bot,
                created_at=member.created_at,
            )

            # Then upsert server membership
            upsert_server_member(
                session=session,
                server_id=guild.id,
                user_id=member.id,
                nickname=member.nick,
                joined_at=member.joined_at,
            )
            member_count += 1

        self.stats["users"] += member_count
        logger.debug(f"Synced {member_count} members")

    async def _sync_channels(
        self,
        session: Session,
        guild: GuildProtocol,
    ) -> None:
        """Sync all text channels and their messages."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.sync_days)

        for channel in guild.text_channels:
            # Upsert channel
            upsert_channel(
                session=session,
                channel_id=channel.id,
                server_id=guild.id,
                name=channel.name,
                channel_type=0,  # Text channel
                topic=channel.topic,
                position=channel.position,
                is_nsfw=channel.nsfw,
                created_at=channel.created_at,
            )
            self.stats["channels"] += 1

            # Sync messages
            await self._sync_channel_messages(session, guild, channel, cutoff_date)

    async def _sync_channel_messages(
        self,
        session: Session,
        guild: GuildProtocol,
        channel: ChannelProtocol,
        after: datetime,
    ) -> None:
        """Sync messages for a single channel."""
        message_count = 0

        async for message in channel.history(limit=None, after=after):
            # Convert Asset to string hash if present
            author_avatar = str(message.author.avatar.key) if message.author.avatar else None

            # Ensure author exists
            upsert_user(
                session=session,
                user_id=message.author.id,
                username=message.author.name,
                discriminator=message.author.discriminator,
                global_name=message.author.global_name,
                avatar_hash=author_avatar,
                is_bot=message.author.bot,
                created_at=message.author.created_at,
            )

            # Determine reply info
            reply_to_message_id = None
            reply_to_author_id = None
            if message.reference and message.reference.message_id:
                reply_to_message_id = message.reference.message_id
                # Try to get reply author from internal attribute if available
                if hasattr(message, '_reply_to_author_id'):
                    reply_to_author_id = message._reply_to_author_id

            # Insert message (convert enum to int value)
            msg_type = message.type.value if hasattr(message.type, 'value') else int(message.type)

            insert_message(
                session=session,
                message_id=message.id,
                server_id=guild.id,
                channel_id=channel.id,
                author_id=message.author.id,
                content=message.content,
                created_at=message.created_at,
                edited_at=message.edited_at,
                message_type=msg_type,
                is_pinned=message.pinned,
                is_tts=message.tts,
                reply_to_message_id=reply_to_message_id,
                reply_to_author_id=reply_to_author_id,
                mentions_everyone=message.mention_everyone,
                mention_count=len(message.mentions),
                attachment_count=len(message.attachments),
                embed_count=len(message.embeds),
            )
            message_count += 1

            # Process mentions
            for mentioned_user in message.mentions:
                # Convert Asset to string hash if present
                mentioned_avatar = str(mentioned_user.avatar.key) if mentioned_user.avatar else None

                # Ensure mentioned user exists
                upsert_user(
                    session=session,
                    user_id=mentioned_user.id,
                    username=mentioned_user.name,
                    discriminator=mentioned_user.discriminator,
                    global_name=mentioned_user.global_name,
                    avatar_hash=mentioned_avatar,
                    is_bot=mentioned_user.bot,
                    created_at=mentioned_user.created_at,
                )
                insert_mention(
                    session=session,
                    message_id=message.id,
                    mentioned_user_id=mentioned_user.id,
                )
                self.stats["mentions"] += 1

            # Process reactions
            if self.fetch_reactions and message.reactions:
                await self._sync_message_reactions(session, guild, message)

            # Commit periodically to avoid large transactions
            if message_count % 100 == 0:
                session.commit()
                logger.debug(f"Synced {message_count} messages in #{channel.name}")

        self.stats["messages"] += message_count
        logger.info(f"Synced {message_count} messages from #{channel.name}")

    async def _sync_message_reactions(
        self,
        session: Session,
        guild: GuildProtocol,
        message: MessageProtocol,
    ) -> None:
        """Sync reactions for a single message."""
        for reaction in message.reactions:
            # Handle emoji - can be str (unicode) or Emoji object (custom)
            emoji = reaction.emoji
            if isinstance(emoji, str):
                # Unicode emoji
                emoji_name = emoji
                emoji_discord_id = None
                is_custom = False
                is_animated = False
            else:
                # Custom emoji (PartialEmoji or Emoji object)
                emoji_name = emoji.name
                emoji_discord_id = emoji.id
                is_custom = emoji.id is not None
                is_animated = getattr(emoji, 'animated', False)

            emoji_id = upsert_emoji(
                session=session,
                name=emoji_name,
                discord_id=emoji_discord_id,
                is_custom=is_custom,
                server_id=guild.id if is_custom else None,
                is_animated=is_animated,
            )

            # Get all users who reacted
            async for user in reaction.users():
                # Convert Asset to string hash if present
                user_avatar = str(user.avatar.key) if user.avatar else None

                # Ensure user exists
                upsert_user(
                    session=session,
                    user_id=user.id,
                    username=user.name,
                    discriminator=user.discriminator,
                    global_name=user.global_name,
                    avatar_hash=user_avatar,
                    is_bot=user.bot,
                    created_at=user.created_at,
                )

                insert_reaction(
                    session=session,
                    message_id=message.id,
                    emoji_id=emoji_id,
                    user_id=user.id,
                )
                self.stats["reactions"] += 1


async def run_extraction(
    client: ClientProtocol,
    engine: "Engine",
    guild_id: int,
    sync_days: int = 7,
    fetch_reactions: bool = True,
) -> dict:
    """
    Convenience function to run extraction.

    Args:
        client: Discord client (real or mock)
        engine: SQLAlchemy database engine
        guild_id: Server to sync
        sync_days: Days of history
        fetch_reactions: Whether to fetch detailed reactions

    Returns:
        Statistics dictionary
    """
    extractor = DiscordExtractor(
        client=client,
        engine=engine,
        sync_days=sync_days,
        fetch_reactions=fetch_reactions,
    )
    return await extractor.sync_server(guild_id)
