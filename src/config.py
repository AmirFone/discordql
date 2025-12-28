"""Configuration for Discord SQL Analytics."""
import os
from dotenv import load_dotenv

load_dotenv()

# Discord Bot Configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

# Database Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://localhost/discord_analytics"
)

# For testing
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://localhost/discord_analytics_test"
)

# Sync Configuration
SYNC_DAYS = int(os.getenv("SYNC_DAYS", "7"))
FETCH_REACTIONS = os.getenv("FETCH_REACTIONS", "true").lower() == "true"
