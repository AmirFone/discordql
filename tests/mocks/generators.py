"""
Realistic Discord data generator.

Generates data that matches real-world Discord server patterns:
- Activity distributions (power users, casuals, lurkers)
- Reply chain patterns
- Reaction distributions
- Time-of-day activity patterns
"""
from __future__ import annotations

import random
import string
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

from .discord_objects import (
    MockUser,
    MockMember,
    MockMessage,
    MockChannel,
    MockGuild,
    MockReaction,
    MockEmoji,
    MockMessageReference,
    DISCORD_EPOCH,
)


# =============================================================================
# REALISTIC DISTRIBUTION CONSTANTS
# =============================================================================

# User activity patterns based on real Discord server analysis
ACTIVITY_PATTERNS: Dict[str, float] = {
    "lurker": 0.60,       # 60% of users rarely post (1-2 msgs/week)
    "casual": 0.25,       # 25% post occasionally (few msgs/day)
    "active": 0.12,       # 12% post regularly (many msgs/day)
    "power_user": 0.03,   # 3% post very frequently (dominant voices)
}

# Activity level weights for message authorship
ACTIVITY_WEIGHTS: Dict[str, int] = {
    "lurker": 1,
    "casual": 5,
    "active": 15,
    "power_user": 40,
}

# Interaction probabilities
REPLY_PROBABILITY = 0.35      # 35% of messages are replies
REACTION_PROBABILITY = 0.20   # 20% of messages get at least one reaction
MENTION_PROBABILITY = 0.15    # 15% of messages mention someone

# Common unicode emoji with realistic usage frequency
COMMON_EMOJIS: List[Tuple[str, float]] = [
    ("👍", 0.25),   # Thumbs up - most common
    ("❤️", 0.15),   # Heart
    ("😂", 0.12),   # Laughing
    ("🔥", 0.08),   # Fire
    ("👀", 0.07),   # Eyes
    ("🎉", 0.06),   # Party
    ("💯", 0.05),   # 100
    ("👎", 0.04),   # Thumbs down
    ("😢", 0.03),   # Sad
    ("🤔", 0.03),   # Thinking
    ("👏", 0.03),   # Clap
    ("✅", 0.03),   # Check
    ("⭐", 0.02),   # Star
    ("🙏", 0.02),   # Pray
    ("💀", 0.02),   # Skull
]

# Message content templates
MESSAGE_TEMPLATES = [
    "Hey everyone!",
    "Does anyone know how to {topic}?",
    "I just finished {topic} and it was great",
    "lol",
    "That's a good point about {topic}",
    "I agree with what you said",
    "Has anyone tried {topic}?",
    "Check this out",
    "Thanks for the help!",
    "brb",
    "gg",
    "Nice!",
    "What do you think about {topic}?",
    "Just saw this and thought of you all",
    "Can someone help me with {topic}?",
    "Finally got it working!",
    "This is interesting",
    "Anyone online?",
    "Good morning everyone",
    "I'm so confused about {topic}",
]

TOPICS = [
    "the new update", "this bug", "Python", "JavaScript", "the API",
    "performance issues", "the documentation", "testing", "deployment",
    "the database", "authentication", "the frontend", "mobile support",
    "async programming", "error handling", "logging", "caching",
]


class DiscordDataGenerator:
    """
    Generates realistic Discord server data for testing.

    Uses seeded random for reproducibility in tests.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize the generator.

        Args:
            seed: Random seed for reproducible generation
        """
        self._random = random.Random(seed)
        self._snowflake_counter = 1000000000000000000
        self._base_time = datetime.utcnow()

    def _next_snowflake(self, created_at: Optional[datetime] = None) -> int:
        """
        Generate a Discord snowflake ID with correct timestamp encoding.

        Discord snowflake format:
        - Bits 22-63: Timestamp (ms since Discord epoch)
        - Bits 17-21: Worker ID
        - Bits 12-16: Process ID
        - Bits 0-11: Increment

        Args:
            created_at: Optional timestamp to encode in snowflake

        Returns:
            Valid Discord snowflake ID
        """
        if created_at is None:
            created_at = self._base_time

        timestamp_ms = int(created_at.timestamp() * 1000) - DISCORD_EPOCH
        self._snowflake_counter += 1

        # Construct snowflake: timestamp | worker | process | increment
        snowflake = (timestamp_ms << 22) | (self._snowflake_counter & 0x3FFFFF)
        return snowflake

    def _pick_weighted(self, weights: Dict[str, float]) -> str:
        """Pick a key from dict weighted by values."""
        items = list(weights.keys())
        probs = list(weights.values())
        return self._random.choices(items, weights=probs, k=1)[0]

    def _random_string(self, length: int) -> str:
        """Generate a random lowercase string."""
        return ''.join(self._random.choices(string.ascii_lowercase, k=length))

    def _random_timestamp(
        self,
        start: datetime,
        end: datetime
    ) -> datetime:
        """
        Generate a timestamp with realistic hour distribution.

        Biases towards peak hours (10am-10pm) to match real Discord usage.
        """
        delta = end - start
        random_seconds = self._random.random() * delta.total_seconds()
        timestamp = start + timedelta(seconds=random_seconds)

        # Bias towards peak hours (10am-10pm)
        hour = timestamp.hour
        if hour < 10 or hour > 22:
            if self._random.random() < 0.7:  # 70% chance to shift
                new_hour = self._random.randint(10, 22)
                timestamp = timestamp.replace(hour=new_hour)

        return timestamp

    def _generate_message_content(self) -> str:
        """Generate realistic message content."""
        template = self._random.choice(MESSAGE_TEMPLATES)
        if "{topic}" in template:
            topic = self._random.choice(TOPICS)
            return template.format(topic=topic)
        return template

    def generate_users(self, count: int) -> List[MockUser]:
        """
        Generate users with realistic activity level distribution.

        60% lurkers, 25% casual, 12% active, 3% power users.
        """
        users = []
        for i in range(count):
            activity_level = self._pick_weighted(ACTIVITY_PATTERNS)

            user = MockUser(
                id=self._next_snowflake(),
                name=f"user_{i}_{self._random_string(4)}",
                discriminator="0",
                global_name=self._random.choice([
                    None,
                    f"User {i}",
                    f"Cool{self._random_string(3).title()}",
                ]),
                bot=self._random.random() < 0.02,  # 2% bots
                _activity_level=activity_level,
            )
            users.append(user)

        return users

    def _pick_author_by_activity(self, users: List[MockUser]) -> MockUser:
        """
        Pick a message author weighted by activity level.

        Power users write disproportionately more messages.
        """
        weights = []
        for user in users:
            level = getattr(user, '_activity_level', 'casual')
            weights.append(ACTIVITY_WEIGHTS[level])
        return self._random.choices(users, weights=weights, k=1)[0]

    def _add_reactions(
        self,
        messages: List[MockMessage],
        users: List[MockUser]
    ) -> None:
        """
        Add reactions to messages with realistic patterns.

        - 20% of messages get reactions
        - Exponential distribution for reactor count
        - Common emoji used more frequently
        """
        for msg in messages:
            if self._random.random() > REACTION_PROBABILITY:
                continue

            # Number of different emoji on this message (1-5, weighted low)
            emoji_count = self._random.choices(
                [1, 2, 3, 4, 5],
                weights=[0.5, 0.25, 0.15, 0.07, 0.03],
                k=1
            )[0]

            # Sample emoji (without replacement)
            selected_emojis = self._random.sample(
                COMMON_EMOJIS,
                min(emoji_count, len(COMMON_EMOJIS))
            )

            for emoji_name, _ in selected_emojis:
                # Exponential distribution for reactor count
                reactor_count = max(1, int(self._random.expovariate(0.3)))
                reactor_count = min(reactor_count, len(users))

                # Sample reactors (can include message author - self-react is common)
                reactors = self._random.sample(users, reactor_count)

                emoji = MockEmoji(id=None, name=emoji_name)
                reaction = MockReaction(
                    message=msg,
                    emoji=emoji,
                    count=len(reactors),
                    _users=reactors,
                )
                msg.reactions.append(reaction)

    def generate_messages(
        self,
        channel: MockChannel,
        users: List[MockUser],
        count: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[MockMessage]:
        """
        Generate messages with realistic patterns.

        - Activity-weighted author selection
        - 35% reply probability
        - 15% mention probability
        - Peak hour time bias
        - Reactions added after all messages generated
        """
        messages: List[MockMessage] = []
        recent_messages: List[MockMessage] = []

        for _ in range(count):
            author = self._pick_author_by_activity(users)
            created_at = self._random_timestamp(start_date, end_date)

            msg = MockMessage(
                id=self._next_snowflake(created_at),
                channel=channel,
                author=author,
                content=self._generate_message_content(),
                created_at=created_at,
                mentions=[],
                reactions=[],
            )

            # Maybe make it a reply (35% chance)
            if recent_messages and self._random.random() < REPLY_PROBABILITY:
                # Reply to one of the last 20 messages
                reply_target = self._random.choice(recent_messages[-20:])
                msg.reference = MockMessageReference(
                    message_id=reply_target.id,
                    channel_id=channel.id,
                    guild_id=channel.guild.id if channel.guild else None,
                )
                msg.type = 19  # MessageType.reply
                msg._reply_to_author_id = reply_target.author.id

            # Maybe add mentions (15% chance)
            if self._random.random() < MENTION_PROBABILITY:
                mention_count = self._random.choices(
                    [1, 2, 3],
                    weights=[0.7, 0.2, 0.1],
                    k=1
                )[0]
                msg.mentions = self._random.sample(
                    users,
                    min(mention_count, len(users))
                )

            messages.append(msg)
            recent_messages.append(msg)

        # Add reactions after all messages exist
        self._add_reactions(messages, users)

        # Sort by creation time
        messages.sort(key=lambda m: m.created_at)

        return messages

    def generate_guild(
        self,
        name: str = "Test Server",
        user_count: int = 50,
        channel_count: int = 5,
        messages_per_channel: int = 200,
        days: int = 7
    ) -> MockGuild:
        """
        Generate a complete guild with users, channels, and messages.

        This is the main entry point for generating test data.
        """
        # Create guild
        guild = MockGuild(
            id=self._next_snowflake(),
            name=name,
            owner_id=0,  # Will be set below
            member_count=user_count,
        )

        # Create users
        users = self.generate_users(user_count)
        guild.owner_id = users[0].id

        # Convert to members
        for user in users:
            member = MockMember(
                id=user.id,
                name=user.name,
                discriminator=user.discriminator,
                global_name=user.global_name,
                bot=user.bot,
                guild=guild,
                joined_at=self._base_time - timedelta(
                    days=self._random.randint(1, 365)
                ),
                _activity_level=user._activity_level,
            )
            guild._members.append(member)

        # Create channels with messages
        end_date = self._base_time
        start_date = end_date - timedelta(days=days)

        channel_names = [
            "general", "random", "help", "announcements", "off-topic",
            "development", "testing", "feedback", "showcase", "resources",
        ]

        for i in range(channel_count):
            channel_name = (
                channel_names[i]
                if i < len(channel_names)
                else f"channel-{i}"
            )

            channel = MockChannel(
                id=self._next_snowflake(),
                name=channel_name,
                guild=guild,
                position=i,
            )

            # Generate messages for this channel
            # Use members as users (they have the same interface)
            channel._messages = self.generate_messages(
                channel=channel,
                users=guild._members,  # type: ignore
                count=messages_per_channel,
                start_date=start_date,
                end_date=end_date,
            )

            guild._channels.append(channel)

        return guild
