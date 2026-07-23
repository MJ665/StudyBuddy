"""doc_assets endpoints (moved verbatim from modules/kt/routers/documents.py)."""
from fastapi import APIRouter

from modules.kt.routers.documents_shared import *  # noqa: F401,F403

router = APIRouter()

@router.get("/documents/{doc_id}/versions")
async def document_versions(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    await _get_doc_or_404(doc_id, org_id, db)
    result = await db.execute(
        select(KTDocumentVersion)
        .where(KTDocumentVersion.document_id == doc_id)
        .order_by(KTDocumentVersion.version.desc())
    )
    return [
        {
            "id": v.id,
            "version": v.version,
            "change_summary": v.change_summary,
            # FE field name predates the model rebuild; snapshots record the
            # writing author in `author_id`.
            "changed_by_id": v.author_id,
            "created_at": v.created_at,
        }
        for v in result.scalars().all()
    ]

@router.post("/documents/{doc_id}/attachments/presign")
async def get_attachment_upload_url(
    doc_id: str,
    body: KTAttachmentPresignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    doc = await _get_doc_or_404(doc_id, org_id, db)

    # Only authors or mentors can add attachments
    uid = int(current_user["sub"])
    if (
        doc.author_id != uid
        and doc.mentor_id != uid
        and current_user.get("role") not in ["GroupAdmin", "LDAdmin"]
    ):
        raise HTTPException(403, "Not authorized to add attachments to this document")

    return s3_service.generate_kt_attachment_upload_url(
        doc_id, body.filename, body.content_type
    )

@router.post("/documents/{doc_id}/attachments", response_model=KTAttachmentOut)
async def register_attachment(
    doc_id: str,
    body: KTAttachmentRegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    await _get_doc_or_404(doc_id, org_id, db)

    uid = int(current_user["sub"])

    # ── GUARDRAIL: S3 EXISTENCE CHECK ──
    if not s3_service.object_exists(body.s3_key):
        raise HTTPException(400, "Attachment payload invalid: S3 object not found.")

    attachment = KTDocumentAttachment(
        document_id=doc_id,
        filename=body.filename,
        s3_key=body.s3_key,
        file_type=body.file_type,
        file_size=body.file_size,
        uploaded_by_id=uid,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment

@router.get("/documents/{doc_id}/attachments", response_model=List[KTAttachmentOut])
async def list_attachments(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(verify_token_optional),
    x_kt_key: Optional[str] = Header(None),
):
    if not current_user and not x_kt_key:
        raise HTTPException(401, "Authentication required (JWT or X-KT-Key)")

    if x_kt_key:
        key_record = await _resolve_key(x_kt_key, db)
        doc = await db.get(KTDocument, doc_id)
        if (
            not doc
            or doc.organization_id != key_record.organization_id
            or doc.project_id not in _normalize_grant_list(key_record.project_ids)
        ):
            raise HTTPException(404, "Document not found or access denied")
        if doc.status not in [DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]:
            raise HTTPException(403, "Access denied: Document not public")
    else:
        assert current_user is not None
        org_id = int(current_user["organization_id"])
        await _get_doc_or_404(doc_id, org_id, db)

    result = await db.execute(
        select(KTDocumentAttachment)
        .where(KTDocumentAttachment.document_id == doc_id)
        .order_by(KTDocumentAttachment.created_at.desc())
    )
    attachments = result.scalars().all()

    for att in attachments:
        att.download_url = s3_service.generate_presigned_get_url(
            att.s3_key, filename=att.filename
        )

    return attachments

@router.get("/documents/{doc_id}/versions/{version}")
async def get_document_version(
    doc_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    await _get_doc_or_404(doc_id, org_id, db)
    result = await db.execute(
        select(KTDocumentVersion).where(
            KTDocumentVersion.document_id == doc_id,
            KTDocumentVersion.version == version,
        )
    )
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(404, "Version not found")
    return {
        "version": v.version,
        "title": v.title,
        "body_markdown": v.body_markdown,
        "change_summary": v.change_summary,
        "created_at": v.created_at,
    }

@router.post("/documents/{doc_id}/versions/{version}/restore")
async def restore_document_version(
    doc_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """Restore a document's title/body from an earlier snapshot.

    The restore itself is recorded as a NEW version (no history rewriting).
    Only someone who can edit the document may restore it. A restored document
    goes back through review before re-indexing (status → DRAFT) so stale or
    superseded knowledge cannot silently re-enter the vector store.
    """
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    doc = await _get_doc_or_404(doc_id, org_id, db)
    if not await _can_edit_doc(doc, current_user):
        raise HTTPException(403, "Not authorized to restore this document")

    result = await db.execute(
        select(KTDocumentVersion).where(
            KTDocumentVersion.document_id == doc_id,
            KTDocumentVersion.version == version,
        )
    )
    snap = result.scalar_one_or_none()
    if not snap:
        raise HTTPException(404, "Version not found")

    doc.title = snap.title or doc.title
    doc.body_markdown = snap.body_markdown or ""
    doc.version = (doc.version or 1) + 1
    doc.status = DocStatusEnum.DRAFT
    db.add(
        KTDocumentVersion(
            document_id=doc.id,
            version=doc.version,
            title=doc.title,
            body_markdown=doc.body_markdown,
            author_id=uid,
            change_summary=f"Restored from version {version}",
        )
    )
    await _audit(
        db,
        org_id,
        AuditActionEnum.DOC_UPDATED,
        user_id=uid,
        resource_type="document",
        resource_id=doc_id,
        meta={"restored_from_version": version},
    )
    await db.commit()
    return {"message": f"Restored from version {version}", "version": doc.version}
