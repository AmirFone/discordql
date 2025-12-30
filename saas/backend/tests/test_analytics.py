"""
Integration tests for Analytics API.

Tests the analytics endpoints with real data using the dev auth flow.
Run with: ./venv/bin/python -m pytest tests/test_analytics.py -v -s
Or standalone: ./venv/bin/python tests/test_analytics.py
"""
import os
import sys
import uuid

import pytest
import httpx

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test configuration
BASE_URL = "http://localhost:8000"


class TestAnalyticsAPI:
    """Integration tests for analytics API endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures."""
        self.client = httpx.Client(base_url=BASE_URL, timeout=30.0)
        # Use a consistent test user that has extracted data
        self.test_clerk_id = f"user_{uuid.uuid4().hex[:24]}"
        yield
        self.client.close()

    def _get_auth_token(self):
        """Get a dev auth token for testing."""
        # Create test user
        self.client.post(
            "/api/auth/dev/create-test-user",
            json={"clerk_id": self.test_clerk_id, "email": "analytics_test@example.com"}
        )
        # Get token
        response = self.client.post(
            "/api/auth/dev/token",
            json={"clerk_id": self.test_clerk_id}
        )
        return response.json()["token"]

    def test_01_analytics_overview_endpoint(self):
        """Test that analytics overview endpoint returns valid data structure."""
        token = self._get_auth_token()

        response = self.client.get(
            "/api/analytics/overview?days=30",
            headers={"Authorization": f"Bearer {token}"}
        )

        print(f"Analytics overview response: {response.status_code}")
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()

        # Verify required fields exist
        assert "overview" in data
        assert "messages_over_time" in data
        assert "hourly_activity" in data
        assert "day_of_week_activity" in data
        assert "top_channels" in data
        assert "top_users" in data
        assert "user_interactions" in data
        assert "content_metrics" in data
        assert "engagement_metrics" in data
        assert "channel_growth" in data
        assert "bot_vs_human" in data
        assert "time_range_days" in data

        print(f"    Overview stats: {data['overview']}")
        print(f"    Time range: {data['time_range_days']} days")
        print(f"    Total messages: {data['overview']['total_messages']}")
        print(f"    Total users: {data['overview']['total_users']}")
        print(f"    Total channels: {data['overview']['total_channels']}")
        print(f"    ✓ Analytics overview returned valid structure")

    def test_02_analytics_overview_structure(self):
        """Test that overview stats have correct field types."""
        token = self._get_auth_token()

        response = self.client.get(
            "/api/analytics/overview?days=30",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        overview = data["overview"]

        # Type checks
        assert isinstance(overview["total_messages"], int)
        assert isinstance(overview["total_users"], int)
        assert isinstance(overview["total_channels"], int)
        assert isinstance(overview["total_mentions"], int)
        assert isinstance(overview["messages_change_percent"], (int, float))
        assert isinstance(overview["users_change_percent"], (int, float))
        assert isinstance(overview["avg_messages_per_day"], (int, float))
        assert isinstance(overview["avg_message_length"], (int, float))

        print(f"    ✓ Overview stats have correct types")

    def test_03_hourly_activity_completeness(self):
        """Test that hourly activity covers all 24 hours."""
        token = self._get_auth_token()

        response = self.client.get(
            "/api/analytics/overview?days=30",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        hourly = data["hourly_activity"]

        # Should have exactly 24 hours
        assert len(hourly) == 24, f"Expected 24 hours, got {len(hourly)}"

        # Each hour should be present
        hours = [h["hour"] for h in hourly]
        assert set(hours) == set(range(24)), "Missing hours in activity data"

        # Check structure of each entry
        for entry in hourly:
            assert "hour" in entry
            assert "message_count" in entry
            assert "unique_users" in entry
            assert isinstance(entry["message_count"], int)
            assert isinstance(entry["unique_users"], int)

        print(f"    ✓ Hourly activity has all 24 hours")

    def test_04_day_of_week_activity_completeness(self):
        """Test that day of week activity covers all 7 days."""
        token = self._get_auth_token()

        response = self.client.get(
            "/api/analytics/overview?days=30",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        dow = data["day_of_week_activity"]

        # Should have exactly 7 days
        assert len(dow) == 7, f"Expected 7 days, got {len(dow)}"

        # Each day should be present (0=Sunday through 6=Saturday)
        days = [d["day"] for d in dow]
        assert set(days) == set(range(7)), "Missing days in activity data"

        # Check day names
        expected_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        for entry in dow:
            assert entry["day_name"] == expected_names[entry["day"]]

        print(f"    ✓ Day of week activity has all 7 days")

    def test_05_content_metrics_structure(self):
        """Test content metrics have correct structure."""
        token = self._get_auth_token()

        response = self.client.get(
            "/api/analytics/overview?days=30",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        content = data["content_metrics"]

        # Required fields
        assert "total_words" in content
        assert "total_characters" in content
        assert "avg_words_per_message" in content
        assert "messages_with_attachments" in content
        assert "messages_with_embeds" in content
        assert "messages_with_mentions" in content
        assert "pinned_messages" in content

        # Type checks
        assert isinstance(content["total_words"], int)
        assert isinstance(content["total_characters"], int)
        assert isinstance(content["avg_words_per_message"], (int, float))

        print(f"    Content metrics: {content}")
        print(f"    ✓ Content metrics have correct structure")

    def test_06_engagement_metrics_structure(self):
        """Test engagement metrics have correct structure."""
        token = self._get_auth_token()

        response = self.client.get(
            "/api/analytics/overview?days=30",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        engagement = data["engagement_metrics"]

        # Required fields
        assert "reply_rate" in engagement
        assert "mention_rate" in engagement
        assert "active_user_ratio" in engagement
        assert "messages_per_active_user" in engagement

        # All values should be numbers between 0 and 100 (percentages or ratios)
        assert 0 <= engagement["reply_rate"] <= 100
        assert 0 <= engagement["mention_rate"] <= 100
        assert 0 <= engagement["active_user_ratio"] <= 100

        print(f"    Engagement metrics: {engagement}")
        print(f"    ✓ Engagement metrics have correct structure")

    def test_07_bot_vs_human_structure(self):
        """Test bot vs human breakdown structure."""
        token = self._get_auth_token()

        response = self.client.get(
            "/api/analytics/overview?days=30",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        bvh = data["bot_vs_human"]

        # Required fields
        assert "human_messages" in bvh
        assert "bot_messages" in bvh
        assert "human_percentage" in bvh
        assert "bot_percentage" in bvh

        # Percentages should sum to 100 (or both be 0 if no messages)
        total_pct = bvh["human_percentage"] + bvh["bot_percentage"]
        assert total_pct == 0 or abs(total_pct - 100) < 0.5, f"Percentages don't sum to 100: {total_pct}"

        print(f"    Bot vs Human: {bvh}")
        print(f"    ✓ Bot vs human structure is correct")

    def test_08_different_time_ranges(self):
        """Test analytics with different time ranges."""
        token = self._get_auth_token()

        time_ranges = [7, 30, 90]

        for days in time_ranges:
            response = self.client.get(
                f"/api/analytics/overview?days={days}",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200, f"Failed for {days} days: {response.text}"
            data = response.json()
            assert data["time_range_days"] == days
            print(f"    ✓ {days}-day range returned successfully")

        print(f"    ✓ All time ranges work correctly")

    def test_09_message_timeline_endpoint(self):
        """Test message timeline endpoint."""
        token = self._get_auth_token()

        response = self.client.get(
            "/api/analytics/messages/timeline?days=30&granularity=day",
            headers={"Authorization": f"Bearer {token}"}
        )

        print(f"Timeline response: {response.status_code}")
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()
        assert isinstance(data, list)

        if len(data) > 0:
            # Check structure
            assert "period" in data[0]
            assert "count" in data[0]
            print(f"    Timeline entries: {len(data)}")
            print(f"    Sample: {data[0] if data else 'empty'}")

        print(f"    ✓ Message timeline endpoint works")

    def test_10_user_activity_distribution_endpoint(self):
        """Test user activity distribution endpoint."""
        token = self._get_auth_token()

        response = self.client.get(
            "/api/analytics/users/activity?days=30",
            headers={"Authorization": f"Bearer {token}"}
        )

        print(f"User activity response: {response.status_code}")
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()
        assert isinstance(data, list)

        if len(data) > 0:
            assert "level" in data[0]
            assert "users" in data[0]
            print(f"    Activity levels: {len(data)}")
            for level in data:
                print(f"      - {level['level']}: {level['users']} users")

        print(f"    ✓ User activity distribution endpoint works")

    def test_11_requires_authentication(self):
        """Test that analytics requires authentication."""
        # Try without token
        response = self.client.get("/api/analytics/overview?days=30")

        # Should get 401 or 403
        assert response.status_code in [401, 403, 422], f"Expected auth error, got {response.status_code}"
        print(f"    ✓ Endpoint properly requires authentication")


def run_tests_standalone():
    """Run tests without pytest for quick debugging."""
    print("=" * 60)
    print("Running Analytics API Integration Tests")
    print("=" * 60)

    client = httpx.Client(base_url=BASE_URL, timeout=30.0)
    test_clerk_id = f"user_{uuid.uuid4().hex[:24]}"

    def get_token():
        # Create test user
        client.post(
            "/api/auth/dev/create-test-user",
            json={"clerk_id": test_clerk_id, "email": "analytics_test@example.com"}
        )
        # Get token
        response = client.post(
            "/api/auth/dev/token",
            json={"clerk_id": test_clerk_id}
        )
        if response.status_code != 200:
            print(f"Failed to get token: {response.text}")
            return None
        return response.json()["token"]

    try:
        # Test 1: Health check
        print("\n[1/10] Testing health check...")
        response = client.get("/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print(f"    ✓ Health check passed")

        # Get auth token
        print("\n[2/10] Getting auth token...")
        token = get_token()
        if not token:
            print("    ✗ Failed to get token")
            return False
        print(f"    ✓ Got auth token")

        # Test 3: Analytics overview
        print("\n[3/10] Testing analytics overview...")
        response = client.get(
            "/api/analytics/overview?days=30",
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code != 200:
            print(f"    ✗ Failed: {response.status_code} - {response.text}")
            return False
        data = response.json()
        overview = data["overview"]
        print(f"    Total messages: {overview['total_messages']}")
        print(f"    Total users: {overview['total_users']}")
        print(f"    Total channels: {overview['total_channels']}")
        print(f"    Avg messages/day: {overview['avg_messages_per_day']}")
        print(f"    ✓ Analytics overview works")

        # Test 4: Verify all sections present
        print("\n[4/10] Verifying response structure...")
        required_sections = [
            "overview", "messages_over_time", "hourly_activity",
            "day_of_week_activity", "top_channels", "top_users",
            "user_interactions", "content_metrics", "engagement_metrics",
            "channel_growth", "bot_vs_human", "time_range_days"
        ]
        missing = [s for s in required_sections if s not in data]
        if missing:
            print(f"    ✗ Missing sections: {missing}")
            return False
        print(f"    ✓ All {len(required_sections)} sections present")

        # Test 5: Hourly activity
        print("\n[5/10] Testing hourly activity...")
        hourly = data["hourly_activity"]
        if len(hourly) != 24:
            print(f"    ✗ Expected 24 hours, got {len(hourly)}")
            return False
        peak_hour = max(hourly, key=lambda x: x["message_count"])
        print(f"    Peak hour: {peak_hour['hour']}:00 ({peak_hour['message_count']} messages)")
        print(f"    ✓ Hourly activity complete (24 hours)")

        # Test 6: Day of week
        print("\n[6/10] Testing day of week activity...")
        dow = data["day_of_week_activity"]
        if len(dow) != 7:
            print(f"    ✗ Expected 7 days, got {len(dow)}")
            return False
        peak_day = max(dow, key=lambda x: x["message_count"])
        print(f"    Peak day: {peak_day['day_name']} ({peak_day['message_count']} messages)")
        print(f"    ✓ Day of week activity complete (7 days)")

        # Test 7: Top channels
        print("\n[7/10] Testing top channels...")
        channels = data["top_channels"]
        print(f"    Found {len(channels)} channels")
        for ch in channels[:3]:
            print(f"      - #{ch['channel_name']}: {ch['message_count']} msgs, {ch['unique_users']} users")
        print(f"    ✓ Top channels data returned")

        # Test 8: Top users
        print("\n[8/10] Testing top users...")
        users = data["top_users"]
        print(f"    Found {len(users)} active users")
        for u in users[:3]:
            bot_tag = " [BOT]" if u["is_bot"] else ""
            print(f"      - {u['username']}{bot_tag}: {u['message_count']} msgs")
        print(f"    ✓ Top users data returned")

        # Test 9: Engagement metrics
        print("\n[9/10] Testing engagement metrics...")
        engagement = data["engagement_metrics"]
        print(f"    Reply rate: {engagement['reply_rate']}%")
        print(f"    Mention rate: {engagement['mention_rate']}%")
        print(f"    Active user ratio: {engagement['active_user_ratio']}%")
        print(f"    Messages per active user: {engagement['messages_per_active_user']}")
        print(f"    ✓ Engagement metrics returned")

        # Test 10: Bot vs Human
        print("\n[10/10] Testing bot vs human breakdown...")
        bvh = data["bot_vs_human"]
        print(f"    Human messages: {bvh['human_messages']} ({bvh['human_percentage']}%)")
        print(f"    Bot messages: {bvh['bot_messages']} ({bvh['bot_percentage']}%)")
        print(f"    ✓ Bot vs human breakdown returned")

        print("\n" + "=" * 60)
        print("ALL ANALYTICS TESTS PASSED ✓")
        print("=" * 60)

        # Print summary
        print("\n📊 Analytics Summary:")
        print(f"   Messages: {overview['total_messages']}")
        print(f"   Users: {overview['total_users']}")
        print(f"   Channels: {overview['total_channels']}")
        print(f"   Mentions: {overview['total_mentions']}")
        print(f"   Avg msg length: {overview['avg_message_length']} chars")

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
