"""
Direct query tests for Analytics API.

Tests each SQL query used in the analytics API against real database data.
Run with: ./venv/bin/python tests/test_analytics_queries.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Need to set up test tenant for RLS
TEST_TENANT_ID = "user_test_analytics_queries"


async def run_query_tests():
    """Run all analytics queries against real database data."""
    from services.shared_database import get_shared_pool
    from services.tenant import tenant_connection

    print("=" * 70)
    print("Testing Analytics Queries Against Real Database Data")
    print("=" * 70)

    pool = await get_shared_pool()

    # First, find an actual tenant that has data
    async with pool.acquire() as conn:
        # Find a tenant with messages
        result = await conn.fetchrow("""
            SELECT DISTINCT tenant_id FROM messages LIMIT 1
        """)
        if not result:
            print("ERROR: No messages found in database. Cannot test queries.")
            return False

        actual_tenant_id = result['tenant_id']
        print(f"\nFound tenant with data: {actual_tenant_id}")

    # Now test with RLS using the actual tenant
    async with tenant_connection(pool, actual_tenant_id) as conn:
        now = datetime.utcnow()
        days = 30
        start_date = now - timedelta(days=days)
        prev_start = start_date - timedelta(days=days)

        all_passed = True

        # =====================================================================
        # QUERY 1: Overview Stats
        # =====================================================================
        print("\n" + "-" * 70)
        print("[1/11] Testing OVERVIEW STATS query...")
        try:
            overview_query = """
            WITH current_period AS (
                SELECT
                    COUNT(*) as msg_count,
                    COUNT(DISTINCT author_id) as user_count,
                    AVG(char_count) as avg_length,
                    SUM(word_count) as total_words
                FROM messages
                WHERE created_at >= $1
            ),
            prev_period AS (
                SELECT COUNT(*) as msg_count, COUNT(DISTINCT author_id) as user_count
                FROM messages
                WHERE created_at >= $2 AND created_at < $1
            ),
            channels AS (
                SELECT COUNT(*) as channel_count FROM channels
            ),
            mentions AS (
                SELECT COUNT(*) as mention_count FROM message_mentions
                WHERE message_id IN (SELECT id FROM messages WHERE created_at >= $1)
            )
            SELECT
                COALESCE(cp.msg_count, 0) as total_messages,
                COALESCE(cp.user_count, 0) as total_users,
                COALESCE(c.channel_count, 0) as total_channels,
                COALESCE(m.mention_count, 0) as total_mentions,
                COALESCE(cp.avg_length, 0) as avg_length,
                COALESCE(pp.msg_count, 0) as prev_messages,
                COALESCE(pp.user_count, 0) as prev_users
            FROM current_period cp, prev_period pp, channels c, mentions m
            """
            row = await conn.fetchrow(overview_query, start_date, prev_start)
            print(f"   Total messages: {row['total_messages']}")
            print(f"   Total users: {row['total_users']}")
            print(f"   Total channels: {row['total_channels']}")
            print(f"   Total mentions: {row['total_mentions']}")
            print(f"   Avg length: {row['avg_length']}")
            print(f"   Prev messages: {row['prev_messages']}")
            print(f"   Prev users: {row['prev_users']}")
            print("   ✓ PASSED")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            all_passed = False

        # =====================================================================
        # QUERY 2: Messages Over Time
        # =====================================================================
        print("\n" + "-" * 70)
        print("[2/11] Testing MESSAGES OVER TIME query...")
        try:
            time_series_query = """
            SELECT
                DATE(created_at) as date,
                COUNT(*) as count
            FROM messages
            WHERE created_at >= $1
            GROUP BY DATE(created_at)
            ORDER BY date
            """
            rows = await conn.fetch(time_series_query, start_date)
            print(f"   Returned {len(rows)} date points")
            if rows:
                print(f"   First date: {rows[0]['date']} ({rows[0]['count']} messages)")
                print(f"   Last date: {rows[-1]['date']} ({rows[-1]['count']} messages)")
            print("   ✓ PASSED")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            all_passed = False

        # =====================================================================
        # QUERY 3: Hourly Activity
        # =====================================================================
        print("\n" + "-" * 70)
        print("[3/11] Testing HOURLY ACTIVITY query...")
        try:
            hourly_query = """
            SELECT
                EXTRACT(HOUR FROM created_at)::int as hour,
                COUNT(*) as message_count,
                COUNT(DISTINCT author_id) as unique_users
            FROM messages
            WHERE created_at >= $1
            GROUP BY hour
            ORDER BY hour
            """
            rows = await conn.fetch(hourly_query, start_date)
            print(f"   Returned {len(rows)} hours with activity")
            if rows:
                peak = max(rows, key=lambda x: x['message_count'])
                print(f"   Peak hour: {peak['hour']}:00 ({peak['message_count']} msgs, {peak['unique_users']} users)")
            print("   ✓ PASSED")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            all_passed = False

        # =====================================================================
        # QUERY 4: Day of Week Activity
        # =====================================================================
        print("\n" + "-" * 70)
        print("[4/11] Testing DAY OF WEEK ACTIVITY query...")
        try:
            dow_query = """
            SELECT
                EXTRACT(DOW FROM created_at)::int as day,
                COUNT(*) as message_count
            FROM messages
            WHERE created_at >= $1
            GROUP BY day
            ORDER BY day
            """
            rows = await conn.fetch(dow_query, start_date)
            day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            print(f"   Returned {len(rows)} days with activity")
            for row in rows:
                print(f"     {day_names[row['day']]}: {row['message_count']} messages")
            print("   ✓ PASSED")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            all_passed = False

        # =====================================================================
        # QUERY 5: Top Channels
        # =====================================================================
        print("\n" + "-" * 70)
        print("[5/11] Testing TOP CHANNELS query...")
        try:
            channels_query = """
            SELECT
                c.id::text as channel_id,
                c.name as channel_name,
                COUNT(m.id) as message_count,
                COUNT(DISTINCT m.author_id) as unique_users,
                AVG(m.char_count) as avg_length
            FROM channels c
            LEFT JOIN messages m ON c.id = m.channel_id AND m.created_at >= $1
            GROUP BY c.id, c.name
            ORDER BY message_count DESC
            LIMIT 10
            """
            rows = await conn.fetch(channels_query, start_date)
            print(f"   Returned {len(rows)} channels")
            for row in rows[:5]:
                print(f"     #{row['channel_name']}: {row['message_count']} msgs, {row['unique_users']} users")
            print("   ✓ PASSED")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            all_passed = False

        # =====================================================================
        # QUERY 6: Top Users
        # =====================================================================
        print("\n" + "-" * 70)
        print("[6/11] Testing TOP USERS query...")
        try:
            users_query = """
            SELECT
                u.id::text as user_id,
                u.username,
                u.is_bot,
                COUNT(m.id) as message_count,
                AVG(m.char_count) as avg_length,
                (SELECT COUNT(*) FROM message_mentions mm
                 JOIN messages msg ON mm.message_id = msg.id
                 WHERE mm.mentioned_user_id = u.id AND msg.created_at >= $1) as mention_count,
                (SELECT COUNT(*) FROM messages r
                 WHERE r.reply_to_author_id = u.id AND r.created_at >= $1) as reply_count
            FROM users u
            LEFT JOIN messages m ON u.id = m.author_id AND m.created_at >= $1
            GROUP BY u.id, u.username, u.is_bot
            HAVING COUNT(m.id) > 0
            ORDER BY message_count DESC
            LIMIT 15
            """
            rows = await conn.fetch(users_query, start_date)
            print(f"   Returned {len(rows)} active users")
            for row in rows[:5]:
                bot_tag = " [BOT]" if row['is_bot'] else ""
                print(f"     {row['username']}{bot_tag}: {row['message_count']} msgs, {row['mention_count']} mentions, {row['reply_count']} replies")
            print("   ✓ PASSED")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            all_passed = False

        # =====================================================================
        # QUERY 7: User Interactions
        # =====================================================================
        print("\n" + "-" * 70)
        print("[7/11] Testing USER INTERACTIONS query...")
        try:
            interactions_query = """
            WITH mention_interactions AS (
                SELECT
                    m.author_id as from_user,
                    mm.mentioned_user_id as to_user,
                    COUNT(*) as mention_count
                FROM messages m
                JOIN message_mentions mm ON m.id = mm.message_id
                WHERE m.created_at >= $1 AND m.author_id != mm.mentioned_user_id
                GROUP BY m.author_id, mm.mentioned_user_id
            ),
            reply_interactions AS (
                SELECT
                    author_id as from_user,
                    reply_to_author_id as to_user,
                    COUNT(*) as reply_count
                FROM messages
                WHERE created_at >= $1
                  AND reply_to_author_id IS NOT NULL
                  AND author_id != reply_to_author_id
                GROUP BY author_id, reply_to_author_id
            )
            SELECT
                COALESCE(fu.username, mi.from_user::text) as from_user,
                COALESCE(tu.username, COALESCE(mi.to_user, ri.to_user)::text) as to_user,
                COALESCE(mi.mention_count, 0) as mention_count,
                COALESCE(ri.reply_count, 0) as reply_count
            FROM mention_interactions mi
            FULL OUTER JOIN reply_interactions ri
                ON mi.from_user = ri.from_user AND mi.to_user = ri.to_user
            LEFT JOIN users fu ON COALESCE(mi.from_user, ri.from_user) = fu.id
            LEFT JOIN users tu ON COALESCE(mi.to_user, ri.to_user) = tu.id
            ORDER BY (COALESCE(mi.mention_count, 0) + COALESCE(ri.reply_count, 0)) DESC
            LIMIT 20
            """
            rows = await conn.fetch(interactions_query, start_date)
            print(f"   Returned {len(rows)} user interactions")
            for row in rows[:5]:
                print(f"     {row['from_user']} -> {row['to_user']}: {row['mention_count']} mentions, {row['reply_count']} replies")
            print("   ✓ PASSED")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            all_passed = False

        # =====================================================================
        # QUERY 8: Content Metrics
        # =====================================================================
        print("\n" + "-" * 70)
        print("[8/11] Testing CONTENT METRICS query...")
        try:
            content_query = """
            SELECT
                COALESCE(SUM(word_count), 0) as total_words,
                COALESCE(SUM(char_count), 0) as total_chars,
                COALESCE(AVG(word_count), 0) as avg_words,
                COUNT(*) FILTER (WHERE attachment_count > 0) as with_attachments,
                COUNT(*) FILTER (WHERE embed_count > 0) as with_embeds,
                COUNT(*) FILTER (WHERE mention_count > 0) as with_mentions,
                COUNT(*) FILTER (WHERE is_pinned = true) as pinned
            FROM messages
            WHERE created_at >= $1
            """
            row = await conn.fetchrow(content_query, start_date)
            print(f"   Total words: {row['total_words']}")
            print(f"   Total chars: {row['total_chars']}")
            print(f"   Avg words/msg: {row['avg_words']:.1f}")
            print(f"   With attachments: {row['with_attachments']}")
            print(f"   With embeds: {row['with_embeds']}")
            print(f"   With mentions: {row['with_mentions']}")
            print(f"   Pinned: {row['pinned']}")
            print("   ✓ PASSED")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            all_passed = False

        # =====================================================================
        # QUERY 9: Engagement Metrics
        # =====================================================================
        print("\n" + "-" * 70)
        print("[9/11] Testing ENGAGEMENT METRICS query...")
        try:
            engagement_query = """
            WITH msg_stats AS (
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE reply_to_message_id IS NOT NULL) as replies,
                    COUNT(*) FILTER (WHERE mention_count > 0) as with_mentions,
                    COUNT(DISTINCT author_id) as active_users
                FROM messages
                WHERE created_at >= $1
            ),
            total_users AS (
                SELECT COUNT(*) as count FROM users
            )
            SELECT
                ms.total,
                ms.replies,
                ms.with_mentions,
                ms.active_users,
                tu.count as total_users
            FROM msg_stats ms, total_users tu
            """
            row = await conn.fetchrow(engagement_query, start_date)
            total_msg = max(row['total'], 1)
            total_usr = max(row['total_users'], 1)
            active_usr = row['active_users']

            reply_rate = (row['replies'] / total_msg) * 100
            mention_rate = (row['with_mentions'] / total_msg) * 100
            active_ratio = (active_usr / total_usr) * 100
            msgs_per_user = total_msg / max(active_usr, 1)

            print(f"   Total messages: {row['total']}")
            print(f"   Replies: {row['replies']} ({reply_rate:.1f}%)")
            print(f"   With mentions: {row['with_mentions']} ({mention_rate:.1f}%)")
            print(f"   Active users: {row['active_users']} / {row['total_users']} ({active_ratio:.1f}%)")
            print(f"   Msgs/active user: {msgs_per_user:.1f}")
            print("   ✓ PASSED")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            all_passed = False

        # =====================================================================
        # QUERY 10: Channel Growth
        # =====================================================================
        print("\n" + "-" * 70)
        print("[10/11] Testing CHANNEL GROWTH query...")
        try:
            growth_query = """
            WITH current_period AS (
                SELECT channel_id, COUNT(*) as count
                FROM messages
                WHERE created_at >= $1
                GROUP BY channel_id
            ),
            prev_period AS (
                SELECT channel_id, COUNT(*) as count
                FROM messages
                WHERE created_at >= $2 AND created_at < $1
                GROUP BY channel_id
            )
            SELECT
                c.name as channel_name,
                COALESCE(cp.count, 0) as current_count,
                COALESCE(pp.count, 0) as prev_count
            FROM channels c
            LEFT JOIN current_period cp ON c.id = cp.channel_id
            LEFT JOIN prev_period pp ON c.id = pp.channel_id
            WHERE COALESCE(cp.count, 0) > 0 OR COALESCE(pp.count, 0) > 0
            ORDER BY current_count DESC
            LIMIT 10
            """
            rows = await conn.fetch(growth_query, start_date, prev_start)
            print(f"   Returned {len(rows)} channels with growth data")
            for row in rows[:5]:
                prev = row['prev_count']
                curr = row['current_count']
                if prev > 0:
                    growth = ((curr - prev) / prev) * 100
                else:
                    growth = 0
                print(f"     #{row['channel_name']}: {prev} -> {curr} ({growth:+.1f}%)")
            print("   ✓ PASSED")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            all_passed = False

        # =====================================================================
        # QUERY 11: Bot vs Human
        # =====================================================================
        print("\n" + "-" * 70)
        print("[11/11] Testing BOT VS HUMAN query...")
        try:
            bot_query = """
            SELECT
                u.is_bot,
                COUNT(m.id) as message_count
            FROM messages m
            JOIN users u ON m.author_id = u.id
            WHERE m.created_at >= $1
            GROUP BY u.is_bot
            """
            rows = await conn.fetch(bot_query, start_date)
            human_msgs = 0
            bot_msgs = 0
            for row in rows:
                if row['is_bot']:
                    bot_msgs = row['message_count']
                else:
                    human_msgs = row['message_count']

            total = human_msgs + bot_msgs
            if total > 0:
                human_pct = (human_msgs / total) * 100
                bot_pct = (bot_msgs / total) * 100
            else:
                human_pct = bot_pct = 0

            print(f"   Human messages: {human_msgs} ({human_pct:.1f}%)")
            print(f"   Bot messages: {bot_msgs} ({bot_pct:.1f}%)")
            print("   ✓ PASSED")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            all_passed = False

        # =====================================================================
        # Final Summary
        # =====================================================================
        print("\n" + "=" * 70)
        if all_passed:
            print("ALL 11 ANALYTICS QUERIES PASSED ✓")
        else:
            print("SOME QUERIES FAILED ✗")
        print("=" * 70)

        return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_query_tests())
    sys.exit(0 if success else 1)
