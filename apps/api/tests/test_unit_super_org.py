"""Tests for the SuperOrganization (paying customer) tier.

    PlatformAdmin (us)
      └── SuperOrganization   ← purchases the app; approved/suspended from /platform
           └── Organization   ← business unit (L&D Admin operates here)
                └── Department → Vertical → Batch → Group → Users

Two scopes exist deliberately:
  * CONTENT  (question banks, questions, exams, KT companies/projects) → super-org,
    so a customer's business units share what they author.
  * LEARNER data (attempts, gradebooks, reports, users) → organization, so one
    business unit cannot read another's results.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect as sa_inspect

import auth_utils
from auth_utils import SUSPENDED_STATUSES, assert_same_super_org, is_platform_admin


class _Row:
    def __init__(self, super_organization_id=None):
        self.super_organization_id = super_organization_id


class _StubDB:
    """Minimal stand-in so scope logic can be tested without a database."""

    def __init__(self, super_id=None):
        self._super_id = super_id

    def query(self, *_):
        return self

    def filter(self, *_):
        return self

    def first(self):
        return (self._super_id,) if self._super_id is not None else None


MENTOR_A = {"sub": "1", "role": "Mentor", "organization_id": 1, "super_organization_id": 100}
MENTOR_B = {"sub": "2", "role": "Mentor", "organization_id": 2, "super_organization_id": 200}
SIBLING_A = {"sub": "3", "role": "Mentor", "organization_id": 9, "super_organization_id": 100}
PLATFORM = {"sub": "4", "role": "PlatformAdmin", "organization_id": 1}
NO_SUPER = {"sub": "5", "role": "Mentor", "organization_id": 3}


class TestSharedContentScope:
    def test_owning_unit_can_read_its_content(self):
        row = _Row(super_organization_id=100)
        assert assert_same_super_org(row, MENTOR_A, _StubDB(100)) is row

    def test_sibling_unit_of_same_customer_can_read_content(self):
        """The whole point: two Organizations under one customer share banks."""
        row = _Row(super_organization_id=100)
        assert assert_same_super_org(row, SIBLING_A, _StubDB(100)) is row

    def test_different_customer_is_denied(self):
        with pytest.raises(HTTPException) as exc:
            assert_same_super_org(_Row(super_organization_id=100), MENTOR_B, _StubDB(200))
        assert exc.value.status_code == 404

    def test_denial_is_404_so_ids_cannot_be_probed(self):
        with pytest.raises(HTTPException) as exc:
            assert_same_super_org(_Row(super_organization_id=999), MENTOR_A, _StubDB(100))
        assert exc.value.status_code == 404

    def test_unattributed_content_fails_closed(self):
        """A row with a NULL super org must match nobody, not everybody."""
        with pytest.raises(HTTPException):
            assert_same_super_org(_Row(super_organization_id=None), MENTOR_A, _StubDB(100))

    def test_caller_without_a_customer_is_denied(self):
        with pytest.raises(HTTPException):
            assert_same_super_org(_Row(super_organization_id=100), NO_SUPER, _StubDB(None))

    def test_platform_admin_crosses_customers(self):
        row = _Row(super_organization_id=999)
        assert assert_same_super_org(row, PLATFORM, _StubDB(1)) is row
        assert is_platform_admin(PLATFORM)


class TestSchema:
    @pytest.mark.parametrize(
        "module,cls",
        [
            ("models.bank", "QuestionBank"),
            ("models.bank", "Question"),
            ("models.exam", "Exam"),
            ("models.kt_model", "KTCompany"),
            ("models.kt_model", "KTProject"),
        ],
    )
    def test_shared_content_carries_the_customer_key(self, module, cls):
        import importlib

        model = getattr(importlib.import_module(module), cls)
        assert "super_organization_id" in {c.key for c in sa_inspect(model).mapper.columns}

    @pytest.mark.parametrize(
        "module,cls",
        [
            ("models.attempt", "Attempt"),
            ("models.exam", "ExamAttempt"),
            ("models.auth", "User"),
        ],
    )
    def test_learner_data_stays_organization_scoped(self, module, cls):
        """Learner results must NOT become customer-wide."""
        import importlib

        model = getattr(importlib.import_module(module), cls)
        cols = {c.key for c in sa_inspect(model).mapper.columns}
        assert "organization_id" in cols
        assert "super_organization_id" not in cols

    def test_organization_links_to_its_customer(self):
        from models.org import Organization, SuperOrganization

        assert "super_organization_id" in {
            c.key for c in sa_inspect(Organization).mapper.columns
        }
        cols = {c.key for c in sa_inspect(SuperOrganization).mapper.columns}
        # the customer owns billing + lifecycle
        assert {"status", "subscription_tier", "stripe_customer_id", "onboarding_token"} <= cols


class TestSuspensionIsEnforced:
    """Suspension used to be cosmetic: /platform flipped a column nobody read."""

    def test_blocked_statuses_cover_pending_and_suspended(self):
        assert {"suspended", "pending"} <= SUSPENDED_STATUSES

    def test_enforcement_helper_exists_and_is_wired_into_auth(self):
        import inspect
        import pathlib

        assert callable(auth_utils.assert_tenant_active)
        src = pathlib.Path(inspect.getfile(auth_utils)).read_text()
        # enforced at BOTH token issue and token verification
        assert src.count("assert_tenant_active(") >= 3
