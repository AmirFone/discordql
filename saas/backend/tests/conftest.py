"""
Pytest configuration and fixtures for Discord Analytics SaaS tests.
"""
import asyncio
import os
from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport

# Set test environment
os.environ["DEBUG"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DISCORD_TOKEN_ENCRYPTION_KEY"] = "dGVzdC1rZXktMzItYnl0ZXMtZm9yLWZlcm5ldC1vaz0="  # Valid Fernet key
os.environ["CLERK_SECRET_KEY"] = "sk_test_fake"
os.environ["CLERK_JWT_ISSUER"] = "https://test.clerk.accounts.dev"
os.environ["CLERK_WEBHOOK_SECRET"] = ""  # Disable webhook verification in tests
os.environ["STRIPE_SECRET_KEY"] = "sk_test_fake"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_fake"
os.environ["NEON_API_KEY"] = "fake-neon-api-key"
os.environ["NEON_PROJECT_ID"] = "fake-project-id"
os.environ["FRONTEND_URL"] = "http://localhost:3000"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    """Create in-memory SQLite engine for tests."""
    from db.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for tests."""
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_clerk_user():
    """Create a mock Clerk user."""
    return {
        "clerk_id": "user_test123",
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def mock_jwt_token():
    """Create a mock JWT token."""
    return "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"


@pytest.fixture
def mock_discord_guild():
    """Create a mock Discord guild."""
    guild = MagicMock()
    guild.id = 123456789012345678
    guild.name = "Test Server"
    guild.owner_id = 987654321098765432
    guild.icon = None
    guild.member_count = 50
    guild.created_at = datetime(2020, 1, 1)
    guild.text_channels = []
    return guild


@pytest.fixture
def mock_discord_user():
    """Create a mock Discord user."""
    user = MagicMock()
    user.id = 111222333444555666
    user.name = "testuser"
    user.discriminator = "0001"
    user.global_name = "Test User"
    user.avatar = None
    user.bot = False
    user.created_at = datetime(2019, 1, 1)
    return user


@pytest.fixture
def mock_discord_message(mock_discord_user):
    """Create a mock Discord message."""
    message = MagicMock()
    message.id = 999888777666555444
    message.author = mock_discord_user
    message.content = "Hello, world!"
    message.created_at = datetime(2024, 1, 15, 12, 0, 0)
    message.edited_at = None
    message.type = MagicMock(value=0)
    message.pinned = False
    message.tts = False
    message.mention_everyone = False
    message.mentions = []
    message.attachments = []
    message.embeds = []
    message.reference = None
    message.reactions = []
    return message


@pytest_asyncio.fixture
async def app_client():
    """Create FastAPI test client."""
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_auth_header(mock_jwt_token):
    """Create mock authorization header."""
    return {"Authorization": f"Bearer {mock_jwt_token}"}


@pytest.fixture
def mock_neon_client():
    """Create mock Neon client."""
    client = AsyncMock()
    client.create_branch.return_value = {
        "branch": {"id": "br_test123", "name": "user_test"},
        "endpoints": [{"host": "test.neon.tech"}],
    }
    client.get_connection_string.return_value = "postgresql://test:test@test.neon.tech/neondb"
    return client
