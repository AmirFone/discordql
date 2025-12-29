"""
Discord data extraction service adapted for SaaS context.

Extracts messages, reactions, and user data from Discord servers
and stores them in the shared database with Row-Level Security (RLS).

All data is tagged with tenant_id (Clerk user ID) for isolation.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
import asyncpg

from sqlalchemy import text

from services.encryption import decrypt_token
from services.shared_database import get_shared_pool
from services.tenant import tenant_connection, TenantContextError
from db.connection import get_db_session

logger = logging.getLogger(__name__)


class SaaSDiscordExtractor:
    """
    Discord data extractor for SaaS users.

    Each extraction runs against the shared database with RLS
    using the user's Clerk ID as tenant_id for isolation.
    """

    def __init__(
        self,
        clerk_id: str,
        job_id: str,
        guild_id: int,
        sync_days: int = 30,
    ):
        self.clerk_id = clerk_id
        self.job_id = job_id
        self.guild_id = guild_id
        self.sync_days = sync_days

        self.stats = {
            "messages": 0,
            "users": 0,
            "channels": 0,
            "reactions": 0,
            "mentions": 0,
        }
        self.db_pool: Optional[asyncpg.Pool] = None
        self.discord_client: Optional[discord.Client] = None

    async def run(self) -> dict:
        """
        Run the extraction process.

        Returns extraction statistics.
        """
        try:
            # Update job status to running
            await self._update_job_status("running")

            # Get encrypted token and decrypt
            token = await self._get_discord_token()

            # Get shared database connection pool
            self.db_pool = await get_shared_pool()

            # Create Discord client
            intents = discord.Intents.default()
            intents.message_content = True
            intents.members = True
            intents.guilds = True

            self.discord_client = discord.Client(intents=intents)

            # Run extraction
            async with self.discord_client:
                await self._connect_and_extract(token)

            # Update job status to completed
            await self._update_job_status(
                "completed",
                messages_extracted=self.stats["messages"],
            )

            return self.stats

        except TenantContextError as e:
            logger.error(f"Tenant context error: {e}")
            await self._update_job_status("failed", error_message=f"Authentication error: {e}")
            raise
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            await self._update_job_status("failed", error_message=str(e))
            raise

    async def _get_discord_token(self) -> str:
        """Get and decrypt the user's Discord bot token."""
        async with get_db_session() as session:
            result = await session.execute(
                text("""
                SELECT encrypted_token FROM discord_tokens
                WHERE user_id = (SELECT id FROM users WHERE clerk_id = :clerk_id)
                AND guild_id = :guild_id
                """),
                {"clerk_id": self.clerk_id, "guild_id": self.guild_id}
            )
            row = result.fetchone()

            if not row:
                raise ValueError("Discord token not found")

            return decrypt_token(row[0])

    async def _update_job_status(
        self,
        status: str,
        messages_extracted: int = 0,
        error_message: Optional[str] = None,
    ):
        """Update extraction job status in the central database."""
        async with get_db_session() as session:
            if status == "completed":
                await session.execute(
                    text("""
                    UPDATE extraction_jobs
                    SET status = :status, messages_extracted = :messages,
                        completed_at = :completed_at
                    WHERE id = :job_id
                    """),
                    {
                        "status": status,
                        "messages": messages_extracted,
                        "completed_at": datetime.utcnow(),
                        "job_id": self.job_id,
                    }
                )
            elif status == "failed":
                await session.execute(
                    text("""
                    UPDATE extraction_jobs
                    SET status = :status, error_message = :error,
                        completed_at = :completed_at
                    WHERE id = :job_id
                    """),
                    {
                        "status": status,
                        "error": error_message,
                        "completed_at": datetime.utcnow(),
                        "job_id": self.job_id,
                    }
                )
            else:
                await session.execute(
                    text("""
                    UPDATE extraction_jobs
                    SET status = :status
                    WHERE id = :job_id
                    """),
                    {"status": status, "job_id": self.job_id}
                )
            await session.commit()

    async def _connect_and_extract(self, token: str):
        """Connect to Discord and run extraction."""
        import asyncio

        # Use asyncio.Event to propagate exceptions from on_ready
        extraction_complete = asyncio.Event()
        extraction_error: Optional[Exception] = None

        @self.discord_client.event
        async def on_ready():
            nonlocal extraction_error
            try:
                logger.info(f"Connected as {self.discord_client.user}")

                # Use fetch_guild() instead of get_guild() to avoid cache race condition
                try:
                    guild = await self.discord_client.fetch_guild(self.guild_id)
                except discord.NotFound:
                    raise ValueError(f"Guild {self.guild_id} not found - bot may not be a member of this server")
                except discord.Forbidden:
                    raise ValueError(f"Guild {self.guild_id} - bot lacks permission to access this guild")

                await self._extract_guild(guild)
            except Exception as e:
                extraction_error = e
            finally:
                extraction_complete.set()
                await self.discord_client.close()

        # Start client in background task
        client_task = asyncio.create_task(self.discord_client.start(token))

        # Wait for extraction to complete or fail (with timeout)
        try:
            await asyncio.wait_for(extraction_complete.wait(), timeout=3600)  # 1 hour timeout
        except asyncio.TimeoutError:
            extraction_error = TimeoutError("Extraction timed out after 1 hour")

        # Cancel the client task if still running
        if not client_task.done():
            client_task.cancel()
            try:
                await client_task
            except asyncio.CancelledError:
                pass

        # Re-raise any captured exception
        if extraction_error:
            raise extraction_error

    async def _extract_guild(self, guild: discord.Guild):
        """Extract all data from a guild."""
        logger.info(f"Extracting guild: {guild.name}")

        # All database operations use tenant_connection for RLS isolation
        async with tenant_connection(self.db_pool, self.clerk_id) as conn:
            # Extract server info
            await self._upsert_server(conn, guild)

            # Extract members
            async for member in guild.fetch_members():
                await self._upsert_user(conn, member)
                await self._upsert_server_member(conn, guild.id, member)
                self.stats["users"] += 1

            # Extract channels and messages
            cutoff = datetime.utcnow() - timedelta(days=self.sync_days)

            for channel in guild.text_channels:
                try:
                    await self._upsert_channel(conn, guild.id, channel)
                    self.stats["channels"] += 1

                    async for message in channel.history(limit=None, after=cutoff):
                        await self._insert_message(conn, guild.id, channel.id, message)
                        self.stats["messages"] += 1

                        # Update progress periodically
                        if self.stats["messages"] % 100 == 0:
                            await self._update_job_status(
                                "running",
                                messages_extracted=self.stats["messages"],
                            )

                except discord.Forbidden:
                    logger.warning(f"No access to #{channel.name}")
                except Exception as e:
                    logger.error(f"Error extracting #{channel.name}: {e}")

        logger.info(f"Extraction complete: {self.stats}")

    async def _upsert_server(self, conn: asyncpg.Connection, guild: discord.Guild):
        """Upsert server info with tenant_id."""
        icon_hash = str(guild.icon.key) if guild.icon else None

        await conn.execute(
            """
            INSERT INTO servers (tenant_id, id, name, owner_id, icon_hash, member_count, created_at, last_synced_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                icon_hash = EXCLUDED.icon_hash,
                member_count = EXCLUDED.member_count,
                last_synced_at = EXCLUDED.last_synced_at
            """,
            self.clerk_id, guild.id, guild.name, guild.owner_id, icon_hash,
            guild.member_count, guild.created_at, datetime.utcnow()
        )

    async def _upsert_user(self, conn: asyncpg.Connection, user: discord.User):
        """Upsert user info with tenant_id."""
        avatar_hash = str(user.avatar.key) if user.avatar else None

        await conn.execute(
            """
            INSERT INTO users (tenant_id, id, username, discriminator, global_name, avatar_hash, is_bot, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (id) DO UPDATE SET
                username = EXCLUDED.username,
                global_name = EXCLUDED.global_name,
                avatar_hash = EXCLUDED.avatar_hash
            """,
            self.clerk_id, user.id, user.name, user.discriminator, user.global_name,
            avatar_hash, user.bot, user.created_at
        )

    async def _upsert_server_member(self, conn: asyncpg.Connection, server_id: int, member: discord.Member):
        """Upsert server member info with tenant_id."""
        await conn.execute(
            """
            INSERT INTO server_members (tenant_id, server_id, user_id, nickname, joined_at, is_active)
            VALUES ($1, $2, $3, $4, $5, TRUE)
            ON CONFLICT (server_id, user_id) DO UPDATE SET
                nickname = EXCLUDED.nickname,
                is_active = TRUE
            """,
            self.clerk_id, server_id, member.id, member.nick, member.joined_at
        )

    async def _upsert_channel(self, conn: asyncpg.Connection, server_id: int, channel: discord.TextChannel):
        """Upsert channel info with tenant_id."""
        await conn.execute(
            """
            INSERT INTO channels (tenant_id, id, server_id, name, type, topic, position, is_nsfw, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                topic = EXCLUDED.topic,
                position = EXCLUDED.position,
                is_nsfw = EXCLUDED.is_nsfw
            """,
            self.clerk_id, channel.id, server_id, channel.name, 0, channel.topic,
            channel.position, channel.nsfw, channel.created_at
        )

    async def _insert_message(
        self,
        conn: asyncpg.Connection,
        server_id: int,
        channel_id: int,
        message: discord.Message,
    ):
        """Insert a message with tenant_id."""
        # Ensure author exists
        await self._upsert_user(conn, message.author)

        # Get reply info
        reply_to_message_id = None
        reply_to_author_id = None
        if message.reference and message.reference.message_id:
            reply_to_message_id = message.reference.message_id

        # Calculate word/char counts
        content = message.content or ""
        word_count = len(content.split())
        char_count = len(content)

        msg_type = message.type.value if hasattr(message.type, 'value') else int(message.type)

        await conn.execute(
            """
            INSERT INTO messages (
                tenant_id, id, server_id, channel_id, author_id, content,
                created_at, edited_at, message_type, is_pinned, is_tts,
                reply_to_message_id, reply_to_author_id, mentions_everyone,
                mention_count, attachment_count, embed_count, word_count, char_count
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
            ON CONFLICT (id) DO NOTHING
            """,
            self.clerk_id, message.id, server_id, channel_id, message.author.id, content,
            message.created_at, message.edited_at, msg_type, message.pinned,
            message.tts, reply_to_message_id, reply_to_author_id,
            message.mention_everyone, len(message.mentions),
            len(message.attachments), len(message.embeds), word_count, char_count
        )

        # Process mentions
        for mentioned_user in message.mentions:
            await self._upsert_user(conn, mentioned_user)
            await conn.execute(
                """
                INSERT INTO message_mentions (tenant_id, message_id, mentioned_user_id)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                self.clerk_id, message.id, mentioned_user.id
            )
            self.stats["mentions"] += 1


async def run_extraction(
    clerk_id: str,
    job_id: str,
    guild_id: int,
    sync_days: int = 30,
) -> dict:
    """
    Convenience function to run an extraction.

    Args:
        clerk_id: The user's Clerk ID (used as tenant_id)
        job_id: The extraction job ID
        guild_id: Discord server ID
        sync_days: Number of days of history to extract

    Returns:
        Extraction statistics
    """
    extractor = SaaSDiscordExtractor(
        clerk_id=clerk_id,
        job_id=job_id,
        guild_id=guild_id,
        sync_days=sync_days,
    )
    return await extractor.run()
