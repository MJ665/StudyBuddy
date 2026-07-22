import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        Index("ix_resources_group_id", "group_id"),
        Index("ix_resources_group_category", "group_id", "category"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    s3_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, default="")
    category: Mapped[str | None] = mapped_column(String, default="General")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)

    user = relationship("User")
    group = relationship("Group", back_populates="resources")
    comments = relationship(
        "ResourceComment", back_populates="resource", cascade="all, delete-orphan"
    )


class ResourceComment(Base):
    __tablename__ = "resource_comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    resource_id: Mapped[int] = mapped_column(Integer, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)

    resource = relationship("Resource", back_populates="comments")
    user = relationship("User")