"""
Service tests for Discord Analytics SaaS.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from cryptography.fernet import Fernet


class TestEncryptionService:
    """Tests for token encryption service."""

    def test_generate_encryption_key(self):
        """Test encryption key generation."""
        from services.encryption import generate_encryption_key

        key = generate_encryption_key()
        assert key is not None
        assert len(key) == 44  # Base64 encoded 32 bytes

        # Verify it's valid Fernet key
        Fernet(key.encode())

    def test_encrypt_decrypt_token(self):
        """Test token encryption and decryption roundtrip."""
        # Generate a valid key for testing
        key = Fernet.generate_key().decode()

        with patch("services.encryption.settings") as mock_settings:
            mock_settings.discord_token_encryption_key = key

            # Reset the cached fernet instance
            import services.encryption as enc_module
            enc_module._fernet = None

            from services.encryption import encrypt_token, decrypt_token

            original_token = "MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.abcdef.ghijklmnop"

            encrypted = encrypt_token(original_token)
            assert encrypted != original_token.encode()
            assert isinstance(encrypted, bytes)

            decrypted = decrypt_token(encrypted)
            assert decrypted == original_token


class TestQueryValidation:
    """Tests for SQL query validation."""

    def test_validate_select_query(self):
        """Test that SELECT queries pass validation."""
        from api.query import validate_query

        # These should not raise
        validate_query("SELECT * FROM messages")
        validate_query("SELECT id, content FROM messages WHERE id = 1")
        validate_query("WITH cte AS (SELECT 1) SELECT * FROM cte")

    def test_validate_blocks_dangerous_queries(self):
        """Test that dangerous queries are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        dangerous_queries = [
            "DROP TABLE messages",
            "DELETE FROM users",
            "TRUNCATE messages",
            "INSERT INTO users VALUES (1, 'test')",
            "UPDATE users SET name = 'hacked'",
            "CREATE TABLE evil (id INT)",
            "ALTER TABLE users ADD COLUMN evil TEXT",
            "GRANT ALL ON messages TO hacker",
        ]

        for query in dangerous_queries:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400

    def test_validate_blocks_non_select(self):
        """Test that non-SELECT queries are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            validate_query("SHOW TABLES")
        assert exc.value.status_code == 400

    def test_validate_blocks_sql_injection_attempts(self):
        """Test that SQL injection attempts are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        injection_attempts = [
            # Comment-based injection
            "SELECT * FROM messages -- DROP TABLE users",
            "SELECT * FROM messages /* malicious */",
            # Statement stacking
            "SELECT 1; DROP TABLE users",
            "SELECT * FROM messages; DELETE FROM users WHERE 1=1",
            # Hex encoding
            "SELECT 0x44524F50",
            # Union injection
            "SELECT * FROM messages UNION ALL SELECT password FROM admin",
        ]

        for query in injection_attempts:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400

    def test_validate_blocks_dangerous_functions(self):
        """Test that dangerous PostgreSQL functions are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        dangerous_functions = [
            "SELECT pg_sleep(10)",
            "SELECT pg_terminate_backend(123)",
            "SELECT pg_cancel_backend(123)",
            "SELECT lo_import('/etc/passwd')",
            "SELECT lo_export(12345, '/tmp/evil')",
        ]

        for query in dangerous_functions:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400

    def test_validate_allows_legitimate_queries(self):
        """Test that legitimate complex queries are allowed."""
        from api.query import validate_query

        legitimate_queries = [
            "SELECT * FROM messages WHERE created_at > NOW() - INTERVAL '7 days'",
            "SELECT channel_id, COUNT(*) FROM messages GROUP BY channel_id",
            "SELECT u.username, m.content FROM users u JOIN messages m ON u.user_id = m.author_id LIMIT 100",
            "WITH top_users AS (SELECT author_id, COUNT(*) as cnt FROM messages GROUP BY author_id) SELECT * FROM top_users ORDER BY cnt DESC LIMIT 10",
            "SELECT COALESCE(content, '') as content FROM messages",
            "SELECT * FROM messages WHERE content ILIKE '%hello%'",
        ]

        for query in legitimate_queries:
            # Should not raise
            validate_query(query)

    def test_validate_empty_query(self):
        """Test that empty queries are rejected."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            validate_query("")
        assert exc.value.status_code == 400

        with pytest.raises(HTTPException) as exc:
            validate_query("   ")
        assert exc.value.status_code == 400

    def test_validate_query_length_limit(self):
        """Test that excessively long queries are rejected."""
        from api.query import validate_query
        from fastapi import HTTPException

        # Create a query longer than 10000 characters (use 5000 items to ensure > 10000 chars)
        long_query = "SELECT * FROM messages WHERE id IN (" + ",".join(["1"] * 5000) + ")"
        assert len(long_query) > 10000

        with pytest.raises(HTTPException) as exc:
            validate_query(long_query)
        assert exc.value.status_code == 400


class TestNeonService:
    """Tests for Neon database service."""

    @pytest.mark.asyncio
    async def test_neon_client_headers(self, mock_neon_client):
        """Test Neon client has correct headers."""
        from services.neon import NeonClient

        client = NeonClient()

        with patch.object(client, "api_key", "test-key"):
            headers = client.headers
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer test-key"
            assert headers["Content-Type"] == "application/json"


class TestDiscordExtractor:
    """Tests for Discord extraction service."""

    def test_stats_initialization(self):
        """Test extractor initializes stats correctly."""
        from services.discord_extractor import SaaSDiscordExtractor

        extractor = SaaSDiscordExtractor(
            clerk_id="user_test",
            job_id="job_123",
            guild_id=123456789,
            sync_days=30,
        )

        assert extractor.stats["messages"] == 0
        assert extractor.stats["users"] == 0
        assert extractor.stats["channels"] == 0
        assert extractor.stats["mentions"] == 0
        assert extractor.stats["reactions"] == 0

    def test_extractor_parameters(self):
        """Test extractor stores parameters correctly."""
        from services.discord_extractor import SaaSDiscordExtractor

        extractor = SaaSDiscordExtractor(
            clerk_id="user_abc",
            job_id="job_xyz",
            guild_id=999888777,
            sync_days=60,
        )

        assert extractor.clerk_id == "user_abc"
        assert extractor.job_id == "job_xyz"
        assert extractor.guild_id == 999888777
        assert extractor.sync_days == 60
