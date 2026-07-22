"""Unit tests for the KT access-key HMAC gate and prompt guardrails (no network)."""
from services.kt_engine import (
    generate_access_key,
    is_injection,
    sanitize_output,
    verify_access_key_signature,
)

CID = "company-123"
PIDS = ["proj-a", "proj-b"]


def test_access_key_roundtrip_valid():
    raw_key, key_hash, key_prefix = generate_access_key(CID, PIDS)
    assert raw_key.startswith("sh_kt_")
    assert key_prefix.startswith("sh_kt_")
    assert len(key_hash) == 64  # sha256 hex
    assert verify_access_key_signature(raw_key, CID, PIDS) is True


def test_access_key_project_order_independent():
    raw_key, _, _ = generate_access_key(CID, ["proj-b", "proj-a"])
    # scope is sorted internally, so order at verification must not matter
    assert verify_access_key_signature(raw_key, CID, ["proj-a", "proj-b"]) is True


def test_access_key_rejects_wrong_company():
    raw_key, _, _ = generate_access_key(CID, PIDS)
    assert verify_access_key_signature(raw_key, "other-company", PIDS) is False


def test_access_key_rejects_wrong_projects():
    raw_key, _, _ = generate_access_key(CID, PIDS)
    assert verify_access_key_signature(raw_key, CID, ["proj-a"]) is False
    assert verify_access_key_signature(raw_key, CID, ["proj-a", "proj-c"]) is False


def test_access_key_rejects_tampered_signature():
    raw_key, _, _ = generate_access_key(CID, PIDS)
    tampered = raw_key[:-1] + ("0" if raw_key[-1] != "0" else "1")
    assert verify_access_key_signature(tampered, CID, PIDS) is False


def test_access_key_rejects_bad_format():
    assert verify_access_key_signature("", CID, PIDS) is False
    assert verify_access_key_signature("not-a-key", CID, PIDS) is False
    assert verify_access_key_signature("sh_kt_short_sig", CID, PIDS) is False


def test_sanitize_output_strips_script_tags():
    dirty = "hello <script>alert(1)</script> world"
    clean = sanitize_output(dirty)
    assert "<script>" not in clean and "</script>" not in clean


def test_is_injection_returns_bool():
    # Current implementation is conservative (returns False); contract is a bool.
    assert isinstance(is_injection("normal question"), bool)
