"""
Document feed and ingestion status
"""

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from modules.kt.routers._shared import *  # noqa: F401, F403

router = APIRouter()

@router.post("/chat/feedback")
async def chat_feedback(
    body: KTChatFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    msg = await db.get(KTChatMessage, body.message_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    msg.feedback = body.feedback
    msg.feedback_note = body.note
    uid = int(current_user["sub"])
    await _audit(
        db,
        int(current_user["organization_id"]),
        AuditActionEnum.CHAT_FEEDBACK_GIVEN,
        user_id=uid,
        resource_id=body.message_id,
    )
    await db.commit()
    return {"message": "Feedback recorded"}



