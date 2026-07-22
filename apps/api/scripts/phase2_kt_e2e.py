"""Phase 2 gate: live KT E2E on pgvector (no Neo4j anywhere).

Creates an isolated company/project/document, runs the REAL ingestion
pipeline (Gemini embeddings → kt_document_chunks), then asks the REAL
chatbot a question and asserts a grounded, cited answer. Cleans up after
itself. Requires GEMINI_API_KEY in .env.

Run:  cd apps/api && ENVIRONMENT=development DEBUG=True .venv/bin/python scripts/phase2_kt_e2e.py
"""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select  # noqa: E402

import models  # noqa: F401, E402
from database import AsyncSessionLocal  # noqa: E402
from models.kt_model import (  # noqa: E402
    DocStatusEnum,
    KTCompany,
    KTDocument,
    KTProject,
)
from modules.kt.models import KTDocumentChunk  # noqa: E402
from modules.kt.services import ingestion_service  # noqa: E402

MARK = "PHASE2-E2E"

DOC_BODY = """\
## Payment Gateway Integration — Handoff Notes

### 2024-01-15
We chose Razorpay over Stripe because settlement in INR avoided a 2.1% FX fee
and their webhook retry policy matched our idempotent consumer design. The
integration lives in `payments/razorpay_client.py`.

### 2024-03-02
Refunds MUST go through the `RefundOrchestrator` — calling the Razorpay refund
API directly bypasses ledger reconciliation and double-refunds were observed
in UAT. The orchestrator holds a Postgres advisory lock per order id.

### Q2 2024
Migrated webhook verification from header signature v1 to v2 (HMAC-SHA256).
The shared secret rotates quarterly via Vault path `secret/payments/rzp`.
"""

QUESTION = "Why did we pick Razorpay, and what is the rule for issuing refunds?"


async def main() -> int:
    async with AsyncSessionLocal() as db:
        # ── fixtures ────────────────────────────────────────────────────────
        company = KTCompany(id=str(uuid.uuid4()), name=f"{MARK} Co", organization_id=999999)
        project = KTProject(
            id=str(uuid.uuid4()), company_id=company.id, organization_id=999999,
            name=f"{MARK} Project",
        )
        doc = KTDocument(
            id=str(uuid.uuid4()), project_id=project.id, company_id=company.id,
            organization_id=999999, title="Payment Gateway Handoff",
            doc_type="TECHNICAL_GUIDE", body_markdown=DOC_BODY,
            status=DocStatusEnum.APPROVED, sensitivity="low",
        )
        db.add_all([company, project, doc])
        await db.commit()
        doc_id, project_id, company_id = doc.id, project.id, company.id

    ok = True
    try:
        # ── 1. ingestion ────────────────────────────────────────────────────
        async with AsyncSessionLocal() as db:
            await ingestion_service.run_pipeline(doc_id, AsyncSessionLocal)

        async with AsyncSessionLocal() as db:
            chunks = (
                (await db.execute(
                    select(KTDocumentChunk).where(KTDocumentChunk.document_id == doc_id)
                )).scalars().all()
            )
            fresh = await db.get(KTDocument, doc_id)
            assert fresh is not None
            print(f"[ingest] chunks={len(chunks)} status={fresh.status} "
                  f"ingestion_status={fresh.ingestion_status} chunk_count={fresh.chunk_count}")
            assert len(chunks) >= 3, "expected >=3 temporal chunks"
            assert all(len(c.embedding) == 3072 for c in chunks), "bad embedding dims"
            assert str(fresh.status) in ("DocStatusEnum.INGESTED", "DocStatusEnum.ingested") or \
                fresh.status == DocStatusEnum.INGESTED
            times = sorted({c.reference_time for c in chunks if c.reference_time})
            print(f"[ingest] reference_times={times}")

        # ── 2. retrieval + chat (non-streaming) ────────────────────────────
        from services.kt_langraph import invoke_kt_chatbot

        state = await invoke_kt_chatbot(
            query=QUESTION, company_id=company_id, project_ids=[project_id],
            user_id=0, session_id="e2e",
        )
        answer = state.get("full_response", "")
        sources = state.get("cited_sources", [])
        print(f"[chat] answer ({len(answer)} chars): {answer[:400]}")
        print(f"[chat] cited_sources={[(s['doc_title']) for s in sources]}")
        low = answer.lower()
        assert "razorpay" in low, "answer not grounded (no Razorpay mention)"
        assert "refundorchestrator" in low.replace(" ", "") or "orchestrator" in low, \
            "answer missed the refund rule"
        assert sources, "no citations extracted"

        # ── 3. scope fail-closed check ──────────────────────────────────────
        from modules.kt.services.retrieval import vector_search

        none = await vector_search([0.0] * 3072, company_id, [])
        assert none == [], "empty project grant must retrieve nothing"
        wrong = await vector_search(
            [0.0] * 3072, "wrong-company", [project_id]
        )
        assert wrong == [], "wrong company must retrieve nothing"
        print("[scope] fail-closed checks passed")

        print("\nPHASE 2 GATE: PASS — KT loop verified live on pgvector")
    except AssertionError as e:
        ok = False
        print(f"\nPHASE 2 GATE: FAIL — {e}")
    finally:
        # ── cleanup ─────────────────────────────────────────────────────────
        async with AsyncSessionLocal() as db:
            await db.execute(delete(KTDocumentChunk).where(KTDocumentChunk.document_id == doc_id))
            await db.execute(delete(KTDocument).where(KTDocument.id == doc_id))
            await db.execute(delete(KTProject).where(KTProject.id == project_id))
            await db.execute(delete(KTCompany).where(KTCompany.id == company_id))
            await db.commit()
            print("[cleanup] fixtures removed")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
