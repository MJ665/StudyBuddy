"""Guards the router↔model contract.

Background: routers/kt.py constructed 8 different models with keyword arguments
that did not exist on those models. SQLAlchemy raises TypeError on unmapped
kwargs, so document creation, versioning, attachments, endorsements, access keys,
handoffs, ingestion jobs and the entire chat flow returned 500s. None of it was
caught by the test suite because no test exercised those constructors.

These tests scan the AST of every router for `Model(...)` calls and assert each
keyword maps to a real mapped attribute — catching the whole bug class, product
wide, without needing to execute the endpoints.
"""

import ast
import pathlib

import pytest
from sqlalchemy import inspect as sa_inspect

import models  # noqa: F401  — registers every mapper
from database import Base

API_ROOT = pathlib.Path(__file__).resolve().parent.parent
# Legacy flat routers + the modular-monolith router files (Phase 2+ split).
ROUTERS = sorted((API_ROOT / "routers").glob("*.py")) + sorted(
    (API_ROOT / "modules").glob("*/routers/*.py")
)


def _mapped_attrs() -> dict[str, set[str]]:
    """Map every ORM class name -> its settable mapped attribute names."""
    out: dict[str, set[str]] = {}
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        out[cls.__name__] = {a.key for a in sa_inspect(cls).attrs}
    return out


MAPPED = _mapped_attrs()


def _bad_kwargs_in(path: pathlib.Path) -> list[tuple[str, int, list[str]]]:
    tree = ast.parse(path.read_text())
    problems = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        model = node.func.id
        if model not in MAPPED:
            continue
        passed = {k.arg for k in node.keywords if k.arg}
        unmapped = sorted(passed - MAPPED[model])
        if unmapped:
            problems.append((model, node.lineno, unmapped))
    return problems


@pytest.mark.parametrize("router", ROUTERS, ids=lambda p: p.name)
def test_router_model_constructors_use_mapped_fields(router):
    """Every Model(...) kwarg in a router must be a real mapped attribute."""
    problems = _bad_kwargs_in(router)
    assert not problems, "\n".join(
        f"{router.name}:{line} {model}(...) passes unmapped kwarg(s): {', '.join(bad)}"
        for model, line, bad in problems
    )


def test_document_version_is_not_a_copy_of_access_key():
    """KTDocumentVersion's class body was once a copy-paste of KTAccessKey.

    That shape reached Postgres via create_all, so version history could never be
    written. Assert it looks like a version record, not a credential.
    """
    from models.kt_model import KTDocumentVersion

    cols = {c.key for c in sa_inspect(KTDocumentVersion).mapper.columns}
    assert {"document_id", "version", "body_markdown", "author_id"} <= cols
    leaked_credential_fields = cols & {"key_hash", "key_prefix", "recipient_email", "max_uses"}
    assert not leaked_credential_fields, (
        f"KTDocumentVersion carries access-key columns: {sorted(leaked_credential_fields)}"
    )


def test_chat_session_can_store_locked_retrieval_scope():
    """KT knowledge access is enforced by filtering retrieval on the session's
    resolved scope. If these columns don't persist, scoping cannot be enforced."""
    from models.kt_model import KTChatSession

    cols = {c.key for c in sa_inspect(KTChatSession).mapper.columns}
    assert {"user_id", "organization_id", "resolved_company_id", "resolved_project_ids"} <= cols


def test_access_key_carries_its_project_grants():
    """Key-based callers are scoped by KTAccessKey.project_ids."""
    from models.kt_model import KTAccessKey

    cols = {c.key for c in sa_inspect(KTAccessKey).mapper.columns}
    assert "project_ids" in cols
