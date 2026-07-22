"""Regression tests for multi-tenant isolation.

Background: the core content tables (`question_banks`, `questions`, `attempts`,
`exam_attempts`, and `users` itself) had NO tenant column. Ownership existed only
implicitly via user -> group -> batch -> vertical -> department -> organization,
and no query walked that chain. `require_mentor_or_above` checks only the global
role string, so any mentor could read another organization's gradebook, exam
attempts and quiz attempts by guessing an id.

Isolation now rests on a denormalized `organization_id` plus the helpers below,
which must fail CLOSED in every ambiguous case.
"""

import pytest
from fastapi import HTTPException

from auth_utils import assert_same_org, caller_org_id, is_platform_admin


class _Row:
    """Stand-in for an ORM row carrying a tenant key."""

    def __init__(self, organization_id=None):
        self.organization_id = organization_id


MEMBER_ORG_1 = {"sub": "10", "role": "Member", "organization_id": 1}
MENTOR_ORG_1 = {"sub": "11", "role": "Mentor", "organization_id": 1}
MENTOR_ORG_2 = {"sub": "12", "role": "Mentor", "organization_id": 2}
PLATFORM_ADMIN = {"sub": "1", "role": "PlatformAdmin", "organization_id": 1}
NO_ORG = {"sub": "13", "role": "Mentor", "organization_id": None}


class TestCallerOrg:
    def test_reads_org_from_claims(self):
        assert caller_org_id(MENTOR_ORG_1) == 1

    def test_missing_org_is_none_not_a_default(self):
        """A hardcoded fallback (previously org 4, which does not exist) would
        mis-scope every subsequent query."""
        assert caller_org_id(NO_ORG) is None
        assert caller_org_id({}) is None

    def test_platform_admin_is_recognised(self):
        assert is_platform_admin(PLATFORM_ADMIN)
        assert not is_platform_admin(MENTOR_ORG_1)


class TestAssertSameOrg:
    def test_same_org_is_allowed(self):
        row = _Row(organization_id=1)
        assert assert_same_org(row, MENTOR_ORG_1) is row

    def test_cross_org_is_denied(self):
        with pytest.raises(HTTPException) as exc:
            assert_same_org(_Row(organization_id=1), MENTOR_ORG_2)
        assert exc.value.status_code == 404

    def test_denial_is_404_not_403(self):
        """403 would confirm the row exists, letting a caller enumerate ids in
        other tenants."""
        with pytest.raises(HTTPException) as exc:
            assert_same_org(_Row(organization_id=99), MENTOR_ORG_1)
        assert exc.value.status_code == 404

    def test_missing_row_is_404(self):
        with pytest.raises(HTTPException) as exc:
            assert_same_org(None, MENTOR_ORG_1)
        assert exc.value.status_code == 404

    def test_row_without_tenant_is_denied(self):
        """Un-backfilled legacy rows must fail closed, not match every tenant."""
        with pytest.raises(HTTPException) as exc:
            assert_same_org(_Row(organization_id=None), MENTOR_ORG_1)
        assert exc.value.status_code == 404

    def test_caller_without_tenant_is_denied(self):
        with pytest.raises(HTTPException) as exc:
            assert_same_org(_Row(organization_id=1), NO_ORG)
        assert exc.value.status_code == 404

    def test_platform_admin_crosses_orgs_by_design(self):
        row = _Row(organization_id=99)
        assert assert_same_org(row, PLATFORM_ADMIN) is row

    def test_role_alone_does_not_grant_cross_org_access(self):
        """A Mentor is privileged WITHIN their org, never across orgs — this is
        precisely what `require_mentor_or_above` could not express."""
        for actor in (MEMBER_ORG_1, MENTOR_ORG_1):
            with pytest.raises(HTTPException):
                assert_same_org(_Row(organization_id=2), actor)


class TestTenantColumnsExist:
    """The isolation story depends on these columns existing."""

    @pytest.mark.parametrize(
        "model_path,attr",
        [
            ("models.bank:QuestionBank", "organization_id"),
            ("models.bank:Question", "organization_id"),
            ("models.attempt:Attempt", "organization_id"),
            ("models.exam:ExamAttempt", "organization_id"),
            ("models.auth:User", "organization_id"),
        ],
    )
    def test_model_has_tenant_key(self, model_path, attr):
        import importlib

        module_name, cls_name = model_path.split(":")
        cls = getattr(importlib.import_module(module_name), cls_name)
        from sqlalchemy import inspect as sa_inspect

        assert attr in {c.key for c in sa_inspect(cls).mapper.columns}


class TestNoHardcodedOrgFallback:
    def test_auth_utils_has_no_magic_org_default(self):
        """`organization_id = 4` and `Organization.first()` silently placed users
        in an arbitrary (or nonexistent) tenant."""
        import pathlib
        import re

        src = (
            pathlib.Path(__file__).resolve().parent.parent / "auth_utils.py"
        ).read_text()
        # strip docstrings/comments describing the old behaviour
        code = "\n".join(
            line for line in src.splitlines() if not line.strip().startswith("#")
        )
        assert not re.search(r'organization_id"\]\s*=\s*\d+', code)
        assert "org_id = first_org.id" not in code


class TestOrgClaimCoercion:
    """JWT claims can carry organization_id as a STRING.

    psycopg2 silently coerced `integer = varchar`; asyncpg raises
    `UndefinedFunctionError: operator does not exist: integer = character varying`.
    So every org comparison must go through a helper that coerces, or async
    endpoints break the moment a token carries a string claim.
    """

    def test_string_claim_is_coerced_to_int(self):
        assert caller_org_id({"organization_id": "2"}) == 2
        assert isinstance(caller_org_id({"organization_id": "2"}), int)

    def test_int_claim_passes_through(self):
        assert caller_org_id({"organization_id": 2}) == 2

    def test_string_and_int_claims_are_equivalent(self):
        assert caller_org_id({"organization_id": "7"}) == caller_org_id({"organization_id": 7})

    def test_assert_same_org_accepts_a_string_claim(self):
        row = _Row(organization_id=3)
        assert assert_same_org(row, {"role": "Mentor", "organization_id": "3"}) is row
