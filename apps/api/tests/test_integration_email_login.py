"""Integration tests for the rebuilt email-first login (Phase 3).

Uses TestClient against the real (dev) database: creates a disposable
group+user with an individual password_hash, logs in by email, and verifies
the legacy group-pattern path still works untouched. Cleans up after itself.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

import main
import models
from modules.identity.routers.auth_shared import pwd_context
from database import SessionLocal

pytestmark = pytest.mark.integration


@pytest.fixture()
def seeded_user():
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]
    org = models.Organization(
        name=f"email-login-test-org-{tag}",
        slug=f"email-login-{tag}",
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    group = models.Group(
        name=f"email-login-test-{tag}",
        password_pattern="<name>@Test123",
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    user = models.User(
        email=f"email.login.{tag}@studyhub-tests.dev",
        full_name="Email LoginTester",
        group_id=group.id,
        # JWT payload builder denies users without tenant attribution.
        organization_id=org.id,
        role="Member",
        password_hash=pwd_context.hash("S3cure!pass"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        yield user, group
    finally:
        db.query(models.RefreshToken).filter(
            models.RefreshToken.user_id == user.id
        ).delete()
        db.delete(user)
        db.delete(group)
        db.delete(org)
        db.commit()
        db.close()


@pytest.fixture(scope="module")
def client():
    # One client (and one app lifespan) for the whole module — per-test
    # clients re-run startup and tear the shared event loop down.
    with TestClient(main.app) as c:
        yield c


class TestEmailLogin:
    def test_email_login_succeeds_with_individual_password(self, client, seeded_user):
        user, _ = seeded_user
        r = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "S3cure!pass"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "success"
        assert body["user"]["id"] == user.id
        assert "access_token" in body

    def test_email_login_wrong_password_is_uniform_401(self, client, seeded_user):
        user, _ = seeded_user
        r = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "wrong"},
        )
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid email or password"

    def test_unknown_email_same_401_no_account_oracle(self, client):
        r = client.post(
            "/api/auth/login",
            json={"email": "nobody@studyhub-tests.dev", "password": "whatever"},
        )
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid email or password"

    def test_legacy_group_pattern_login_still_works(self, client, seeded_user):
        """A pattern-era user (no password_hash) logs in with the group
        pattern until Phase 4 flips the frontend."""
        user, group = seeded_user
        db = SessionLocal()
        try:
            db.query(models.User).filter(models.User.id == user.id).update(
                {"password_hash": None}
            )
            db.commit()
            r = client.post(
                "/api/auth/login",
                json={
                    "group_id": group.id,
                    "full_name": user.full_name,
                    # pattern "<name>@Test123" with first name "email" (sanitized)
                    "password": "email@Test123",
                },
            )
            assert r.status_code == 200, r.text
        finally:
            db.close()

    def test_missing_both_shapes_is_422(self, client):
        r = client.post("/api/auth/login", json={"password": "x"})
        assert r.status_code == 422


class TestCredentialIssuance:
    """Email-first lifecycle: creating a user WITHOUT a password must still
    issue individual credentials (auto-generated + hashed), so no new account
    ever depends on the shared group pattern."""

    def test_create_user_without_password_gets_hash(self, seeded_user):
        import schemas
        from modules.identity.routers.users import create_user

        user, group = seeded_user
        db = SessionLocal()
        try:
            created = create_user(
                user=schemas.UserCreate(
                    email=f"nopw.{uuid.uuid4().hex[:8]}@studyhub-tests.dev",
                    full_name="No Password Given",
                    group_id=group.id,
                    role="Member",
                ),
                db=db,
                current_user={
                    "sub": str(user.id),
                    "role": "GroupAdmin",
                    "group_id": group.id,
                    "organization_id": user.organization_id,
                },
            )
            fresh = db.query(models.User).filter(models.User.id == created.id).first()
            assert fresh.password_hash, "auto-generated credentials missing"
            db.delete(fresh)
            # create_user audit-logs the actor (the seeded admin) — clear it so
            # the seeded_user fixture teardown isn't FK-blocked.
            db.query(models.AdminAuditLog).filter(
                models.AdminAuditLog.actor_id == user.id
            ).delete()
            db.commit()
        finally:
            db.close()