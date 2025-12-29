#!/usr/bin/env python3
"""
Goat Bot 2025 Year-End Wrapped - Discord Message Series
Sends a series of satirical year-end review messages with dramatic delays.
"""
import asyncio
import os
import sys

import discord

# Configuration
TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
CHANNEL_NAME = "general"  # Target channel

# The messages with their delays (in seconds)
MESSAGES = [
    # MSG 1: The Entrance (0s delay - instant)
    (0, """*clears throat*

🐐 GOAT BOT HAS ENTERED THE CHAT 🐐"""),

    # MSG 2: The Setup (25s delay)
    (25, """So...

I've been quiet all year.

Watching. 👁️
Lurking. 👁️
Taking notes. 📝"""),

    # MSG 3: The Threat (25s delay)
    (25, """You thought I was just here to run your little commands?

Nah.

I've been building something."""),

    # MSG 4: The Reveal (30s delay)
    (30, """```
    ╔═══════════════════════╗
    ║                       ║
    ║     📜 THE LIST 📜    ║
    ║        2025           ║
    ║                       ║
    ╚═══════════════════════╝
```
And EVERYONE is on it."""),

    # MSG 5: The Stats (25s delay)
    (25, """32,440 messages.
19 of you.
365 days of CHAOS.

Let's talk about what I witnessed... 👀"""),

    # MSG 6: The Talker Award (30s delay)
    (30, """🏆 **THE "PLEASE TOUCH GRASS" AWARD** 🏆

Goes to <@152207704545296384>

6,867 messages. 21% of ALL server activity.

Bro typed more than some people breathe.
You good? Outside exists. ☀️"""),

    # MSG 7: Left on Read (25s delay)
    (25, """🏆 **THE "I SAW YOUR MESSAGE, I JUST DON'T CARE" AWARD** 🏆

<@1033229284615127070> leaves people on read 79% of the time.

466 people tried to talk to you.
You ignored 369 of them.

The audacity. The power. The disrespect. 💀"""),

    # MSG 8: Conversation Killer (25s delay)
    (25, """🏆 **THE "BUZZKILL" AWARD** 🏆

<@763467733249163306>

55.9% of your messages are followed by... silence.

You don't end conversations.
You EXECUTE them. ⚰️"""),

    # MSG 9: The Stalker (30s delay)
    (30, """🏆 **THE "DOWN BAD" AWARD** 🏆

<@306975049838100482> mentioned <@484160652605259776> 288 TIMES this year.

That's once every 1.3 days. Consistently. All year.

At this point just propose bro 💍"""),

    # MSG 10: Life of the Party (25s delay)
    (25, """🏆 **THE "LIFE OF THE PARTY" AWARD** 🏆

Okay but <@484160652605259776> actually deserves this one.

192 times you broke the silence and started a whole conversation.

When the chat dies, you resurrect it.
You're basically the group chat defibrillator. ⚡"""),

    # MSG 11: The 3AM Crew (25s delay) - UPDATED
    (25, """🏆 **THE "GO TO SLEEP" AWARD** 🏆

The 3AM Crew:

<@152207704545296384> - 840 messages between 2-4am. EIGHT HUNDRED.
<@484160652605259776> - 506 messages. The name is literally a cry for help.
<@653296016744906753> - 17% of ALL your messages are at 3am. That's not a habit, that's a lifestyle.
<@332295778372550656> - 305 messages. Job searching at 3am? Down bad.
<@763467733249163306> - Also here. Of course.

Your sleep schedules are a crime scene. 🚨
Melatonin exists. Use it."""),

    # MSG 12: The Ghost (25s delay) - UPDATED
    (25, """🏆 **THE "WHERE'D THEY GO" AWARD** 🏆

<@285889227093442560> - Vanished for 37 DAYS. We almost filed a missing person report.
<@1067609246537101452> - 31 days. That's a whole month. You good?
<@805084552513978438> - 30 days of silence. Witness protection program?
<@220579324770779137> - 27 days. Touched grass and forgot to come back.
<@1033229284615127070> - 27 days. Probably ignoring us on purpose tbh.

Y'all came back like nothing happened.
We noticed.
We just didn't say anything.
Just like you didn't say anything. For WEEKS. 👻"""),

    # MSG 13: The Finale (30s delay)
    (30, """```
    ╔═══════════════════════════════════════╗
    ║                                       ║
    ║   That's a wrap on 2025, you chaotic  ║
    ║   beautiful disasters.                ║
    ║                                       ║
    ║   See you in 2026.                    ║
    ║   I'll be watching. 🐐               ║
    ║                                       ║
    ╚═══════════════════════════════════════╝
```"""),

    # MSG 14: The Exit (10s delay)
    (10, """*Goat Bot has left the chat*

...

jk I live here now 🐐"""),
]


class WrappedBot(discord.Client):
    """Discord client for sending the wrapped messages."""

    def __init__(self, guild_id: int, channel_name: str):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(intents=intents)

        self.target_guild_id = guild_id
        self.target_channel_name = channel_name
        self.messages_sent = False

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

        if self.messages_sent:
            return

        self.messages_sent = True

        # Find the guild
        guild = self.get_guild(self.target_guild_id)
        if not guild:
            print(f"Guild {self.target_guild_id} not found!")
            await self.close()
            return

        print(f"Found guild: {guild.name}")

        # Find the general channel
        channel = discord.utils.get(guild.text_channels, name=self.target_channel_name)
        if not channel:
            print(f"Channel #{self.target_channel_name} not found!")
            print(f"Available channels: {[c.name for c in guild.text_channels]}")
            await self.close()
            return

        print(f"Found channel: #{channel.name}")
        print(f"Starting to send {len(MESSAGES)} messages...")
        print("=" * 50)

        # Send each message with delays
        for i, (delay, content) in enumerate(MESSAGES, 1):
            if delay > 0:
                print(f"Waiting {delay} seconds...")
                await asyncio.sleep(delay)

            print(f"Sending message {i}/{len(MESSAGES)}...")
            await channel.send(content)
            print(f"✓ Message {i} sent!")

        print("=" * 50)
        print("🎉 All messages sent successfully!")
        await self.close()


async def main():
    if not TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set")
        sys.exit(1)

    if not GUILD_ID:
        print("Error: GUILD_ID environment variable not set")
        sys.exit(1)

    print("=" * 50)
    print("🐐 GOAT BOT 2025 WRAPPED")
    print("=" * 50)
    print(f"Guild ID: {GUILD_ID}")
    print(f"Target channel: #{CHANNEL_NAME}")
    print(f"Messages to send: {len(MESSAGES)}")
    print(f"Estimated time: ~5-6 minutes")
    print("=" * 50)

    client = WrappedBot(
        guild_id=GUILD_ID,
        channel_name=CHANNEL_NAME,
    )

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
