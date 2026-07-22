"""notifications endpoints (moved verbatim from routers/auth.py)."""
from fastapi import APIRouter

from modules.identity.routers.auth_shared import *  # noqa: F401,F403

router = APIRouter()

@router.get("/notifications")
def get_notifications(
    limit: int = 20,
    skip: int = 0,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Fetch notifications for the current user, newest first with pagination."""
    user_id = int(current_user["sub"])
    notifications = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id)
        .order_by(models.Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "notification_type": n.notification_type,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "link_id": n.link_id,
            "link_type": n.link_type,
        }
        for n in notifications
    ]

@router.get("/notifications/stream")
async def stream_notifications(
    token: str = Query(..., description="JWT token for SSE authentication"),
    db: AsyncSession = Depends(get_async_db),
):
    """Real-time Server-Sent Events (SSE) stream for unread notifications."""
    try:
        import jwt
        from auth_utils import ALGORITHM, SECRET_KEY

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    async def event_generator():
        while True:
            # 1. Check for new notifications
            count = (
                await db.run_sync(lambda s: s.query(models.Notification)
                .filter(
                    models.Notification.user_id == user_id,
                    models.Notification.is_read.is_(False),
                )
                .count())
            )

            # 2. Check for latest activity (Heatmap Sync)
            latest_activity = (
                await db.run_sync(lambda s: s.query(func.max(models.Attempt.attempted_at))
                .filter(models.Attempt.user_id == user_id)
                .scalar())
            )

            activity_ts = latest_activity.isoformat() if latest_activity else None

            # 3. Emit event payload
            yield f'data: {{"unread_count": {count}, "activity_ts": "{activity_ts}"}}\n\n'

            await asyncio.sleep(5)  # Poll every 5 seconds for changes

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/notifications/unread-count")
def get_unread_notification_count(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """Returns count of unread notifications for badge display."""
    user_id = int(current_user["sub"])
    count = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id, models.Notification.is_read.is_(False))
        .count()
    )
    return {"unread_count": count}

@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Mark a single notification as read."""
    user_id = int(current_user["sub"])
    notif = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == user_id,
        )
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"success": True}

@router.post("/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """Mark all notifications as read for the current user."""
    user_id = int(current_user["sub"])
    db.query(models.Notification).filter(
        models.Notification.user_id == user_id, models.Notification.is_read.is_(False)
    ).update({"is_read": True})
    db.commit()
    return {"success": True}

@router.delete("/notifications/{notification_id}")
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Delete a specific notification."""
    user_id = int(current_user["sub"])
    notif = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == user_id,
        )
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.delete(notif)
    db.commit()
    return {"success": True}
