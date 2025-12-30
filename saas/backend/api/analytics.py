"""
Analytics API endpoints.
Provides real-time analytics data from the shared Discord database with RLS.
"""
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.auth import User, get_current_user
from services.shared_database import get_shared_pool
from services.tenant import tenant_connection

router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================

class OverviewStats(BaseModel):
    """High-level server statistics."""
    total_messages: int
    total_users: int
    total_channels: int
    total_mentions: int
    messages_change_percent: float  # vs previous period
    users_change_percent: float
    avg_messages_per_day: float
    avg_message_length: float


class TimeSeriesPoint(BaseModel):
    """Single point in a time series."""
    date: str
    count: int


class ChannelStats(BaseModel):
    """Statistics for a single channel."""
    channel_id: str
    channel_name: str
    message_count: int
    unique_users: int
    avg_message_length: float


class UserStats(BaseModel):
    """Statistics for a single user."""
    user_id: str
    username: str
    message_count: int
    mention_count: int
    reply_count: int
    avg_message_length: float
    is_bot: bool


class HourlyActivity(BaseModel):
    """Activity breakdown by hour."""
    hour: int
    message_count: int
    unique_users: int


class DayOfWeekActivity(BaseModel):
    """Activity breakdown by day of week."""
    day: int  # 0=Sunday, 6=Saturday
    day_name: str
    message_count: int


class UserInteraction(BaseModel):
    """Interaction between two users."""
    from_user: str
    to_user: str
    mention_count: int
    reply_count: int


class MessageTypeBreakdown(BaseModel):
    """Breakdown of message types."""
    message_type: str
    count: int
    percentage: float


class ContentMetrics(BaseModel):
    """Content analysis metrics."""
    total_words: int
    total_characters: int
    avg_words_per_message: float
    messages_with_attachments: int
    messages_with_embeds: int
    messages_with_mentions: int
    pinned_messages: int


class EngagementMetrics(BaseModel):
    """User engagement metrics."""
    reply_rate: float  # % of messages that are replies
    mention_rate: float  # % of messages with mentions
    active_user_ratio: float  # users who sent messages / total users
    messages_per_active_user: float


class ChannelGrowth(BaseModel):
    """Channel activity growth."""
    channel_name: str
    current_period: int
    previous_period: int
    growth_percent: float


class AnalyticsResponse(BaseModel):
    """Complete analytics response."""
    overview: OverviewStats
    messages_over_time: List[TimeSeriesPoint]
    hourly_activity: List[HourlyActivity]
    day_of_week_activity: List[DayOfWeekActivity]
    top_channels: List[ChannelStats]
    top_users: List[UserStats]
    user_interactions: List[UserInteraction]
    content_metrics: ContentMetrics
    engagement_metrics: EngagementMetrics
    channel_growth: List[ChannelGrowth]
    bot_vs_human: dict
    time_range_days: int


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/overview", response_model=AnalyticsResponse)
async def get_analytics(
    days: int = Query(default=30, ge=1, le=365, description="Time range in days"),
    user: User = Depends(get_current_user),
):
    """
    Get comprehensive analytics for the user's Discord data.

    All queries use Row-Level Security to ensure tenant isolation.
    """
    pool = await get_shared_pool()

    async with tenant_connection(pool, user.clerk_id) as conn:
        now = datetime.utcnow()
        start_date = now - timedelta(days=days)
        prev_start = start_date - timedelta(days=days)

        # =================================================================
        # Overview Stats
        # =================================================================
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

        overview_row = await conn.fetchrow(overview_query, start_date, prev_start)

        total_messages = overview_row['total_messages']
        prev_messages = overview_row['prev_messages']
        total_users = overview_row['total_users']
        prev_users = overview_row['prev_users']

        msg_change = ((total_messages - prev_messages) / max(prev_messages, 1)) * 100 if prev_messages else 0
        user_change = ((total_users - prev_users) / max(prev_users, 1)) * 100 if prev_users else 0

        overview = OverviewStats(
            total_messages=total_messages,
            total_users=total_users,
            total_channels=overview_row['total_channels'],
            total_mentions=overview_row['total_mentions'],
            messages_change_percent=round(msg_change, 1),
            users_change_percent=round(user_change, 1),
            avg_messages_per_day=round(total_messages / max(days, 1), 1),
            avg_message_length=round(overview_row['avg_length'] or 0, 1),
        )

        # =================================================================
        # Messages Over Time (daily)
        # =================================================================
        time_series_query = """
        SELECT
            DATE(created_at) as date,
            COUNT(*) as count
        FROM messages
        WHERE created_at >= $1
        GROUP BY DATE(created_at)
        ORDER BY date
        """

        time_series_rows = await conn.fetch(time_series_query, start_date)
        messages_over_time = [
            TimeSeriesPoint(date=str(row['date']), count=row['count'])
            for row in time_series_rows
        ]

        # =================================================================
        # Hourly Activity
        # =================================================================
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

        hourly_rows = await conn.fetch(hourly_query, start_date)
        # Fill in missing hours with zeros
        hourly_map = {row['hour']: row for row in hourly_rows}
        hourly_activity = [
            HourlyActivity(
                hour=h,
                message_count=hourly_map.get(h, {}).get('message_count', 0),
                unique_users=hourly_map.get(h, {}).get('unique_users', 0)
            )
            for h in range(24)
        ]

        # =================================================================
        # Day of Week Activity
        # =================================================================
        dow_query = """
        SELECT
            EXTRACT(DOW FROM created_at)::int as day,
            COUNT(*) as message_count
        FROM messages
        WHERE created_at >= $1
        GROUP BY day
        ORDER BY day
        """

        dow_rows = await conn.fetch(dow_query, start_date)
        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        dow_map = {row['day']: row['message_count'] for row in dow_rows}
        day_of_week_activity = [
            DayOfWeekActivity(
                day=d,
                day_name=day_names[d],
                message_count=dow_map.get(d, 0)
            )
            for d in range(7)
        ]

        # =================================================================
        # Top Channels
        # =================================================================
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

        channel_rows = await conn.fetch(channels_query, start_date)
        top_channels = [
            ChannelStats(
                channel_id=row['channel_id'],
                channel_name=row['channel_name'],
                message_count=row['message_count'] or 0,
                unique_users=row['unique_users'] or 0,
                avg_message_length=round(row['avg_length'] or 0, 1)
            )
            for row in channel_rows
        ]

        # =================================================================
        # Top Users
        # =================================================================
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

        user_rows = await conn.fetch(users_query, start_date)
        top_users = [
            UserStats(
                user_id=row['user_id'],
                username=row['username'],
                message_count=row['message_count'] or 0,
                mention_count=row['mention_count'] or 0,
                reply_count=row['reply_count'] or 0,
                avg_message_length=round(row['avg_length'] or 0, 1),
                is_bot=row['is_bot'] or False
            )
            for row in user_rows
        ]

        # =================================================================
        # User Interactions (mentions and replies)
        # =================================================================
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

        interaction_rows = await conn.fetch(interactions_query, start_date)
        user_interactions = [
            UserInteraction(
                from_user=row['from_user'] or 'Unknown',
                to_user=row['to_user'] or 'Unknown',
                mention_count=row['mention_count'] or 0,
                reply_count=row['reply_count'] or 0
            )
            for row in interaction_rows
        ]

        # =================================================================
        # Content Metrics
        # =================================================================
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

        content_row = await conn.fetchrow(content_query, start_date)
        content_metrics = ContentMetrics(
            total_words=content_row['total_words'],
            total_characters=content_row['total_chars'],
            avg_words_per_message=round(content_row['avg_words'], 1),
            messages_with_attachments=content_row['with_attachments'],
            messages_with_embeds=content_row['with_embeds'],
            messages_with_mentions=content_row['with_mentions'],
            pinned_messages=content_row['pinned'],
        )

        # =================================================================
        # Engagement Metrics
        # =================================================================
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

        engagement_row = await conn.fetchrow(engagement_query, start_date)
        total_msg = max(engagement_row['total'], 1)
        total_usr = max(engagement_row['total_users'], 1)
        active_usr = engagement_row['active_users']

        engagement_metrics = EngagementMetrics(
            reply_rate=round((engagement_row['replies'] / total_msg) * 100, 1),
            mention_rate=round((engagement_row['with_mentions'] / total_msg) * 100, 1),
            active_user_ratio=round((active_usr / total_usr) * 100, 1),
            messages_per_active_user=round(total_msg / max(active_usr, 1), 1),
        )

        # =================================================================
        # Channel Growth (current vs previous period)
        # =================================================================
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

        growth_rows = await conn.fetch(growth_query, start_date, prev_start)
        channel_growth = [
            ChannelGrowth(
                channel_name=row['channel_name'],
                current_period=row['current_count'],
                previous_period=row['prev_count'],
                growth_percent=round(
                    ((row['current_count'] - row['prev_count']) / max(row['prev_count'], 1)) * 100, 1
                ) if row['prev_count'] else 0
            )
            for row in growth_rows
        ]

        # =================================================================
        # Bot vs Human Activity
        # =================================================================
        bot_query = """
        SELECT
            u.is_bot,
            COUNT(m.id) as message_count
        FROM messages m
        JOIN users u ON m.author_id = u.id
        WHERE m.created_at >= $1
        GROUP BY u.is_bot
        """

        bot_rows = await conn.fetch(bot_query, start_date)
        bot_vs_human = {
            'human_messages': 0,
            'bot_messages': 0,
            'human_percentage': 0,
            'bot_percentage': 0
        }
        total_typed = 0
        for row in bot_rows:
            if row['is_bot']:
                bot_vs_human['bot_messages'] = row['message_count']
            else:
                bot_vs_human['human_messages'] = row['message_count']
            total_typed += row['message_count']

        if total_typed > 0:
            bot_vs_human['human_percentage'] = round((bot_vs_human['human_messages'] / total_typed) * 100, 1)
            bot_vs_human['bot_percentage'] = round((bot_vs_human['bot_messages'] / total_typed) * 100, 1)

        return AnalyticsResponse(
            overview=overview,
            messages_over_time=messages_over_time,
            hourly_activity=hourly_activity,
            day_of_week_activity=day_of_week_activity,
            top_channels=top_channels,
            top_users=top_users,
            user_interactions=user_interactions,
            content_metrics=content_metrics,
            engagement_metrics=engagement_metrics,
            channel_growth=channel_growth,
            bot_vs_human=bot_vs_human,
            time_range_days=days,
        )


# =============================================================================
# Additional Endpoints for Specific Analytics
# =============================================================================

@router.get("/messages/timeline")
async def get_message_timeline(
    days: int = Query(default=30, ge=1, le=365),
    granularity: str = Query(default="day", regex="^(hour|day|week)$"),
    user: User = Depends(get_current_user),
):
    """Get message count timeline with configurable granularity."""
    pool = await get_shared_pool()

    async with tenant_connection(pool, user.clerk_id) as conn:
        start_date = datetime.utcnow() - timedelta(days=days)

        if granularity == "hour":
            query = """
            SELECT
                DATE_TRUNC('hour', created_at) as period,
                COUNT(*) as count
            FROM messages
            WHERE created_at >= $1
            GROUP BY period
            ORDER BY period
            """
        elif granularity == "week":
            query = """
            SELECT
                DATE_TRUNC('week', created_at) as period,
                COUNT(*) as count
            FROM messages
            WHERE created_at >= $1
            GROUP BY period
            ORDER BY period
            """
        else:  # day
            query = """
            SELECT
                DATE(created_at) as period,
                COUNT(*) as count
            FROM messages
            WHERE created_at >= $1
            GROUP BY period
            ORDER BY period
            """

        rows = await conn.fetch(query, start_date)
        return [{"period": str(row['period']), "count": row['count']} for row in rows]


@router.get("/users/activity")
async def get_user_activity_distribution(
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
):
    """Get distribution of user activity levels."""
    pool = await get_shared_pool()

    async with tenant_connection(pool, user.clerk_id) as conn:
        start_date = datetime.utcnow() - timedelta(days=days)

        query = """
        WITH user_msg_counts AS (
            SELECT author_id, COUNT(*) as msg_count
            FROM messages
            WHERE created_at >= $1
            GROUP BY author_id
        )
        SELECT
            CASE
                WHEN msg_count = 1 THEN '1 message'
                WHEN msg_count BETWEEN 2 AND 5 THEN '2-5 messages'
                WHEN msg_count BETWEEN 6 AND 20 THEN '6-20 messages'
                WHEN msg_count BETWEEN 21 AND 50 THEN '21-50 messages'
                WHEN msg_count BETWEEN 51 AND 100 THEN '51-100 messages'
                ELSE '100+ messages'
            END as activity_level,
            COUNT(*) as user_count
        FROM user_msg_counts
        GROUP BY activity_level
        ORDER BY MIN(msg_count)
        """

        rows = await conn.fetch(query, start_date)
        return [{"level": row['activity_level'], "users": row['user_count']} for row in rows]


@router.get("/channels/{channel_id}/stats")
async def get_channel_details(
    channel_id: str,
    days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
):
    """Get detailed statistics for a specific channel."""
    pool = await get_shared_pool()

    async with tenant_connection(pool, user.clerk_id) as conn:
        start_date = datetime.utcnow() - timedelta(days=days)

        query = """
        SELECT
            c.name,
            c.topic,
            COUNT(m.id) as total_messages,
            COUNT(DISTINCT m.author_id) as unique_users,
            AVG(m.word_count) as avg_words,
            AVG(m.char_count) as avg_chars,
            COUNT(*) FILTER (WHERE m.reply_to_message_id IS NOT NULL) as replies,
            COUNT(*) FILTER (WHERE m.attachment_count > 0) as with_attachments
        FROM channels c
        LEFT JOIN messages m ON c.id = m.channel_id AND m.created_at >= $2
        WHERE c.id = $1
        GROUP BY c.id, c.name, c.topic
        """

        try:
            channel_id_int = int(channel_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid channel ID")

        row = await conn.fetchrow(query, channel_id_int, start_date)

        if not row:
            raise HTTPException(status_code=404, detail="Channel not found")

        return {
            "name": row['name'],
            "topic": row['topic'],
            "total_messages": row['total_messages'] or 0,
            "unique_users": row['unique_users'] or 0,
            "avg_words_per_message": round(row['avg_words'] or 0, 1),
            "avg_chars_per_message": round(row['avg_chars'] or 0, 1),
            "reply_count": row['replies'] or 0,
            "messages_with_attachments": row['with_attachments'] or 0,
        }
