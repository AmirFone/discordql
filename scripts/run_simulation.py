#!/usr/bin/env python3
"""
Run a full simulation with generated Discord data.

This script:
1. Creates a mock Discord server with realistic data
2. Runs the extraction pipeline
3. Stores data in PostgreSQL (or SQLite for testing)
4. Demonstrates analytics queries

Usage:
    python scripts/run_simulation.py [--users N] [--channels N] [--messages N] [--days N]
"""
import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

from tests.mocks import create_mock_client, DiscordDataGenerator
from src.extractor import run_extraction

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_sqlite_schema():
    """SQLite-compatible schema for simulation."""
    return """
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            icon_hash TEXT,
            owner_id INTEGER,
            member_count INTEGER,
            created_at TIMESTAMP,
            first_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_synced_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            discriminator TEXT,
            global_name TEXT,
            avatar_hash TEXT,
            is_bot INTEGER DEFAULT 0,
            created_at TIMESTAMP,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS server_members (
            server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            nickname TEXT,
            joined_at TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            PRIMARY KEY (server_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY,
            server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            type INTEGER NOT NULL,
            parent_id INTEGER,
            topic TEXT,
            position INTEGER,
            is_nsfw INTEGER DEFAULT 0,
            created_at TIMESTAMP,
            is_archived INTEGER DEFAULT 0,
            last_synced_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
            channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
            author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            content TEXT,
            created_at TIMESTAMP NOT NULL,
            edited_at TIMESTAMP,
            message_type INTEGER DEFAULT 0,
            is_pinned INTEGER DEFAULT 0,
            is_tts INTEGER DEFAULT 0,
            reply_to_message_id INTEGER,
            reply_to_author_id INTEGER,
            thread_id INTEGER,
            mentions_everyone INTEGER DEFAULT 0,
            mention_count INTEGER DEFAULT 0,
            attachment_count INTEGER DEFAULT 0,
            embed_count INTEGER DEFAULT 0,
            has_poll INTEGER DEFAULT 0,
            word_count INTEGER,
            char_count INTEGER
        );

        CREATE TABLE IF NOT EXISTS message_mentions (
            message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
            mentioned_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY (message_id, mentioned_user_id)
        );

        CREATE TABLE IF NOT EXISTS emojis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id INTEGER,
            name TEXT NOT NULL,
            is_custom INTEGER DEFAULT 0,
            server_id INTEGER,
            is_animated INTEGER DEFAULT 0,
            UNIQUE(name, server_id)
        );

        CREATE TABLE IF NOT EXISTS reactions (
            message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
            emoji_id INTEGER REFERENCES emojis(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            reacted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_super_reaction INTEGER DEFAULT 0,
            PRIMARY KEY (message_id, emoji_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS sync_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
            channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
            sync_type TEXT NOT NULL,
            last_message_id INTEGER,
            oldest_message_id INTEGER,
            status TEXT DEFAULT 'pending',
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            message_count INTEGER DEFAULT 0,
            error_message TEXT,
            UNIQUE(server_id, channel_id, sync_type)
        );

        CREATE INDEX IF NOT EXISTS idx_messages_channel_time ON messages(channel_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_author_time ON messages(author_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_server_time ON messages(server_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_reply_author ON messages(reply_to_author_id);
        CREATE INDEX IF NOT EXISTS idx_reactions_user ON reactions(user_id);
        CREATE INDEX IF NOT EXISTS idx_reactions_message ON reactions(message_id);
        CREATE INDEX IF NOT EXISTS idx_mentions_user ON message_mentions(mentioned_user_id);
    """


def setup_database(db_path: str) -> "Engine":
    """Create and initialize SQLite database."""
    from sqlalchemy import create_engine

    # Remove old database
    if os.path.exists(db_path):
        os.remove(db_path)

    engine = create_engine(f"sqlite:///{db_path}", echo=False)

    # Create tables
    schema = get_sqlite_schema()
    with engine.connect() as conn:
        for statement in schema.split(';'):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
        conn.commit()

    return engine


def run_analytics_queries(engine, server_id: int):
    """Run and display analytics queries."""
    print("\n" + "=" * 60)
    print("ANALYTICS RESULTS")
    print("=" * 60)

    with engine.connect() as conn:
        # 1. Top message authors
        print("\n📊 Top 10 Message Authors:")
        print("-" * 40)
        result = conn.execute(text("""
            SELECT
                u.username,
                u.global_name,
                COUNT(*) as message_count
            FROM messages m
            JOIN users u ON m.author_id = u.id
            WHERE m.server_id = :server_id
            GROUP BY u.id
            ORDER BY message_count DESC
            LIMIT 10
        """), {"server_id": server_id})

        for row in result:
            display_name = row[1] or row[0]
            print(f"  {display_name}: {row[2]} messages")

        # 2. Reply patterns (who replies to whom)
        print("\n💬 Top Reply Relationships:")
        print("-" * 40)
        result = conn.execute(text("""
            SELECT
                author.username as replier,
                replied_to.username as replied_to_user,
                COUNT(*) as reply_count
            FROM messages m
            JOIN users author ON m.author_id = author.id
            JOIN messages original ON m.reply_to_message_id = original.id
            JOIN users replied_to ON original.author_id = replied_to.id
            WHERE m.server_id = :server_id
              AND m.reply_to_message_id IS NOT NULL
              AND m.author_id != original.author_id
            GROUP BY author.id, replied_to.id
            ORDER BY reply_count DESC
            LIMIT 10
        """), {"server_id": server_id})

        for row in result:
            print(f"  {row[0]} → {row[1]}: {row[2]} replies")

        # 3. Reaction patterns (who reacts to whom)
        print("\n❤️ Top Reaction Relationships:")
        print("-" * 40)
        result = conn.execute(text("""
            SELECT
                reactor.username as reactor,
                author.username as message_author,
                COUNT(*) as reaction_count
            FROM reactions r
            JOIN messages m ON r.message_id = m.id
            JOIN users reactor ON r.user_id = reactor.id
            JOIN users author ON m.author_id = author.id
            WHERE m.server_id = :server_id
              AND r.user_id != m.author_id
            GROUP BY reactor.id, author.id
            ORDER BY reaction_count DESC
            LIMIT 10
        """), {"server_id": server_id})

        for row in result:
            print(f"  {row[0]} → {row[1]}: {row[2]} reactions")

        # 4. Most used emojis
        print("\n😀 Most Used Emojis:")
        print("-" * 40)
        result = conn.execute(text("""
            SELECT e.name, COUNT(*) as usage_count
            FROM reactions r
            JOIN emojis e ON r.emoji_id = e.id
            GROUP BY e.id
            ORDER BY usage_count DESC
            LIMIT 10
        """))

        for row in result:
            print(f"  {row[0]}: {row[1]} uses")

        # 5. Channel activity
        print("\n📢 Channel Activity:")
        print("-" * 40)
        result = conn.execute(text("""
            SELECT c.name, COUNT(*) as message_count
            FROM messages m
            JOIN channels c ON m.channel_id = c.id
            WHERE m.server_id = :server_id
            GROUP BY c.id
            ORDER BY message_count DESC
        """), {"server_id": server_id})

        for row in result:
            print(f"  #{row[0]}: {row[1]} messages")

        # 6. Mention patterns
        print("\n📣 Most Mentioned Users:")
        print("-" * 40)
        result = conn.execute(text("""
            SELECT u.username, COUNT(*) as mention_count
            FROM message_mentions mm
            JOIN users u ON mm.mentioned_user_id = u.id
            GROUP BY u.id
            ORDER BY mention_count DESC
            LIMIT 10
        """))

        for row in result:
            print(f"  @{row[0]}: {row[1]} mentions")


async def main():
    parser = argparse.ArgumentParser(description="Run Discord SQL simulation")
    parser.add_argument("--users", type=int, default=50, help="Number of users")
    parser.add_argument("--channels", type=int, default=5, help="Number of channels")
    parser.add_argument("--messages", type=int, default=200, help="Messages per channel")
    parser.add_argument("--days", type=int, default=7, help="Days of history")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--db", type=str, default="simulation.db", help="Database file")
    args = parser.parse_args()

    print("=" * 60)
    print("DISCORD SQL ANALYTICS SIMULATION")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Users: {args.users}")
    print(f"  Channels: {args.channels}")
    print(f"  Messages per channel: {args.messages}")
    print(f"  Days of history: {args.days}")
    print(f"  Random seed: {args.seed}")
    print(f"  Database: {args.db}")

    # Setup database
    print(f"\n📦 Setting up database...")
    engine = setup_database(args.db)

    # Generate mock data
    print(f"\n🎲 Generating mock Discord data...")
    start_time = datetime.now()

    client = create_mock_client(
        user_count=args.users,
        channel_count=args.channels,
        messages_per_channel=args.messages,
        days=args.days,
        seed=args.seed,
    )

    guild = client.guilds[0]
    total_messages = sum(len(ch._messages) for ch in guild._channels)
    total_reactions = sum(
        sum(len(r._users) for r in m.reactions)
        for ch in guild._channels
        for m in ch._messages
    )

    print(f"  Generated {len(guild._members)} users")
    print(f"  Generated {len(guild._channels)} channels")
    print(f"  Generated {total_messages} messages")
    print(f"  Generated ~{total_reactions} reactions")

    gen_time = (datetime.now() - start_time).total_seconds()
    print(f"  Generation time: {gen_time:.2f}s")

    # Run extraction
    print(f"\n⚙️ Running extraction pipeline...")
    start_time = datetime.now()

    stats = await run_extraction(
        client=client,
        engine=engine,
        guild_id=guild.id,
        sync_days=args.days,
        fetch_reactions=True,
    )

    extract_time = (datetime.now() - start_time).total_seconds()
    print(f"\n  Extraction complete in {extract_time:.2f}s")
    print(f"  Stats: {stats}")

    # Run analytics
    run_analytics_queries(engine, guild.id)

    print("\n" + "=" * 60)
    print(f"Simulation complete! Data stored in: {args.db}")
    print("=" * 60)

    # Print example queries user can run
    print("\n📝 Example SQL queries you can run:")
    print(f"\n  sqlite3 {args.db}")
    print("""
  -- Who talks to whom most (via replies)
  SELECT author.username, replied_to.username, COUNT(*)
  FROM messages m
  JOIN messages orig ON m.reply_to_message_id = orig.id
  JOIN users author ON m.author_id = author.id
  JOIN users replied_to ON orig.author_id = replied_to.id
  WHERE m.author_id != orig.author_id
  GROUP BY author.id, replied_to.id
  ORDER BY COUNT(*) DESC LIMIT 10;

  -- Most active hours
  SELECT strftime('%H', created_at) as hour, COUNT(*)
  FROM messages GROUP BY hour ORDER BY COUNT(*) DESC;

  -- Reaction network
  SELECT reactor.username, author.username, COUNT(*)
  FROM reactions r
  JOIN messages m ON r.message_id = m.id
  JOIN users reactor ON r.user_id = reactor.id
  JOIN users author ON m.author_id = author.id
  WHERE r.user_id != m.author_id
  GROUP BY reactor.id, author.id
  ORDER BY COUNT(*) DESC LIMIT 10;
    """)


if __name__ == "__main__":
    asyncio.run(main())
