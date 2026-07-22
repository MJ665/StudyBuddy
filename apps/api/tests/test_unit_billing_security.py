"""Regression tests for the /billing webhook.

Before this was hardened, `/billing/webhook` accepted ANY unauthenticated JSON
body and would set an arbitrary organization's `subscription_tier` to "Pro" —
there was no signature verification at all.
"""

import hashlib
import hmac
import json
import time

import pytest
import routers.billing as billing
from fastapi import HTTPException

WEBHOOK_SECRET = "whsec_unit_test_secret"


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(billing, "STRIPE_SECRET_KEY", "sk_live_unit_test")
    monkeypatch.setattr(billing, "STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)


def _sign(payload: bytes, ts: int, secret: str = WEBHOOK_SECRET) -> str:
    mac = hmac.new(
        secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={mac}"


PAYLOAD = json.dumps(
    {
        "type": "checkout.session.completed",
        "data": {"object": {"client_reference_id": "1", "customer": "cus_x"}},
    }
).encode()


def test_billing_disabled_by_default():
    """With placeholder keys, billing must fail closed rather than mutate state."""
    assert billing._billing_enabled() is False
    with pytest.raises(HTTPException) as exc:
        billing._require_billing_enabled()
    assert exc.value.status_code == 503


def test_missing_signature_rejected(enabled):
    with pytest.raises(HTTPException) as exc:
        billing._verify_stripe_signature(PAYLOAD, None)
    assert exc.value.status_code == 400


def test_forged_signature_rejected(enabled):
    ts = int(time.time())
    with pytest.raises(HTTPException) as exc:
        billing._verify_stripe_signature(PAYLOAD, f"t={ts},v1=deadbeef")
    assert exc.value.status_code == 400


def test_signature_from_wrong_secret_rejected(enabled):
    ts = int(time.time())
    header = _sign(PAYLOAD, ts, secret="whsec_attacker_guess")
    with pytest.raises(HTTPException) as exc:
        billing._verify_stripe_signature(PAYLOAD, header)
    assert exc.value.status_code == 400


def test_replayed_old_signature_rejected(enabled):
    stale = int(time.time()) - (billing._SIGNATURE_TOLERANCE_SECONDS + 60)
    with pytest.raises(HTTPException) as exc:
        billing._verify_stripe_signature(PAYLOAD, _sign(PAYLOAD, stale))
    assert exc.value.status_code == 400


def test_tampered_body_rejected(enabled):
    """A signature valid for one body must not validate a different body."""
    ts = int(time.time())
    header = _sign(PAYLOAD, ts)
    tampered = PAYLOAD.replace(b'"client_reference_id": "1"', b'"client_reference_id": "2"')
    with pytest.raises(HTTPException) as exc:
        billing._verify_stripe_signature(tampered, header)
    assert exc.value.status_code == 400


def test_valid_signature_accepted(enabled):
    ts = int(time.time())
    billing._verify_stripe_signature(PAYLOAD, _sign(PAYLOAD, ts))  # must not raise
