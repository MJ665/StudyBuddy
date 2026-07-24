import datetime

from database import Base
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class DeviceToken(Base):
    """A push-notification token for one user's device (Expo/FCM).

    Registered by the mobile wrapper (apps/mobile) after login. `token` is unique
    so re-registering the same device updates ownership instead of duplicating.
    """

    __tablename__ = "device_tokens"
    __table_args__ = (UniqueConstraint("token", name="uq_device_token"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), default="android", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
