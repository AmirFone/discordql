"""
Authentication endpoints and Clerk JWT validation.
"""
from typing import Optional
import hashlib
import hmac
import uuid
import logging

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from pydantic import BaseModel

from sqlalchemy import text

from config import get_settings
from db.connection import get_db_session
from services.neon import provision_user_database, delete_user_database

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


class User(BaseModel):
    """Authenticated user from Clerk."""
    clerk_id: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class ClerkJWTValidator:
    """Validates Clerk JWT tokens."""

    # JWKS cache TTL in seconds (5 minutes)
    JWKS_CACHE_TTL = 300

    def __init__(self):
        self._jwks = None
        self._jwks_client = None
        self._jwks_fetched_at = 0

    def _validate_config(self):
        """
        Check that Clerk JWT configuration is present.
        Raises HTTPException with helpful error message if not configured.
        """
        if not settings.clerk_jwt_issuer:
            logger.error(
                "CLERK_JWT_ISSUER is not configured. "
                "Set this environment variable to your Clerk issuer URL "
                "(e.g., https://your-app.clerk.accounts.dev)"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication not configured. Please contact support."
            )

        if not settings.clerk_jwt_issuer.startswith("https://"):
            logger.error(
                f"CLERK_JWT_ISSUER must start with 'https://'. "
                f"Current value: {settings.clerk_jwt_issuer}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication misconfigured. Please contact support."
            )

    async def get_jwks(self):
        """Fetch JWKS from Clerk with TTL-based caching."""
        import time

        # Validate config BEFORE attempting to fetch
        self._validate_config()

        # Check if cache is expired or empty
        current_time = time.time()
        cache_expired = (current_time - self._jwks_fetched_at) > self.JWKS_CACHE_TTL

        if self._jwks is None or cache_expired:
            # Clerk JWKS endpoint
            jwks_url = f"{settings.clerk_jwt_issuer}/.well-known/jwks.json"
            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_url)
                response.raise_for_status()
                self._jwks = response.json()
                self._jwks_fetched_at = current_time
                logger.debug("JWKS cache refreshed")
        return self._jwks

    async def validate_token(self, token: str) -> dict:
        """Validate a Clerk JWT token and return claims."""
        try:
            # Get JWKS
            jwks = await self.get_jwks()

            # Decode header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            # Log key info at DEBUG level only (not INFO) to avoid information disclosure
            available_kids = [k.get("kid") for k in jwks.get("keys", [])]
            logger.debug(f"Token kid: {kid}, Available: {available_kids}")

            # Find matching key
            key = None
            for k in jwks.get("keys", []):
                if k.get("kid") == kid:
                    key = jwt.algorithms.RSAAlgorithm.from_jwk(k)
                    break

            if key is None:
                logger.error(
                    f"Key mismatch! Token kid '{kid}' not in JWKS keys {available_kids}. "
                    f"This usually means: 1) Frontend Clerk keys don't match backend CLERK_JWT_ISSUER, "
                    f"2) User needs to log out and log back in to get fresh token, or "
                    f"3) Clerk is running in 'keyless mode' (check frontend for .env.local)"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: key not found"
                )

            # Verify and decode token
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=settings.clerk_jwt_issuer,
                options={"verify_aud": False}  # Clerk doesn't always set audience
            )

            return claims

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            # SECURITY: Log detailed error server-side, return generic message to client
            logger.debug(f"Token validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        except httpx.HTTPStatusError:
            # JWKS fetch failed - treat as unauthorized
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate token"
            )
        except httpx.RequestError:
            # Network error fetching JWKS - treat as unauthorized
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate token"
            )


jwt_validator = ClerkJWTValidator()


async def get_current_user(
    authorization: Optional[str] = Header(None)
) -> User:
    """
    Dependency to get the current authenticated user from Clerk JWT.

    Usage:
        @router.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.clerk_id}
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )

    # Extract bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )

    token = parts[1]

    # Validate token
    claims = await jwt_validator.validate_token(token)

    # SECURITY: Validate required claims before creating User
    sub = claims.get("sub")
    if not sub:
        logger.warning("Token missing 'sub' claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user identifier"
        )

    return User(
        clerk_id=sub,
        email=claims.get("email"),
        first_name=claims.get("first_name"),
        last_name=claims.get("last_name"),
    )


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """Get current authenticated user info."""
    return user


@router.get("/verify")
async def verify_token(user: User = Depends(get_current_user)):
    """Verify that the provided token is valid."""
    return {"valid": True, "user_id": user.clerk_id}


class ClerkWebhookPayload(BaseModel):
    """Clerk webhook event payload."""
    type: str
    data: dict


def verify_clerk_webhook(payload: bytes, signature: str) -> bool:
    """
    Verify Clerk webhook signature using HMAC.

    Clerk uses Svix for webhooks. The signature header contains:
    v1,<timestamp>,<signature>
    """
    if not settings.clerk_webhook_secret:
        logger.warning("Clerk webhook secret not configured")
        return False

    try:
        # Parse the svix signature header
        parts = signature.split(",")
        if len(parts) < 3:
            return False

        timestamp = parts[0].replace("v1=", "").strip()
        received_signature = None

        for part in parts[1:]:
            if part.startswith("v1="):
                received_signature = part.replace("v1=", "").strip()
                break

        if not received_signature:
            # Try simpler format
            received_signature = parts[1].strip()

        # Create the signed content
        signed_content = f"{timestamp}.{payload.decode()}"

        # Compute expected signature
        secret = settings.clerk_webhook_secret
        if secret.startswith("whsec_"):
            secret = secret[6:]

        expected_signature = hmac.new(
            secret.encode(),
            signed_content.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(received_signature, expected_signature)
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        return False


@router.post("/webhook/clerk")
async def clerk_webhook(request: Request):
    """
    Handle Clerk webhook events.

    Handles user.created event to provision user database.
    """
    # Get raw body and signature
    body = await request.body()
    signature = request.headers.get("svix-signature", "")

    # SECURITY: Always require webhook signature verification
    # Fail-closed: reject webhooks if secret is not configured
    if not settings.clerk_webhook_secret:
        logger.error("Clerk webhook secret not configured - rejecting webhook")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing not configured"
        )

    if not verify_clerk_webhook(body, signature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature"
        )

    # Parse the event
    import json
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    event_type = event.get("type")
    data = event.get("data", {})

    logger.info(f"Received Clerk webhook: {event_type}")

    if event_type == "user.created":
        await handle_user_created(data)
    elif event_type == "user.deleted":
        await handle_user_deleted(data)
    elif event_type == "user.updated":
        await handle_user_updated(data)

    return {"status": "ok"}


async def handle_user_created(data: dict):
    """
    Handle user.created event - provision user database.
    """
    clerk_id = data.get("id")
    email = None

    # Extract email from email_addresses array
    email_addresses = data.get("email_addresses", [])
    for email_obj in email_addresses:
        if email_obj.get("id") == data.get("primary_email_address_id"):
            email = email_obj.get("email_address")
            break

    if not email and email_addresses:
        email = email_addresses[0].get("email_address")

    # SECURITY: Don't log full email addresses (PII)
    email_domain = email.split("@")[1] if email and "@" in email else "unknown"
    logger.info(f"Provisioning user: {clerk_id} (***@{email_domain})")

    async with get_db_session() as session:
        # Check if user already exists
        result = await session.execute(
            text("SELECT id FROM users WHERE clerk_id = :clerk_id"),
            {"clerk_id": clerk_id}
        )
        if result.fetchone():
            logger.info(f"User {clerk_id} already exists")
            return

        # Provision Neon database
        try:
            neon_branch_id = await provision_user_database(clerk_id)
            logger.info(f"Created Neon branch {neon_branch_id} for user {clerk_id}")
        except Exception as e:
            logger.error(f"Failed to provision Neon database for {clerk_id}: {e}")
            neon_branch_id = None

        # Create user record
        user_id = str(uuid.uuid4())
        await session.execute(
            text("""
            INSERT INTO users (id, clerk_id, email, subscription_tier, neon_branch_id)
            VALUES (:id, :clerk_id, :email, 'free', :neon_branch_id)
            """),
            {
                "id": user_id,
                "clerk_id": clerk_id,
                "email": email,
                "neon_branch_id": neon_branch_id,
            }
        )
        await session.commit()

        logger.info(f"Created user {clerk_id} with ID {user_id}")


async def handle_user_deleted(data: dict):
    """
    Handle user.deleted event - clean up user data.
    """
    clerk_id = data.get("id")

    logger.info(f"Deleting user: {clerk_id}")

    # Delete Neon database branch
    try:
        await delete_user_database(clerk_id)
    except Exception as e:
        logger.error(f"Failed to delete Neon database for {clerk_id}: {e}")

    # Delete user record (cascades to tokens, jobs, etc.)
    async with get_db_session() as session:
        await session.execute(
            text("DELETE FROM users WHERE clerk_id = :clerk_id"),
            {"clerk_id": clerk_id}
        )
        await session.commit()

    logger.info(f"Deleted user {clerk_id}")


async def handle_user_updated(data: dict):
    """
    Handle user.updated event - sync email changes.
    """
    clerk_id = data.get("id")
    email = None

    email_addresses = data.get("email_addresses", [])
    for email_obj in email_addresses:
        if email_obj.get("id") == data.get("primary_email_address_id"):
            email = email_obj.get("email_address")
            break

    if email:
        async with get_db_session() as session:
            await session.execute(
                text("UPDATE users SET email = :email WHERE clerk_id = :clerk_id"),
                {"email": email, "clerk_id": clerk_id}
            )
            await session.commit()

        logger.info(f"Updated email for user {clerk_id}")
