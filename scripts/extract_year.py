#!/usr/bin/env python3
"""
Extract a full year of Discord data for year-end review.

Features:
- 365 days of message history
- Inter-channel delays to avoid rate limits
- Progress logging
- Optional reaction fetching (disabled by default for speed)

Usage:
    export DISCORD_TOKEN="your_token"
    export GUILD_ID="your_guild_id"
    python scripts/extract_year.py
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from sqlalchemy import create_engine, text
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
from scripts.run_simulation import get_sqlite_schema

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
SYNC_DAYS = int(os.getenv("SYNC_DAYS", "365"))  # Default to 365 days
DB_PATH = os.getenv("DB_PATH", "discord_year.db")
FETCH_REACTIONS = os.getenv("FETCH_REACTIONS", "false").lower() == "true"
CHANNEL_DELAY = float(os.getenv("CHANNEL_DELAY", "2.0"))  # Seconds between channels


def setup_database(db_path: str):
    """Create and initialize SQLite database."""
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.info(f"Removed existing database: {db_path}")

    engine = create_engine(f"sqlite:///{db_path}", echo=False)

    schema = get_sqlite_schema()
    with engine.connect() as conn:
        for statement in schema.split(';'):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
        conn.commit()

    logger.info(f"Created database: {db_path}")
    return engine


class YearExtractor:
    """
    Extracts a full year of Discord data with rate limiting.
    """

    def __init__(
        self,
        client: discord.Client,
        engine,
        sync_days: int = 365,
        fetch_reactions: bool = False,
        channel_delay: float = 2.0,
    ):
        self.client = client
        self.engine = engine
        self.sync_days = sync_days
        self.fetch_reactions = fetch_reactions
        self.channel_delay = channel_delay

        self.stats = {
            "servers": 0,
            "users": 0,
            "channels": 0,
            "messages": 0,
            "reactions": 0,
            "mentions": 0,
        }

        self.start_time = None
        self.messages_per_channel = {}

    def _get_session(self):
        """Get a database session."""
        from sqlalchemy.orm import sessionmaker
        SessionFactory = sessionmaker(bind=self.engine, expire_on_commit=False)
        return SessionFactory()

    async def sync_server(self, guild_id: int) -> dict:
        """Sync all data for a server."""
        self.start_time = datetime.now()
        guild = self.client.get_guild(guild_id)
        if guild is None:
            raise ValueError(f"Guild {guild_id} not found")

        logger.info(f"Starting year extraction for: {guild.name}")
        logger.info(f"  Members: {guild.member_count}")
        logger.info(f"  Text channels: {len(guild.text_channels)}")
        logger.info(f"  Sync days: {self.sync_days}")
        logger.info(f"  Fetch reactions: {self.fetch_reactions}")
        logger.info(f"  Channel delay: {self.channel_delay}s")

        session = self._get_session()
        try:
            # 1. Sync server metadata
            await self._sync_server_metadata(session, guild)

            # 2. Sync members
            await self._sync_members(session, guild)

            # 3. Sync channels with delays
            await self._sync_channels_with_delay(session, guild)

            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

        elapsed = (datetime.now() - self.start_time).total_seconds()
        logger.info(f"Extraction complete in {elapsed:.1f}s")
        logger.info(f"Final stats: {self.stats}")
        return self.stats

    async def _sync_server_metadata(self, session: Session, guild) -> None:
        """Sync server metadata."""
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
        logger.info(f"Synced server: {guild.name}")

    async def _sync_members(self, session: Session, guild) -> None:
        """Sync all guild members."""
        member_count = 0
        async for member in guild.fetch_members():
            avatar_hash = str(member.avatar.key) if member.avatar else None

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

            upsert_server_member(
                session=session,
                server_id=guild.id,
                user_id=member.id,
                nickname=member.nick,
                joined_at=member.joined_at,
            )
            member_count += 1

        self.stats["users"] += member_count
        logger.info(f"Synced {member_count} members")
        session.commit()

    async def _sync_channels_with_delay(self, session: Session, guild) -> None:
        """Sync all text channels with delays between each."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.sync_days)
        total_channels = len(guild.text_channels)

        for idx, channel in enumerate(guild.text_channels, 1):
            logger.info(f"Processing channel {idx}/{total_channels}: #{channel.name}")

            # Upsert channel
            upsert_channel(
                session=session,
                channel_id=channel.id,
                server_id=guild.id,
                name=channel.name,
                channel_type=0,
                topic=channel.topic,
                position=channel.position,
                is_nsfw=channel.nsfw,
                created_at=channel.created_at,
            )
            self.stats["channels"] += 1

            # Sync messages
            channel_start = datetime.now()
            msg_count = await self._sync_channel_messages(session, guild, channel, cutoff_date)
            channel_elapsed = (datetime.now() - channel_start).total_seconds()

            self.messages_per_channel[channel.name] = msg_count
            logger.info(f"  #{channel.name}: {msg_count} messages in {channel_elapsed:.1f}s")

            # Commit after each channel
            session.commit()

            # Delay before next channel (except for last one)
            if idx < total_channels and self.channel_delay > 0:
                logger.debug(f"  Waiting {self.channel_delay}s before next channel...")
                await asyncio.sleep(self.channel_delay)

    async def _sync_channel_messages(
        self,
        session: Session,
        guild,
        channel,
        after: datetime,
    ) -> int:
        """Sync messages for a single channel."""
        message_count = 0

        try:
            async for message in channel.history(limit=None, after=after):
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
                    if hasattr(message, '_reply_to_author_id'):
                        reply_to_author_id = message._reply_to_author_id

                # Get message type value
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
                    mentioned_avatar = str(mentioned_user.avatar.key) if mentioned_user.avatar else None

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

                # Process reactions if enabled
                if self.fetch_reactions and message.reactions:
                    await self._sync_message_reactions(session, guild, message)

                # Commit and log progress periodically
                if message_count % 100 == 0:
                    session.commit()
                    elapsed = (datetime.now() - self.start_time).total_seconds()
                    total_msgs = self.stats["messages"] + message_count
                    rate = total_msgs / elapsed if elapsed > 0 else 0
                    logger.info(f"    Progress: {message_count} messages ({rate:.1f} msg/s total)")

        except discord.Forbidden:
            logger.warning(f"  No access to #{channel.name}")
        except Exception as e:
            logger.error(f"  Error in #{channel.name}: {e}")

        self.stats["messages"] += message_count
        return message_count

    async def _sync_message_reactions(self, session: Session, guild, message) -> None:
        """Sync reactions for a single message."""
        for reaction in message.reactions:
            emoji = reaction.emoji
            if isinstance(emoji, str):
                emoji_name = emoji
                emoji_discord_id = None
                is_custom = False
                is_animated = False
            else:
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

            async for user in reaction.users():
                user_avatar = str(user.avatar.key) if user.avatar else None

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


class ExtractionClient(discord.Client):
    """Discord client for year data extraction."""

    def __init__(self, engine, guild_id: int, sync_days: int, fetch_reactions: bool, channel_delay: float):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        super().__init__(intents=intents)

        self.engine = engine
        self.target_guild_id = guild_id
        self.sync_days = sync_days
        self.fetch_reactions = fetch_reactions
        self.channel_delay = channel_delay
        self.extraction_complete = asyncio.Event()
        self.stats = {}

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        guild = self.get_guild(self.target_guild_id)
        if not guild:
            logger.error(f"Guild {self.target_guild_id} not found!")
            logger.info(f"Available guilds: {[g.name for g in self.guilds]}")
            self.extraction_complete.set()
            return

        logger.info(f"Found guild: {guild.name} ({guild.member_count} members)")

        try:
            extractor = YearExtractor(
                client=self,
                engine=self.engine,
                sync_days=self.sync_days,
                fetch_reactions=self.fetch_reactions,
                channel_delay=self.channel_delay,
            )

            self.stats = await extractor.sync_server(self.target_guild_id)

            # Print summary
            print("\n" + "=" * 60)
            print("EXTRACTION SUMMARY")
            print("=" * 60)
            print(f"\nMessages per channel:")
            for channel, count in sorted(extractor.messages_per_channel.items(), key=lambda x: -x[1]):
                print(f"  #{channel}: {count}")
            print(f"\nTotals:")
            for key, value in self.stats.items():
                print(f"  {key}: {value}")

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            import traceback
            traceback.print_exc()

        self.extraction_complete.set()

    async def on_error(self, event, *args, **kwargs):
        logger.error(f"Error in {event}: {args}")
        import traceback
        traceback.print_exc()


async def main():
    if not TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set")
        sys.exit(1)

    if not GUILD_ID:
        print("Error: GUILD_ID environment variable not set")
        sys.exit(1)

    print("=" * 60)
    print("DISCORD YEAR EXTRACTION")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Guild ID: {GUILD_ID}")
    print(f"  Sync days: {SYNC_DAYS}")
    print(f"  Database: {DB_PATH}")
    print(f"  Fetch reactions: {FETCH_REACTIONS}")
    print(f"  Channel delay: {CHANNEL_DELAY}s")

    # Setup database
    engine = setup_database(DB_PATH)

    # Create client and run extraction
    client = ExtractionClient(
        engine=engine,
        guild_id=GUILD_ID,
        sync_days=SYNC_DAYS,
        fetch_reactions=FETCH_REACTIONS,
        channel_delay=CHANNEL_DELAY,
    )

    # Start client
    async def run_client():
        await client.start(TOKEN)

    client_task = asyncio.create_task(run_client())

    # Wait for extraction to complete
    await client.extraction_complete.wait()

    # Close client
    await client.close()

    print("\n" + "=" * 60)
    print(f"Extraction complete! Data stored in: {DB_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
