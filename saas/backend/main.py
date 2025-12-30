"""
Discord Analytics SaaS - FastAPI Backend

Main application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from config import get_settings, validate_startup_config, ConfigurationError
from api import auth, bot, extraction, query, billing, analytics
from db.connection import init_database


settings = get_settings()
logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Security headers to prevent common attacks
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Only add HSTS in production (when not debug mode)
        if not settings.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content Security Policy - adjust as needed for your frontend
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' https://api.clerk.com https://*.clerk.accounts.dev; "
            "frame-ancestors 'none';"
        )

        return response


def _log_config_status():
    """Log configuration status at startup."""
    # Check each config category and log status
    auth_errors = settings.validate_auth_config()
    db_errors = settings.validate_database_config()
    encryption_errors = settings.validate_encryption_config()
    billing_errors = settings.validate_billing_config()

    logger.info("=" * 60)
    logger.info("Configuration Status")
    logger.info("=" * 60)
    logger.info(f"  Authentication: {'OK' if not auth_errors else 'MISSING'}")
    logger.info(f"  Database:       {'OK' if not db_errors else 'MISSING'}")
    logger.info(f"  Encryption:     {'OK' if not encryption_errors else 'MISSING'}")
    logger.info(f"  Billing:        {'OK' if not billing_errors else 'MISSING'}")
    logger.info("=" * 60)

    # Log specific missing items
    all_errors = auth_errors + db_errors + encryption_errors + billing_errors
    if all_errors:
        logger.warning("Missing configuration:")
        for error in all_errors:
            # Truncate long error messages for log readability
            short_error = error.split(".")[0] if "." in error else error
            logger.warning(f"  - {short_error}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    print(f"Starting {settings.app_name}...")

    # Log configuration status
    _log_config_status()

    # Validate configuration (warnings only in debug mode)
    try:
        validate_startup_config(require_all=False)
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        raise

    # Initialize database tables
    try:
        await init_database()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Continue anyway - tables might already exist

    yield
    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    description="API for Discord Analytics SaaS Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Add security headers middleware first
app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware for frontend
# SECURITY: Only allow specific origins - NEVER use wildcards in production
import os

ALLOWED_ORIGINS = []

# Allow localhost for local development
# Check if running locally (HOST is localhost/127.0.0.1 or DEBUG is true)
host = os.getenv("HOST", "127.0.0.1")
is_local = host in ("127.0.0.1", "localhost", "0.0.0.0") or settings.debug

if is_local:
    ALLOWED_ORIGINS.append("http://localhost:3000")  # Next.js dev
    logger.info("CORS: Allowing http://localhost:3000 for local development")

# Add production domain from environment if set
if os.getenv("FRONTEND_URL"):
    ALLOWED_ORIGINS.append(os.getenv("FRONTEND_URL"))

# SECURITY: Require at least one origin in production
if not ALLOWED_ORIGINS:
    logger.warning("No CORS origins configured - API will reject cross-origin requests")

logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Include routers
app.include_router(auth.router, prefix=f"{settings.api_prefix}/auth", tags=["auth"])
app.include_router(bot.router, prefix=f"{settings.api_prefix}/bot", tags=["bot"])
app.include_router(extraction.router, prefix=f"{settings.api_prefix}/extraction", tags=["extraction"])
app.include_router(query.router, prefix=f"{settings.api_prefix}/query", tags=["query"])
app.include_router(billing.router, prefix=f"{settings.api_prefix}/billing", tags=["billing"])
app.include_router(analytics.router, prefix=f"{settings.api_prefix}/analytics", tags=["analytics"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "app": settings.app_name}


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "services": {
            "database": "ok",  # TODO: actual check
            "redis": "ok",     # TODO: actual check
            "neon": "ok",      # TODO: actual check
        }
    }


if __name__ == "__main__":
    import uvicorn

    # SECURITY: Bind to localhost in dev mode, allow override via env
    # In production, use a proper reverse proxy (nginx, etc.)
    host = os.getenv("HOST", "127.0.0.1" if settings.debug else "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=settings.debug,
    )
