"""
Extraction integration tests.

Run with: ./venv/bin/python tests/test_extraction.py
"""
import sys
import os
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

BASE_URL = "http://localhost:8000"

# Test credentials - set via environment variables
TEST_BOT_TOKEN = os.environ.get("TEST_BOT_TOKEN", "fake_token_" + "x" * 50)
TEST_GUILD_ID = os.environ.get("TEST_GUILD_ID", "1234567890")
TEST_GUILD_NAME = os.environ.get("TEST_GUILD_NAME", "Test Server")


def run_extraction_tests():
    """Run full extraction test flow."""
    print("=" * 60)
    print("Running Extraction Integration Tests")
    print("=" * 60)

    client = httpx.Client(base_url=BASE_URL, timeout=120.0)  # 2 min timeout for extraction
    # Use Clerk-like format: user_XXXX (required by tenant validation)
    test_clerk_id = f"user_{uuid.uuid4().hex[:24]}"

    try:
        # Step 1: Health check
        print("\n[1/6] Health check...")
        response = client.get("/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("    ✓ Backend is healthy")

        # Step 2: Create test user
        print("\n[2/6] Creating test user...")
        response = client.post(
            "/api/auth/dev/create-test-user",
            json={"clerk_id": test_clerk_id, "email": "extraction_test@example.com"}
        )
        if response.status_code not in [200, 201]:
            print(f"    ✗ Failed: {response.status_code} - {response.text}")
            return False
        print(f"    ✓ User created: {test_clerk_id}")

        # Step 3: Get dev token
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

        # Step 4: Connect bot
        print("\n[4/6] Connecting Discord bot...")
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
        print(f"    ✓ Bot connected: {response.json()}")

        # Step 5: Test Discord connection
        print("\n[5/6] Testing Discord connection...")
        response = client.get(
            f"/api/extraction/dev/test-discord-connection?clerk_id={test_clerk_id}&guild_id={TEST_GUILD_ID}"
        )
        if response.status_code != 200:
            print(f"    ✗ Request failed: {response.status_code} - {response.text}")
            return False

        connection_result = response.json()
        print(f"    Result: {connection_result}")

        if connection_result.get("status") != "success":
            print(f"    ✗ Discord connection failed: {connection_result.get('message', 'Unknown error')}")
            return False
        print(f"    ✓ Discord connection successful!")
        print(f"      Bot: {connection_result.get('bot_user')}")
        print(f"      Guild: {connection_result.get('guild_name')} ({connection_result.get('member_count')} members)")

        # Step 6: Run extraction (with 1 day to be quick)
        print("\n[6/6] Running extraction (1 day sync)...")
        response = client.post(
            "/api/extraction/dev/run-sync",
            json={
                "clerk_id": test_clerk_id,
                "guild_id": TEST_GUILD_ID,
                "sync_days": 1  # Just 1 day to keep it fast
            }
        )
        if response.status_code != 200:
            print(f"    ✗ Extraction failed: {response.status_code} - {response.text}")
            return False

        extraction_result = response.json()
        print(f"    ✓ Extraction completed!")
        print(f"      Job ID: {extraction_result.get('job_id')}")
        print(f"      Stats: {extraction_result.get('stats')}")

        print("\n" + "=" * 60)
        print("ALL EXTRACTION TESTS PASSED ✓")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


def quick_discord_test():
    """Quick test just to verify Discord connection works."""
    print("=" * 60)
    print("Quick Discord Connection Test")
    print("=" * 60)

    client = httpx.Client(base_url=BASE_URL, timeout=60.0)
    # Use Clerk-like format: user_XXXX (required by tenant validation)
    test_clerk_id = f"user_{uuid.uuid4().hex[:24]}"

    try:
        # Create user
        print("\n[1/3] Creating test user...")
        response = client.post(
            "/api/auth/dev/create-test-user",
            json={"clerk_id": test_clerk_id, "email": "quick_test@example.com"}
        )
        print(f"    User: {response.status_code}")

        # Get token and connect bot
        print("\n[2/3] Connecting bot...")
        token_resp = client.post("/api/auth/dev/token", json={"clerk_id": test_clerk_id})
        token = token_resp.json()["token"]

        response = client.post(
            "/api/bot/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "token": TEST_BOT_TOKEN,
                "guild_id": TEST_GUILD_ID,
                "guild_name": TEST_GUILD_NAME
            }
        )
        print(f"    Connect: {response.status_code} - {response.text[:100] if response.text else 'OK'}")

        # Test Discord
        print("\n[3/3] Testing Discord connection...")
        response = client.get(
            f"/api/extraction/dev/test-discord-connection?clerk_id={test_clerk_id}&guild_id={TEST_GUILD_ID}"
        )
        result = response.json()
        print(f"    Result: {result}")

        return result.get("status") == "success"

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        success = quick_discord_test()
    else:
        success = run_extraction_tests()

    sys.exit(0 if success else 1)
