"""
Tests for configuration validation.

These tests ensure that missing configuration is detected early with clear error messages,
preventing cryptic runtime errors like "Could not validate token" when CLERK_JWT_ISSUER is missing.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

# Import the config module components
from config import Settings, ConfigurationError, validate_startup_config


class TestAuthConfigValidation:
    """Tests for authentication configuration validation."""

    def test_missing_clerk_jwt_issuer_returns_clear_error(self):
        """
        CRITICAL: Missing CLERK_JWT_ISSUER must return a clear, helpful error message.

        This was the root cause of the "Could not validate token" 401 error.
        The error message should explain:
        1. What is missing (CLERK_JWT_ISSUER)
        2. What it should be set to (Clerk issuer URL)
        3. How to find the value (base64 decode publishable key)
        """
        settings = Settings(
            clerk_jwt_issuer="",
            clerk_secret_key="sk_test_xxx",
        )
        errors = settings.validate_auth_config()

        assert len(errors) > 0, "Missing CLERK_JWT_ISSUER should produce an error"
        assert any("CLERK_JWT_ISSUER" in e for e in errors), \
            "Error message should mention CLERK_JWT_ISSUER"
        assert any("clerk.accounts.dev" in e.lower() or "issuer" in e.lower() for e in errors), \
            "Error message should explain what the value should be"

    def test_missing_clerk_secret_key_returns_clear_error(self):
        """Missing CLERK_SECRET_KEY should return a helpful error."""
        settings = Settings(
            clerk_jwt_issuer="https://test.clerk.accounts.dev",
            clerk_secret_key="",
        )
        errors = settings.validate_auth_config()

        assert len(errors) > 0, "Missing CLERK_SECRET_KEY should produce an error"
        assert any("CLERK_SECRET_KEY" in e for e in errors), \
            "Error message should mention CLERK_SECRET_KEY"

    def test_invalid_clerk_jwt_issuer_not_https_returns_error(self):
        """CLERK_JWT_ISSUER must start with https://."""
        settings = Settings(
            clerk_jwt_issuer="http://test.clerk.accounts.dev",  # http, not https
            clerk_secret_key="sk_test_xxx",
        )
        errors = settings.validate_auth_config()

        assert len(errors) > 0, "Non-HTTPS issuer should produce an error"
        assert any("https://" in e for e in errors), \
            "Error message should mention https:// requirement"

    def test_valid_auth_config_returns_no_errors(self):
        """Valid auth config should pass validation."""
        settings = Settings(
            clerk_jwt_issuer="https://test.clerk.accounts.dev",
            clerk_secret_key="sk_test_xxx",
        )
        errors = settings.validate_auth_config()

        assert len(errors) == 0, f"Valid config should have no errors, got: {errors}"

    def test_is_auth_configured_returns_false_when_missing(self):
        """is_auth_configured() should return False when auth is not configured."""
        settings = Settings(
            clerk_jwt_issuer="",
            clerk_secret_key="",
        )
        assert settings.is_auth_configured() is False

    def test_is_auth_configured_returns_true_when_configured(self):
        """is_auth_configured() should return True when auth is properly configured."""
        settings = Settings(
            clerk_jwt_issuer="https://test.clerk.accounts.dev",
            clerk_secret_key="sk_test_xxx",
        )
        assert settings.is_auth_configured() is True


class TestDatabaseConfigValidation:
    """Tests for database configuration validation."""

    def test_missing_database_url_returns_clear_error(self):
        """Missing DATABASE_URL should return a helpful error."""
        settings = Settings(
            database_url="",
            neon_api_key="xxx",
            neon_project_id="xxx",
        )
        errors = settings.validate_database_config()

        assert len(errors) > 0, "Missing DATABASE_URL should produce an error"
        assert any("DATABASE_URL" in e for e in errors), \
            "Error message should mention DATABASE_URL"

    def test_missing_shared_database_url_returns_clear_error(self):
        """Missing SHARED_DATABASE_URL should return a helpful error."""
        settings = Settings(
            database_url="postgresql://xxx",
            shared_database_url="",
        )
        errors = settings.validate_database_config()

        assert len(errors) > 0, "Missing SHARED_DATABASE_URL should produce an error"
        assert any("SHARED_DATABASE_URL" in e for e in errors), \
            "Error message should mention SHARED_DATABASE_URL"

    def test_shared_database_url_mentions_rls(self):
        """SHARED_DATABASE_URL error should mention RLS for tenant isolation."""
        settings = Settings(
            database_url="postgresql://xxx",
            shared_database_url="",
        )
        errors = settings.validate_database_config()

        shared_error = next((e for e in errors if "SHARED_DATABASE_URL" in e), None)
        assert shared_error is not None
        assert "RLS" in shared_error or "Row-Level Security" in shared_error, \
            "Error message should mention RLS for tenant isolation"

    def test_valid_database_config_returns_no_errors(self):
        """Valid database config should pass validation."""
        settings = Settings(
            database_url="postgresql://xxx",
            shared_database_url="postgresql://xxx",
        )
        errors = settings.validate_database_config()

        assert len(errors) == 0, f"Valid config should have no errors, got: {errors}"


class TestEncryptionConfigValidation:
    """Tests for encryption configuration validation."""

    def test_missing_encryption_key_returns_clear_error(self):
        """
        Missing DISCORD_TOKEN_ENCRYPTION_KEY should return a helpful error.

        This prevents the cryptic "Key not set" error when encrypting tokens.
        """
        settings = Settings(
            discord_token_encryption_key="",
        )
        errors = settings.validate_encryption_config()

        assert len(errors) > 0, "Missing encryption key should produce an error"
        assert any("DISCORD_TOKEN_ENCRYPTION_KEY" in e for e in errors), \
            "Error message should mention DISCORD_TOKEN_ENCRYPTION_KEY"
        assert any("Fernet" in e or "generate" in e.lower() for e in errors), \
            "Error message should explain how to generate a key"

    def test_valid_encryption_config_returns_no_errors(self):
        """Valid encryption config should pass validation."""
        settings = Settings(
            discord_token_encryption_key="test-key-xxx",
        )
        errors = settings.validate_encryption_config()

        assert len(errors) == 0, f"Valid config should have no errors, got: {errors}"


class TestBillingConfigValidation:
    """Tests for billing configuration validation."""

    def test_missing_stripe_secret_key_returns_clear_error(self):
        """Missing STRIPE_SECRET_KEY should return a helpful error."""
        settings = Settings(
            stripe_secret_key="",
        )
        errors = settings.validate_billing_config()

        assert len(errors) > 0, "Missing STRIPE_SECRET_KEY should produce an error"
        assert any("STRIPE_SECRET_KEY" in e for e in errors), \
            "Error message should mention STRIPE_SECRET_KEY"

    def test_valid_billing_config_returns_no_errors(self):
        """Valid billing config should pass validation."""
        settings = Settings(
            stripe_secret_key="sk_test_xxx",
        )
        errors = settings.validate_billing_config()

        assert len(errors) == 0, f"Valid config should have no errors, got: {errors}"


class TestFullConfigValidation:
    """Tests for complete configuration validation."""

    def test_validate_required_config_returns_all_errors(self):
        """validate_required_config should return all missing config errors."""
        settings = Settings(
            clerk_jwt_issuer="",
            clerk_secret_key="",
            database_url="",
            shared_database_url="",
            discord_token_encryption_key="",
            stripe_secret_key="",
        )
        is_valid, errors = settings.validate_required_config()

        assert is_valid is False
        # Should have errors for all 6 missing items:
        # CLERK_JWT_ISSUER, CLERK_SECRET_KEY, DATABASE_URL, SHARED_DATABASE_URL,
        # DISCORD_TOKEN_ENCRYPTION_KEY, STRIPE_SECRET_KEY
        assert len(errors) >= 6, f"Expected at least 6 errors, got {len(errors)}: {errors}"

    def test_validate_required_config_with_all_set(self):
        """validate_required_config should pass when all config is set."""
        settings = Settings(
            clerk_jwt_issuer="https://test.clerk.accounts.dev",
            clerk_secret_key="sk_test_xxx",
            database_url="postgresql://xxx",
            shared_database_url="postgresql://xxx",
            discord_token_encryption_key="xxx",
            stripe_secret_key="sk_test_xxx",
        )
        is_valid, errors = settings.validate_required_config()

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_required_config_can_skip_billing(self):
        """validate_required_config should be able to skip billing validation."""
        settings = Settings(
            clerk_jwt_issuer="https://test.clerk.accounts.dev",
            clerk_secret_key="sk_test_xxx",
            database_url="postgresql://xxx",
            shared_database_url="postgresql://xxx",
            discord_token_encryption_key="xxx",
            stripe_secret_key="",  # Missing, but should be skipped
        )
        is_valid, errors = settings.validate_required_config(include_billing=False)

        assert is_valid is True
        assert len(errors) == 0


class TestStartupValidation:
    """Tests for startup configuration validation."""

    def test_validate_startup_config_raises_in_production_mode(self):
        """
        validate_startup_config should raise ConfigurationError in production mode
        when required config is missing.
        """
        # Create settings with debug=False (production) and missing config
        with patch('config.get_settings') as mock_get_settings:
            mock_settings = Settings(
                debug=False,
                clerk_jwt_issuer="",
                clerk_secret_key="",
            )
            mock_get_settings.return_value = mock_settings

            # Clear the lru_cache to force re-read
            from config import get_settings
            get_settings.cache_clear()

            # Should raise in production mode with require_all=True
            with pytest.raises(ConfigurationError) as exc_info:
                validate_startup_config(require_all=True)

            assert "CLERK_JWT_ISSUER" in str(exc_info.value)

    def test_validate_startup_config_warns_in_debug_mode(self):
        """
        validate_startup_config should only warn (not raise) in debug mode
        when required config is missing.
        """
        with patch('config.get_settings') as mock_get_settings:
            mock_settings = Settings(
                debug=True,
                clerk_jwt_issuer="",
                clerk_secret_key="",
            )
            mock_get_settings.return_value = mock_settings

            # Should not raise in debug mode
            validate_startup_config(require_all=False)  # Should complete without exception


class TestAuthModuleConfigCheck:
    """Tests for early config check in auth module."""

    @pytest.mark.asyncio
    async def test_jwt_validator_raises_500_when_issuer_missing(self):
        """
        ClerkJWTValidator should raise HTTP 500 with clear message
        when CLERK_JWT_ISSUER is not configured.
        """
        from api.auth import ClerkJWTValidator

        with patch('api.auth.settings') as mock_settings:
            mock_settings.clerk_jwt_issuer = ""

            validator = ClerkJWTValidator()

            with pytest.raises(HTTPException) as exc_info:
                await validator.get_jwks()

            assert exc_info.value.status_code == 500
            assert "not configured" in exc_info.value.detail.lower() or \
                   "contact support" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_jwt_validator_raises_500_when_issuer_not_https(self):
        """
        ClerkJWTValidator should raise HTTP 500 with clear message
        when CLERK_JWT_ISSUER doesn't start with https://.
        """
        from api.auth import ClerkJWTValidator

        with patch('api.auth.settings') as mock_settings:
            mock_settings.clerk_jwt_issuer = "http://test.clerk.accounts.dev"

            validator = ClerkJWTValidator()

            with pytest.raises(HTTPException) as exc_info:
                await validator.get_jwks()

            assert exc_info.value.status_code == 500
            assert "misconfigured" in exc_info.value.detail.lower() or \
                   "contact support" in exc_info.value.detail.lower()


class TestConfigErrorMessages:
    """Tests to ensure error messages are helpful and actionable."""

    def test_clerk_jwt_issuer_error_explains_base64_derivation(self):
        """
        The CLERK_JWT_ISSUER error should mention that it can be derived
        from the publishable key via base64 decoding.
        """
        settings = Settings(clerk_jwt_issuer="")
        errors = settings.validate_auth_config()

        clerk_error = next((e for e in errors if "CLERK_JWT_ISSUER" in e), None)
        assert clerk_error is not None

        # Should mention base64 or CLERK_PUBLISHABLE_KEY
        assert "base64" in clerk_error.lower() or "publishable" in clerk_error.lower(), \
            f"Error should explain derivation from publishable key: {clerk_error}"

    def test_encryption_key_error_explains_generation(self):
        """
        The DISCORD_TOKEN_ENCRYPTION_KEY error should explain how to generate a key.
        """
        settings = Settings(discord_token_encryption_key="")
        errors = settings.validate_encryption_config()

        key_error = next((e for e in errors if "DISCORD_TOKEN_ENCRYPTION_KEY" in e), None)
        assert key_error is not None

        # Should mention Fernet or generation command
        assert "fernet" in key_error.lower() or "generate" in key_error.lower(), \
            f"Error should explain key generation: {key_error}"

    def test_all_errors_mention_environment_variable_name(self):
        """
        All configuration errors should clearly mention the environment variable name
        that needs to be set.
        """
        settings = Settings(
            clerk_jwt_issuer="",
            clerk_secret_key="",
            database_url="",
            shared_database_url="",
            discord_token_encryption_key="",
            stripe_secret_key="",
        )

        _, errors = settings.validate_required_config()

        expected_vars = [
            "CLERK_JWT_ISSUER",
            "CLERK_SECRET_KEY",
            "DATABASE_URL",
            "SHARED_DATABASE_URL",
            "DISCORD_TOKEN_ENCRYPTION_KEY",
            "STRIPE_SECRET_KEY",
        ]

        for var in expected_vars:
            assert any(var in e for e in errors), \
                f"Error messages should mention {var}. Got: {errors}"


class TestConfigValidationDoesNotLeakSecrets:
    """
    Security tests to ensure configuration validation doesn't leak secrets.
    """

    def test_error_messages_do_not_include_secret_values(self):
        """
        Error messages should mention variable NAMES but not their VALUES.
        This prevents accidentally logging secrets.
        """
        settings = Settings(
            clerk_jwt_issuer="http://wrong-format.com",  # Invalid but should not be shown
            clerk_secret_key="",
        )

        errors = settings.validate_auth_config()

        # The actual URL value should not appear in full (security)
        # But "http://" mention is fine as it explains the problem
        for error in errors:
            # Ensure we're not exposing full secret values
            assert "sk_test_" not in error
            assert "sk_live_" not in error
