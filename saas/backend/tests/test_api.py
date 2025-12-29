"""
API endpoint tests for Discord Analytics SaaS.
"""
import pytest
from unittest.mock import patch, AsyncMock


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self, app_client):
        """Test root health check."""
        response = await app_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "app" in data

    @pytest.mark.asyncio
    async def test_health_endpoint(self, app_client):
        """Test detailed health check."""
        response = await app_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_verify_without_token(self, app_client):
        """Test verify endpoint without token."""
        response = await app_client.get("/api/auth/verify")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_with_invalid_token(self, app_client):
        """Test verify endpoint with invalid token."""
        response = await app_client.get(
            "/api/auth/verify",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_without_token(self, app_client):
        """Test /me endpoint without token."""
        response = await app_client.get("/api/auth/me")
        assert response.status_code == 401


class TestBotEndpoints:
    """Tests for bot configuration endpoints."""

    @pytest.mark.asyncio
    async def test_connect_without_auth(self, app_client):
        """Test bot connect without authentication."""
        response = await app_client.post(
            "/api/bot/connect",
            json={
                "token": "fake_token",
                "guild_id": 123456789,
                "guild_name": "Test Server",
            }
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_status_without_auth(self, app_client):
        """Test bot status without authentication."""
        response = await app_client.get("/api/bot/status")
        assert response.status_code == 401


class TestExtractionEndpoints:
    """Tests for extraction endpoints."""

    @pytest.mark.asyncio
    async def test_start_extraction_without_auth(self, app_client):
        """Test extraction start without authentication."""
        response = await app_client.post(
            "/api/extraction/start",
            json={"guild_id": 123456789, "sync_days": 30}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_extraction_status_without_auth(self, app_client):
        """Test extraction status without authentication."""
        response = await app_client.get("/api/extraction/status/fake-job-id")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_extraction_history_without_auth(self, app_client):
        """Test extraction history without authentication."""
        response = await app_client.get("/api/extraction/history")
        assert response.status_code == 401


class TestQueryEndpoints:
    """Tests for SQL query endpoints."""

    @pytest.mark.asyncio
    async def test_execute_without_auth(self, app_client):
        """Test query execution without authentication."""
        response = await app_client.post(
            "/api/query/execute",
            json={"sql": "SELECT 1"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_schema_without_auth(self, app_client):
        """Test schema endpoint without authentication."""
        response = await app_client.get("/api/query/schema")
        assert response.status_code == 401


class TestBillingEndpoints:
    """Tests for billing endpoints."""

    @pytest.mark.asyncio
    async def test_subscription_without_auth(self, app_client):
        """Test subscription endpoint without authentication."""
        response = await app_client.get("/api/billing/subscription")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_usage_without_auth(self, app_client):
        """Test usage endpoint without authentication."""
        response = await app_client.get("/api/billing/usage")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_checkout_without_auth(self, app_client):
        """Test checkout without authentication."""
        response = await app_client.post("/api/billing/checkout/pro")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_with_invalid_signature(self, app_client):
        """Test Stripe webhook with invalid signature."""
        response = await app_client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "invalid"}
        )
        assert response.status_code == 400
