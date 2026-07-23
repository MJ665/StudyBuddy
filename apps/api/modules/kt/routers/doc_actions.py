"""KT document lifecycle actions (deprecate/delete/endorse/ai-suggest) — split verbatim from doc_lifecycle.py to stay under the 800-line cap."""
from fastapi import APIRouter

from modules.kt.routers.documents_shared import *  # noqa: F401,F403

router = APIRouter()

@router.post("/documents/{doc_id}/deprecate")
async def deprecate_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    doc = await _get_doc_or_404(doc_id, org_id, db)
    doc.status = DocStatusEnum.DEPRECATED
    doc.deprecated_at = datetime.now(timezone.utc)
    # Remove from the vector store (retrieval also filters status==INGESTED).
    from modules.kt.services.ingestion_service import purge_chunks

    await purge_chunks(db, doc_id)
    await _audit(
        db,
        org_id,
        AuditActionEnum.DOC_DEPRECATED,
        user_id=uid,
        resource_type="document",
        resource_id=doc_id,
    )
    await db.commit()
    return {"message": "Deprecated and removed from knowledge graph"}

@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    _db_user_res = await db.execute(
        select(User.role).where(User.id == int(current_user["sub"]))
    )
    role = _db_user_res.scalar_one_or_none() or current_user.get("role", "Member")
    doc = await _get_doc_or_404(doc_id, org_id, db)

    if doc.author_id != uid and role not in [
        "Mentor",
        "GroupAdmin",
        "LDAdmin",
        "Owner",
    ]:
        raise HTTPException(403, "Not authorized to delete")

    from models.assignment import Assignment
    from models.learning_path import UserLearningPath

    # Referential Integrity Check Guardrail
    is_in_assignment = await db.execute(
        select(Assignment).where(Assignment.instructions.like(f"%{doc_id}%"))
    )
    if is_in_assignment.first():
        raise HTTPException(
            status_code=400,
            detail="Document is actively referenced in an Assignment and cannot be deleted.",
        )

    is_in_path = await db.execute(
        select(UserLearningPath).where(
            UserLearningPath.roadmap_json.like(f"%{doc_id}%")
        )
    )
    if is_in_path.first():
        raise HTTPException(
            status_code=400,
            detail="Document is actively referenced in a Learning Path and cannot be deleted.",
        )

    # Chunks cascade with the document row (FK ondelete=CASCADE); explicit
    # purge keeps behavior obvious and covers any orphaned rows.
    from modules.kt.services.ingestion_service import purge_chunks

    await purge_chunks(db, doc_id)

    await db.execute(
        update(KTProject)
        .where(KTProject.id == doc.project_id)
        .values(doc_count=KTProject.doc_count - 1)
    )
    await _audit(
        db,
        org_id,
        AuditActionEnum.DOC_DELETED,
        user_id=uid,
        resource_type="document",
        resource_id=doc_id,
    )
    await db.delete(doc)
    await db.commit()
    return {"message": "Document deleted"}

@router.post("/documents/{doc_id}/endorse")
async def endorse_document(
    doc_id: str,
    comment: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    doc = await _get_doc_or_404(doc_id, org_id, db)
    if doc.status not in [DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]:
        raise HTTPException(400, "Can only endorse approved documents")
    # Check if already endorsed
    existing = await db.execute(
        select(KTEndorsement).where(
            KTEndorsement.document_id == doc_id, KTEndorsement.user_id == uid
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Already endorsed this document")

    try:
        e = KTEndorsement(document_id=doc_id, user_id=uid, comment=comment)
        db.add(e)
        doc.endorsement_count = (doc.endorsement_count or 0) + 1
        await db.commit()
    except Exception as err:
        await db.rollback()
        from sqlalchemy.exc import IntegrityError

        if isinstance(err, IntegrityError) or "unique" in str(err).lower():
            raise HTTPException(400, "Already endorsed this document")
        raise
    return {"message": "Endorsed"}

@router.post("/documents/{doc_id}/ai-suggest")
async def ai_suggest_improvements(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    doc = await _get_doc_or_404(doc_id, org_id, db)

    date_log_pattern = r"###\s+\d{4}-\d{2}-\d{2}"
    has_date_log = bool(re.search(date_log_pattern, doc.body_markdown))
    prompt = f"""Analyze this KT document and give specific improvement suggestions.

Title: {doc.title}
Type: {doc.doc_type}
Quality Score: {doc.quality_score}/100
Header Completeness: {doc.header_completeness}%
Word Count: {doc.word_count}
Has date-log sections: {has_date_log}

Return JSON:
{{
  "missing_fields": ["empty header fields"],
  "content_gaps": ["missing sections"],
  "temporal_log_suggestion": "specific date-log entries to add",
  "quality_tips": ["concrete tips"],
  "estimated_new_score": 85
}}
"""
    import hashlib
    import json

    # STRAT-AI-CACHE: Hash doc body to avoid redundant LLM calls for same exact doc state
    cache_hash = hashlib.sha256(f"{doc_id}|{doc.body_markdown}".encode()).hexdigest()
    redis_key = f"ai:suggest_kt:{cache_hash}"
    try:
        cached_str = await redis_client.get(redis_key)
        if cached_str:
            return json.loads(cached_str)
    except Exception:
        pass

    result = await gemini.generate_json(prompt)

    try:
        await redis_client.set(redis_key, json.dumps(result), ex=86400)  # 24h
    except Exception:
        pass

    return result
