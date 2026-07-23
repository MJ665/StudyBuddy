import hashlib
import hmac
import json
import logging
import os
import time

from auth_utils import require_ldadmin
from database import get_async_db
from fastapi import APIRouter, Depends, HTTPException, Request
from models.org import Organization
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/billing", tags=["billing"])
logger = logging.getLogger(__name__)

# Stripe is NOT enabled yet (product decision: cost tracking only, no payments).
# These placeholders mean "unconfigured" — every endpoint below fails closed
# while they are in effect, rather than mutating tenant subscription state.
_PLACEHOLDER_SECRET = "sk_test_placeholder"
_PLACEHOLDER_WEBHOOK = "whsec_placeholder"

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", _PLACEHOLDER_SECRET)
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", _PLACEHOLDER_WEBHOOK)

# Reject webhook payloads older than this to blunt replay attacks.
_SIGNATURE_TOLERANCE_SECONDS = 300


def _billing_enabled() -> bool:
    return (
        STRIPE_SECRET_KEY not in ("", _PLACEHOLDER_SECRET)
        and STRIPE_WEBHOOK_SECRET not in ("", _PLACEHOLDER_WEBHOOK)
    )


def _require_billing_enabled() -> None:
    if not _billing_enabled():
        raise HTTPException(
            status_code=503,
            detail="Billing is not enabled on this deployment.",
        )


def _verify_stripe_signature(payload: bytes, sig_header: str | None) -> None:
    """Validate Stripe's `Stripe-Signature` header.

    Implements the documented scheme (`t=<ts>,v1=<hmac>` over `"{t}.{payload}"`,
    HMAC-SHA256 keyed by the webhook secret) directly, so signature checking does
    not depend on the stripe SDK being installed. Previously this endpoint parsed
    the body with NO verification at all and would set any organization's tier to
    "Pro" on request — an unauthenticated privilege escalation.
    """
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    timestamp = None
    signatures = []
    for part in sig_header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)

    if not timestamp or not signatures:
        raise HTTPException(status_code=400, detail="Malformed Stripe signature")

    try:
        ts = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed Stripe signature")

    if abs(time.time() - ts) > _SIGNATURE_TOLERANCE_SECONDS:
        raise HTTPException(status_code=400, detail="Stripe signature expired")

    expected = hmac.new(
        STRIPE_WEBHOOK_SECRET.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + payload,
        hashlib.sha256,
    ).hexdigest()

    if not any(hmac.compare_digest(expected, s) for s in signatures):
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")


@router.post("/checkout")
async def create_checkout_session(
    org_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    """Generate a Stripe Checkout URL for an Organization to upgrade their tier."""
    _require_billing_enabled()

    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Reaching here requires real Stripe credentials; wire the live
    # stripe.checkout.Session.create call in when payments are turned on.
    raise HTTPException(
        status_code=501,
        detail="Stripe checkout is configured but not yet implemented.",
    )


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_async_db)):
    """Listen to Stripe webhook events to update subscription tiers."""
    _require_billing_enabled()

    payload = await request.body()
    _verify_stripe_signature(payload, request.headers.get("stripe-signature"))

    try:
        event = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload")

    if event.get("type") == "checkout.session.completed":
        session = event.get("data", {}).get("object", {})
        org_id = session.get("client_reference_id")
        stripe_customer_id = session.get("customer")

        if org_id:
            try:
                org = await db.get(Organization, int(org_id))
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=400, detail="Invalid client_reference_id"
                )
            if org:
                org.stripe_customer_id = stripe_customer_id
                org.subscription_tier = "Pro"
                await db.commit()
                logger.info(f"Billing: org {org_id} upgraded via verified webhook")

    return {"status": "success"}
