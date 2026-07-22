"""Tests for the durable background job queue.

KT ingestion, document enrichment and transactional email used FastAPI
`BackgroundTasks` — in-process, so a deploy or crash mid-flight discarded the work
with no record and no retry. For ingestion that meant a member's contribution
never reached the knowledge graph and nobody was told.

These tests cover the properties that make the replacement durable rather than
just asynchronous.
"""

import ast
import pathlib

import pytest

from services import job_queue
from services.job_queue import _backoff_seconds, registered_handlers

ROUTERS = pathlib.Path(__file__).resolve().parent.parent / "routers"


class TestHandlerRegistry:
    def test_the_losable_work_has_handlers(self):
        import services.job_handlers  # noqa: F401  — registers them

        handlers = registered_handlers()
        assert "kt.ingest_document" in handlers
        assert "kt.enrich_document" in handlers
        assert "email.send" in handlers

    def test_unknown_job_type_is_rejected_at_enqueue(self):
        """Fail loudly when queued, rather than silently never running."""
        import asyncio

        with pytest.raises(ValueError, match="No handler registered"):
            asyncio.run(job_queue.enqueue(None, "does.not.exist", {}))


class TestRetryBackoff:
    def test_backoff_grows(self):
        assert _backoff_seconds(1) < _backoff_seconds(2) < _backoff_seconds(3)

    def test_backoff_is_capped(self):
        """An unbounded backoff would park a job effectively forever."""
        assert _backoff_seconds(50) <= 600

    def test_first_retry_is_prompt(self):
        assert _backoff_seconds(1) <= 30


class TestClaimSafety:
    def test_claim_uses_skip_locked(self):
        """Without SKIP LOCKED, two replicas would run the same job twice —
        double-ingesting a document into the knowledge graph."""
        import inspect

        src = inspect.getsource(job_queue._claim_batch)
        assert "FOR UPDATE SKIP LOCKED" in src

    def test_stale_claims_are_recoverable(self):
        """A worker that dies holding a claim must not park the job in `running`
        forever — that is the exact silent-loss this queue prevents."""
        import inspect

        src = inspect.getsource(job_queue.recover_stale_jobs)
        assert "RUNNING" in src and "PENDING" in src

    def test_enqueue_does_not_commit(self):
        """Enqueue must join the caller's transaction: a rolled-back request must
        not leave a job pointing at a row that never existed."""
        import inspect

        src = inspect.getsource(job_queue.enqueue)
        assert "db.flush()" in src
        assert "commit()" not in src


class TestLosableWorkIsQueued:
    """The point of the exercise: this work must no longer be in-process."""

    @staticmethod
    def _kt_router_files():
        """routers/kt.py aggregator + the split files under modules/kt/routers/."""
        return [ROUTERS / "kt.py"] + sorted(
            (ROUTERS.parent / "modules" / "kt" / "routers").glob("*.py")
        )

    def test_kt_router_has_no_in_process_background_tasks(self):
        offenders = []
        for f in self._kt_router_files():
            tree = ast.parse(f.read_text())
            offenders += [
                f"{f.name}:{node.lineno}"
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_task"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "background_tasks"
            ]
        assert not offenders, (
            f"KT routers still schedule in-process work at {offenders}; "
            "that work is lost on restart — enqueue a durable job instead"
        )

    def test_ingestion_is_enqueued_durably(self):
        src = "\n".join(f.read_text() for f in self._kt_router_files())
        assert "JOB_KT_INGEST" in src
        assert "enqueue_job(" in src
