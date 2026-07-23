"""Live end-to-end KT test on the pgvector pipeline (Phase 6 rewrite).

ingest a throwaway doc → chunks in kt_document_chunks → grounded chat (both
paths) → clean up. Marked `live` — needs a real GEMINI_API_KEY. Creates its
own throwaway company/project so it runs on any database, including fresh.
"""
import json
import uuid

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.live, pytest.mark.asyncio]

BODY = (
    "### 2024-04-15\n"
    "We migrated billing to Stripe. Payment retries are made safe with idempotency "
    "keys and exponential backoff, capped at 5 attempts.\n"
    "### 2024-05-20\n"
    "We added webhook signature verification and a dead-letter queue."
)


async def test_kt_full_loop(live_ready):
    from database import async_engine, db_session_factory
    from models.kt_model import DocStatusEnum, KTCompany, KTDocument, KTProject
    from modules.kt.services import ingestion_service
    from services.kt_langraph import stream_kt_chatbot_response
    from services.kt_workflows import run_rag_query

    doc_id = str(uuid.uuid4())
    cid = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    org_id = 999998

    try:
        # 1. Author creates + it is approved (throwaway fixtures).
        async with db_session_factory() as db:
            db.add(KTCompany(id=cid, name="pytest-live-co", organization_id=org_id))
            db.add(KTProject(id=pid, company_id=cid, organization_id=org_id,
                             name="pytest-live-project"))
            db.add(
                KTDocument(
                    id=doc_id, project_id=pid, company_id=cid, organization_id=org_id,
                    title="PyTest Billing Runbook", doc_type="runbook",
                    knowledge_domain="backend", body_markdown=BODY,
                    status=DocStatusEnum.APPROVED, sensitivity="low",
                )
            )
            await db.commit()

        # 2. Mentor "feed" → real pgvector ingestion pipeline.
        await ingestion_service.run_pipeline(doc_id, db_session_factory)

        # 3. Chunks with embeddings were written.
        async with async_engine.connect() as c:
            n = (await c.execute(
                text("SELECT count(*) FROM kt_document_chunks WHERE document_id=:d"),
                {"d": doc_id},
            )).scalar_one()
        assert n >= 2, "ingestion wrote too few chunks"

        # 4. Doc marked INGESTED with chunk_count.
        async with async_engine.connect() as c:
            row = (await c.execute(
                text("SELECT status, ingested_at, chunk_count FROM kt_documents WHERE id=:d"),
                {"d": doc_id},
            )).first()
        assert row.status == "INGESTED"
        assert row.ingested_at is not None
        assert row.chunk_count == n

        q = "How did we make payment retries safe?"

        # 5. Non-streaming chat returns a grounded answer + sources.
        async with db_session_factory() as db:
            rag = await run_rag_query(q, cid, [pid], [], db)
        assert rag["answer"] and "don't have enough" not in rag["answer"].lower()
        assert len(rag["sources"]) >= 1
        assert rag["was_answered"] is True

        # 6. Streaming chat yields tokens then a terminal frame with a citation.
        tokens, final = [], None
        async for line in stream_kt_chatbot_response(q, cid, [pid], 0, "pytest-sess"):
            obj = json.loads(line)
            if obj.get("done"):
                final = obj
            elif obj.get("token"):
                tokens.append(obj["token"])
        answer = "".join(tokens)
        assert final is not None
        assert answer and "Error:" not in answer
        assert "[citation:" in answer or len(final.get("sources", [])) >= 1
    finally:
        async with async_engine.begin() as c:
            await c.execute(text("DELETE FROM kt_document_chunks WHERE document_id=:d"), {"d": doc_id})
            await c.execute(text("DELETE FROM kt_documents WHERE id=:d"), {"d": doc_id})
            await c.execute(text("DELETE FROM kt_projects WHERE id=:p"), {"p": pid})
            await c.execute(text("DELETE FROM kt_companies WHERE id=:c"), {"c": cid})
        # NOTE: never dispose() the shared async_engine here — it is
        # process-wide, and killing its pool poisons every test that runs
        # after this one in the same session (the old flakiness).
