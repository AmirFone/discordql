#!/usr/bin/env python3
"""
Discord Year-End Review Analytics.

Generates creative analytics and insights from a year of Discord data.

Usage:
    python scripts/year_end_review.py [--db discord_year.db]
"""
import argparse
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict

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


def format_section(title, content):
    """Format a section with title and content."""
    return f"\n{'='*60}\n{title}\n{'='*60}\n{content}\n"


def generate_report(engine, output_file):
    """Generate the complete year-end review report."""
    report = []

    with engine.connect() as conn:
        # =====================================================================
        # HEADER
        # =====================================================================
        server = run_query(conn, "SELECT name, member_count FROM servers LIMIT 1")
        server_name = server[0]['name'] if server else "Unknown Server"
        member_count = server[0]['member_count'] if server else 0

        report.append(f"""
################################################################################
#                                                                              #
#                    {server_name.upper()} - YEAR IN REVIEW 2024                    #
#                                                                              #
################################################################################

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Server: {server_name}
Members: {member_count}
""")

        # =====================================================================
        # SECTION 1: THE BIG NUMBERS
        # =====================================================================
        stats = run_query(conn, """
            SELECT
                (SELECT COUNT(*) FROM messages) as total_messages,
                (SELECT COUNT(DISTINCT author_id) FROM messages) as active_users,
                (SELECT COUNT(*) FROM channels) as channels,
                (SELECT COUNT(*) FROM message_mentions) as total_mentions,
                (SELECT COUNT(*) FROM messages WHERE reply_to_message_id IS NOT NULL) as total_replies
        """)[0]

        # Date range
        date_range = run_query(conn, """
            SELECT
                MIN(created_at) as first_msg,
                MAX(created_at) as last_msg
            FROM messages
        """)[0]

        content = f"""
Total Messages: {stats['total_messages']:,}
Active Users: {stats['active_users']}
Channels Used: {stats['channels']}
Total Mentions: {stats['total_mentions']:,}
Total Replies: {stats['total_replies']:,}

Date Range: {date_range['first_msg']} to {date_range['last_msg']}
"""
        report.append(format_section("THE BIG NUMBERS", content))

        # =====================================================================
        # SECTION 2: TOP MESSAGERS
        # =====================================================================
        top_users = run_query(conn, """
            SELECT
                u.username,
                COALESCE(u.global_name, u.username) as display_name,
                COUNT(*) as message_count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM messages), 1) as pct
            FROM messages m
            JOIN users u ON m.author_id = u.id
            GROUP BY u.id
            ORDER BY message_count DESC
            LIMIT 10
        """)

        content = "\nRank  User                          Messages    % of Total\n"
        content += "-" * 60 + "\n"
        for i, user in enumerate(top_users, 1):
            content += f"{i:2}.   {user['display_name']:<28} {user['message_count']:>8,}    {user['pct']:>5.1f}%\n"

        report.append(format_section("TOP 10 MESSAGERS", content))

        # =====================================================================
        # SECTION 3: CHANNEL LEADERBOARD
        # =====================================================================
        channel_stats = run_query(conn, """
            SELECT
                c.name,
                COUNT(*) as message_count,
                COUNT(DISTINCT m.author_id) as unique_users,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM messages), 1) as pct
            FROM messages m
            JOIN channels c ON m.channel_id = c.id
            GROUP BY c.id
            ORDER BY message_count DESC
        """)

        content = "\nChannel               Messages    Users    % of Total\n"
        content += "-" * 60 + "\n"
        for ch in channel_stats[:10]:
            content += f"#{ch['name']:<20} {ch['message_count']:>8,}    {ch['unique_users']:>5}    {ch['pct']:>5.1f}%\n"

        report.append(format_section("CHANNEL LEADERBOARD", content))

        # =====================================================================
        # SECTION 4: BEST FRIENDS (Most Back-and-Forth)
        # =====================================================================
        # This finds pairs who reply to each other the most
        # Uses join with messages table since reply_to_author_id may not be populated
        best_friends = run_query(conn, """
            WITH reply_pairs AS (
                SELECT
                    m.author_id as user_a,
                    orig.author_id as user_b,
                    COUNT(*) as replies
                FROM messages m
                JOIN messages orig ON m.reply_to_message_id = orig.id
                WHERE m.author_id != orig.author_id
                GROUP BY m.author_id, orig.author_id
            ),
            bidirectional AS (
                SELECT
                    CASE WHEN rp1.user_a < rp1.user_b THEN rp1.user_a ELSE rp1.user_b END as user_a,
                    CASE WHEN rp1.user_a < rp1.user_b THEN rp1.user_b ELSE rp1.user_a END as user_b,
                    COALESCE(rp1.replies, 0) + COALESCE(rp2.replies, 0) as total_exchanges
                FROM reply_pairs rp1
                LEFT JOIN reply_pairs rp2 ON rp1.user_a = rp2.user_b AND rp1.user_b = rp2.user_a
                WHERE rp1.user_a < rp1.user_b OR rp2.user_a IS NULL
            )
            SELECT
                u1.username as user_1,
                u2.username as user_2,
                SUM(total_exchanges) as exchanges
            FROM bidirectional b
            JOIN users u1 ON b.user_a = u1.id
            JOIN users u2 ON b.user_b = u2.id
            GROUP BY b.user_a, b.user_b
            ORDER BY exchanges DESC
            LIMIT 10
        """)

        content = "\nThese pairs had the most back-and-forth conversations:\n\n"
        content += "Rank  Pair                                    Exchanges\n"
        content += "-" * 60 + "\n"
        for i, pair in enumerate(best_friends, 1):
            pair_name = f"{pair['user_1']} <-> {pair['user_2']}"
            content += f"{i:2}.   {pair_name:<40} {pair['exchanges']:>8}\n"

        report.append(format_section("BEST FRIENDS (Most Reply Exchanges)", content))

        # =====================================================================
        # SECTION 5: MOST REPLIED-TO USERS
        # =====================================================================
        # Uses join with messages table since reply_to_author_id may not be populated
        most_replied = run_query(conn, """
            SELECT
                u.username,
                COUNT(*) as times_replied_to
            FROM messages m
            JOIN messages orig ON m.reply_to_message_id = orig.id
            JOIN users u ON orig.author_id = u.id
            GROUP BY orig.author_id
            ORDER BY times_replied_to DESC
            LIMIT 10
        """)

        content = "\nThese users get the most responses:\n\n"
        content += "Rank  User                          Times Replied To\n"
        content += "-" * 60 + "\n"
        for i, user in enumerate(most_replied, 1):
            content += f"{i:2}.   {user['username']:<28} {user['times_replied_to']:>10,}\n"

        report.append(format_section("MOST REPLIED-TO USERS", content))

        # =====================================================================
        # SECTION 6: THE LONELY ONES (Low Reply Rate)
        # =====================================================================
        # Uses join with messages table since reply_to_author_id may not be populated
        lonely_users = run_query(conn, """
            WITH user_messages AS (
                SELECT author_id, COUNT(*) as sent
                FROM messages
                GROUP BY author_id
                HAVING COUNT(*) >= 10
            ),
            replies_received AS (
                SELECT orig.author_id as user_id, COUNT(*) as received
                FROM messages m
                JOIN messages orig ON m.reply_to_message_id = orig.id
                GROUP BY orig.author_id
            )
            SELECT
                u.username,
                um.sent as messages_sent,
                COALESCE(rr.received, 0) as replies_received,
                ROUND(COALESCE(rr.received, 0) * 100.0 / um.sent, 1) as reply_rate
            FROM user_messages um
            JOIN users u ON um.author_id = u.id
            LEFT JOIN replies_received rr ON um.author_id = rr.user_id
            ORDER BY reply_rate ASC
            LIMIT 10
        """)

        content = "\nUsers whose messages rarely get direct replies:\n"
        content += "(Minimum 10 messages sent)\n\n"
        content += "Rank  User                     Sent    Replies    Reply Rate\n"
        content += "-" * 60 + "\n"
        for i, user in enumerate(lonely_users, 1):
            content += f"{i:2}.   {user['username']:<22} {user['messages_sent']:>5}    {user['replies_received']:>7}    {user['reply_rate']:>8.1f}%\n"

        report.append(format_section("LOOKING FOR ATTENTION (Low Reply Rate)", content))

        # =====================================================================
        # SECTION 7: CONVERSATION STARTERS
        # =====================================================================
        # Users whose messages are not replies (they start conversations)
        convo_starters = run_query(conn, """
            SELECT
                u.username,
                COUNT(*) as conversations_started,
                ROUND(COUNT(*) * 100.0 / (
                    SELECT COUNT(*) FROM messages m2 WHERE m2.author_id = m.author_id
                ), 1) as pct_original
            FROM messages m
            JOIN users u ON m.author_id = u.id
            WHERE m.reply_to_message_id IS NULL
            GROUP BY m.author_id
            HAVING COUNT(*) >= 50
            ORDER BY conversations_started DESC
            LIMIT 10
        """)

        content = "\nUsers who start the most conversations (non-reply messages):\n\n"
        content += "Rank  User                      Started    % Original\n"
        content += "-" * 60 + "\n"
        for i, user in enumerate(convo_starters, 1):
            content += f"{i:2}.   {user['username']:<24} {user['conversations_started']:>7}    {user['pct_original']:>8.1f}%\n"

        report.append(format_section("CONVERSATION STARTERS", content))

        # =====================================================================
        # SECTION 8: PEAK ACTIVITY HOURS
        # =====================================================================
        hourly = run_query(conn, """
            SELECT
                CAST(strftime('%H', created_at) AS INTEGER) as hour,
                COUNT(*) as messages
            FROM messages
            GROUP BY hour
            ORDER BY hour
        """)

        max_msgs = max(h['messages'] for h in hourly) if hourly else 1
        content = "\nMessages by hour of day (server time):\n\n"
        content += "Hour  Messages    Activity\n"
        content += "-" * 60 + "\n"
        for h in hourly:
            bar_len = int(h['messages'] / max_msgs * 30)
            bar = "#" * bar_len
            content += f"{h['hour']:02d}:00  {h['messages']:>7}    {bar}\n"

        # Find peak hours
        peak_hour = max(hourly, key=lambda x: x['messages']) if hourly else {'hour': 0, 'messages': 0}
        content += f"\nPeak Hour: {peak_hour['hour']:02d}:00 with {peak_hour['messages']:,} messages\n"

        report.append(format_section("ACTIVITY BY HOUR", content))

        # =====================================================================
        # SECTION 9: DAY OF WEEK PATTERNS
        # =====================================================================
        daily = run_query(conn, """
            SELECT
                CASE CAST(strftime('%w', created_at) AS INTEGER)
                    WHEN 0 THEN 'Sunday'
                    WHEN 1 THEN 'Monday'
                    WHEN 2 THEN 'Tuesday'
                    WHEN 3 THEN 'Wednesday'
                    WHEN 4 THEN 'Thursday'
                    WHEN 5 THEN 'Friday'
                    WHEN 6 THEN 'Saturday'
                END as day_name,
                CAST(strftime('%w', created_at) AS INTEGER) as day_num,
                COUNT(*) as messages
            FROM messages
            GROUP BY day_num
            ORDER BY day_num
        """)

        max_daily = max(d['messages'] for d in daily) if daily else 1
        content = "\nMessages by day of week:\n\n"
        content += "Day          Messages    Activity\n"
        content += "-" * 60 + "\n"
        for d in daily:
            bar_len = int(d['messages'] / max_daily * 30)
            bar = "#" * bar_len
            content += f"{d['day_name']:<12} {d['messages']:>7}    {bar}\n"

        # Weekend vs weekday
        weekend = sum(d['messages'] for d in daily if d['day_num'] in [0, 6])
        weekday = sum(d['messages'] for d in daily if d['day_num'] not in [0, 6])
        content += f"\nWeekday Messages: {weekday:,}\n"
        content += f"Weekend Messages: {weekend:,}\n"
        content += f"Weekend Ratio: {weekend / (weekday or 1) * 100:.1f}% of weekday activity\n"

        report.append(format_section("ACTIVITY BY DAY OF WEEK", content))

        # =====================================================================
        # SECTION 10: NIGHT OWLS vs EARLY BIRDS
        # =====================================================================
        time_slots = run_query(conn, """
            SELECT
                u.username,
                SUM(CASE WHEN CAST(strftime('%H', m.created_at) AS INTEGER) BETWEEN 0 AND 5 THEN 1 ELSE 0 END) as night_owl,
                SUM(CASE WHEN CAST(strftime('%H', m.created_at) AS INTEGER) BETWEEN 5 AND 9 THEN 1 ELSE 0 END) as early_bird,
                SUM(CASE WHEN CAST(strftime('%H', m.created_at) AS INTEGER) BETWEEN 9 AND 17 THEN 1 ELSE 0 END) as work_hours,
                SUM(CASE WHEN CAST(strftime('%H', m.created_at) AS INTEGER) BETWEEN 17 AND 24 THEN 1 ELSE 0 END) as evening,
                COUNT(*) as total
            FROM messages m
            JOIN users u ON m.author_id = u.id
            GROUP BY u.id
            HAVING COUNT(*) >= 50
        """)

        content = "\nNight Owls (most messages between 12am-5am):\n\n"
        night_owls = sorted(time_slots, key=lambda x: x['night_owl'], reverse=True)[:5]
        for i, u in enumerate(night_owls, 1):
            pct = u['night_owl'] / u['total'] * 100 if u['total'] > 0 else 0
            content += f"{i}. {u['username']}: {u['night_owl']} late-night messages ({pct:.1f}% of their total)\n"

        content += "\nEarly Birds (most messages between 5am-9am):\n\n"
        early_birds = sorted(time_slots, key=lambda x: x['early_bird'], reverse=True)[:5]
        for i, u in enumerate(early_birds, 1):
            pct = u['early_bird'] / u['total'] * 100 if u['total'] > 0 else 0
            content += f"{i}. {u['username']}: {u['early_bird']} early morning messages ({pct:.1f}% of their total)\n"

        report.append(format_section("NIGHT OWLS vs EARLY BIRDS", content))

        # =====================================================================
        # SECTION 11: WEEKEND WARRIORS
        # =====================================================================
        weekend_warriors = run_query(conn, """
            SELECT
                u.username,
                SUM(CASE WHEN CAST(strftime('%w', m.created_at) AS INTEGER) IN (0, 6) THEN 1 ELSE 0 END) as weekend_msgs,
                SUM(CASE WHEN CAST(strftime('%w', m.created_at) AS INTEGER) NOT IN (0, 6) THEN 1 ELSE 0 END) as weekday_msgs,
                COUNT(*) as total,
                ROUND(
                    SUM(CASE WHEN CAST(strftime('%w', m.created_at) AS INTEGER) IN (0, 6) THEN 1 ELSE 0 END) * 100.0 /
                    NULLIF(SUM(CASE WHEN CAST(strftime('%w', m.created_at) AS INTEGER) NOT IN (0, 6) THEN 1 ELSE 0 END), 0),
                    1
                ) as weekend_ratio
            FROM messages m
            JOIN users u ON m.author_id = u.id
            GROUP BY u.id
            HAVING COUNT(*) >= 50
            ORDER BY weekend_ratio DESC
            LIMIT 10
        """)

        content = "\nUsers who are most active on weekends relative to weekdays:\n\n"
        content += "Rank  User                     Weekend    Weekday    Ratio\n"
        content += "-" * 60 + "\n"
        for i, u in enumerate(weekend_warriors, 1):
            ratio = u['weekend_ratio'] if u['weekend_ratio'] else 0
            content += f"{i:2}.   {u['username']:<22} {u['weekend_msgs']:>7}    {u['weekday_msgs']:>7}    {ratio:>5.1f}%\n"

        report.append(format_section("WEEKEND WARRIORS", content))

        # =====================================================================
        # SECTION 12: THE ESSAY WRITERS (Longest Messages)
        # =====================================================================
        long_msgs = run_query(conn, """
            SELECT
                u.username,
                AVG(LENGTH(m.content)) as avg_length,
                MAX(LENGTH(m.content)) as max_length,
                COUNT(*) as total_msgs
            FROM messages m
            JOIN users u ON m.author_id = u.id
            WHERE LENGTH(m.content) > 0
            GROUP BY u.id
            HAVING COUNT(*) >= 20
            ORDER BY avg_length DESC
            LIMIT 10
        """)

        content = "\nUsers who write the longest messages on average:\n\n"
        content += "Rank  User                      Avg Chars    Max Chars    Messages\n"
        content += "-" * 70 + "\n"
        for i, u in enumerate(long_msgs, 1):
            content += f"{i:2}.   {u['username']:<24} {u['avg_length']:>9.0f}    {u['max_length']:>9}    {u['total_msgs']:>8}\n"

        report.append(format_section("THE ESSAY WRITERS", content))

        # =====================================================================
        # SECTION 13: HYPE BUILDERS (Exclamation and Caps)
        # =====================================================================
        hype = run_query(conn, """
            SELECT
                u.username,
                SUM(LENGTH(m.content) - LENGTH(REPLACE(m.content, '!', ''))) as exclamations,
                COUNT(*) as msgs,
                ROUND(
                    SUM(LENGTH(m.content) - LENGTH(REPLACE(m.content, '!', ''))) * 1.0 / COUNT(*),
                    2
                ) as excl_per_msg
            FROM messages m
            JOIN users u ON m.author_id = u.id
            WHERE LENGTH(m.content) > 0
            GROUP BY u.id
            HAVING COUNT(*) >= 20
            ORDER BY excl_per_msg DESC
            LIMIT 10
        """)

        content = "\nUsers who use the most exclamation marks (per message):\n\n"
        content += "Rank  User                      Total !    Per Msg\n"
        content += "-" * 60 + "\n"
        for i, u in enumerate(hype, 1):
            content += f"{i:2}.   {u['username']:<24} {u['exclamations']:>7}    {u['excl_per_msg']:>7.2f}\n"

        report.append(format_section("HYPE BUILDERS", content))

        # =====================================================================
        # SECTION 14: QUESTION ASKERS
        # =====================================================================
        questioners = run_query(conn, """
            SELECT
                u.username,
                SUM(CASE WHEN m.content LIKE '%?' THEN 1 ELSE 0 END) as questions,
                COUNT(*) as total,
                ROUND(
                    SUM(CASE WHEN m.content LIKE '%?' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
                    1
                ) as question_pct
            FROM messages m
            JOIN users u ON m.author_id = u.id
            GROUP BY u.id
            HAVING COUNT(*) >= 20
            ORDER BY questions DESC
            LIMIT 10
        """)

        content = "\nUsers who ask the most questions (messages ending in ?):\n\n"
        content += "Rank  User                      Questions    % of Msgs\n"
        content += "-" * 60 + "\n"
        for i, u in enumerate(questioners, 1):
            content += f"{i:2}.   {u['username']:<24} {u['questions']:>9}    {u['question_pct']:>8.1f}%\n"

        report.append(format_section("THE CURIOUS ONES (Question Askers)", content))

        # =====================================================================
        # SECTION 15: MOST MENTIONED USERS
        # =====================================================================
        mentioned = run_query(conn, """
            SELECT
                u.username,
                COUNT(*) as times_mentioned
            FROM message_mentions mm
            JOIN users u ON mm.mentioned_user_id = u.id
            GROUP BY mm.mentioned_user_id
            ORDER BY times_mentioned DESC
            LIMIT 10
        """)

        content = "\nMost tagged/mentioned users:\n\n"
        content += "Rank  User                          Mentions\n"
        content += "-" * 60 + "\n"
        for i, u in enumerate(mentioned, 1):
            content += f"{i:2}.   {u['username']:<28} {u['times_mentioned']:>8}\n"

        report.append(format_section("MOST MENTIONED", content))

        # =====================================================================
        # SECTION 16: WHO MENTIONS OTHERS MOST
        # =====================================================================
        mentioners = run_query(conn, """
            SELECT
                u.username,
                SUM(m.mention_count) as mentions_given,
                COUNT(*) as total_msgs,
                ROUND(SUM(m.mention_count) * 1.0 / COUNT(*), 2) as mentions_per_msg
            FROM messages m
            JOIN users u ON m.author_id = u.id
            GROUP BY m.author_id
            HAVING COUNT(*) >= 20
            ORDER BY mentions_given DESC
            LIMIT 10
        """)

        content = "\nUsers who mention others the most:\n\n"
        content += "Rank  User                      Mentions    Per Msg\n"
        content += "-" * 60 + "\n"
        for i, u in enumerate(mentioners, 1):
            content += f"{i:2}.   {u['username']:<24} {u['mentions_given']:>8}    {u['mentions_per_msg']:>7.2f}\n"

        report.append(format_section("TAG HAPPY (Who Mentions Others Most)", content))

        # =====================================================================
        # SECTION 17: MONTHLY ACTIVITY TREND
        # =====================================================================
        monthly = run_query(conn, """
            SELECT
                strftime('%Y-%m', created_at) as month,
                COUNT(*) as messages,
                COUNT(DISTINCT author_id) as active_users
            FROM messages
            GROUP BY month
            ORDER BY month
        """)

        max_monthly = max(m['messages'] for m in monthly) if monthly else 1
        content = "\nMessages per month:\n\n"
        content += "Month       Messages    Users    Activity\n"
        content += "-" * 60 + "\n"
        for m in monthly:
            bar_len = int(m['messages'] / max_monthly * 25)
            bar = "#" * bar_len
            content += f"{m['month']}    {m['messages']:>7}    {m['active_users']:>5}    {bar}\n"

        if monthly:
            peak_month = max(monthly, key=lambda x: x['messages'])
            low_month = min(monthly, key=lambda x: x['messages'])
            content += f"\nPeak Month: {peak_month['month']} ({peak_month['messages']:,} messages)\n"
            content += f"Slowest Month: {low_month['month']} ({low_month['messages']:,} messages)\n"

        report.append(format_section("MONTHLY ACTIVITY TREND", content))

        # =====================================================================
        # SECTION 18: FIRST AND LAST MESSAGES
        # =====================================================================
        first_msg = run_query(conn, """
            SELECT
                u.username,
                m.content,
                m.created_at,
                c.name as channel
            FROM messages m
            JOIN users u ON m.author_id = u.id
            JOIN channels c ON m.channel_id = c.id
            ORDER BY m.created_at ASC
            LIMIT 1
        """)

        last_msg = run_query(conn, """
            SELECT
                u.username,
                m.content,
                m.created_at,
                c.name as channel
            FROM messages m
            JOIN users u ON m.author_id = u.id
            JOIN channels c ON m.channel_id = c.id
            ORDER BY m.created_at DESC
            LIMIT 1
        """)

        content = "\nFirst Message of the Year:\n"
        if first_msg:
            fm = first_msg[0]
            content += f"  By: {fm['username']}\n"
            content += f"  When: {fm['created_at']}\n"
            content += f"  Channel: #{fm['channel']}\n"
            content += f"  Message: \"{fm['content'][:100]}{'...' if len(fm['content']) > 100 else ''}\"\n"

        content += "\nMost Recent Message:\n"
        if last_msg:
            lm = last_msg[0]
            content += f"  By: {lm['username']}\n"
            content += f"  When: {lm['created_at']}\n"
            content += f"  Channel: #{lm['channel']}\n"
            content += f"  Message: \"{lm['content'][:100]}{'...' if len(lm['content']) > 100 else ''}\"\n"

        report.append(format_section("FIRST AND LAST MESSAGES", content))

        # =====================================================================
        # SECTION 19: FAN RELATIONSHIPS (One-Sided Attention)
        # =====================================================================
        # Uses join with messages table since reply_to_author_id may not be populated
        fans = run_query(conn, """
            WITH reply_counts AS (
                SELECT
                    m.author_id as replier,
                    orig.author_id as target,
                    COUNT(*) as reply_count
                FROM messages m
                JOIN messages orig ON m.reply_to_message_id = orig.id
                WHERE m.author_id != orig.author_id
                GROUP BY m.author_id, orig.author_id
            )
            SELECT
                u1.username as fan,
                u2.username as idol,
                rc1.reply_count as fan_to_idol,
                COALESCE(rc2.reply_count, 0) as idol_to_fan,
                rc1.reply_count - COALESCE(rc2.reply_count, 0) as imbalance
            FROM reply_counts rc1
            JOIN users u1 ON rc1.replier = u1.id
            JOIN users u2 ON rc1.target = u2.id
            LEFT JOIN reply_counts rc2 ON rc1.replier = rc2.target AND rc1.target = rc2.replier
            WHERE rc1.reply_count >= 5
            ORDER BY imbalance DESC
            LIMIT 10
        """)

        content = "\nOne-sided reply relationships (Fan replies to Idol more than vice versa):\n\n"
        content += "Fan                   -> Idol                    Fan->Idol  Idol->Fan\n"
        content += "-" * 70 + "\n"
        for f in fans:
            content += f"{f['fan']:<20} -> {f['idol']:<22} {f['fan_to_idol']:>8}    {f['idol_to_fan']:>8}\n"

        report.append(format_section("FAN RELATIONSHIPS (One-Sided Attention)", content))

        # =====================================================================
        # SECTION 20: BUSIEST DAYS
        # =====================================================================
        busiest = run_query(conn, """
            SELECT
                DATE(created_at) as date,
                COUNT(*) as messages,
                COUNT(DISTINCT author_id) as active_users
            FROM messages
            GROUP BY date
            ORDER BY messages DESC
            LIMIT 10
        """)

        content = "\nThe 10 busiest days of the year:\n\n"
        content += "Rank  Date          Messages    Active Users\n"
        content += "-" * 60 + "\n"
        for i, day in enumerate(busiest, 1):
            content += f"{i:2}.   {day['date']}    {day['messages']:>7}    {day['active_users']:>12}\n"

        report.append(format_section("BUSIEST DAYS", content))

        # =====================================================================
        # FOOTER
        # =====================================================================
        report.append(f"""
################################################################################
#                                                                              #
#                         END OF YEAR-END REVIEW                               #
#                                                                              #
################################################################################

Thanks for a great year, {server_name}!

Report generated by Discord SQL Analytics
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""")

    # Write report to file
    full_report = "\n".join(report)
    with open(output_file, 'w') as f:
        f.write(full_report)

    print(full_report)
    print(f"\n\nReport saved to: {output_file}")

    return full_report


def main():
    parser = argparse.ArgumentParser(description="Generate Discord Year-End Review")
    parser.add_argument("--db", type=str, default=DEFAULT_DB, help="Database file")
    parser.add_argument("--output", type=str, default=OUTPUT_FILE, help="Output file")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Error: Database file not found: {args.db}")
        sys.exit(1)

    print(f"Generating year-end review from: {args.db}")
    print(f"Output file: {args.output}")
    print()

    engine = create_engine(f"sqlite:///{args.db}", echo=False)
    generate_report(engine, args.output)


if __name__ == "__main__":
    main()
