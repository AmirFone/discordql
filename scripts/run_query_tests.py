#!/usr/bin/env python3
"""
Comprehensive SQL Query Validation Tests for Discord Data.

Runs 40 queries across 8 categories to validate data integrity and query correctness.
Saves all results to query_results.txt for review.
"""
import os
import sys
import sqlite3
from datetime import datetime
from typing import List, Tuple, Any

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "discord_data.db")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "query_results.txt")


# ============================================================================
# QUERY DEFINITIONS (40 queries)
# ============================================================================

QUERIES = [
    # ==========================================================================
    # CATEGORY 1: Basic Counts & Validation (5 queries)
    # ==========================================================================
    (
        "Total count of each table",
        """
        SELECT 'servers' as table_name, COUNT(*) as count FROM servers
        UNION ALL SELECT 'users', COUNT(*) FROM users
        UNION ALL SELECT 'channels', COUNT(*) FROM channels
        UNION ALL SELECT 'server_members', COUNT(*) FROM server_members
        UNION ALL SELECT 'messages', COUNT(*) FROM messages
        UNION ALL SELECT 'message_mentions', COUNT(*) FROM message_mentions
        UNION ALL SELECT 'emojis', COUNT(*) FROM emojis
        UNION ALL SELECT 'reactions', COUNT(*) FROM reactions
        UNION ALL SELECT 'sync_state', COUNT(*) FROM sync_state
        """
    ),
    (
        "Verify all messages have valid author_id (FK check)",
        """
        SELECT COUNT(*) as orphan_messages
        FROM messages m
        LEFT JOIN users u ON m.author_id = u.id
        WHERE u.id IS NULL
        """
    ),
    (
        "Verify all reactions have valid message_id",
        """
        SELECT COUNT(*) as orphan_reactions
        FROM reactions r
        LEFT JOIN messages m ON r.message_id = m.id
        WHERE m.id IS NULL
        """
    ),
    (
        "Verify all mentions have valid message_id",
        """
        SELECT COUNT(*) as orphan_mentions
        FROM message_mentions mm
        LEFT JOIN messages m ON mm.message_id = m.id
        WHERE m.id IS NULL
        """
    ),
    (
        "Check for orphan channel references in messages",
        """
        SELECT COUNT(*) as orphan_channel_refs
        FROM messages m
        LEFT JOIN channels c ON m.channel_id = c.id
        WHERE c.id IS NULL
        """
    ),

    # ==========================================================================
    # CATEGORY 2: User Activity (6 queries)
    # ==========================================================================
    (
        "Top 10 most active users by message count",
        """
        SELECT
            u.username,
            u.global_name,
            COUNT(m.id) as message_count
        FROM users u
        LEFT JOIN messages m ON u.id = m.author_id
        GROUP BY u.id
        ORDER BY message_count DESC
        LIMIT 10
        """
    ),
    (
        "Users by reaction count given (who reacts most)",
        """
        SELECT
            u.username,
            u.global_name,
            COUNT(r.user_id) as reactions_given
        FROM users u
        LEFT JOIN reactions r ON u.id = r.user_id
        GROUP BY u.id
        ORDER BY reactions_given DESC
        LIMIT 10
        """
    ),
    (
        "Users by reaction count received (most reacted to)",
        """
        SELECT
            u.username,
            u.global_name,
            COUNT(r.message_id) as reactions_received
        FROM users u
        LEFT JOIN messages m ON u.id = m.author_id
        LEFT JOIN reactions r ON m.id = r.message_id
        GROUP BY u.id
        ORDER BY reactions_received DESC
        LIMIT 10
        """
    ),
    (
        "Users by mentions given (who mentions others most)",
        """
        SELECT
            u.username,
            u.global_name,
            COUNT(mm.message_id) as mentions_given
        FROM users u
        LEFT JOIN messages m ON u.id = m.author_id
        LEFT JOIN message_mentions mm ON m.id = mm.message_id
        GROUP BY u.id
        ORDER BY mentions_given DESC
        LIMIT 10
        """
    ),
    (
        "Users by mentions received (most mentioned)",
        """
        SELECT
            u.username,
            u.global_name,
            COUNT(mm.mentioned_user_id) as mentions_received
        FROM users u
        LEFT JOIN message_mentions mm ON u.id = mm.mentioned_user_id
        GROUP BY u.id
        ORDER BY mentions_received DESC
        LIMIT 10
        """
    ),
    (
        "Bot vs human message distribution",
        """
        SELECT
            CASE WHEN u.is_bot = 1 THEN 'Bot' ELSE 'Human' END as user_type,
            COUNT(m.id) as message_count,
            COUNT(DISTINCT m.author_id) as unique_users
        FROM messages m
        JOIN users u ON m.author_id = u.id
        GROUP BY u.is_bot
        """
    ),

    # ==========================================================================
    # CATEGORY 3: Channel Analytics (5 queries)
    # ==========================================================================
    (
        "Messages per channel (all channels)",
        """
        SELECT
            c.name as channel_name,
            COUNT(m.id) as message_count
        FROM channels c
        LEFT JOIN messages m ON c.id = m.channel_id
        GROUP BY c.id
        ORDER BY message_count DESC
        """
    ),
    (
        "Most active channels (last 7 days)",
        """
        SELECT
            c.name as channel_name,
            COUNT(m.id) as message_count
        FROM channels c
        LEFT JOIN messages m ON c.id = m.channel_id
        WHERE m.created_at >= datetime('now', '-7 days')
        GROUP BY c.id
        ORDER BY message_count DESC
        LIMIT 10
        """
    ),
    (
        "Channels with most reactions",
        """
        SELECT
            c.name as channel_name,
            COUNT(r.message_id) as reaction_count
        FROM channels c
        LEFT JOIN messages m ON c.id = m.channel_id
        LEFT JOIN reactions r ON m.id = r.message_id
        GROUP BY c.id
        ORDER BY reaction_count DESC
        LIMIT 10
        """
    ),
    (
        "Channels with most mentions",
        """
        SELECT
            c.name as channel_name,
            COUNT(mm.message_id) as mention_count
        FROM channels c
        LEFT JOIN messages m ON c.id = m.channel_id
        LEFT JOIN message_mentions mm ON m.id = mm.message_id
        GROUP BY c.id
        ORDER BY mention_count DESC
        LIMIT 10
        """
    ),
    (
        "Empty channels (no messages in last 30 days)",
        """
        SELECT
            c.name as channel_name,
            c.type as channel_type
        FROM channels c
        LEFT JOIN messages m ON c.id = m.channel_id
            AND m.created_at >= datetime('now', '-30 days')
        WHERE m.id IS NULL
        ORDER BY c.name
        """
    ),

    # ==========================================================================
    # CATEGORY 4: Message Content Analysis (5 queries)
    # ==========================================================================
    (
        "Average message length (word_count, char_count)",
        """
        SELECT
            AVG(word_count) as avg_words,
            AVG(char_count) as avg_chars,
            MIN(word_count) as min_words,
            MAX(word_count) as max_words,
            MIN(char_count) as min_chars,
            MAX(char_count) as max_chars
        FROM messages
        WHERE content IS NOT NULL AND content != ''
        """
    ),
    (
        "Messages with attachments",
        """
        SELECT
            COUNT(*) as total_with_attachments,
            SUM(attachment_count) as total_attachments,
            AVG(attachment_count) as avg_attachments_per_message
        FROM messages
        WHERE attachment_count > 0
        """
    ),
    (
        "Messages with embeds",
        """
        SELECT
            COUNT(*) as total_with_embeds,
            SUM(embed_count) as total_embeds,
            AVG(embed_count) as avg_embeds_per_message
        FROM messages
        WHERE embed_count > 0
        """
    ),
    (
        "Longest messages (top 10 by word count)",
        """
        SELECT
            u.username,
            c.name as channel,
            m.word_count,
            m.char_count,
            SUBSTR(m.content, 1, 50) as content_preview
        FROM messages m
        JOIN users u ON m.author_id = u.id
        JOIN channels c ON m.channel_id = c.id
        WHERE m.word_count IS NOT NULL
        ORDER BY m.word_count DESC
        LIMIT 10
        """
    ),
    (
        "Empty messages (no content but may have attachments/embeds)",
        """
        SELECT
            COUNT(*) as empty_content_count,
            SUM(CASE WHEN attachment_count > 0 THEN 1 ELSE 0 END) as with_attachments,
            SUM(CASE WHEN embed_count > 0 THEN 1 ELSE 0 END) as with_embeds
        FROM messages
        WHERE content IS NULL OR content = ''
        """
    ),

    # ==========================================================================
    # CATEGORY 5: Reply Patterns (5 queries)
    # ==========================================================================
    (
        "Count of reply messages vs regular",
        """
        SELECT
            CASE
                WHEN reply_to_message_id IS NOT NULL THEN 'Reply'
                ELSE 'Original'
            END as message_type,
            COUNT(*) as count
        FROM messages
        GROUP BY (reply_to_message_id IS NOT NULL)
        """
    ),
    (
        "Top reply relationships (who replies to whom)",
        """
        SELECT
            author.username as replier,
            replied_to.username as replied_to_user,
            COUNT(*) as reply_count
        FROM messages m
        JOIN users author ON m.author_id = author.id
        JOIN messages orig ON m.reply_to_message_id = orig.id
        JOIN users replied_to ON orig.author_id = replied_to.id
        WHERE m.reply_to_message_id IS NOT NULL
        GROUP BY author.id, replied_to.id
        ORDER BY reply_count DESC
        LIMIT 15
        """
    ),
    (
        "Self-replies count (users replying to themselves)",
        """
        SELECT
            COUNT(*) as self_reply_count
        FROM messages m
        JOIN messages orig ON m.reply_to_message_id = orig.id
        WHERE m.author_id = orig.author_id
        """
    ),
    (
        "Users who reply most (total replies sent)",
        """
        SELECT
            u.username,
            u.global_name,
            COUNT(*) as replies_sent
        FROM messages m
        JOIN users u ON m.author_id = u.id
        WHERE m.reply_to_message_id IS NOT NULL
        GROUP BY u.id
        ORDER BY replies_sent DESC
        LIMIT 10
        """
    ),
    (
        "Most replied-to users (received most replies)",
        """
        SELECT
            u.username,
            u.global_name,
            COUNT(*) as replies_received
        FROM messages m
        JOIN messages orig ON m.reply_to_message_id = orig.id
        JOIN users u ON orig.author_id = u.id
        WHERE m.reply_to_message_id IS NOT NULL
        GROUP BY u.id
        ORDER BY replies_received DESC
        LIMIT 10
        """
    ),

    # ==========================================================================
    # CATEGORY 6: Reaction Analysis (5 queries)
    # ==========================================================================
    (
        "Most used emojis (top 15)",
        """
        SELECT
            e.name as emoji,
            e.is_custom,
            COUNT(r.emoji_id) as usage_count
        FROM emojis e
        LEFT JOIN reactions r ON e.id = r.emoji_id
        GROUP BY e.id
        ORDER BY usage_count DESC
        LIMIT 15
        """
    ),
    (
        "Custom vs unicode emoji usage",
        """
        SELECT
            CASE WHEN e.is_custom = 1 THEN 'Custom' ELSE 'Unicode' END as emoji_type,
            COUNT(r.emoji_id) as usage_count,
            COUNT(DISTINCT e.id) as unique_emojis
        FROM emojis e
        LEFT JOIN reactions r ON e.id = r.emoji_id
        GROUP BY e.is_custom
        """
    ),
    (
        "Most reacted messages (top 10)",
        """
        SELECT
            u.username as author,
            c.name as channel,
            COUNT(r.message_id) as reaction_count,
            SUBSTR(m.content, 1, 50) as content_preview
        FROM messages m
        JOIN users u ON m.author_id = u.id
        JOIN channels c ON m.channel_id = c.id
        LEFT JOIN reactions r ON m.id = r.message_id
        GROUP BY m.id
        HAVING reaction_count > 0
        ORDER BY reaction_count DESC
        LIMIT 10
        """
    ),
    (
        "Users who react most (top 10)",
        """
        SELECT
            u.username,
            u.global_name,
            COUNT(*) as total_reactions,
            COUNT(DISTINCT r.emoji_id) as unique_emojis_used
        FROM reactions r
        JOIN users u ON r.user_id = u.id
        GROUP BY u.id
        ORDER BY total_reactions DESC
        LIMIT 10
        """
    ),
    (
        "Self-reactions count (users reacting to own messages)",
        """
        SELECT
            COUNT(*) as self_reaction_count
        FROM reactions r
        JOIN messages m ON r.message_id = m.id
        WHERE r.user_id = m.author_id
        """
    ),

    # ==========================================================================
    # CATEGORY 7: Mention Analysis (4 queries)
    # ==========================================================================
    (
        "Most mentioned users (top 10)",
        """
        SELECT
            u.username,
            u.global_name,
            COUNT(*) as times_mentioned
        FROM message_mentions mm
        JOIN users u ON mm.mentioned_user_id = u.id
        GROUP BY u.id
        ORDER BY times_mentioned DESC
        LIMIT 10
        """
    ),
    (
        "Users who mention others most (top 10)",
        """
        SELECT
            u.username,
            u.global_name,
            COUNT(DISTINCT mm.mentioned_user_id) as unique_users_mentioned,
            COUNT(*) as total_mentions
        FROM messages m
        JOIN users u ON m.author_id = u.id
        JOIN message_mentions mm ON m.id = mm.message_id
        GROUP BY u.id
        ORDER BY total_mentions DESC
        LIMIT 10
        """
    ),
    (
        "Self-mentions count",
        """
        SELECT
            COUNT(*) as self_mention_count
        FROM message_mentions mm
        JOIN messages m ON mm.message_id = m.id
        WHERE mm.mentioned_user_id = m.author_id
        """
    ),
    (
        "@everyone mentions (mentions_everyone flag)",
        """
        SELECT
            COUNT(*) as everyone_mention_count,
            u.username as author
        FROM messages m
        JOIN users u ON m.author_id = u.id
        WHERE m.mentions_everyone = 1
        GROUP BY m.author_id
        ORDER BY everyone_mention_count DESC
        """
    ),

    # ==========================================================================
    # CATEGORY 8: Time-Based Analysis (5 queries)
    # ==========================================================================
    (
        "Messages by hour of day",
        """
        SELECT
            strftime('%H', created_at) as hour,
            COUNT(*) as message_count
        FROM messages
        GROUP BY hour
        ORDER BY hour
        """
    ),
    (
        "Messages by day of week",
        """
        SELECT
            CASE strftime('%w', created_at)
                WHEN '0' THEN 'Sunday'
                WHEN '1' THEN 'Monday'
                WHEN '2' THEN 'Tuesday'
                WHEN '3' THEN 'Wednesday'
                WHEN '4' THEN 'Thursday'
                WHEN '5' THEN 'Friday'
                WHEN '6' THEN 'Saturday'
            END as day_of_week,
            COUNT(*) as message_count
        FROM messages
        GROUP BY strftime('%w', created_at)
        ORDER BY strftime('%w', created_at)
        """
    ),
    (
        "Most active dates (top 10)",
        """
        SELECT
            date(created_at) as date,
            COUNT(*) as message_count
        FROM messages
        GROUP BY date(created_at)
        ORDER BY message_count DESC
        LIMIT 10
        """
    ),
    (
        "First and last message timestamps",
        """
        SELECT
            MIN(created_at) as first_message,
            MAX(created_at) as last_message,
            julianday(MAX(created_at)) - julianday(MIN(created_at)) as days_span
        FROM messages
        """
    ),
    (
        "Activity trend (messages per day, last 14 days)",
        """
        SELECT
            date(created_at) as date,
            COUNT(*) as message_count
        FROM messages
        WHERE created_at >= datetime('now', '-14 days')
        GROUP BY date(created_at)
        ORDER BY date
        """
    ),
]


def run_query(cursor: sqlite3.Cursor, query: str) -> Tuple[List[str], List[Tuple[Any, ...]], str]:
    """
    Execute a query and return column names, results, and any error.
    """
    try:
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        results = cursor.fetchall()
        return columns, results, ""
    except Exception as e:
        return [], [], str(e)


def format_results(columns: List[str], results: List[Tuple[Any, ...]], error: str) -> str:
    """
    Format query results as a readable string.
    """
    if error:
        return f"ERROR: {error}\n"

    if not results:
        return "No results returned.\n"

    # Calculate column widths
    col_widths = []
    for i, col in enumerate(columns):
        max_width = len(col)
        for row in results:
            val_str = str(row[i]) if row[i] is not None else "NULL"
            max_width = max(max_width, min(len(val_str), 50))  # Cap at 50 chars
        col_widths.append(max_width)

    # Build output
    lines = []

    # Header
    header = " | ".join(col.ljust(col_widths[i]) for i, col in enumerate(columns))
    lines.append(header)
    lines.append("-" * len(header))

    # Rows
    for row in results:
        row_str = " | ".join(
            (str(val) if val is not None else "NULL")[:col_widths[i]].ljust(col_widths[i])
            for i, val in enumerate(row)
        )
        lines.append(row_str)

    lines.append(f"\n({len(results)} rows returned)")
    return "\n".join(lines) + "\n"


def main():
    """
    Run all queries and save results to file.
    """
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Build output
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("DISCORD SQL QUERY VALIDATION REPORT")
    output_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output_lines.append(f"Database: {DB_PATH}")
    output_lines.append("=" * 80)
    output_lines.append("")

    errors = []
    success_count = 0

    for i, (name, query) in enumerate(QUERIES, 1):
        print(f"Running query {i}/{len(QUERIES)}: {name}")

        output_lines.append(f"QUERY #{i}: {name}")
        output_lines.append("-" * 80)

        columns, results, error = run_query(cursor, query)
        formatted = format_results(columns, results, error)
        output_lines.append(formatted)
        output_lines.append("")

        if error:
            errors.append((i, name, error))
        else:
            success_count += 1

    # Summary
    output_lines.append("=" * 80)
    output_lines.append("SUMMARY")
    output_lines.append("=" * 80)
    output_lines.append(f"Total queries: {len(QUERIES)}")
    output_lines.append(f"Successful: {success_count}")
    output_lines.append(f"Errors: {len(errors)}")
    output_lines.append("")

    if errors:
        output_lines.append("ERRORS:")
        for num, name, err in errors:
            output_lines.append(f"  Query #{num} ({name}): {err}")
    else:
        output_lines.append("All queries executed successfully!")

    # Write to file
    output_text = "\n".join(output_lines)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(output_text)

    print(f"\nResults saved to: {OUTPUT_PATH}")
    print(f"Total: {len(QUERIES)} queries, {success_count} successful, {len(errors)} errors")

    conn.close()

    # Return exit code based on errors
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
