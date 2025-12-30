"""
Stripe billing endpoints.
Handles subscriptions, webhooks, and usage tracking.
"""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text
import stripe

from api.auth import User, get_current_user
from db.connection import get_db_session
from config import get_settings

router = APIRouter()
settings = get_settings()

# Initialize Stripe
stripe.api_key = settings.stripe_secret_key


class SubscriptionResponse(BaseModel):
    """Current subscription details."""
    tier: str
    status: str
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False


class CheckoutResponse(BaseModel):
    """Checkout session URL."""
    checkout_url: str


class UsageResponse(BaseModel):
    """Current usage stats."""
    storage_used_mb: float
    storage_limit_mb: int
    queries_this_month: int
    queries_limit: int
    extractions_this_month: int


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(user: User = Depends(get_current_user)):
    """Get the user's current subscription details."""
    async with get_db_session() as session:
        result = await session.execute(
            text("""
            SELECT subscription_tier, stripe_customer_id
            FROM app_users WHERE clerk_id = :clerk_id
            """),
            {"clerk_id": user.clerk_id}
        )
        row = result.fetchone()

        if not row:
            return SubscriptionResponse(tier="free", status="active")

        tier, customer_id = row

        # Get subscription details from Stripe
        if customer_id and tier != "free":
            try:
                subscriptions = stripe.Subscription.list(customer=customer_id, limit=1)
                if subscriptions.data:
                    sub = subscriptions.data[0]
                    return SubscriptionResponse(
                        tier=tier,
                        status=sub.status,
                        current_period_end=datetime.fromtimestamp(sub.current_period_end),
                        cancel_at_period_end=sub.cancel_at_period_end,
                    )
            except Exception:
                pass

        return SubscriptionResponse(tier=tier, status="active")


@router.post("/checkout/{plan}", response_model=CheckoutResponse)
async def create_checkout(
    plan: str,
    user: User = Depends(get_current_user),
):
    """
    Create a Stripe checkout session for upgrading to a plan.

    Plans: 'pro', 'team'
    """
    if plan not in ("pro", "team"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan. Choose 'pro' or 'team'."
        )

    price_id = settings.stripe_price_pro if plan == "pro" else settings.stripe_price_team

    # Get or create Stripe customer
    async with get_db_session() as session:
        result = await session.execute(
            text("""
            SELECT stripe_customer_id, email FROM app_users WHERE clerk_id = :clerk_id
            """),
            {"clerk_id": user.clerk_id}
        )
        row = result.fetchone()

        if row and row[0]:
            customer_id = row[0]
        else:
            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=row[1] if row else user.email,
                metadata={"clerk_id": user.clerk_id}
            )
            customer_id = customer.id

            # Save customer ID
            await session.execute(
                text("""
                UPDATE app_users SET stripe_customer_id = :customer_id
                WHERE clerk_id = :clerk_id
                """),
                {"customer_id": customer_id, "clerk_id": user.clerk_id}
            )
            await session.commit()

    # Create checkout session
    try:
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url="http://localhost:3000/dashboard?upgraded=true",
            cancel_url="http://localhost:3000/dashboard/settings",
            metadata={"clerk_id": user.clerk_id, "plan": plan},
        )
        return CheckoutResponse(checkout_url=checkout_session.url)
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}"
        )


@router.post("/portal")
async def create_portal_session(user: User = Depends(get_current_user)):
    """Create a Stripe billing portal session for managing subscription."""
    async with get_db_session() as session:
        result = await session.execute(
            text("""
            SELECT stripe_customer_id FROM app_users WHERE clerk_id = :clerk_id
            """),
            {"clerk_id": user.clerk_id}
        )
        row = result.fetchone()

        if not row or not row[0]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No billing account found"
            )

        customer_id = row[0]

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url="http://localhost:3000/dashboard/settings",
        )
        return {"portal_url": portal_session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}"
        )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(user: User = Depends(get_current_user)):
    """Get the user's current usage stats."""
    async with get_db_session() as session:
        # Get user record with UUID and subscription tier
        user_result = await session.execute(
            text("""
            SELECT id, subscription_tier FROM app_users WHERE clerk_id = :clerk_id
            """),
            {"clerk_id": user.clerk_id}
        )
        user_row = user_result.fetchone()

        if not user_row:
            return UsageResponse(
                storage_used_mb=0,
                storage_limit_mb=settings.free_tier_storage_mb,
                queries_this_month=0,
                queries_limit=settings.free_tier_queries_per_month,
                extractions_this_month=0,
            )

        user_uuid = str(user_row[0])
        tier = user_row[1] or "free"

        # Get query count this month
        query_result = await session.execute(
            text("""
            SELECT COUNT(*) FROM usage_logs
            WHERE user_id = :user_id
            AND action = 'query'
            AND created_at >= date_trunc('month', CURRENT_DATE)
            """),
            {"user_id": user_uuid}
        )
        queries = query_result.fetchone()[0]

        # Get extraction count this month
        extraction_result = await session.execute(
            text("""
            SELECT COUNT(*) FROM extraction_jobs
            WHERE user_id = :user_id
            AND started_at >= date_trunc('month', CURRENT_DATE)
            """),
            {"user_id": user_uuid}
        )
        extractions = extraction_result.fetchone()[0]

        # Get storage usage (from usage_logs or Neon API)
        storage_result = await session.execute(
            text("""
            SELECT COALESCE(SUM(storage_bytes), 0) FROM usage_logs
            WHERE user_id = :user_id
            """),
            {"user_id": user_uuid}
        )
        storage_bytes = storage_result.fetchone()[0]
        storage_mb = storage_bytes / (1024 * 1024)

        # Get limits based on tier
        limits = {
            "free": (settings.free_tier_storage_mb, settings.free_tier_queries_per_month),
            "pro": (settings.pro_tier_storage_mb, 999999),
            "team": (settings.team_tier_storage_mb, 999999),
        }
        storage_limit, query_limit = limits.get(tier, limits["free"])

        return UsageResponse(
            storage_used_mb=round(storage_mb, 2),
            storage_limit_mb=storage_limit,
            queries_this_month=queries,
            queries_limit=query_limit,
            extractions_this_month=extractions,
        )


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhooks for subscription events.

    Events handled:
    - checkout.session.completed
    - customer.subscription.updated
    - customer.subscription.deleted
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle events
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        clerk_id = session.get("metadata", {}).get("clerk_id")
        plan = session.get("metadata", {}).get("plan")

        if clerk_id and plan:
            async with get_db_session() as db_session:
                await db_session.execute(
                    text("""
                    UPDATE app_users SET subscription_tier = :tier
                    WHERE clerk_id = :clerk_id
                    """),
                    {"tier": plan, "clerk_id": clerk_id}
                )
                await db_session.commit()

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]

        async with get_db_session() as db_session:
            await db_session.execute(
                text("""
                UPDATE app_users SET subscription_tier = 'free'
                WHERE stripe_customer_id = :customer_id
                """),
                {"customer_id": customer_id}
            )
            await db_session.commit()

    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]

        # Check if subscription is past_due or cancelled
        if subscription["status"] in ("past_due", "canceled", "unpaid"):
            async with get_db_session() as db_session:
                await db_session.execute(
                    text("""
                    UPDATE app_users SET subscription_tier = 'free'
                    WHERE stripe_customer_id = :customer_id
                    """),
                    {"customer_id": customer_id}
                )
                await db_session.commit()

    return {"received": True}
