"""
Mock Discord objects that match discord.py signatures exactly.

These objects allow the extractor to run identically whether connected
to real Discord or using simulated data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, AsyncIterator, TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Discord epoch: January 1, 2015 00:00:00 UTC in milliseconds
DISCORD_EPOCH = 1420070400000


def snowflake_to_datetime(snowflake: int) -> datetime:
    """Convert Discord snowflake ID to datetime."""
    timestamp_ms = (snowflake >> 22) + DISCORD_EPOCH
    return datetime.utcfromtimestamp(timestamp_ms / 1000)


@dataclass
class MockUser:
    """
    Matches discord.User signature exactly.

    Properties match discord.py 2.0+ naming conventions.
    """
    id: int
    name: str
    discriminator: str = "0"
    global_name: Optional[str] = None
    avatar: Optional[str] = None
    bot: bool = False
    system: bool = False

    # Internal: activity level for message generation weighting
    _activity_level: str = field(default="casual", repr=False)

    @property
    def display_name(self) -> str:
        """The user's display name (global_name or username)."""
        return self.global_name or self.name

    @property
    def created_at(self) -> datetime:
        """When the user's account was created (derived from snowflake)."""
        return snowflake_to_datetime(self.id)

    @property
    def mention(self) -> str:
        """Returns a string to mention the user."""
        return f"<@{self.id}>"

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, MockUser):
            return self.id == other.id
        return False


@dataclass
class MockMember(MockUser):
    """
    Matches discord.Member signature.

    Extends MockUser with guild-specific information.
    """
    nick: Optional[str] = None
    joined_at: Optional[datetime] = None
    guild: Optional["MockGuild"] = field(default=None, repr=False)

    @property
    def display_name(self) -> str:
        """The member's display name (nick, global_name, or username)."""
        return self.nick or self.global_name or self.name


@dataclass
class MockEmoji:
    """
    Matches discord.PartialEmoji / discord.Emoji signature.

    For unicode emoji, id is None and name is the unicode character.
    For custom emoji, id is the emoji's snowflake ID.
    """
    id: Optional[int]
    name: str
    animated: bool = False

    @property
    def is_custom_emoji(self) -> bool:
        """Whether this is a custom emoji (vs unicode)."""
        return self.id is not None

    @property
    def is_unicode_emoji(self) -> bool:
        """Whether this is a unicode emoji."""
        return self.id is None

    def __str__(self) -> str:
        """String representation matching Discord format."""
        if self.id:
            prefix = "a" if self.animated else ""
            return f"<{prefix}:{self.name}:{self.id}>"
        return self.name

    def __hash__(self):
        return hash((self.id, self.name))

    def __eq__(self, other):
        if isinstance(other, MockEmoji):
            return self.id == other.id and self.name == other.name
        return False


@dataclass
class MockReaction:
    """
    Matches discord.Reaction signature.

    Represents a reaction on a message with all users who reacted.
    """
    message: "MockMessage" = field(repr=False)
    emoji: MockEmoji
    count: int
    me: bool = False
    _users: List[MockUser] = field(default_factory=list, repr=False)

    async def users(self, limit: Optional[int] = None) -> AsyncIterator[MockUser]:
        """
        Async iterator over users who reacted.

        Mimics discord.py's paginated async iterator behavior exactly.
        In real discord.py, this makes API calls with pagination.
        """
        users_to_yield = self._users if limit is None else self._users[:limit]
        for user in users_to_yield:
            yield user


@dataclass
class MockMessageReference:
    """
    Matches discord.MessageReference signature.

    Used for replies and forwarded messages.
    """
    message_id: Optional[int]
    channel_id: int
    guild_id: Optional[int] = None

    @property
    def resolved(self) -> Optional["MockMessage"]:
        """The resolved message (not implemented in mock)."""
        return None


@dataclass
class MockMessage:
    """
    Matches discord.Message signature exactly.

    Core message object with all fields needed for analytics.
    """
    id: int
    channel: "MockChannel" = field(repr=False)
    author: MockUser
    content: str
    created_at: datetime
    edited_at: Optional[datetime] = None
    tts: bool = False
    mention_everyone: bool = False
    mentions: List[MockUser] = field(default_factory=list)
    pinned: bool = False
    type: int = 0  # MessageType.default = 0, reply = 19
    reference: Optional[MockMessageReference] = None
    reactions: List[MockReaction] = field(default_factory=list)
    attachments: List = field(default_factory=list)
    embeds: List = field(default_factory=list)

    # Internal: for tracking reply target author (used in extraction)
    _reply_to_author_id: Optional[int] = field(default=None, repr=False)

    @property
    def guild(self) -> Optional["MockGuild"]:
        """The guild this message was sent in."""
        if hasattr(self.channel, 'guild'):
            return self.channel.guild
        return None

    @property
    def jump_url(self) -> str:
        """URL to jump to this message."""
        guild_id = self.guild.id if self.guild else "@me"
        return f"https://discord.com/channels/{guild_id}/{self.channel.id}/{self.id}"

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, MockMessage):
            return self.id == other.id
        return False


@dataclass
class MockChannel:
    """
    Matches discord.TextChannel signature.

    Implements history() method that behaves exactly like discord.py.
    """
    id: int
    name: str
    guild: "MockGuild" = field(repr=False)
    topic: Optional[str] = None
    position: int = 0
    nsfw: bool = False
    category_id: Optional[int] = None
    _messages: List[MockMessage] = field(default_factory=list, repr=False)

    @property
    def mention(self) -> str:
        """Returns a string to mention this channel."""
        return f"<#{self.id}>"

    @property
    def created_at(self) -> datetime:
        """When the channel was created (derived from snowflake)."""
        return snowflake_to_datetime(self.id)

    async def history(
        self,
        limit: Optional[int] = 100,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None,
        around: Optional[datetime] = None,
        oldest_first: bool = False
    ) -> AsyncIterator[MockMessage]:
        """
        Async iterator over message history.

        Mimics discord.py's channel.history() EXACTLY:
        - Respects limit, before, after parameters
        - Returns messages newest-first by default
        - Supports oldest_first parameter

        In real discord.py, this makes paginated API calls.
        discord.py handles rate limiting automatically.
        """
        messages = self._messages.copy()

        # Filter by time range
        if after is not None:
            if isinstance(after, datetime):
                messages = [m for m in messages if m.created_at > after]
            else:
                # Could be a snowflake or message object
                after_time = after if isinstance(after, datetime) else snowflake_to_datetime(after)
                messages = [m for m in messages if m.created_at > after_time]

        if before is not None:
            if isinstance(before, datetime):
                messages = [m for m in messages if m.created_at < before]
            else:
                before_time = before if isinstance(before, datetime) else snowflake_to_datetime(before)
                messages = [m for m in messages if m.created_at < before_time]

        # Sort order: newest first by default
        messages.sort(key=lambda m: m.created_at, reverse=not oldest_first)

        # Apply limit
        if limit is not None:
            messages = messages[:limit]

        for msg in messages:
            yield msg

    def __hash__(self):
        return hash(self.id)


@dataclass
class MockGuild:
    """
    Matches discord.Guild signature.

    Represents a Discord server with channels and members.
    """
    id: int
    name: str
    owner_id: int
    icon: Optional[str] = None
    member_count: int = 0
    _members: List[MockMember] = field(default_factory=list, repr=False)
    _channels: List[MockChannel] = field(default_factory=list, repr=False)

    @property
    def text_channels(self) -> List[MockChannel]:
        """List of text channels in this guild."""
        return list(self._channels)

    @property
    def channels(self) -> List[MockChannel]:
        """All channels in this guild."""
        return list(self._channels)

    @property
    def members(self) -> List[MockMember]:
        """All members in this guild."""
        return list(self._members)

    @property
    def created_at(self) -> datetime:
        """When the guild was created (derived from snowflake)."""
        return snowflake_to_datetime(self.id)

    async def fetch_members(
        self,
        limit: Optional[int] = None
    ) -> AsyncIterator[MockMember]:
        """
        Async iterator over guild members.

        Mimics discord.py's guild.fetch_members() paginated behavior.
        Requires GUILD_MEMBERS intent in real Discord.
        """
        members_to_yield = self._members if limit is None else self._members[:limit]
        for member in members_to_yield:
            yield member

    def get_member(self, user_id: int) -> Optional[MockMember]:
        """Get a member by ID."""
        for member in self._members:
            if member.id == user_id:
                return member
        return None

    def get_channel(self, channel_id: int) -> Optional[MockChannel]:
        """Get a channel by ID."""
        for channel in self._channels:
            if channel.id == channel_id:
                return channel
        return None

    def __hash__(self):
        return hash(self.id)
