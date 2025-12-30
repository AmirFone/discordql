"""
Integration tests for the backend API.

These tests exercise the full flow without requiring a real Clerk token.
Run with: ./venv/bin/python -m pytest tests/test_integration.py -v -s
"""
import asyncio
import uuid
import os
import sys

import pytest
import httpx

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test configuration
BASE_URL = "http://localhost:8000"
# Use Clerk-like format: user_XXXX (required by tenant validation)
TEST_USER_CLERK_ID = f"user_{uuid.uuid4().hex[:24]}"
TEST_USER_EMAIL = "test@example.com"
TEST_GUILD_ID = "1002294283065380926"
TEST_GUILD_NAME = "Test Server"
# Use a fake token that's long enough to pass validation (50+ chars)
TEST_BOT_TOKEN = "fake_bot_token_for_testing_purposes_only_" + "x" * 50


class TestBackendIntegration:
    """Integration tests for backend API."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures."""
        self.client = httpx.Client(base_url=BASE_URL, timeout=30.0)
        self.test_clerk_id = TEST_USER_CLERK_ID
        yield
        self.client.close()

    def test_01_health_check(self):
        """Test that the backend is running."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print(f"✓ Health check passed: {data}")

    def test_02_dev_create_user(self):
        """Test creating a user via dev endpoint."""
        response = self.client.post(
            "/api/auth/dev/create-test-user",
            json={
                "clerk_id": self.test_clerk_id,
                "email": TEST_USER_EMAIL
            }
        )
        print(f"Create user response: {response.status_code} - {response.text}")
        assert response.status_code in [200, 201], f"Failed to create user: {response.text}"
        data = response.json()
        assert "user_id" in data or "id" in data
        print(f"✓ User created: {data}")

    def test_03_dev_get_test_token(self):
        """Test getting a dev auth token."""
        response = self.client.post(
            "/api/auth/dev/token",
            json={"clerk_id": self.test_clerk_id}
        )
        print(f"Get token response: {response.status_code} - {response.text}")
        assert response.status_code == 200, f"Failed to get token: {response.text}"
        data = response.json()
        assert "token" in data
        self.dev_token = data["token"]
        print(f"✓ Got dev token: {self.dev_token[:20]}...")
        return self.dev_token

    def test_04_bot_status_no_connection(self):
        """Test bot status when no bot is connected."""
        # First get a token
        token_response = self.client.post(
            "/api/auth/dev/token",
            json={"clerk_id": self.test_clerk_id}
        )
        token = token_response.json()["token"]

        response = self.client.get(
            "/api/bot/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        print(f"Bot status response: {response.status_code} - {response.text}")
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] == False
        print(f"✓ Bot status (no connection): {data}")

    def test_05_bot_connect(self):
        """Test connecting a Discord bot."""
        # Get token
        token_response = self.client.post(
            "/api/auth/dev/token",
            json={"clerk_id": self.test_clerk_id}
        )
        token = token_response.json()["token"]

        response = self.client.post(
            "/api/bot/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "token": TEST_BOT_TOKEN,
                "guild_id": TEST_GUILD_ID,
                "guild_name": TEST_GUILD_NAME
            }
        )
        print(f"Bot connect response: {response.status_code} - {response.text}")
        assert response.status_code == 200, f"Failed to connect bot: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["guild_name"] == TEST_GUILD_NAME
        print(f"✓ Bot connected: {data}")

    def test_06_bot_status_connected(self):
        """Test bot status after connecting."""
        # Get token
        token_response = self.client.post(
            "/api/auth/dev/token",
            json={"clerk_id": self.test_clerk_id}
        )
        token = token_response.json()["token"]

        response = self.client.get(
            "/api/bot/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        print(f"Bot status response: {response.status_code} - {response.text}")
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] == True
        assert data["guild_name"] == TEST_GUILD_NAME
        print(f"✓ Bot status (connected): {data}")

    def test_07_cleanup_disconnect_bot(self):
        """Cleanup: disconnect the bot."""
        # Get token
        token_response = self.client.post(
            "/api/auth/dev/token",
            json={"clerk_id": self.test_clerk_id}
        )
        token = token_response.json()["token"]

        response = self.client.delete(
            f"/api/bot/disconnect?guild_id={TEST_GUILD_ID}",
            headers={"Authorization": f"Bearer {token}"}
        )
        print(f"Bot disconnect response: {response.status_code} - {response.text}")
        # May fail if already disconnected, that's ok
        print(f"✓ Bot disconnect attempted")


def run_tests_standalone():
    """Run tests without pytest for quick debugging."""
    print("=" * 60)
    print("Running Backend Integration Tests")
    print("=" * 60)

    client = httpx.Client(base_url=BASE_URL, timeout=30.0)
    # Use Clerk-like format: user_XXXX (required by tenant validation for extraction)
    test_clerk_id = f"user_{uuid.uuid4().hex[:24]}"

    try:
        # Test 1: Health check
        print("\n[1/6] Testing health check...")
        response = client.get("/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print(f"    ✓ Health check passed")

        # Test 2: Create test user
        print("\n[2/6] Creating test user...")
        response = client.post(
            "/api/auth/dev/create-test-user",
            json={"clerk_id": test_clerk_id, "email": "test@example.com"}
        )
        if response.status_code not in [200, 201]:
            print(f"    ✗ Failed: {response.status_code} - {response.text}")
            return False
        user_data = response.json()
        print(f"    ✓ User created: {user_data}")

        # Test 3: Get dev token
        print("\n[3/6] Getting dev token...")
        response = client.post(
            "/api/auth/dev/token",
            json={"clerk_id": test_clerk_id}
        )
        if response.status_code != 200:
            print(f"    ✗ Failed: {response.status_code} - {response.text}")
            return False
        token = response.json()["token"]
        print(f"    ✓ Got token: {token[:30]}...")

        # Test 4: Check bot status (should be disconnected)
        print("\n[4/6] Checking bot status (should be disconnected)...")
        response = client.get(
            "/api/bot/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code != 200:
            print(f"    ✗ Failed: {response.status_code} - {response.text}")
            return False
        status_data = response.json()
        assert status_data["connected"] == False, f"Expected disconnected, got: {status_data}"
        print(f"    ✓ Bot status: {status_data}")

        # Test 5: Connect bot
        print("\n[5/6] Connecting bot...")
        response = client.post(
            "/api/bot/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "token": TEST_BOT_TOKEN,
                "guild_id": TEST_GUILD_ID,
                "guild_name": TEST_GUILD_NAME
            }
        )
        if response.status_code != 200:
            print(f"    ✗ Failed: {response.status_code} - {response.text}")
            return False
        connect_data = response.json()
        print(f"    ✓ Bot connected: {connect_data}")

        # Test 6: Check bot status (should be connected)
        print("\n[6/6] Checking bot status (should be connected)...")
        response = client.get(
            "/api/bot/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code != 200:
            print(f"    ✗ Failed: {response.status_code} - {response.text}")
            return False
        status_data = response.json()
        assert status_data["connected"] == True, f"Expected connected, got: {status_data}"
        assert status_data["guild_name"] == TEST_GUILD_NAME
        print(f"    ✓ Bot status: {status_data}")

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


if __name__ == "__main__":
    success = run_tests_standalone()
    sys.exit(0 if success else 1)
