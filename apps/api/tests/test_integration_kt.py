"""Live end-to-end KT test: ingest a throwaway doc, retrieve, chat (both paths), clean up.

Marked `live` — skipped automatically when Gemini/Neo4j are unavailable. Uses an
existing company/project (real FKs) and a TEST_ document that is deleted afterwards,
so no real KT data is touched.
"""
import json

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.live, pytest.mark.asyncio]

TEST_DOC_ID = "TEST_PYTEST_KT_DOC"
BODY = (
    "### 2024-04-15\n"
    "We migrated billing to Stripe. Payment retries are made safe with idempotency "
    "keys and exponential backoff, capped at 5 attempts.\n"
    "### 2024-05-20\n"
    "We added webhook signature verification and a dead-letter queue."
)


async def _first_company_and_project(engine):
    async with engine.connect() as c:
        comp = (await c.execute(text("SELECT id, organization_id FROM kt_companies LIMIT 1"))).first()
        assert comp is not None, "no KT company to attach test doc to"
        proj = (
            await c.execute(
                text("SELECT id FROM kt_projects WHERE company_id=:c LIMIT 1"),
                {"c": comp.id},
            )
        ).first()
        assert proj is not None, "no KT project under company"
    return comp.id, comp.organization_id, proj.id


async def _cleanup(engine, neo4j):
    await neo4j.connect()
    async with neo4j.driver.session() as s:
        await s.run("MATCH (ep:Episode {doc_id:$d}) DETACH DELETE ep", d=TEST_DOC_ID)
        await s.run("MATCH (d:Document {id:$d}) DETACH DELETE d", d=TEST_DOC_ID)
    async with engine.begin() as c:
        await c.execute(text("DELETE FROM kt_documents WHERE id=:d"), {"d": TEST_DOC_ID})


async def test_kt_full_loop(live_ready):
    from database import async_engine, db_session_factory
    from models.kt_model import DocStatusEnum, KTDocument
    from services.kt_engine import neo4j
    from services.kt_langraph import stream_kt_chatbot_response
    from services.kt_workflows import KTIngestionService, run_rag_query

    cid, org_id, pid = await _first_company_and_project(async_engine)
    await _cleanup(async_engine, neo4j)  # ensure clean slate

    try:
        # 1. Author creates + it is approved (throwaway).
        async with db_session_factory() as db:
            db.add(
                KTDocument(
                    id=TEST_DOC_ID, project_id=pid, company_id=cid, organization_id=org_id,
                    title="PyTest Billing Runbook", doc_type="runbook",
                    knowledge_domain="backend", body_markdown=BODY,
                    status=DocStatusEnum.APPROVED,
                )
            )
            await db.commit()

        # 2. Mentor "feed" → real ingestion pipeline.
        await KTIngestionService.run_pipeline(TEST_DOC_ID, db_session_factory)

        # 3. Episodes were written to the graph.
        await neo4j.connect()
        async with neo4j.driver.session() as s:
            n = (await (await s.run(
                "MATCH (ep:Episode {doc_id:$d}) RETURN count(ep) AS c", d=TEST_DOC_ID
            )).data())[0]["c"]
        assert n >= 1, "ingestion wrote no episodes"

        # 4. Doc marked INGESTED with chunk_count.
        async with async_engine.connect() as c:
            row = (await c.execute(
                text("SELECT status, ingested_at, chunk_count FROM kt_documents WHERE id=:d"),
                {"d": TEST_DOC_ID},
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
        await _cleanup(async_engine, neo4j)
        await neo4j.close()
        await async_engine.dispose()
