"""Regression tests for KT knowledge-access scoping.

Background: `routers/kt.py` set the chat session's retrieval scope straight from
the request body (`resolved_project_ids = body.project_ids`). The Cypher filter
was real, but it was handed client-controlled values — so any authenticated user
could name any project in their organization and read its knowledge.

Access is now least-privilege: membership in `kt_project_members` is the only
grant, a request may narrow that set but never widen it, and every layer fails
closed on an empty grant list.
"""

import asyncio

import pytest
from services import kt_engine
from routers.kt import _normalize_grant_list


class TestGrantListsFailClosed:
    """An absent/NULL grant list must mean 'nothing', never 'everything'."""

    @pytest.mark.parametrize("value", [None, [], "", 0])
    def test_empty_grants_normalize_to_empty(self, value):
        assert _normalize_grant_list(value) == []

    def test_values_are_coerced_to_strings(self):
        assert _normalize_grant_list(["a", 1]) == ["a", "1"]

    def test_vector_search_returns_nothing_without_grants(self):
        """Fail closed before any connection or query is attempted.
        (Phase 7: targets the pgvector retriever — Neo4j is retired.)"""
        from modules.kt.services.retrieval import vector_search

        result = asyncio.run(
            vector_search(
                query_embedding=[0.0] * 8, company_id="c", project_ids=[], top_k=5
            )
        )
        assert result == []


class TestSensitivityPolicy:
    """`high` sensitivity means credentials/PII are present."""

    def test_project_leads_may_read_high_sensitivity(self):
        assert kt_engine.SENSITIVITY_HIGH in kt_engine.sensitivities_for(["lead"])

    def test_ordinary_members_may_not_read_high_sensitivity(self):
        allowed = kt_engine.sensitivities_for(["contributor", "reviewer"])
        assert kt_engine.SENSITIVITY_HIGH not in allowed
        assert kt_engine.SENSITIVITY_LOW in allowed

    def test_non_members_default_to_the_safe_set(self):
        """External access-key callers are never project members."""
        assert kt_engine.sensitivities_for(None) == kt_engine.DEFAULT_SENSITIVITIES
        assert kt_engine.SENSITIVITY_HIGH not in kt_engine.sensitivities_for([])

    def test_role_matching_is_case_insensitive(self):
        assert kt_engine.sensitivities_for(["LEAD"]) == kt_engine.ALL_SENSITIVITIES


class TestNoRetrievalPathTrustsClientScope:
    """The same flaw existed in three places: chat, /explorer/graph and
    /explorer/timeline each assigned the caller's requested project ids straight
    into the resolved scope. They now share `_resolve_retrieval_scope`."""

    @staticmethod
    def _kt_router_sources():
        """The KT router code, post Phase-2 split: the routers/kt.py aggregator
        plus every file under modules/kt/routers/."""
        import pathlib

        api_root = pathlib.Path(__file__).resolve().parent.parent
        files = [api_root / "routers" / "kt.py"]
        files += sorted((api_root / "modules" / "kt" / "routers").glob("*.py"))
        return [(f, f.read_text()) for f in files]

    def test_scope_is_never_assigned_from_request_input(self):
        import re

        offenders = []
        for f, source in self._kt_router_sources():
            offenders += [
                (f.name, i + 1, line.strip())
                for i, line in enumerate(source.splitlines())
                # an assignment, not a comment describing the old bug
                if re.match(
                    r"\s*resolved_project_ids\s*=\s*(body\.)?project_ids\s*$", line
                )
            ]
        assert not offenders, (
            "retrieval scope assigned from client input at: "
            + "; ".join(f"{f}:{n} {t}" for f, n, t in offenders)
        )

    def test_every_retrieval_entry_point_uses_the_shared_resolver(self):
        # one definition + one call per retrieval entry point (chat, graph, timeline)
        total = sum(
            source.count("_resolve_retrieval_scope(")
            for _, source in self._kt_router_sources()
        )
        assert total >= 4


class TestRetrievalQueriesCarryTheFilter:
    """Both retrieval paths must filter on sensitivity, not just tenancy."""

    def test_query_filters_on_sensitivity(self):
        """(Phase 7) The pgvector retriever must bind the sensitivity filter."""
        import inspect

        from modules.kt.services import retrieval

        source = inspect.getsource(retrieval.vector_search)
        assert "sensitivity" in source, "retriever does not filter on sensitivity"
        assert "sensitivities" in source, "retriever does not bind the allowed set"

    def test_query_is_scoped_to_company_and_projects(self):
        import inspect

        from modules.kt.services import retrieval

        source = inspect.getsource(retrieval.vector_search)
        assert "company_id == company_id" in source or "KTDocument.company_id" in source
        assert "project_id.in_(project_ids)" in source
