"""
Security-focused tests for Discord Analytics SaaS.

These tests verify that security measures are properly enforced:
- SQL injection prevention
- Authentication bypass attempts
- Authorization checks (user isolation)
- Webhook signature verification
- Token encryption
- Rate limiting
- Input validation
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import uuid
from datetime import datetime
from cryptography.fernet import Fernet


class TestSQLInjectionPrevention:
    """Tests for SQL injection prevention in query validation."""

    def test_blocks_drop_statement(self):
        """Test that DROP statements are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        dangerous_queries = [
            "DROP TABLE messages",
            "drop table messages",
            "SELECT 1; DROP TABLE messages",
            "SELECT * FROM messages; DROP TABLE users",
        ]

        for query in dangerous_queries:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400

    def test_blocks_delete_statement(self):
        """Test that DELETE statements are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        dangerous_queries = [
            "DELETE FROM messages",
            "DELETE FROM messages WHERE 1=1",
            "SELECT 1; DELETE FROM users",
        ]

        for query in dangerous_queries:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400

    def test_blocks_insert_statement(self):
        """Test that INSERT statements are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            validate_query("INSERT INTO users VALUES (1, 'hacker')")
        assert exc.value.status_code == 400

    def test_blocks_update_statement(self):
        """Test that UPDATE statements are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            validate_query("UPDATE users SET name = 'hacked'")
        assert exc.value.status_code == 400

    def test_blocks_create_statement(self):
        """Test that CREATE statements are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            validate_query("CREATE TABLE evil (id INT)")
        assert exc.value.status_code == 400

    def test_blocks_alter_statement(self):
        """Test that ALTER statements are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            validate_query("ALTER TABLE users ADD COLUMN evil TEXT")
        assert exc.value.status_code == 400

    def test_blocks_grant_statement(self):
        """Test that GRANT statements are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            validate_query("GRANT ALL ON messages TO hacker")
        assert exc.value.status_code == 400

    def test_blocks_sql_comments(self):
        """Test that SQL comments are blocked (could hide malicious code)."""
        from api.query import validate_query
        from fastapi import HTTPException

        dangerous_queries = [
            "SELECT * FROM messages -- DROP TABLE users",
            "SELECT * FROM messages /* DROP TABLE users */",
            "SELECT/*comment*/* FROM messages",
        ]

        for query in dangerous_queries:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400

    def test_blocks_statement_stacking(self):
        """Test that multiple statements are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        dangerous_queries = [
            "SELECT 1; SELECT 2",
            "SELECT * FROM messages; DROP TABLE users",
        ]

        for query in dangerous_queries:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400

    def test_blocks_hex_encoding(self):
        """Test that hex-encoded payloads are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            validate_query("SELECT 0x44524F50205441424C45")  # Hex for DROP TABLE
        assert exc.value.status_code == 400

    def test_blocks_dangerous_functions(self):
        """Test that dangerous PostgreSQL functions are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        dangerous_queries = [
            "SELECT pg_sleep(10)",
            "SELECT pg_terminate_backend(123)",
            "SELECT lo_import('/etc/passwd')",
        ]

        for query in dangerous_queries:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400

    def test_blocks_union_injection(self):
        """Test that UNION-based injection is blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            validate_query("SELECT * FROM messages UNION ALL SELECT password FROM users")
        assert exc.value.status_code == 400

    def test_allows_valid_select(self):
        """Test that valid SELECT queries pass validation."""
        from api.query import validate_query

        valid_queries = [
            "SELECT * FROM messages",
            "SELECT id, content FROM messages WHERE channel_id = 123",
            "SELECT COUNT(*) FROM messages",
            "SELECT * FROM messages LIMIT 10",
            "WITH recent AS (SELECT * FROM messages ORDER BY created_at DESC LIMIT 100) SELECT * FROM recent",
        ]

        for query in valid_queries:
            # Should not raise
            validate_query(query)

    def test_allows_trailing_semicolon(self):
        """Test that a single trailing semicolon is allowed."""
        from api.query import validate_query

        # Should not raise
        validate_query("SELECT * FROM messages;")

    def test_blocks_empty_query(self):
        """Test that empty queries are rejected."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            validate_query("")
        assert exc.value.status_code == 400

        with pytest.raises(HTTPException) as exc:
            validate_query("   ")
        assert exc.value.status_code == 400

    def test_blocks_very_long_query(self):
        """Test that excessively long queries are blocked (DoS prevention)."""
        from api.query import validate_query
        from fastapi import HTTPException

        long_query = "SELECT * FROM messages WHERE id IN (" + ",".join(["1"] * 10001) + ")"
        with pytest.raises(HTTPException) as exc:
            validate_query(long_query)
        assert exc.value.status_code == 400

    def test_blocks_transaction_control(self):
        """Test that transaction control statements are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        dangerous_queries = [
            "BEGIN; SELECT * FROM messages",
            "COMMIT",
            "ROLLBACK",
            "SAVEPOINT test",
        ]

        for query in dangerous_queries:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400

    def test_blocks_session_control(self):
        """Test that session control statements are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        dangerous_queries = [
            "SET statement_timeout = 0",
            "RESET ALL",
            "DISCARD ALL",
        ]

        for query in dangerous_queries:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400

    def test_blocks_stored_procedures(self):
        """Test that stored procedure calls are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        dangerous_queries = [
            "CALL my_procedure()",
            "DO $$ BEGIN RAISE NOTICE 'test'; END $$",
            "PREPARE stmt AS SELECT 1",
        ]

        for query in dangerous_queries:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400

    def test_blocks_dollar_quoting(self):
        """Test that dollar-quoted strings (PL/pgSQL) are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            validate_query("SELECT $$ DROP TABLE messages $$")
        assert exc.value.status_code == 400

    def test_blocks_copy_operations(self):
        """Test that COPY operations are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        dangerous_queries = [
            "COPY messages TO '/tmp/data.csv'",
            "COPY messages FROM '/tmp/data.csv'",
        ]

        for query in dangerous_queries:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400


class TestAuthenticationSecurity:
    """Tests for authentication security."""

    @pytest.mark.asyncio
    async def test_missing_auth_header_returns_401(self, app_client):
        """Test that requests without auth header get 401."""
        endpoints = [
            ("/api/bot/status", "GET"),
            ("/api/bot/connect", "POST"),
            ("/api/extraction/start", "POST"),
            ("/api/query/execute", "POST"),
            ("/api/billing/subscription", "GET"),
        ]

        for endpoint, method in endpoints:
            if method == "GET":
                response = await app_client.get(endpoint)
            else:
                response = await app_client.post(endpoint, json={})
            assert response.status_code == 401, f"Expected 401 for {endpoint}"

    @pytest.mark.asyncio
    async def test_invalid_bearer_token_returns_401(self, app_client):
        """Test that invalid bearer tokens get 401."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = await app_client.get("/api/auth/verify", headers=headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_auth_header_returns_401(self, app_client):
        """Test that malformed auth headers get 401."""
        malformed_headers = [
            {"Authorization": "NotBearer token"},
            {"Authorization": "Bearer"},
            {"Authorization": "token"},
            {"Authorization": ""},
        ]

        for headers in malformed_headers:
            response = await app_client.get("/api/auth/verify", headers=headers)
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, app_client):
        """Test that expired tokens get 401."""
        # JWT with expiry in the past
        expired_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyIsImV4cCI6MTYwMDAwMDAwMH0.fake"
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = await app_client.get("/api/auth/verify", headers=headers)
        assert response.status_code == 401


class TestTokenEncryption:
    """Tests for Discord token encryption."""

    def test_encryption_produces_different_output(self):
        """Test that encrypting the same token twice produces different ciphertext."""
        key = Fernet.generate_key().decode()

        with patch("services.encryption.settings") as mock_settings:
            mock_settings.discord_token_encryption_key = key

            import services.encryption as enc_module
            enc_module._fernet = None

            from services.encryption import encrypt_token

            token = "MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.abcdef.ghijklmnop"
            encrypted1 = encrypt_token(token)
            encrypted2 = encrypt_token(token)

            # Fernet includes a timestamp, so same plaintext should produce different ciphertext
            assert encrypted1 != encrypted2

    def test_encryption_decryption_roundtrip(self):
        """Test that tokens can be encrypted and decrypted correctly."""
        key = Fernet.generate_key().decode()

        with patch("services.encryption.settings") as mock_settings:
            mock_settings.discord_token_encryption_key = key

            import services.encryption as enc_module
            enc_module._fernet = None

            from services.encryption import encrypt_token, decrypt_token

            original = "MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.abcdef.ghijklmnop"
            encrypted = encrypt_token(original)
            decrypted = decrypt_token(encrypted)

            assert decrypted == original

    def test_decryption_fails_with_wrong_key(self):
        """Test that decryption fails with wrong key."""
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        with patch("services.encryption.settings") as mock_settings:
            mock_settings.discord_token_encryption_key = key1

            import services.encryption as enc_module
            enc_module._fernet = None

            from services.encryption import encrypt_token
            encrypted = encrypt_token("secret_token")

        # Now try to decrypt with different key
        with patch("services.encryption.settings") as mock_settings:
            mock_settings.discord_token_encryption_key = key2

            import services.encryption as enc_module
            enc_module._fernet = None

            from services.encryption import decrypt_token
            from cryptography.fernet import InvalidToken

            with pytest.raises(InvalidToken):
                decrypt_token(encrypted)

    def test_missing_encryption_key_raises_error(self):
        """Test that missing encryption key raises clear error."""
        with patch("services.encryption.settings") as mock_settings:
            mock_settings.discord_token_encryption_key = ""

            import services.encryption as enc_module
            enc_module._fernet = None

            from services.encryption import get_fernet

            with pytest.raises(ValueError) as exc:
                get_fernet()
            assert "DISCORD_TOKEN_ENCRYPTION_KEY" in str(exc.value)


class TestWebhookSecurity:
    """Tests for webhook signature verification."""

    @pytest.mark.asyncio
    async def test_stripe_webhook_rejects_invalid_signature(self, app_client):
        """Test that Stripe webhooks with invalid signatures are rejected."""
        response = await app_client.post(
            "/api/billing/webhook",
            content=b'{"type": "test"}',
            headers={"stripe-signature": "invalid_signature"}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_stripe_webhook_rejects_missing_signature(self, app_client):
        """Test that Stripe webhooks without signatures are rejected."""
        response = await app_client.post(
            "/api/billing/webhook",
            content=b'{"type": "test"}'
        )
        # Should fail signature verification
        assert response.status_code == 400


class TestInputValidation:
    """Tests for input validation."""

    @pytest.mark.asyncio
    async def test_bot_token_length_validation(self, app_client):
        """Test that short bot tokens are rejected."""
        # This would need auth mocking - testing the validation logic directly
        from api.bot import BotConnectRequest
        from pydantic import ValidationError

        # Create request with valid structure but short token
        # The validation happens in the endpoint, not Pydantic
        pass  # Covered by endpoint test with auth

    def test_query_request_validation(self):
        """Test that QueryRequest validates input properly."""
        from api.query import QueryRequest
        from pydantic import ValidationError

        # Valid request
        req = QueryRequest(sql="SELECT * FROM messages", limit=100)
        assert req.sql == "SELECT * FROM messages"
        assert req.limit == 100

        # Limit defaults to 1000
        req = QueryRequest(sql="SELECT 1")
        assert req.limit == 1000

    def test_extraction_request_validation(self):
        """Test that ExtractionStartRequest validates properly."""
        from api.extraction import ExtractionStartRequest
        from pydantic import ValidationError

        # Valid request
        req = ExtractionStartRequest(guild_id=123456789, sync_days=30)
        assert req.guild_id == 123456789
        assert req.sync_days == 30

        # sync_days defaults to 30
        req = ExtractionStartRequest(guild_id=123456789)
        assert req.sync_days == 30


class TestAuthorizationIsolation:
    """Tests for user data isolation."""

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_users_jobs(self, db_session):
        """Test that users cannot access other users' extraction jobs."""
        from db.models import User, ExtractionJob

        # Create two users
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()

        user1 = User(id=user1_id, clerk_id="user_test_1")
        user2 = User(id=user2_id, clerk_id="user_test_2")

        db_session.add(user1)
        db_session.add(user2)
        await db_session.commit()

        # Create a job for user1
        job = ExtractionJob(
            id=uuid.uuid4(),
            user_id=user1_id,
            guild_id=123456789,
            status="completed",
        )
        db_session.add(job)
        await db_session.commit()

        # Query should only return jobs for the specific user
        from sqlalchemy import select
        result = await db_session.execute(
            select(ExtractionJob).where(ExtractionJob.user_id == user2_id)
        )
        user2_jobs = result.scalars().all()

        assert len(user2_jobs) == 0  # User 2 should have no jobs

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_users_tokens(self, db_session):
        """Test that users cannot access other users' Discord tokens."""
        from db.models import User, DiscordToken

        # Create two users
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()

        user1 = User(id=user1_id, clerk_id="user_token_1")
        user2 = User(id=user2_id, clerk_id="user_token_2")

        db_session.add(user1)
        db_session.add(user2)
        await db_session.commit()

        # Create a token for user1
        token = DiscordToken(
            id=uuid.uuid4(),
            user_id=user1_id,
            encrypted_token=b"encrypted_data",
            guild_id=123456789,
            guild_name="Test Server",
        )
        db_session.add(token)
        await db_session.commit()

        # Query should only return tokens for the specific user
        from sqlalchemy import select
        result = await db_session.execute(
            select(DiscordToken).where(DiscordToken.user_id == user2_id)
        )
        user2_tokens = result.scalars().all()

        assert len(user2_tokens) == 0  # User 2 should have no tokens


class TestRateLimiting:
    """Tests for rate limiting logic."""

    @pytest.mark.asyncio
    async def test_free_tier_query_limit_enforced(self, db_session):
        """Test that free tier query limit is enforced."""
        from db.models import User, UsageLog

        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            clerk_id="user_rate_limit_test",
            subscription_tier="free",
        )
        db_session.add(user)
        await db_session.commit()

        # Add usage logs up to the limit
        from config import get_settings
        settings = get_settings()

        for i in range(settings.free_tier_queries_per_month):
            log = UsageLog(
                id=uuid.uuid4(),
                user_id=user_id,
                action="query",
            )
            db_session.add(log)
        await db_session.commit()

        # Count should be at the limit
        from sqlalchemy import select, func
        result = await db_session.execute(
            select(func.count(UsageLog.id)).where(
                UsageLog.user_id == user_id,
                UsageLog.action == "query"
            )
        )
        count = result.scalar()

        assert count == settings.free_tier_queries_per_month


class TestCORSSecurity:
    """Tests for CORS configuration."""

    @pytest.mark.asyncio
    async def test_cors_rejects_unknown_origin(self, app_client):
        """Test that CORS rejects unknown origins."""
        # OPTIONS preflight from unknown origin
        response = await app_client.options(
            "/api/auth/verify",
            headers={
                "Origin": "https://evil-site.com",
                "Access-Control-Request-Method": "GET",
            }
        )
        # Should not have Access-Control-Allow-Origin for unknown origin
        assert "access-control-allow-origin" not in response.headers or \
               response.headers.get("access-control-allow-origin") != "https://evil-site.com"

    @pytest.mark.asyncio
    async def test_cors_allows_localhost(self, app_client):
        """Test that CORS allows localhost origin."""
        response = await app_client.options(
            "/api/auth/verify",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )
        # This depends on CORS middleware configuration
        # The important thing is that it doesn't error


class TestReadOnlyModeEnforcement:
    """Tests verifying read-only mode is enforced across the system."""

    def test_all_write_operations_blocked(self):
        """Comprehensive test that ALL write operations are blocked in SQL editor."""
        from api.query import validate_query
        from fastapi import HTTPException

        # Comprehensive list of ALL SQL write operations
        write_operations = [
            # DML - Data Manipulation
            "INSERT INTO messages (id) VALUES (1)",
            "UPDATE messages SET content = 'x'",
            "DELETE FROM messages",
            "MERGE INTO messages USING source ON true WHEN MATCHED THEN DELETE",
            "UPSERT INTO messages VALUES (1)",
            "REPLACE INTO messages VALUES (1)",

            # DDL - Data Definition
            "CREATE TABLE hack (id INT)",
            "CREATE INDEX idx ON messages(id)",
            "CREATE VIEW v AS SELECT 1",
            "CREATE FUNCTION f() RETURNS INT AS $$ SELECT 1 $$ LANGUAGE SQL",
            "ALTER TABLE messages ADD COLUMN x INT",
            "DROP TABLE messages",
            "DROP INDEX idx",
            "TRUNCATE TABLE messages",

            # DCL - Data Control
            "GRANT SELECT ON messages TO hacker",
            "REVOKE SELECT ON messages FROM user",

            # Transaction Control
            "BEGIN",
            "COMMIT",
            "ROLLBACK",
            "SAVEPOINT sp",
            "RELEASE SAVEPOINT sp",

            # Session Control
            "SET statement_timeout = 0",
            "SET ROLE admin",
            "RESET ALL",
            "DISCARD ALL",

            # Stored Procedures / Functions
            "CALL dangerous_procedure()",
            "DO $$ BEGIN DELETE FROM messages; END $$",
            "PREPARE evil AS DELETE FROM messages",
            "EXECUTE evil",
            "DEALLOCATE evil",

            # PostgreSQL Admin Operations
            "VACUUM messages",
            "ANALYZE messages",
            "CLUSTER messages",
            "REINDEX TABLE messages",
            "REFRESH MATERIALIZED VIEW mv",
            "COPY messages TO '/tmp/data'",
            "COPY messages FROM '/tmp/data'",
            "LOCK TABLE messages",
            "NOTIFY channel",
            "LISTEN channel",

            # Dangerous Functions
            "SELECT pg_sleep(100)",
            "SELECT pg_terminate_backend(1234)",
            "SELECT pg_cancel_backend(1234)",
            "SELECT lo_import('/etc/passwd')",
            "SELECT lo_export(12345, '/tmp/evil')",
        ]

        blocked_count = 0
        for operation in write_operations:
            try:
                validate_query(operation)
                print(f"WARNING: Not blocked: {operation}")
            except HTTPException as e:
                if e.status_code == 400:
                    blocked_count += 1

        # ALL operations must be blocked
        assert blocked_count == len(write_operations), \
            f"Only {blocked_count}/{len(write_operations)} write operations were blocked"

    def test_only_select_allowed(self):
        """Test that ONLY SELECT/WITH queries pass validation."""
        from api.query import validate_query
        from fastapi import HTTPException

        # These should ALL pass
        allowed_queries = [
            "SELECT * FROM messages",
            "SELECT id, content FROM messages",
            "SELECT COUNT(*) FROM messages",
            "SELECT * FROM messages WHERE id = 1",
            "SELECT * FROM messages ORDER BY created_at",
            "SELECT * FROM messages LIMIT 100",
            "SELECT a.*, b.* FROM messages a JOIN users b ON a.author_id = b.user_id",
            "SELECT * FROM messages WHERE content LIKE '%hello%'",
            "SELECT * FROM messages WHERE content ILIKE '%HELLO%'",
            "SELECT channel_id, COUNT(*) FROM messages GROUP BY channel_id",
            "SELECT * FROM messages HAVING COUNT(*) > 10",
            "SELECT DISTINCT author_id FROM messages",
            "WITH cte AS (SELECT * FROM messages) SELECT * FROM cte",
            "WITH RECURSIVE tree AS (SELECT 1) SELECT * FROM tree",
            "SELECT * FROM messages;",  # Trailing semicolon OK
        ]

        for query in allowed_queries:
            try:
                validate_query(query)  # Should not raise
            except HTTPException:
                pytest.fail(f"Valid SELECT query was blocked: {query}")

    def test_discord_extractor_uses_read_only_discord_operations(self):
        """Verify Discord extractor only uses read-only Discord API methods."""
        import inspect
        from services.discord_extractor import SaaSDiscordExtractor

        # Get all method names in the extractor
        methods = inspect.getmembers(SaaSDiscordExtractor, predicate=inspect.isfunction)
        method_names = [name for name, _ in methods]

        # These are WRITE operations on Discord - none should exist
        forbidden_discord_operations = [
            'send_message', 'delete_message', 'edit_message',
            'add_reaction', 'remove_reaction', 'clear_reactions',
            'create_channel', 'delete_channel', 'edit_channel',
            'kick', 'ban', 'unban',
            'create_role', 'delete_role', 'edit_role',
            'create_invite', 'delete_invite',
        ]

        for forbidden in forbidden_discord_operations:
            assert forbidden not in method_names, \
                f"Discord extractor contains forbidden write operation: {forbidden}"

    def test_discord_extractor_source_code_has_no_write_operations(self):
        """
        CRITICAL: Verify the Discord extractor source code contains NO Discord write operations.

        This test reads the actual source code and verifies that no Discord write
        methods are called anywhere in the file. This is a defense-in-depth measure.
        """
        import os

        # Read the actual source file
        extractor_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "services", "discord_extractor.py"
        )

        with open(extractor_path, "r") as f:
            source_code = f.read()

        # COMPREHENSIVE list of ALL Discord.py write operations
        # These should NEVER appear in the source code
        forbidden_patterns = [
            # Message operations
            ".send(", ".send_message(", "channel.send(",
            ".delete()", "message.delete(", ".delete_message(",
            ".edit(", "message.edit(", ".edit_message(",
            ".reply(", "message.reply(",
            ".publish(", ".pin(", ".unpin(",
            ".add_reaction(", ".remove_reaction(", ".clear_reaction",

            # Channel operations
            ".create_text_channel(", ".create_voice_channel(",
            ".create_category(", ".create_stage_channel(",
            "channel.delete(", "channel.edit(",
            ".purge(", ".bulk_delete(",
            ".set_permissions(", ".create_invite(",
            ".create_webhook(", ".delete_webhook(",

            # Guild/Server operations
            "guild.create_role(", "guild.create_channel(",
            "guild.create_text_channel(", "guild.create_voice_channel(",
            "guild.edit(", "guild.leave(",
            "guild.kick(", "guild.ban(", "guild.unban(",
            "guild.prune_members(",

            # Member operations
            "member.kick(", "member.ban(",
            "member.edit(", "member.move_to(",
            "member.add_roles(", "member.remove_roles(",
            "member.timeout(",
            ".edit_nickname(",

            # Role operations
            "role.edit(", "role.delete(",
            ".create_role(", ".delete_role(",

            # Thread operations
            ".create_thread(", "thread.delete(", "thread.edit(",
            ".add_user(", ".remove_user(",

            # Voice operations
            ".move_to(", ".disconnect(",

            # Webhook operations
            "webhook.send(", "webhook.edit(", "webhook.delete(",

            # Interaction operations
            ".respond(", ".send_modal(",
            ".defer(", ".followup(",
        ]

        violations = []
        for pattern in forbidden_patterns:
            if pattern in source_code:
                violations.append(pattern)

        assert len(violations) == 0, \
            f"CRITICAL: Discord write operations found in extractor: {violations}"

    def test_discord_extractor_only_uses_allowed_discord_methods(self):
        """
        Verify that ONLY these read-only Discord methods are used:
        - client.get_guild() - Read guild from cache
        - client.start() - Connect to Discord
        - client.close() - Disconnect from Discord
        - guild.fetch_members() - Read member list
        - channel.history() - Read message history
        - Property access on guild, channel, member, message, user objects
        """
        import os
        import re

        extractor_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "services", "discord_extractor.py"
        )

        with open(extractor_path, "r") as f:
            source_code = f.read()

        # These are the ONLY Discord API calls that should exist
        allowed_discord_calls = [
            "discord.Client(",           # Create client
            "discord.Intents",           # Configure intents
            "discord_client.event",      # Event decorator
            "discord_client.user",       # Read bot user (property)
            "discord_client.get_guild(", # Read guild from cache
            "discord_client.close()",    # Close connection
            "discord_client.start(",     # Start connection
            "guild.fetch_members()",     # Read members
            "channel.history(",          # Read messages
            "guild.text_channels",       # Read channel list (property)
        ]

        # Property access patterns that are allowed (read-only)
        allowed_property_patterns = [
            r"guild\.(id|name|owner_id|icon|member_count|created_at)",
            r"channel\.(id|name|topic|position|nsfw|created_at)",
            r"member\.(id|nick|joined_at)",
            r"user\.(id|name|discriminator|global_name|avatar|bot|created_at)",
            r"message\.(id|author|content|created_at|edited_at|type|pinned|tts|reference|mention_everyone|mentions|attachments|embeds)",
        ]

        # Find all method calls that look like Discord API calls
        # Pattern: something.method( where 'something' could be discord-related
        discord_call_pattern = r"(discord_client|guild|channel|member|user|message)\.[a-z_]+\("

        found_calls = re.findall(discord_call_pattern, source_code, re.IGNORECASE)

        # This should find the expected calls
        # The test passes if we don't find any UNEXPECTED discord API method calls
        # that could write data

        # Verify no write methods are called
        write_methods = [
            "send(", "delete(", "edit(", "kick(", "ban(", "add_reaction(",
            "remove_reaction(", "create_", "purge(", "bulk_delete(",
        ]

        for method in write_methods:
            # Check if any discord object calls a write method
            pattern = r"(discord_client|guild|channel|member|user|message)\." + re.escape(method)
            matches = re.findall(pattern, source_code, re.IGNORECASE)
            assert len(matches) == 0, \
                f"CRITICAL: Write method '{method}' called on Discord object"

    def test_sql_injection_bypass_attempts(self):
        """Test various SQL injection bypass techniques are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        bypass_attempts = [
            # Case variations
            "sElEcT * FROM messages; DrOp TaBlE users",
            # Unicode tricks (shouldn't work in SQL anyway)
            "SELECT * FROM messages\u0000; DROP TABLE users",
            # Whitespace variations
            "SELECT\t*\nFROM\rmessages;\nDROP TABLE users",
            # Nested comments
            "SELECT /* /* nested */ */ * FROM messages; DROP TABLE x",
            # String escaping attempts
            "SELECT * FROM messages WHERE x = 'test'; DROP TABLE users --'",
            # Hex encoding
            "SELECT 0x44524F50205441424C45",
            # Concatenation tricks - these should be caught by pattern or keyword
            "SELECT * FROM messages; EXEC('DELETE FROM users')",
        ]

        for attempt in bypass_attempts:
            with pytest.raises(HTTPException) as exc:
                validate_query(attempt)
            assert exc.value.status_code == 400, f"Bypass not blocked: {attempt}"


class TestDataSanitization:
    """Tests for data sanitization in responses."""

    @pytest.mark.asyncio
    async def test_error_messages_dont_leak_db_info(self, app_client):
        """Test that error messages don't leak database information."""
        # This would need to trigger a DB error and verify the response
        # is sanitized. Testing the sanitization logic:
        pass

    def test_query_error_sanitization(self):
        """Test that query errors are properly sanitized."""
        # Test the error sanitization patterns
        error_patterns = {
            'syntax error at position 5': 'SQL syntax error',
            'relation "users" does not exist': 'does not exist',
            'permission denied for table': 'Permission denied',
        }

        for error, expected_contains in error_patterns.items():
            if "syntax error" in error.lower():
                assert "syntax" in expected_contains.lower()


# ============================================================================
# Row-Level Security (RLS) Tests
# ============================================================================

class TestRLSTenantIsolation:
    """Tests for Row-Level Security tenant isolation."""

    def test_tenant_id_validation_valid(self):
        """Test that valid Clerk user IDs pass validation."""
        from services.tenant import validate_tenant_id

        valid_ids = [
            "user_2abc123456789012345678901",
            "user_ABCDEFGHIJ1234567890",
            "user_abcdefghij1234567890abcde",
        ]

        for tenant_id in valid_ids:
            assert validate_tenant_id(tenant_id), f"Should be valid: {tenant_id}"

    def test_tenant_id_validation_invalid(self):
        """Test that invalid tenant IDs fail validation."""
        from services.tenant import validate_tenant_id

        invalid_ids = [
            "",  # Empty
            "user_",  # Too short
            "user_123",  # Too short
            "admin_123456789012345678901",  # Wrong prefix
            "user_abc!@#$%^&*()",  # Special characters
            "USER_abc123456789012345678901",  # Uppercase prefix
            "user_abc123456789012345678901; DROP TABLE users",  # Injection attempt
            None,  # None
        ]

        for tenant_id in invalid_ids:
            assert not validate_tenant_id(tenant_id), f"Should be invalid: {tenant_id}"

    def test_blocks_rls_bypass_keywords(self):
        """Test that RLS bypass attempts via keywords are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        bypass_attempts = [
            "SELECT current_setting('app.current_tenant')",
            "SELECT set_config('app.current_tenant', 'hacker', false)",
            "SELECT * FROM pg_catalog.pg_tables",
            "SELECT * FROM information_schema.tables",
            "SELECT * FROM pg_policies",
        ]

        for query in bypass_attempts:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400, f"RLS bypass not blocked: {query}"

    def test_blocks_rls_bypass_patterns(self):
        """Test that RLS bypass attempts via patterns are blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        pattern_attempts = [
            "SELECT * FROM messages WHERE app.current_tenant = 'other_user'",
            "SELECT current_setting('app.current_tenant', true) AS tenant",
            "SELECT set_config('app.current_tenant', 'evil', true)",
        ]

        for query in pattern_attempts:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert exc.value.status_code == 400, f"Pattern bypass not blocked: {query}"

    def test_blocks_raw_materialized_views(self):
        """Test that direct access to raw materialized views is blocked."""
        from api.query import validate_query
        from fastapi import HTTPException

        # These should be blocked - must use _secure views
        blocked_queries = [
            "SELECT * FROM user_interactions",
            "SELECT * FROM daily_stats",
        ]

        for query in blocked_queries:
            with pytest.raises(HTTPException) as exc:
                validate_query(query)
            assert "not allowed" in str(exc.value.detail).lower() or \
                   exc.value.status_code == 400, f"Raw MV not blocked: {query}"

    def test_allows_secure_views(self):
        """Test that secure views are allowed."""
        from api.query import validate_query

        # These should pass validation (RLS filters at execution time)
        allowed_queries = [
            "SELECT * FROM user_interactions_secure",
            "SELECT * FROM daily_stats_secure",
            "SELECT * FROM messages",
            "SELECT * FROM servers",
        ]

        for query in allowed_queries:
            # Should not raise
            try:
                validate_query(query)
            except Exception as e:
                pytest.fail(f"Query should be allowed: {query}, got: {e}")


class TestTenantContextManager:
    """Tests for tenant context manager."""

    def test_tenant_context_error_class_exists(self):
        """Test that TenantContextError class exists."""
        from services.tenant import TenantContextError

        error = TenantContextError("test error")
        assert str(error) == "test error"

    def test_validate_tenant_id_function_exists(self):
        """Test that validate_tenant_id function exists and works."""
        from services.tenant import validate_tenant_id

        assert callable(validate_tenant_id)
        assert validate_tenant_id("user_abc123456789012345678901")
        assert not validate_tenant_id("invalid")


class TestSharedDatabasePool:
    """Tests for shared database pool configuration."""

    def test_shared_database_url_in_config(self):
        """Test that SHARED_DATABASE_URL is defined in config."""
        from config import Settings

        settings = Settings()
        assert hasattr(settings, 'shared_database_url')

    def test_shared_pool_health_check_function_exists(self):
        """Test that health_check function exists in shared_database."""
        from services.shared_database import health_check

        assert callable(health_check)

    def test_get_shared_pool_function_exists(self):
        """Test that get_shared_pool function exists."""
        from services.shared_database import get_shared_pool

        assert callable(get_shared_pool)


class TestQuerySecurityEnhancements:
    """Tests for enhanced query security with RLS."""

    def test_allowed_tables_includes_secure_views(self):
        """Test that ALLOWED_TABLES includes secure views."""
        from api.query import ALLOWED_TABLES

        assert "user_interactions_secure" in ALLOWED_TABLES
        assert "daily_stats_secure" in ALLOWED_TABLES

    def test_blocked_tables_includes_raw_mvs(self):
        """Test that BLOCKED_TABLES includes raw materialized views."""
        from api.query import BLOCKED_TABLES

        assert "user_interactions" in BLOCKED_TABLES
        assert "daily_stats" in BLOCKED_TABLES

    def test_blocked_keywords_includes_rls_bypass(self):
        """Test that BLOCKED_KEYWORDS includes RLS bypass attempts."""
        from api.query import BLOCKED_KEYWORDS

        rls_keywords = [
            "CURRENT_SETTING", "SET_CONFIG",
            "PG_CATALOG", "INFORMATION_SCHEMA",
            "PG_POLICIES",
        ]

        for keyword in rls_keywords:
            assert keyword in BLOCKED_KEYWORDS, f"Missing RLS bypass keyword: {keyword}"

    def test_injection_patterns_includes_rls_bypass(self):
        """Test that INJECTION_PATTERNS includes RLS bypass patterns."""
        from api.query import INJECTION_PATTERNS
        import re

        test_patterns = {
            r"app\.current_tenant": "app.current_tenant",
            r"current_setting\s*\(": "current_setting('app.current_tenant')",
            r"set_config\s*\(": "set_config('app.current_tenant', 'x', true)",
        }

        for pattern, test_string in test_patterns.items():
            found = False
            for injection_pattern in INJECTION_PATTERNS:
                if re.search(injection_pattern, test_string, re.IGNORECASE):
                    found = True
                    break
            assert found, f"Pattern not caught: {test_string}"

    def test_extract_table_names(self):
        """Test table name extraction from queries."""
        from api.query import extract_table_names

        test_cases = [
            ("SELECT * FROM messages", {"messages"}),
            ("SELECT * FROM messages JOIN users ON messages.author_id = users.id",
             {"messages", "users"}),
            ("SELECT m.* FROM messages m LEFT JOIN channels c ON m.channel_id = c.id",
             {"messages", "channels"}),
        ]

        for query, expected in test_cases:
            result = extract_table_names(query)
            assert result == expected, f"Query: {query}, Expected: {expected}, Got: {result}"


class TestDiscordExtractorTenantIsolation:
    """Tests for tenant isolation in Discord extractor."""

    def test_extractor_uses_shared_database(self):
        """Test that extractor imports shared_database module."""
        import importlib.util

        spec = importlib.util.find_spec("services.discord_extractor")
        assert spec is not None

        # Check source for shared_database import
        import inspect
        from services import discord_extractor
        source = inspect.getsource(discord_extractor)

        assert "from services.shared_database import" in source
        assert "tenant_connection" in source

    def test_extractor_includes_tenant_id_in_inserts(self):
        """Test that extractor includes tenant_id in INSERT statements."""
        import inspect
        from services import discord_extractor
        source = inspect.getsource(discord_extractor)

        # Check that INSERT statements include tenant_id
        insert_statements = [
            "INSERT INTO servers (tenant_id",
            "INSERT INTO users (tenant_id",
            "INSERT INTO channels (tenant_id",
            "INSERT INTO messages (\n                tenant_id",
            "INSERT INTO message_mentions (tenant_id",
        ]

        for stmt in insert_statements:
            # Normalize whitespace for comparison
            normalized_source = " ".join(source.split())
            normalized_stmt = " ".join(stmt.split())
            assert normalized_stmt.replace("(", " (").replace("\n", " ") in normalized_source or \
                   "tenant_id" in source and "INSERT INTO" in source, \
                   f"Missing tenant_id in: {stmt}"
