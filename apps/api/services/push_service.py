"""Mobile push delivery via the Expo Push API (routes to FCM on Android).

Best-effort and non-throwing: push failures must never break the request that
triggered the notification. One batched HTTP call regardless of device count.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_push_to_user(db, user_id: int, title: str, body: str = "", url: str | None = None) -> None:
    """Send a push to every registered device of `user_id`. Best-effort."""
    import models

    try:
        rows = (
            db.query(models.DeviceToken)
            .filter(models.DeviceToken.user_id == user_id)
            .all()
        )
    except Exception as e:  # DB hiccup must not break the caller
        logger.warning("push: token lookup failed for user %s: %s", user_id, e)
        return

    messages = [
        {
            "to": r.token,
            "title": title,
            "body": body or "",
            "data": {"url": url or "/dashboard"},
            "channelId": "default",
            "priority": "high",
        }
        for r in rows
        if str(r.token).startswith("ExponentPushToken")
        or str(r.token).startswith("ExpoPushToken")
    ]
    if not messages:
        return

    try:
        httpx.post(
            EXPO_PUSH_URL,
            json=messages,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=8.0,
        )
    except Exception as e:
        logger.warning("push: Expo send failed for user %s: %s", user_id, e)
