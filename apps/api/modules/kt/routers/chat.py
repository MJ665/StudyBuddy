"""
Chat sessions and messaging
"""

from fastapi import APIRouter
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from modules.kt.routers._shared import *  # noqa: F401, F403

router = APIRouter()

@router.post("/chat/session")
async def start_chat_session(
    body: KTChatStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(verify_token_optional),
    x_kt_key: Optional[str] = Header(None),
):
    """
    Start a chat session.
    - JWT users: provide project_ids + company_id
    - External (key) users: key is resolved via x_kt_key header
    company_id and project_ids are LOCKED at session creation.
    """
    org_id = int(current_user["organization_id"]) if current_user else None
    uid = int(current_user["sub"]) if current_user else None

    resolved_company_id = None
    resolved_project_ids = []
    key_id = None

    # SECURITY: the retrieval scope is derived from the caller's GRANTS, never from
    # the request body. Shared with /explorer/graph and /explorer/timeline so the
    # rule cannot drift between the three retrieval entry points.
    (
        resolved_company_id,
        resolved_project_ids,
        key_id,
        scope_org_id,
    ) = await _resolve_retrieval_scope(
        db,
        current_user,
        x_kt_key,
        requested_project_ids=body.project_ids,
        requested_company_id=body.company_id,
    )
    org_id = org_id or scope_org_id

    session = KTChatSession(
        access_key_id=key_id,
        user_id=uid,
        company_id=resolved_company_id,
        organization_id=org_id,
        resolved_company_id=resolved_company_id,
        resolved_project_ids=resolved_project_ids,
    )
    db.add(session)
    assert org_id is not None
    await _audit(
        db,
        org_id,
        AuditActionEnum.CHAT_SESSION_STARTED,
        company_id=str(resolved_company_id) if resolved_company_id else None,
        user_id=uid,
        resource_type="chat_session",
        request=request,
    )
    await db.commit()
    await db.refresh(session)

    return {
        "session_id": session.id,
        "company_id": resolved_company_id,
        "project_ids": resolved_project_ids,
    }



@router.post("/chat/message")
async def send_message(
    body: KTChatMessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(verify_token_optional),
    x_kt_key: Optional[str] = Header(None),
):
    """
    Send a message. scope (company_id + project_ids) is read from the
    LOCKED session — NEVER from the request body.
    """
    session = await db.get(KTChatSession, body.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    # Validate session ownership
    if x_kt_key:
        if not verify_access_key_signature(x_kt_key):
            raise HTTPException(403, "Invalid key signature")
    elif current_user:
        if session.user_id and session.user_id != int(current_user["sub"]):
            raise HTTPException(403, "Session belongs to another user")
    else:
        raise HTTPException(401, "Authentication required")

    # Save user message
    user_msg = KTChatMessage(session_id=session.id, role="user", content=body.message)
    db.add(user_msg)
    session.message_count = (session.message_count or 0) + 1
    session.last_message_at = datetime.now(timezone.utc)
    # Auto-title the thread from the first message (ChatGPT-style).
    if not session.title:
        session.title = (body.message or "").strip()[:60] or "New chat"
    await db.commit()

    # Get conversation history
    hist_result = await db.execute(
        select(KTChatMessage)
        .where(KTChatMessage.session_id == session.id)
        .order_by(KTChatMessage.created_at.desc())
        .limit(10)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in reversed(hist_result.scalars().all())
    ]

    # ── RAG — HARD SCOPED ────────────────────────────────────────────────
    # Sensitivity is resolved per-request (not cached on the session) so that
    # revoking someone's project lead role takes effect on their very next message.
    rag = await run_rag_query(
        query=body.message,
        company_id=session.resolved_company_id,  # from LOCKED session
        project_ids=_normalize_grant_list(session.resolved_project_ids),  # LOCKED
        history=history,
        db=db,
        allowed_sensitivities=await _sensitivities_for_session(session, db),
    )

    # Log unanswered queries
    if not rag.get("was_answered"):
        normalized = body.message.lower().strip()
        existing = await db.execute(
            select(KTUnansweredQuery).where(
                KTUnansweredQuery.company_id == session.resolved_company_id,
                KTUnansweredQuery.query_normalized == normalized,
                KTUnansweredQuery.resolved.is_(False),
            )
        )
        uq = existing.scalar_one_or_none()
        if uq:
            uq.occurrence_count = (uq.occurrence_count or 0) + 1
            uq.last_asked_at = datetime.now(timezone.utc)
            uq.priority = uq.occurrence_count
        else:
            db.add(
                KTUnansweredQuery(
                    company_id=session.resolved_company_id,
                    organization_id=session.organization_id or 0,
                    project_ids=session.resolved_project_ids,
                    query_text=body.message,
                    query_normalized=normalized,
                )
            )

    # Save assistant message
    asst_msg = KTChatMessage(
        session_id=session.id,
        role="assistant",
        content=rag["answer"],
        retrieved_doc_ids=[s["doc_id"] for s in rag.get("sources", [])],
        confidence_score=rag.get("confidence"),
        was_answered=rag.get("was_answered"),
        latency_ms=rag.get("latency_ms"),
        sources_metadata=rag.get("sources", []),
        graph_hops=rag.get("graph_hops"),
    )
    db.add(asst_msg)
    session.message_count = (session.message_count or 0) + 1
    await _audit(
        db,
        session.organization_id or 0,
        AuditActionEnum.CHAT_MESSAGE_SENT,
        company_id=session.resolved_company_id,
        user_id=session.user_id,
        resource_type="chat_message",
        resource_id=asst_msg.id,
    )
    await db.commit()
    await db.refresh(asst_msg)

    return {
        "id": asst_msg.id,
        "content": rag["answer"],
        "sources": rag.get("sources", []),
        "confidence_score": rag.get("confidence"),
        "was_answered": rag.get("was_answered"),
        "latency_ms": rag.get("latency_ms"),
    }



@router.post("/chat/message/stream")
async def stream_message(
    body: KTChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(verify_token),
    x_kt_key: Optional[str] = Header(None),
):
    """SSE streaming version of send_message."""
    session = await db.get(KTChatSession, body.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    # is_injection, is_sensitive etc are now imported at top level

    if is_injection(body.message):

        async def _blocked():
            yield 'data: {"token": "⚠️ Request blocked.", "done": true}\n\n'

        return StreamingResponse(_blocked(), media_type="text/event-stream")

    # Use LangGraph streaming wrapper which handles retrieve→rerank→generate
    user_id = int(current_user["sub"]) if current_user else 0

    async def event_stream():
        # stream_kt_chatbot_response yields JSON lines (one per \n)
        final_payload = None
        async for line in stream_kt_chatbot_response(
            body.message, session.resolved_company_id, session.resolved_project_ids, user_id, session.id
        ):
            # Parse the JSON line
            try:
                payload = json.loads(line.strip())
            except Exception:
                payload = {"token": line.strip(), "done": False}

            # Forward tokens as SSE
            yield f"data: {json.dumps(payload)}\n\n"

            # Capture final payload when done
            if isinstance(payload, dict) and payload.get("done"):
                final_payload = payload

        # After stream completes, persist messages including the full assistant response and citations
        from database import db_session_factory

        async with db_session_factory() as save_db:
            # Save the user message
            save_db.add(KTChatMessage(session_id=session.id, role="user", content=body.message))

            # Save assistant message using full_response if provided, else placeholder
            assistant_content = "[STREAMED RESPONSE]"
            sources_meta = []
            if final_payload:
                assistant_content = final_payload.get("full_response") or assistant_content
                sources_meta = final_payload.get("sources", []) or []

            save_db.add(
                KTChatMessage(
                    session_id=session.id,
                    role="assistant",
                    content=sanitize_output(assistant_content),
                    was_answered=bool(sources_meta),
                    sources_metadata=sources_meta,
                    confidence_score=(final_payload or {}).get("confidence_score"),
                )
            )

            await save_db.execute(
                update(KTChatSession)
                .where(KTChatSession.id == session.id)
                .values(
                    message_count=KTChatSession.message_count + 2,
                    last_message_at=datetime.now(timezone.utc),
                    # Auto-title from the first message (keep any existing title).
                    title=func.coalesce(
                        KTChatSession.title, (body.message or "").strip()[:60] or "New chat"
                    ),
                )
            )
            await save_db.commit()

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})



@router.get("/chat/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(verify_token),
    x_kt_key: Optional[str] = Header(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    session = await db.get(KTChatSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    result = await db.execute(
        select(KTChatMessage)
        .where(KTChatMessage.session_id == session_id)
        .order_by(KTChatMessage.created_at.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    msgs = result.scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "sources": m.sources_metadata,
            "confidence_score": m.confidence_score,
            "feedback": m.feedback,
            "created_at": m.created_at,
        }
        for m in msgs
    ]


@router.get("/chat/sessions")
async def list_chat_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_token),
    company_id: Optional[str] = Query(None),
):
    """The caller's persisted chat threads (ChatGPT-style history), newest first.
    Optionally filtered to one company. Ownership: the caller's own sessions."""
    uid = int(current_user["sub"])
    q = select(KTChatSession).where(KTChatSession.user_id == uid)
    if company_id:
        q = q.where(KTChatSession.resolved_company_id == company_id)
    q = q.order_by(
        KTChatSession.last_message_at.desc().nullslast(),
        KTChatSession.created_at.desc(),
    ).limit(200)
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "session_id": s.id,
            "title": s.title or "New chat",
            "company_id": s.resolved_company_id,
            "project_ids": s.resolved_project_ids or [],
            "message_count": s.message_count or 0,
            "last_message_at": s.last_message_at,
            "created_at": s.created_at,
        }
        for s in rows
    ]


@router.patch("/chat/sessions/{session_id}")
async def rename_chat_session(
    session_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Rename a chat thread."""
    uid = int(current_user["sub"])
    session = await db.get(KTChatSession, session_id)
    if not session or session.user_id != uid:
        raise HTTPException(404, "Session not found")
    title = (body.get("title") or "").strip()[:200]
    if not title:
        raise HTTPException(400, "Title required")
    session.title = title
    await db.commit()
    return {"session_id": session_id, "title": title}


@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Delete a chat thread and its messages."""
    uid = int(current_user["sub"])
    session = await db.get(KTChatSession, session_id)
    if not session or session.user_id != uid:
        raise HTTPException(404, "Session not found")
    await db.execute(
        delete(KTChatMessage).where(KTChatMessage.session_id == session_id)
    )
    await db.delete(session)
    await db.commit()
    return {"session_id": session_id, "deleted": True}


# ════════════════════════════════════════════════════════════════════════════
# INSIGHTS & ANALYTICS (RBAC-scoped)
# ════════════════════════════════════════════════════════════════════════════



