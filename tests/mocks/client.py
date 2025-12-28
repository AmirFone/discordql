"""
Mock Discord client that serves as a drop-in replacement for discord.Client.

The extractor code uses this abstraction layer, allowing it to work
identically whether connected to real Discord or using simulated data.
"""
from __future__ import annotations

from typing import Optional, List

from .discord_objects import MockGuild, MockChannel
from .generators import DiscordDataGenerator


class MockDiscordClient:
    """
    Drop-in replacement for discord.Client.

    Implements the subset of discord.Client interface used by the extractor.
    The extractor code doesn't know if it's talking to real Discord or this mock.
    """

    def __init__(self, guilds: Optional[List[MockGuild]] = None):
        """
        Initialize the mock client.

        Args:
            guilds: Pre-populated guilds, or empty list if None
        """
        self.guilds: List[MockGuild] = guilds or []
        self._is_ready = False
        self._is_closed = False

    def get_guild(self, guild_id: int) -> Optional[MockGuild]:
        """
        Get a guild by ID.

        Matches discord.Client.get_guild() signature.
        """
        for guild in self.guilds:
            if guild.id == guild_id:
                return guild
        return None

    def get_channel(self, channel_id: int) -> Optional[MockChannel]:
        """
        Get a channel by ID from any guild.

        Matches discord.Client.get_channel() signature.
        """
        for guild in self.guilds:
            for channel in guild._channels:
                if channel.id == channel_id:
                    return channel
        return None

    async def wait_until_ready(self) -> None:
        """
        Wait until the client is ready.

        In real discord.py, this waits for the READY event.
        For mock, we just set the flag immediately.
        """
        self._is_ready = True

    @property
    def is_ready(self) -> bool:
        """Whether the client is ready."""
        return self._is_ready

    @property
    def is_closed(self) -> bool:
        """Whether the client connection is closed."""
        return self._is_closed

    async def close(self) -> None:
        """Close the client connection."""
        self._is_closed = True

    async def start(self, token: str) -> None:
        """
        Start the client (mock implementation).

        In real discord.py, this connects to Discord.
        For mock, we just mark as ready.
        """
        self._is_ready = True

    def run(self, token: str) -> None:
        """
        Run the client (mock implementation).

        In real discord.py, this is a blocking call.
        For mock, we just mark as ready.
        """
        self._is_ready = True


def create_test_server(
    user_count: int = 50,
    channel_count: int = 5,
    messages_per_channel: int = 200,
    days: int = 7,
    seed: int = 42
) -> MockGuild:
    """
    Factory function to create a fully populated test server.

    This is the main entry point for creating test data.

    Args:
        user_count: Number of users to generate
        channel_count: Number of channels to generate
        messages_per_channel: Messages per channel
        days: How many days of history to generate
        seed: Random seed for reproducibility

    Returns:
        Fully populated MockGuild with users, channels, and messages
    """
    generator = DiscordDataGenerator(seed=seed)
    return generator.generate_guild(
        name="Test Server",
        user_count=user_count,
        channel_count=channel_count,
        messages_per_channel=messages_per_channel,
        days=days,
    )


def create_mock_client(
    user_count: int = 50,
    channel_count: int = 5,
    messages_per_channel: int = 200,
    days: int = 7,
    seed: int = 42
) -> MockDiscordClient:
    """
    Factory function to create a mock client with a test server.

    Returns a MockDiscordClient that can be used as a drop-in replacement
    for discord.Client in the extractor.

    Args:
        user_count: Number of users to generate
        channel_count: Number of channels to generate
        messages_per_channel: Messages per channel
        days: How many days of history to generate
        seed: Random seed for reproducibility

    Returns:
        MockDiscordClient with one populated guild
    """
    guild = create_test_server(
        user_count=user_count,
        channel_count=channel_count,
        messages_per_channel=messages_per_channel,
        days=days,
        seed=seed,
    )
    client = MockDiscordClient(guilds=[guild])
    client._is_ready = True
    return client
