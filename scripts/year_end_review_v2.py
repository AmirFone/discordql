#!/usr/bin/env python3
"""
Discord Year-End Review V2 - Creative Analytics Edition

Generates deeply insightful analytics about community dynamics,
relationship patterns, and behavioral insights.

IMPORTANT: Excludes all bots from analytics.

Usage:
    python scripts/year_end_review_v2.py [--db discord_year.db]
"""
import argparse
import os
import sys
from datetime import datetime
from collections import defaultdict
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

# Configuration
DEFAULT_DB = "discord_year.db"
OUTPUT_FILE = "year_end_review_2024.txt"


def run_query(conn, query, params=None):
    """Execute a query and return results as a list of dicts."""
    result = conn.execute(text(query), params or {})
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result]


def section(title):
    """Format a section header."""
    return f"\n{'='*70}\n{title}\n{'='*70}\n"


def subsection(title):
    """Format a subsection header."""
    return f"\n--- {title} ---\n"


def generate_report(engine, output_file):
    """Generate the complete creative year-end review report."""
    report = []

    with engine.connect() as conn:
        # =====================================================================
        # HEADER
        # =====================================================================
        server = run_query(conn, "SELECT name, member_count FROM servers LIMIT 1")
        server_name = server[0]['name'] if server else "Unknown Server"

        # Get stats excluding bots
        stats = run_query(conn, """
            SELECT
                (SELECT COUNT(*) FROM messages m JOIN users u ON m.author_id = u.id WHERE u.is_bot = 0) as total_messages,
                (SELECT COUNT(DISTINCT m.author_id) FROM messages m JOIN users u ON m.author_id = u.id WHERE u.is_bot = 0) as active_users,
                (SELECT COUNT(*) FROM users WHERE is_bot = 0) as total_users,
                (SELECT COUNT(*) FROM users WHERE is_bot = 1) as bot_count
        """)[0]

        report.append(f"""
################################################################################
#                                                                              #
#            {server_name.upper()} - YEAR IN REVIEW 2024                       #
#                        CREATIVE ANALYTICS EDITION                            #
#                                                                              #
################################################################################

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Server: {server_name}

Total Messages (humans only): {stats['total_messages']:,}
Active Human Users: {stats['active_users']}
(Excluded {stats['bot_count']} bots from all analytics)
""")

        # =====================================================================
        # PART 1: RESPONSE DYNAMICS
        # =====================================================================
        report.append(section("PART 1: RESPONSE DYNAMICS"))

        # 1.1 Response Speed Leaderboard
        report.append(subsection("1.1 RESPONSE SPEED LEADERBOARD"))
        response_times = run_query(conn, """
            WITH reply_times AS (
                SELECT
                    m.author_id,
                    orig.author_id as original_author,
                    (julianday(m.created_at) - julianday(orig.created_at)) * 24 * 60 as response_minutes
                FROM messages m
                JOIN messages orig ON m.reply_to_message_id = orig.id
                JOIN users u ON m.author_id = u.id
                WHERE u.is_bot = 0
                  AND m.author_id != orig.author_id
                  AND (julianday(m.created_at) - julianday(orig.created_at)) * 24 * 60 BETWEEN 0.1 AND 1440
            )
            SELECT
                u.username,
                ROUND(AVG(response_minutes), 1) as avg_response_min,
                COUNT(*) as reply_count
            FROM reply_times rt
            JOIN users u ON rt.author_id = u.id
            GROUP BY rt.author_id
            HAVING COUNT(*) >= 10
            ORDER BY avg_response_min ASC
            LIMIT 10
        """)

        report.append("Fastest Fingers (quickest average response time):\n")
        for i, u in enumerate(response_times[:5], 1):
            report.append(f"  {i}. {u['username']}: {u['avg_response_min']:.1f} min avg ({u['reply_count']} replies)\n")

        report.append("\nThe 'I'll Get Back To You' Club (slowest responders):\n")
        slowest = sorted(response_times, key=lambda x: x['avg_response_min'], reverse=True)[:5]
        for i, u in enumerate(slowest, 1):
            report.append(f"  {i}. {u['username']}: {u['avg_response_min']:.1f} min avg\n")

        # 1.2 Left on Read Index
        report.append(subsection("1.2 THE 'LEFT ON READ' INDEX"))
        left_on_read = run_query(conn, """
            WITH mentions_received AS (
                SELECT mm.mentioned_user_id as user_id, COUNT(*) as received
                FROM message_mentions mm
                JOIN users u ON mm.mentioned_user_id = u.id
                WHERE u.is_bot = 0
                GROUP BY mm.mentioned_user_id
            ),
            replies_received AS (
                SELECT orig.author_id as user_id, COUNT(*) as received
                FROM messages m
                JOIN messages orig ON m.reply_to_message_id = orig.id
                JOIN users u ON orig.author_id = u.id
                WHERE u.is_bot = 0
                GROUP BY orig.author_id
            ),
            responses_given AS (
                SELECT m.author_id as user_id, COUNT(*) as given
                FROM messages m
                JOIN users u ON m.author_id = u.id
                WHERE u.is_bot = 0 AND m.reply_to_message_id IS NOT NULL
                GROUP BY m.author_id
            ),
            total_received AS (
                SELECT user_id, SUM(received) as total
                FROM (
                    SELECT user_id, received FROM mentions_received
                    UNION ALL
                    SELECT user_id, received FROM replies_received
                ) GROUP BY user_id
            )
            SELECT
                u.username,
                COALESCE(tr.total, 0) as pings_received,
                COALESCE(rg.given, 0) as responses_given,
                CASE WHEN tr.total > 0
                    THEN ROUND((1 - COALESCE(rg.given, 0) * 1.0 / tr.total) * 100, 1)
                    ELSE 0
                END as left_on_read_pct
            FROM users u
            LEFT JOIN total_received tr ON u.id = tr.user_id
            LEFT JOIN responses_given rg ON u.id = rg.user_id
            WHERE u.is_bot = 0 AND COALESCE(tr.total, 0) >= 20
            ORDER BY left_on_read_pct DESC
            LIMIT 10
        """)

        report.append("Who leaves people hanging the most?\n")
        report.append("(Higher % = more likely to ignore you)\n\n")
        for i, u in enumerate(left_on_read[:10], 1):
            report.append(f"  {i}. {u['username']}: {u['left_on_read_pct']:.1f}% ignored ({u['pings_received']} pings received)\n")

        # 1.3 Conversation Killers
        report.append(subsection("1.3 CONVERSATION KILLERS"))
        report.append("Users whose messages are followed by 30+ min of silence:\n\n")

        convo_killers = run_query(conn, """
            WITH msg_with_next AS (
                SELECT
                    m.id,
                    m.author_id,
                    m.channel_id,
                    m.created_at as msg_time,
                    LEAD(m.created_at) OVER (PARTITION BY m.channel_id ORDER BY m.created_at) as next_msg_time
                FROM messages m
                JOIN users u ON m.author_id = u.id
                WHERE u.is_bot = 0
            )
            SELECT
                u.username,
                COUNT(*) as total_msgs,
                SUM(CASE WHEN (julianday(next_msg_time) - julianday(msg_time)) * 24 * 60 > 30 THEN 1 ELSE 0 END) as kills,
                ROUND(
                    SUM(CASE WHEN (julianday(next_msg_time) - julianday(msg_time)) * 24 * 60 > 30 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                    1
                ) as kill_rate
            FROM msg_with_next mwn
            JOIN users u ON mwn.author_id = u.id
            WHERE next_msg_time IS NOT NULL
            GROUP BY mwn.author_id
            HAVING COUNT(*) >= 50
            ORDER BY kill_rate DESC
            LIMIT 10
        """)

        report.append("The 'Buzzkill' Leaderboard:\n")
        for i, u in enumerate(convo_killers[:10], 1):
            report.append(f"  {i}. {u['username']}: {u['kill_rate']:.1f}% of messages killed the chat ({u['kills']} times)\n")

        # 1.4 Conversation Revivers
        report.append(subsection("1.4 CONVERSATION REVIVERS"))

        revivers = run_query(conn, """
            WITH msg_with_prev AS (
                SELECT
                    m.id,
                    m.author_id,
                    m.channel_id,
                    m.created_at as msg_time,
                    LAG(m.created_at) OVER (PARTITION BY m.channel_id ORDER BY m.created_at) as prev_msg_time
                FROM messages m
                JOIN users u ON m.author_id = u.id
                WHERE u.is_bot = 0
            )
            SELECT
                u.username,
                SUM(CASE WHEN (julianday(msg_time) - julianday(prev_msg_time)) * 24 * 60 > 60 THEN 1 ELSE 0 END) as revivals
            FROM msg_with_prev mwp
            JOIN users u ON mwp.author_id = u.id
            WHERE prev_msg_time IS NOT NULL
            GROUP BY mwp.author_id
            ORDER BY revivals DESC
            LIMIT 10
        """)

        report.append("The 'Spark Plug' Award - Who brings dead chats back to life:\n")
        report.append("(First message after 1+ hour of silence)\n\n")
        for i, u in enumerate(revivers[:10], 1):
            report.append(f"  {i}. {u['username']}: {u['revivals']} revivals\n")

        # 1.5 Conversation Catalysts
        report.append(subsection("1.5 CONVERSATION CATALYSTS"))
        report.append("Who sparks actual conversations (not just breaks silence)?\n\n")

        catalysts = run_query(conn, """
            WITH msg_ordered AS (
                SELECT
                    m.id,
                    m.author_id,
                    m.channel_id,
                    m.created_at,
                    LAG(m.created_at) OVER (PARTITION BY m.channel_id ORDER BY m.created_at) as prev_time,
                    ROW_NUMBER() OVER (PARTITION BY m.channel_id ORDER BY m.created_at) as rn
                FROM messages m
                JOIN users u ON m.author_id = u.id
                WHERE u.is_bot = 0
            ),
            potential_sparks AS (
                SELECT
                    mo.id as spark_id,
                    mo.author_id as spark_author,
                    mo.channel_id,
                    mo.created_at as spark_time
                FROM msg_ordered mo
                WHERE (julianday(mo.created_at) - julianday(mo.prev_time)) * 24 * 60 > 30
                   OR mo.prev_time IS NULL
            ),
            spark_results AS (
                SELECT
                    ps.spark_id,
                    ps.spark_author,
                    COUNT(DISTINCT m.id) as follow_up_count,
                    COUNT(DISTINCT m.author_id) as unique_responders
                FROM potential_sparks ps
                JOIN messages m ON m.channel_id = ps.channel_id
                    AND m.created_at > ps.spark_time
                    AND (julianday(m.created_at) - julianday(ps.spark_time)) * 24 * 60 <= 30
                JOIN users u ON m.author_id = u.id
                WHERE u.is_bot = 0
                GROUP BY ps.spark_id, ps.spark_author
            )
            SELECT
                u.username,
                COUNT(*) as spark_attempts,
                SUM(CASE WHEN sr.follow_up_count >= 5 AND sr.unique_responders >= 2 THEN 1 ELSE 0 END) as successful_ignitions,
                ROUND(
                    SUM(CASE WHEN sr.follow_up_count >= 5 AND sr.unique_responders >= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                    1
                ) as success_rate,
                ROUND(AVG(sr.follow_up_count), 1) as avg_chain_length
            FROM spark_results sr
            JOIN users u ON sr.spark_author = u.id
            GROUP BY sr.spark_author
            HAVING COUNT(*) >= 5
            ORDER BY successful_ignitions DESC
            LIMIT 10
        """)

        report.append("'Life of the Party' - Most successful conversation starters:\n")
        for i, u in enumerate(catalysts[:10], 1):
            report.append(f"  {i}. {u['username']}: {u['successful_ignitions']} ignitions ({u['success_rate']:.1f}% success, avg {u['avg_chain_length']:.1f} msgs)\n")

        # =====================================================================
        # PART 2: SOCIAL GRAPH INSIGHTS
        # =====================================================================
        report.append(section("PART 2: SOCIAL GRAPH INSIGHTS"))

        # 2.1 Social Butterfly Score
        report.append(subsection("2.1 SOCIAL BUTTERFLY SCORE"))

        social_butterfly = run_query(conn, """
            WITH interactions AS (
                SELECT DISTINCT m.author_id, orig.author_id as interacted_with
                FROM messages m
                JOIN messages orig ON m.reply_to_message_id = orig.id
                JOIN users u1 ON m.author_id = u1.id
                JOIN users u2 ON orig.author_id = u2.id
                WHERE u1.is_bot = 0 AND u2.is_bot = 0 AND m.author_id != orig.author_id
                UNION
                SELECT DISTINCT m.author_id, mm.mentioned_user_id as interacted_with
                FROM messages m
                JOIN message_mentions mm ON m.id = mm.message_id
                JOIN users u1 ON m.author_id = u1.id
                JOIN users u2 ON mm.mentioned_user_id = u2.id
                WHERE u1.is_bot = 0 AND u2.is_bot = 0 AND m.author_id != mm.mentioned_user_id
            )
            SELECT
                u.username,
                COUNT(DISTINCT interacted_with) as unique_interactions,
                (SELECT COUNT(*) FROM users WHERE is_bot = 0) as total_humans
            FROM interactions i
            JOIN users u ON i.author_id = u.id
            GROUP BY i.author_id
            ORDER BY unique_interactions DESC
            LIMIT 15
        """)

        total_humans = social_butterfly[0]['total_humans'] if social_butterfly else 1
        report.append(f"Who talks to the most different people? (out of {total_humans} humans)\n\n")
        for i, u in enumerate(social_butterfly[:10], 1):
            pct = u['unique_interactions'] / total_humans * 100
            report.append(f"  {i}. {u['username']}: {u['unique_interactions']} people ({pct:.0f}% of server)\n")

        # The loners
        report.append("\nThe 'Selective Socializers' (fewest unique interactions):\n")
        loners = sorted(social_butterfly, key=lambda x: x['unique_interactions'])[:5]
        for i, u in enumerate(loners, 1):
            report.append(f"  {i}. {u['username']}: only {u['unique_interactions']} people\n")

        # 2.2 Reciprocity Index
        report.append(subsection("2.2 RECIPROCITY INDEX"))

        reciprocity = run_query(conn, """
            WITH reply_counts AS (
                SELECT
                    m.author_id as user_a,
                    orig.author_id as user_b,
                    COUNT(*) as replies
                FROM messages m
                JOIN messages orig ON m.reply_to_message_id = orig.id
                JOIN users u1 ON m.author_id = u1.id
                JOIN users u2 ON orig.author_id = u2.id
                WHERE u1.is_bot = 0 AND u2.is_bot = 0 AND m.author_id != orig.author_id
                GROUP BY m.author_id, orig.author_id
            )
            SELECT
                u1.username as user_a,
                u2.username as user_b,
                rc1.replies as a_to_b,
                COALESCE(rc2.replies, 0) as b_to_a,
                ABS(rc1.replies - COALESCE(rc2.replies, 0)) as imbalance
            FROM reply_counts rc1
            JOIN users u1 ON rc1.user_a = u1.id
            JOIN users u2 ON rc1.user_b = u2.id
            LEFT JOIN reply_counts rc2 ON rc1.user_a = rc2.user_b AND rc1.user_b = rc2.user_a
            WHERE rc1.replies >= 10
            ORDER BY imbalance DESC
            LIMIT 10
        """)

        report.append("Most UNBALANCED relationships (one-sided attention):\n\n")
        for i, r in enumerate(reciprocity[:10], 1):
            report.append(f"  {i}. {r['user_a']} -> {r['user_b']}: {r['a_to_b']} replies vs {r['b_to_a']} back (imbalance: {r['imbalance']})\n")

        # Most balanced
        report.append(subsection("2.3 BEST FRIENDS FOREVER"))
        bffs = run_query(conn, """
            WITH reply_counts AS (
                SELECT
                    CASE WHEN m.author_id < orig.author_id THEN m.author_id ELSE orig.author_id END as user_a,
                    CASE WHEN m.author_id < orig.author_id THEN orig.author_id ELSE m.author_id END as user_b,
                    m.author_id as replier
                FROM messages m
                JOIN messages orig ON m.reply_to_message_id = orig.id
                JOIN users u1 ON m.author_id = u1.id
                JOIN users u2 ON orig.author_id = u2.id
                WHERE u1.is_bot = 0 AND u2.is_bot = 0 AND m.author_id != orig.author_id
            ),
            pair_counts AS (
                SELECT
                    user_a, user_b,
                    SUM(CASE WHEN replier = user_a THEN 1 ELSE 0 END) as a_to_b,
                    SUM(CASE WHEN replier = user_b THEN 1 ELSE 0 END) as b_to_a,
                    COUNT(*) as total
                FROM reply_counts
                GROUP BY user_a, user_b
            )
            SELECT
                u1.username as user_1,
                u2.username as user_2,
                pc.a_to_b,
                pc.b_to_a,
                pc.total,
                ABS(pc.a_to_b - pc.b_to_a) as imbalance
            FROM pair_counts pc
            JOIN users u1 ON pc.user_a = u1.id
            JOIN users u2 ON pc.user_b = u2.id
            WHERE pc.total >= 20
            ORDER BY pc.total DESC, imbalance ASC
            LIMIT 10
        """)

        report.append("Strongest friendships (most mutual exchanges):\n\n")
        for i, p in enumerate(bffs[:10], 1):
            report.append(f"  {i}. {p['user_1']} <-> {p['user_2']}: {p['total']} total ({p['a_to_b']} / {p['b_to_a']})\n")

        # =====================================================================
        # PART 3: BEHAVIORAL PATTERNS
        # =====================================================================
        report.append(section("PART 3: BEHAVIORAL PATTERNS"))

        # 3.1 Consistency Score
        report.append(subsection("3.1 CONSISTENCY SCORE"))

        consistency = run_query(conn, """
            WITH daily_counts AS (
                SELECT
                    m.author_id,
                    DATE(m.created_at) as msg_date,
                    COUNT(*) as daily_msgs
                FROM messages m
                JOIN users u ON m.author_id = u.id
                WHERE u.is_bot = 0
                GROUP BY m.author_id, DATE(m.created_at)
            ),
            user_stats AS (
                SELECT
                    author_id,
                    AVG(daily_msgs) as avg_daily,
                    COUNT(*) as active_days,
                    SUM(daily_msgs) as total_msgs
                FROM daily_counts
                GROUP BY author_id
            )
            SELECT
                u.username,
                us.avg_daily,
                us.active_days,
                us.total_msgs,
                ROUND(us.total_msgs * 1.0 / us.active_days, 1) as msgs_per_active_day
            FROM user_stats us
            JOIN users u ON us.author_id = u.id
            WHERE us.active_days >= 10
            ORDER BY us.active_days DESC
            LIMIT 15
        """)

        report.append("Most CONSISTENT contributors (most active days):\n\n")
        for i, u in enumerate(consistency[:10], 1):
            report.append(f"  {i}. {u['username']}: {u['active_days']} days active, {u['msgs_per_active_day']:.1f} msgs/day\n")

        # 3.2 Longest Streaks
        report.append(subsection("3.2 LONGEST STREAK CHAMPIONS"))

        # This requires a more complex query - we'll use a gaps and islands approach
        streaks = run_query(conn, """
            WITH daily_activity AS (
                SELECT DISTINCT
                    m.author_id,
                    DATE(m.created_at) as activity_date
                FROM messages m
                JOIN users u ON m.author_id = u.id
                WHERE u.is_bot = 0
            ),
            with_row_num AS (
                SELECT
                    author_id,
                    activity_date,
                    julianday(activity_date) - ROW_NUMBER() OVER (PARTITION BY author_id ORDER BY activity_date) as grp
                FROM daily_activity
            ),
            streaks AS (
                SELECT
                    author_id,
                    MIN(activity_date) as streak_start,
                    MAX(activity_date) as streak_end,
                    COUNT(*) as streak_length
                FROM with_row_num
                GROUP BY author_id, grp
            )
            SELECT
                u.username,
                MAX(streak_length) as longest_streak,
                (SELECT streak_start FROM streaks s2 WHERE s2.author_id = s.author_id ORDER BY streak_length DESC LIMIT 1) as best_streak_start
            FROM streaks s
            JOIN users u ON s.author_id = u.id
            GROUP BY s.author_id
            ORDER BY longest_streak DESC
            LIMIT 10
        """)

        report.append("Longest consecutive days with activity:\n\n")
        for i, u in enumerate(streaks[:10], 1):
            report.append(f"  {i}. {u['username']}: {u['longest_streak']} day streak!\n")

        # 3.3 Ghost Probability
        report.append(subsection("3.3 GHOST PROBABILITY"))

        ghosts = run_query(conn, """
            WITH user_gaps AS (
                SELECT
                    m.author_id,
                    m.created_at,
                    LAG(m.created_at) OVER (PARTITION BY m.author_id ORDER BY m.created_at) as prev_msg,
                    julianday(m.created_at) - julianday(LAG(m.created_at) OVER (PARTITION BY m.author_id ORDER BY m.created_at)) as gap_days
                FROM messages m
                JOIN users u ON m.author_id = u.id
                WHERE u.is_bot = 0
            )
            SELECT
                u.username,
                MAX(gap_days) as longest_absence_days,
                ROUND(AVG(gap_days), 1) as avg_gap_days
            FROM user_gaps ug
            JOIN users u ON ug.author_id = u.id
            WHERE gap_days IS NOT NULL
            GROUP BY ug.author_id
            HAVING COUNT(*) >= 20
            ORDER BY longest_absence_days DESC
            LIMIT 10
        """)

        report.append("Longest disappearances (most likely to ghost):\n\n")
        for i, u in enumerate(ghosts[:10], 1):
            report.append(f"  {i}. {u['username']}: {u['longest_absence_days']:.0f} days gone at longest\n")

        # 3.4 Channel Loyalty
        report.append(subsection("3.4 CHANNEL LOYALTY"))

        loyalty = run_query(conn, """
            WITH user_channel_counts AS (
                SELECT
                    m.author_id,
                    m.channel_id,
                    c.name as channel_name,
                    COUNT(*) as msgs
                FROM messages m
                JOIN channels c ON m.channel_id = c.id
                JOIN users u ON m.author_id = u.id
                WHERE u.is_bot = 0
                GROUP BY m.author_id, m.channel_id
            ),
            user_totals AS (
                SELECT author_id, SUM(msgs) as total FROM user_channel_counts GROUP BY author_id
            ),
            user_home AS (
                SELECT
                    ucc.author_id,
                    ucc.channel_name as home_channel,
                    ucc.msgs as home_msgs,
                    ut.total,
                    ROUND(ucc.msgs * 100.0 / ut.total, 1) as home_pct,
                    ROW_NUMBER() OVER (PARTITION BY ucc.author_id ORDER BY ucc.msgs DESC) as rn
                FROM user_channel_counts ucc
                JOIN user_totals ut ON ucc.author_id = ut.author_id
            )
            SELECT u.username, uh.home_channel, uh.home_msgs, uh.total, uh.home_pct
            FROM user_home uh
            JOIN users u ON uh.author_id = u.id
            WHERE uh.rn = 1 AND uh.total >= 50
            ORDER BY uh.home_pct DESC
            LIMIT 15
        """)

        report.append("Most loyal to their 'home' channel:\n\n")
        for i, u in enumerate(loyalty[:10], 1):
            report.append(f"  {i}. {u['username']}: #{u['home_channel']} ({u['home_pct']:.1f}% of {u['total']} msgs)\n")

        report.append("\nMost spread out (least loyal):\n")
        spread = sorted(loyalty, key=lambda x: x['home_pct'])[:5]
        for i, u in enumerate(spread, 1):
            report.append(f"  {i}. {u['username']}: only {u['home_pct']:.1f}% in #{u['home_channel']}\n")

        # =====================================================================
        # PART 4: ENGAGEMENT QUALITY
        # =====================================================================
        report.append(section("PART 4: ENGAGEMENT QUALITY"))

        # 4.1 Engagement Magnetism
        report.append(subsection("4.1 ENGAGEMENT MAGNETISM"))

        magnetism = run_query(conn, """
            WITH user_msgs AS (
                SELECT author_id, COUNT(*) as sent
                FROM messages m
                JOIN users u ON m.author_id = u.id
                WHERE u.is_bot = 0
                GROUP BY author_id
            ),
            replies_received AS (
                SELECT orig.author_id, COUNT(*) as received
                FROM messages m
                JOIN messages orig ON m.reply_to_message_id = orig.id
                JOIN users u ON orig.author_id = u.id
                WHERE u.is_bot = 0
                GROUP BY orig.author_id
            ),
            mentions_received AS (
                SELECT mentioned_user_id as author_id, COUNT(*) as received
                FROM message_mentions mm
                JOIN users u ON mm.mentioned_user_id = u.id
                WHERE u.is_bot = 0
                GROUP BY mentioned_user_id
            )
            SELECT
                u.username,
                um.sent,
                COALESCE(rr.received, 0) as replies_received,
                COALESCE(mr.received, 0) as mentions_received,
                COALESCE(rr.received, 0) + COALESCE(mr.received, 0) as total_engagement,
                ROUND((COALESCE(rr.received, 0) + COALESCE(mr.received, 0)) * 1.0 / um.sent, 2) as engagement_ratio
            FROM user_msgs um
            JOIN users u ON um.author_id = u.id
            LEFT JOIN replies_received rr ON um.author_id = rr.author_id
            LEFT JOIN mentions_received mr ON um.author_id = mr.author_id
            WHERE um.sent >= 50
            ORDER BY engagement_ratio DESC
            LIMIT 15
        """)

        report.append("Who generates the most engagement per message?\n")
        report.append("(replies + mentions received / messages sent)\n\n")
        for i, u in enumerate(magnetism[:10], 1):
            report.append(f"  {i}. {u['username']}: {u['engagement_ratio']:.2f} engagement/msg ({u['total_engagement']} from {u['sent']} msgs)\n")

        report.append("\nLowest engagement (needs more love):\n")
        low_engage = sorted(magnetism, key=lambda x: x['engagement_ratio'])[:5]
        for i, u in enumerate(low_engage, 1):
            report.append(f"  {i}. {u['username']}: {u['engagement_ratio']:.2f} engagement/msg\n")

        # 4.2 Viral Messages
        report.append(subsection("4.2 VIRAL MESSAGES"))

        viral = run_query(conn, """
            SELECT
                u.username,
                m.content,
                c.name as channel,
                m.created_at,
                COUNT(r.id) as reply_count
            FROM messages m
            JOIN users u ON m.author_id = u.id
            JOIN channels c ON m.channel_id = c.id
            LEFT JOIN messages r ON r.reply_to_message_id = m.id
            WHERE u.is_bot = 0
            GROUP BY m.id
            ORDER BY reply_count DESC
            LIMIT 5
        """)

        report.append("Messages that sparked the most replies:\n\n")
        for i, v in enumerate(viral, 1):
            content_preview = v['content'][:80] + "..." if len(v['content']) > 80 else v['content']
            content_preview = content_preview.replace('\n', ' ')
            report.append(f"  {i}. [{v['reply_count']} replies] {v['username']} in #{v['channel']}:\n")
            report.append(f"     \"{content_preview}\"\n\n")

        # =====================================================================
        # PART 5: SPOTIFY WRAPPED PERSONAL STATS
        # =====================================================================
        report.append(section("PART 5: PERSONAL WRAPPED STATS"))

        # Get active users (top 10 by message count)
        active_users = run_query(conn, """
            SELECT u.id, u.username, COUNT(*) as msg_count
            FROM messages m
            JOIN users u ON m.author_id = u.id
            WHERE u.is_bot = 0
            GROUP BY u.id
            HAVING COUNT(*) >= 100
            ORDER BY msg_count DESC
            LIMIT 10
        """)

        for user in active_users:
            report.append(f"\n{'~'*60}\n")
            report.append(f"  {user['username']}'s Year in Review\n")
            report.append(f"{'~'*60}\n")

            stats = run_query(conn, """
                WITH user_stats AS (
                    SELECT
                        COUNT(*) as total_msgs,
                        MAX(LENGTH(content)) as longest_msg,
                        SUM(CASE WHEN content LIKE '%?' THEN 1 ELSE 0 END) as questions_asked,
                        SUM(CASE WHEN CAST(strftime('%H', created_at) AS INTEGER) BETWEEN 0 AND 5 THEN 1 ELSE 0 END) as late_night
                    FROM messages WHERE author_id = :user_id
                ),
                rank_info AS (
                    SELECT
                        COUNT(*) + 1 as rank,
                        (SELECT COUNT(DISTINCT author_id) FROM messages m JOIN users u ON m.author_id = u.id WHERE u.is_bot = 0) as total_users
                    FROM (
                        SELECT author_id, COUNT(*) as cnt
                        FROM messages m JOIN users u ON m.author_id = u.id
                        WHERE u.is_bot = 0
                        GROUP BY author_id
                        HAVING COUNT(*) > (SELECT COUNT(*) FROM messages WHERE author_id = :user_id)
                    )
                ),
                fav_channel AS (
                    SELECT c.name, COUNT(*) as cnt,
                           ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM messages WHERE author_id = :user_id), 1) as pct
                    FROM messages m
                    JOIN channels c ON m.channel_id = c.id
                    WHERE m.author_id = :user_id
                    GROUP BY c.id
                    ORDER BY cnt DESC LIMIT 1
                ),
                best_friend AS (
                    SELECT u.username, COUNT(*) as exchanges
                    FROM messages m
                    JOIN messages orig ON m.reply_to_message_id = orig.id
                    JOIN users u ON orig.author_id = u.id
                    WHERE m.author_id = :user_id AND orig.author_id != :user_id AND u.is_bot = 0
                    GROUP BY orig.author_id
                    ORDER BY exchanges DESC LIMIT 1
                ),
                mentions_info AS (
                    SELECT COUNT(*) as times_mentioned,
                           COUNT(DISTINCT m.author_id) as by_people
                    FROM message_mentions mm
                    JOIN messages m ON mm.message_id = m.id
                    WHERE mm.mentioned_user_id = :user_id
                ),
                busiest_day AS (
                    SELECT DATE(created_at) as the_date, COUNT(*) as cnt
                    FROM messages WHERE author_id = :user_id
                    GROUP BY DATE(created_at)
                    ORDER BY cnt DESC LIMIT 1
                ),
                unique_people AS (
                    SELECT COUNT(DISTINCT orig.author_id) as cnt
                    FROM messages m
                    JOIN messages orig ON m.reply_to_message_id = orig.id
                    WHERE m.author_id = :user_id AND orig.author_id != :user_id
                )
                SELECT
                    us.*,
                    ri.rank, ri.total_users,
                    fc.name as fav_channel, fc.pct as fav_channel_pct,
                    bf.username as best_friend, bf.exchanges as bf_exchanges,
                    mi.times_mentioned, mi.by_people,
                    bd.the_date as busiest_date, bd.cnt as busiest_count,
                    up.cnt as unique_convos
                FROM user_stats us, rank_info ri, fav_channel fc, mentions_info mi, busiest_day bd, unique_people up
                LEFT JOIN best_friend bf ON 1=1
            """, {"user_id": user['id']})

            if stats:
                s = stats[0]
                percentile = round((1 - s['rank'] / s['total_users']) * 100)
                report.append(f"\n  You were in the TOP {percentile}% of messagers!\n")
                report.append(f"  Total messages: {s['total_msgs']:,}\n")
                report.append(f"\n  Your favorite channel: #{s['fav_channel']} ({s['fav_channel_pct']:.1f}% of your messages)\n")
                if s['best_friend']:
                    report.append(f"  Your #1 conversation partner: {s['best_friend']} ({s['bf_exchanges']} exchanges)\n")
                report.append(f"  You talked to {s['unique_convos']} different people\n")
                report.append(f"\n  You were mentioned {s['times_mentioned']} times by {s['by_people']} people\n")
                report.append(f"  Your busiest day: {s['busiest_date']} ({s['busiest_count']} messages!)\n")
                report.append(f"  You asked {s['questions_asked']} questions\n")
                report.append(f"  Late night messages (12am-5am): {s['late_night']}\n")
                report.append(f"  Longest message: {s['longest_msg']} characters\n")

        # =====================================================================
        # PART 6: FUN QUIRKY AWARDS
        # =====================================================================
        report.append(section("PART 6: FUN QUIRKY AWARDS"))

        # LOL Champion
        report.append(subsection("THE 'LOL' CHAMPION"))
        lol = run_query(conn, """
            SELECT
                u.username,
                SUM(
                    (LENGTH(LOWER(content)) - LENGTH(REPLACE(LOWER(content), 'lol', ''))) / 3 +
                    (LENGTH(LOWER(content)) - LENGTH(REPLACE(LOWER(content), 'lmao', ''))) / 4 +
                    (LENGTH(LOWER(content)) - LENGTH(REPLACE(LOWER(content), 'haha', ''))) / 4 +
                    (LENGTH(LOWER(content)) - LENGTH(REPLACE(LOWER(content), 'hehe', ''))) / 4
                ) as laugh_count
            FROM messages m
            JOIN users u ON m.author_id = u.id
            WHERE u.is_bot = 0
            GROUP BY m.author_id
            ORDER BY laugh_count DESC
            LIMIT 5
        """)
        for i, u in enumerate(lol[:5], 1):
            report.append(f"  {i}. {u['username']}: {u['laugh_count']} lols/lmaos/hahas\n")

        # Link Sharer
        report.append(subsection("LINK SHARER CHAMPION"))
        links = run_query(conn, """
            SELECT
                u.username,
                SUM(
                    (LENGTH(content) - LENGTH(REPLACE(content, 'http://', ''))) / 7 +
                    (LENGTH(content) - LENGTH(REPLACE(content, 'https://', ''))) / 8
                ) as link_count
            FROM messages m
            JOIN users u ON m.author_id = u.id
            WHERE u.is_bot = 0
            GROUP BY m.author_id
            ORDER BY link_count DESC
            LIMIT 5
        """)
        for i, u in enumerate(links[:5], 1):
            report.append(f"  {i}. {u['username']}: {u['link_count']} links shared\n")

        # The Rambler
        report.append(subsection("THE RAMBLER (Longest Avg Messages)"))
        rambler = run_query(conn, """
            SELECT
                u.username,
                ROUND(AVG(LENGTH(content)), 1) as avg_length,
                MAX(LENGTH(content)) as max_length
            FROM messages m
            JOIN users u ON m.author_id = u.id
            WHERE u.is_bot = 0 AND LENGTH(content) > 0
            GROUP BY m.author_id
            HAVING COUNT(*) >= 50
            ORDER BY avg_length DESC
            LIMIT 5
        """)
        for i, u in enumerate(rambler[:5], 1):
            report.append(f"  {i}. {u['username']}: {u['avg_length']:.0f} chars avg (max: {u['max_length']})\n")

        # The Succinct One
        report.append(subsection("THE SUCCINCT ONE (Shortest Avg Messages)"))
        succinct = run_query(conn, """
            SELECT
                u.username,
                ROUND(AVG(LENGTH(content)), 1) as avg_length
            FROM messages m
            JOIN users u ON m.author_id = u.id
            WHERE u.is_bot = 0 AND LENGTH(content) > 0
            GROUP BY m.author_id
            HAVING COUNT(*) >= 50
            ORDER BY avg_length ASC
            LIMIT 5
        """)
        for i, u in enumerate(succinct[:5], 1):
            report.append(f"  {i}. {u['username']}: {u['avg_length']:.0f} chars avg\n")

        # Night Owl vs Early Bird
        report.append(subsection("NIGHT OWL CHAMPION (12am-5am)"))
        night_owl = run_query(conn, """
            SELECT
                u.username,
                SUM(CASE WHEN CAST(strftime('%H', m.created_at) AS INTEGER) BETWEEN 0 AND 5 THEN 1 ELSE 0 END) as late_msgs,
                COUNT(*) as total,
                ROUND(SUM(CASE WHEN CAST(strftime('%H', m.created_at) AS INTEGER) BETWEEN 0 AND 5 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as pct
            FROM messages m
            JOIN users u ON m.author_id = u.id
            WHERE u.is_bot = 0
            GROUP BY m.author_id
            HAVING COUNT(*) >= 50
            ORDER BY pct DESC
            LIMIT 5
        """)
        for i, u in enumerate(night_owl[:5], 1):
            report.append(f"  {i}. {u['username']}: {u['pct']:.1f}% of messages after midnight ({u['late_msgs']} msgs)\n")

        # =====================================================================
        # PART 7: COMMUNITY HEALTH
        # =====================================================================
        report.append(section("PART 7: COMMUNITY HEALTH"))

        # Activity Concentration
        report.append(subsection("ACTIVITY CONCENTRATION"))
        concentration = run_query(conn, """
            WITH ranked AS (
                SELECT
                    u.username,
                    COUNT(*) as msgs,
                    SUM(COUNT(*)) OVER () as total,
                    ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) as rn
                FROM messages m
                JOIN users u ON m.author_id = u.id
                WHERE u.is_bot = 0
                GROUP BY m.author_id
            )
            SELECT
                username,
                msgs,
                total,
                ROUND(msgs * 100.0 / total, 1) as pct,
                rn
            FROM ranked
            ORDER BY rn
            LIMIT 5
        """)

        report.append("How concentrated is the activity?\n\n")
        cumulative = 0
        for c in concentration:
            cumulative += c['pct']
            report.append(f"  Top {c['rn']}: {c['username']} - {c['pct']:.1f}% (cumulative: {cumulative:.1f}%)\n")

        report.append(f"\n  Top 3 users account for {sum(c['pct'] for c in concentration[:3]):.1f}% of all messages!\n")

        # =====================================================================
        # PART 8: RELATIONSHIP SUPERLATIVES
        # =====================================================================
        report.append(section("PART 8: RELATIONSHIP SUPERLATIVES"))

        # Late Night Crew
        report.append(subsection("THE LATE NIGHT CREW"))
        late_night_crew = run_query(conn, """
            WITH late_night_pairs AS (
                SELECT
                    CASE WHEN m.author_id < orig.author_id THEN m.author_id ELSE orig.author_id END as user_a,
                    CASE WHEN m.author_id < orig.author_id THEN orig.author_id ELSE m.author_id END as user_b,
                    COUNT(*) as exchanges
                FROM messages m
                JOIN messages orig ON m.reply_to_message_id = orig.id
                JOIN users u1 ON m.author_id = u1.id
                JOIN users u2 ON orig.author_id = u2.id
                WHERE u1.is_bot = 0 AND u2.is_bot = 0
                  AND m.author_id != orig.author_id
                  AND CAST(strftime('%H', m.created_at) AS INTEGER) BETWEEN 0 AND 5
                GROUP BY user_a, user_b
            )
            SELECT u1.username as user_1, u2.username as user_2, exchanges
            FROM late_night_pairs lnp
            JOIN users u1 ON lnp.user_a = u1.id
            JOIN users u2 ON lnp.user_b = u2.id
            ORDER BY exchanges DESC
            LIMIT 5
        """)

        report.append("Pairs who chat together after midnight:\n\n")
        for i, p in enumerate(late_night_crew[:5], 1):
            report.append(f"  {i}. {p['user_1']} & {p['user_2']}: {p['exchanges']} late-night exchanges\n")

        # =====================================================================
        # FOOTER
        # =====================================================================
        report.append(f"""

################################################################################
#                                                                              #
#                         END OF YEAR-END REVIEW                               #
#                        CREATIVE ANALYTICS EDITION                            #
#                                                                              #
################################################################################

Thanks for an amazing year, {server_name}!

Report generated by Discord SQL Analytics V2
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""")

    # Write report
    full_report = "".join(report)
    with open(output_file, 'w') as f:
        f.write(full_report)

    print(full_report)
    print(f"\n\nReport saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate Creative Discord Year-End Review")
    parser.add_argument("--db", type=str, default=DEFAULT_DB, help="Database file")
    parser.add_argument("--output", type=str, default=OUTPUT_FILE, help="Output file")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Error: Database file not found: {args.db}")
        sys.exit(1)

    print(f"Generating CREATIVE year-end review from: {args.db}")
    print(f"Output file: {args.output}")
    print("(Excluding all bots from analytics)")
    print()

    engine = create_engine(f"sqlite:///{args.db}", echo=False)
    generate_report(engine, args.output)


if __name__ == "__main__":
    main()
