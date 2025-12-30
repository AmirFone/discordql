"""
Configuration for the Discord Analytics SaaS backend.
Uses environment variables for all sensitive settings.
"""
from functools import lru_cache
from typing import Optional, List, Tuple
import os

from pydantic_settings import BaseSettings


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Discord Analytics SaaS"
    debug: bool = False
    api_prefix: str = "/api"
    frontend_url: str = "http://localhost:3000"  # Frontend URL for redirects

    # Clerk Authentication
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_jwt_issuer: str = ""  # e.g., https://your-app.clerk.accounts.dev
    clerk_webhook_secret: str = ""  # Webhook signing secret from Clerk

    # Neon Database
    neon_api_key: str = ""
    neon_project_id: str = ""
    database_url: str = ""  # Central application database (users, tokens, jobs)
    shared_database_url: str = ""  # Shared Discord data database with RLS

    # Stripe Billing
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_team: str = ""

    # Encryption
    discord_token_encryption_key: str = ""  # Fernet key

    # Redis (for Celery)
    redis_url: str = "redis://localhost:6379"

    # Rate Limiting
    rate_limit_queries_per_minute: int = 100
    query_timeout_seconds: int = 30
    max_result_rows: int = 10000

    # Subscription Limits
    free_tier_storage_mb: int = 500
    free_tier_sync_days: int = 30
    free_tier_queries_per_month: int = 1000
    pro_tier_storage_mb: int = 5000
    pro_tier_sync_days: int = 365
    team_tier_storage_mb: int = 25000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def validate_auth_config(self) -> List[str]:
        """
        Validate authentication configuration.
        Returns list of error messages for missing/invalid config.
        """
        errors = []

        if not self.clerk_jwt_issuer:
            errors.append(
                "CLERK_JWT_ISSUER is not set. "
                "Set this to your Clerk issuer URL (e.g., https://your-app.clerk.accounts.dev). "
                "You can derive this from your CLERK_PUBLISHABLE_KEY by base64 decoding it."
            )
        elif not self.clerk_jwt_issuer.startswith("https://"):
            errors.append(
                f"CLERK_JWT_ISSUER must start with 'https://'. Got: {self.clerk_jwt_issuer}"
            )

        if not self.clerk_secret_key:
            errors.append(
                "CLERK_SECRET_KEY is not set. "
                "Get this from the Clerk Dashboard > API Keys."
            )

        return errors

    def validate_database_config(self) -> List[str]:
        """
        Validate database configuration.
        Returns list of error messages for missing/invalid config.
        """
        errors = []

        if not self.database_url:
            errors.append(
                "DATABASE_URL is not set. "
                "Set this to your PostgreSQL connection string for the central app database."
            )

        if not self.shared_database_url:
            errors.append(
                "SHARED_DATABASE_URL is not set. "
                "Set this to your PostgreSQL connection string for the shared Discord data database. "
                "This database uses Row-Level Security (RLS) for tenant isolation."
            )

        return errors

    def validate_encryption_config(self) -> List[str]:
        """
        Validate encryption configuration.
        Returns list of error messages for missing/invalid config.
        """
        errors = []

        if not self.discord_token_encryption_key:
            errors.append(
                "DISCORD_TOKEN_ENCRYPTION_KEY is not set. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

        return errors

    def validate_billing_config(self) -> List[str]:
        """
        Validate billing configuration.
        Returns list of error messages for missing/invalid config.
        """
        errors = []

        if not self.stripe_secret_key:
            errors.append(
                "STRIPE_SECRET_KEY is not set. "
                "Get this from the Stripe Dashboard > Developers > API keys."
            )

        return errors

    def validate_required_config(self, include_billing: bool = True) -> Tuple[bool, List[str]]:
        """
        Validate all required configuration for production.

        Args:
            include_billing: Whether to validate billing config (can be False for testing)

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        errors.extend(self.validate_auth_config())
        errors.extend(self.validate_database_config())
        errors.extend(self.validate_encryption_config())

        if include_billing:
            errors.extend(self.validate_billing_config())

        return (len(errors) == 0, errors)

    def is_auth_configured(self) -> bool:
        """Check if authentication is properly configured."""
        return len(self.validate_auth_config()) == 0

    def is_database_configured(self) -> bool:
        """Check if database is properly configured."""
        return len(self.validate_database_config()) == 0


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def validate_startup_config(require_all: bool = False) -> None:
    """
    Validate configuration at startup.

    Args:
        require_all: If True, raise error for any missing config.
                    If False, only log warnings.

    Raises:
        ConfigurationError: If require_all=True and config is invalid.
    """
    settings = get_settings()

    # In debug mode, just warn about missing config
    if settings.debug and not require_all:
        is_valid, errors = settings.validate_required_config(include_billing=False)
        if not is_valid:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("=" * 60)
            logger.warning("CONFIGURATION WARNINGS (debug mode)")
            logger.warning("=" * 60)
            for error in errors:
                logger.warning(f"  - {error}")
            logger.warning("=" * 60)
        return

    # In production, validate and fail fast
    is_valid, errors = settings.validate_required_config(include_billing=True)
    if not is_valid:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ConfigurationError(error_msg)
