"""Device push-token registration for the mobile wrapper (apps/mobile).

Mounted at /api/notifications. The mobile shell POSTs its Expo push token here
after login (Bearer auth), associating the device with the current user.
"""

import models
from auth_utils import verify_token
from database import get_db
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter()


class DeviceRegister(BaseModel):
    token: str
    platform: str = "android"


@router.post("/register-device")
def register_device(
    body: DeviceRegister,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    user_id = int(current_user["sub"])
    existing = (
        db.query(models.DeviceToken)
        .filter(models.DeviceToken.token == body.token)
        .first()
    )
    if existing:
        existing.user_id = user_id
        existing.platform = body.platform
    else:
        db.add(
            models.DeviceToken(
                user_id=user_id, token=body.token, platform=body.platform
            )
        )
    db.commit()
    return {"status": "registered"}


@router.delete("/register-device")
def unregister_device(
    body: DeviceRegister,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    db.query(models.DeviceToken).filter(
        models.DeviceToken.token == body.token,
        models.DeviceToken.user_id == int(current_user["sub"]),
    ).delete()
    db.commit()
    return {"status": "unregistered"}
