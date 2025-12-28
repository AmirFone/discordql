#!/usr/bin/env python3
"""
Extract live Discord data from a real server.

Usage:
    python scripts/extract_live.py
"""
import asyncio
import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from sqlalchemy import create_engine, text

from src.extractor import DiscordExtractor
from scripts.run_simulation import get_sqlite_schema, run_analytics_queries

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
SYNC_DAYS = int(os.getenv("SYNC_DAYS", "7"))
DB_PATH = os.getenv("DB_PATH", "discord_data.db")


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


class ExtractionClient(discord.Client):
    """Discord client for data extraction."""

    def __init__(self, engine, guild_id: int, sync_days: int):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        super().__init__(intents=intents)

        self.engine = engine
        self.target_guild_id = guild_id
        self.sync_days = sync_days
        self.extraction_complete = asyncio.Event()
        self.stats = {}

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        # Find target guild
        guild = self.get_guild(self.target_guild_id)
        if not guild:
            logger.error(f"Guild {self.target_guild_id} not found!")
            logger.info(f"Available guilds: {[g.name for g in self.guilds]}")
            self.extraction_complete.set()
            return

        logger.info(f"Found guild: {guild.name} ({guild.member_count} members)")

        # Run extraction
        try:
            extractor = DiscordExtractor(
                client=self,
                engine=self.engine,
                sync_days=self.sync_days,
                fetch_reactions=True,
            )

            logger.info(f"Starting extraction for last {self.sync_days} days...")
            start_time = datetime.now()

            self.stats = await extractor.sync_server(self.target_guild_id)

            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"Extraction complete in {elapsed:.2f}s")
            logger.info(f"Stats: {self.stats}")

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
    print("DISCORD DATA EXTRACTION")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Guild ID: {GUILD_ID}")
    print(f"  Sync days: {SYNC_DAYS}")
    print(f"  Database: {DB_PATH}")

    # Setup database
    engine = setup_database(DB_PATH)

    # Create client and run extraction
    client = ExtractionClient(engine, GUILD_ID, SYNC_DAYS)

    # Start client in background
    async def run_client():
        await client.start(TOKEN)

    client_task = asyncio.create_task(run_client())

    # Wait for extraction to complete
    await client.extraction_complete.wait()

    # Run analytics
    if client.stats:
        run_analytics_queries(engine, GUILD_ID)

    # Close client
    await client.close()

    print("\n" + "=" * 60)
    print(f"Extraction complete! Data stored in: {DB_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
