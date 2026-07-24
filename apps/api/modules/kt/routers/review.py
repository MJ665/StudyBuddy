"""
Document review workflow
"""

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from modules.kt.routers._shared import *  # noqa: F401, F403

router = APIRouter()

@router.post("/documents/{doc_id}/review")
async def review_document(
    doc_id: str,
    body: ReviewRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    doc = await _get_doc_or_404(doc_id, org_id, db)

    if doc.author_id == uid:
        raise HTTPException(403, "Self-approval is not permitted.")

    if doc.status not in [DocStatusEnum.SUBMITTED, DocStatusEnum.UNDER_REVIEW]:
        raise HTTPException(400, "Document not in reviewable state")

    review = KTDocumentReview(
        document_id=doc_id,
        reviewer_id=uid,
        action=body.action,
        comment=body.comment,
        inline_comments=body.inline_comments or [],
    )
    db.add(review)

    author = await db.get(User, doc.author_id) if doc.author_id else None

    if body.action == ReviewActionEnum.APPROVED:
        doc.status = DocStatusEnum.APPROVED
        doc.approved_at = datetime.now(timezone.utc)
        doc.approved_by_id = uid
        await _audit(
            db,
            org_id,
            AuditActionEnum.DOC_APPROVED,
            user_id=uid,
            resource_type="document",
            resource_id=doc_id,
        )
        # Approval-gated ingestion: approving AUTO-ENQUEUES ingestion, so the
        # document becomes queryable knowledge without a separate manual "feed".
        # (Only APPROVED docs reach INGESTED; retrieval filters on INGESTED.)
        job = KTIngestionJob(
            document_id=doc_id,
            triggered_by_id=uid,
            is_re_ingestion=False,
            status=IngestionStatusEnum.PENDING,
        )
        db.add(job)
        await enqueue_job(db, JOB_KT_INGEST, {"document_id": str(doc.id)})

        if author:
            await enqueue_job(
                db,
                JOB_EMAIL,
                {"method": "send_doc_approved", "args": [author.email, author.full_name, doc.title]},
            )
            await _notify(
                db,
                author.id,
                org_id,
                doc.company_id,
                "doc_approved",
                "Document approved! 🎉",
                f'"{doc.title}" was approved and is being ingested into the knowledge base.',
                "document",
                doc_id,
            )

    elif body.action == ReviewActionEnum.REJECTED:
        doc.status = DocStatusEnum.REJECTED
        doc.rejection_reason = body.comment
        await _audit(
            db,
            org_id,
            AuditActionEnum.DOC_REJECTED,
            user_id=uid,
            resource_type="document",
            resource_id=doc_id,
        )
        if author:
            await enqueue_job(
                db,
                JOB_EMAIL,
                {"method": "send_doc_rejected", "args": [author.email, author.full_name, doc.title, body.comment or ""]},
            )
            await _notify(
                db,
                author.id,
                org_id,
                doc.company_id,
                "doc_rejected",
                "Changes requested",
                f'"{doc.title}" needs updates: {body.comment or ""}',
                "document",
                doc_id,
            )
    else:
        doc.status = DocStatusEnum.UNDER_REVIEW

    await db.commit()
    return {"message": f"Document {body.action.value}", "status": doc.status}



