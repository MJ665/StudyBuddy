import datetime
import uuid
from typing import Optional

import models
from auth_utils import (
    assert_group_in_org,
    assert_same_org,
    require_admin,
    verify_token,
)
from cache_manager import redis_client
from database import get_async_db, get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

router = APIRouter(prefix="/resources", tags=["resources"])

import logging  # noqa: E402

from botocore.exceptions import ClientError  # noqa: E402
from config import settings  # noqa: E402
from services.s3_service import (  # noqa: E402
    delete_s3_object,
    generate_presigned_get_url,
    generate_resource_upload_url,
)

logger = logging.getLogger("resources")


class ResourceUploadRequest(BaseModel):
    file_name: str = Field(..., max_length=255)
    file_type: str = Field(
        ...,
        pattern=r"^(application/pdf|application/msword|application/vnd\.openxmlformats-officedocument\.wordprocessingml\.document|text/plain|text/csv|image/.*)$",
    )
    group_id: int
    user_id: int
    description: Optional[str] = Field("", max_length=1000)
    category: Optional[str] = Field("General", max_length=50)
    file_size_bytes: int = Field(
        default=10485760, le=52428800
    )  # Max 50MB for resources


class ImageUploadRequest(BaseModel):
    file_name: str = Field(..., max_length=255)
    file_type: str = Field(
        ..., pattern=r"^(image/jpeg|image/png|image/webp|image/gif)$"
    )
    file_size_bytes: int = Field(default=2097152, le=5242880)  # Max 5MB for images


class MarkReviewedRequest(BaseModel):
    is_reviewed: bool


@router.post("/presigned-upload")
async def get_presigned_upload_url(
    req: ResourceUploadRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """
    Generates a pre-signed POST policy for the frontend to upload a PDF directly to S3.
    Enforces a strict 10MB limit via S3 Conditions. Stores description and category.
    """
    if (
        str(req.user_id) != str(current_user["sub"])
        or req.group_id != current_user["group_id"]
    ):
        raise HTTPException(status_code=403, detail="Unauthorized upload attempt")

    # Rate limit: max 1 upload URL request per user every 10 seconds to prevent presigned URL spam
    lock_key = f"rl:presigned_url:{req.user_id}"
    try:
        acquired = await redis_client.set(lock_key, "locked", ex=10, nx=True)
        if not acquired:
            raise HTTPException(
                status_code=429,
                detail="Too many upload requests. Please wait a moment.",
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        pass

    # Validate filename extension at backend
    if not req.file_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are permitted.")

    group = await db.get(models.Group, req.group_id)
    user = await db.get(models.User, req.user_id)

    if not group or not user:
        raise HTTPException(status_code=404, detail="User or Group not found")

    # Storage Path: group_name/user_email/filename.pdf — clean and predictable

    if not settings.AWS_ACCESS_KEY_ID:
        raise HTTPException(
            status_code=503, detail="AWS credentials are not configured on this server."
        )

    try:
        upload_data = generate_resource_upload_url(
            group_name=group.name,
            user_email=user.email,
            filename=req.file_name,
            file_type=req.file_type,
            max_size_bytes=req.file_size_bytes,
        )
        s3_key = upload_data["s3_key"]
        response = upload_data["upload_url"]

        # Create DB record with metadata
        new_resource = models.Resource(
            group_id=req.group_id,
            user_id=req.user_id,
            file_name=req.file_name,
            s3_key=s3_key,
            description=req.description or "",
            category=req.category or "General",
        )
        db.add(new_resource)
        await db.commit()
        await db.refresh(new_resource)

        return {
            "upload_url_data": response,
            "resource_id": new_resource.id,
            "s3_key": s3_key,
        }
    except ClientError:
        raise HTTPException(status_code=500, detail="Could not generate presigned URL")


@router.post("/images/presigned-upload")
def get_image_presigned_upload(
    req: ImageUploadRequest, current_user: dict = Depends(verify_token)
):
    """
    STRAT-IMAGE-V4: Specialized endpoint for uploading content images (e.g. for RichText).
    """
    from services.s3_service import generate_image_resource_url

    user_id = int(current_user["sub"])

    # Restrict to common image types
    if not any(
        req.file_type.lower().startswith(t)
        for t in ["image/jpeg", "image/png", "image/webp", "image/gif"]
    ):
        raise HTTPException(
            status_code=400,
            detail="Only standard image formats (JPG, PNG, WEBP, GIF) are allowed.",
        )

    return generate_image_resource_url(
        user_id=user_id,
        filename=req.file_name,
        file_type=req.file_type,
        max_size_bytes=req.file_size_bytes,
    )


@router.get("/group/{group_id}")
def get_group_resources(
    group_id: int,
    page: int = 1,
    size: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """
    Lists resources for a group with pagination.
    Generates short-lived view-only pre-signed GET urls.
    """
    # The role check below lets LDAdmin/Mentor read ANY group — including
    # another organization's. Bound the group to the caller's org first.
    assert_group_in_org(group_id, db, current_user)
    from pagination import paginate

    # VII: Robust authorization check
    if current_user["role"] not in ["LDAdmin", "Mentor"] and int(group_id) != int(
        current_user["group_id"]
    ):
        raise HTTPException(
            status_code=403,
            detail="Strategic Boundary: Cannot access resources outside of your cohort.",
        )

    from sqlalchemy.orm import joinedload

    query = (
        db.query(models.Resource)
        .options(joinedload(models.Resource.user))
        .join(models.User, models.Resource.user_id == models.User.id)
        .filter(
            (models.Resource.group_id == group_id) | (models.User.role == "LDAdmin")
        )
        .order_by(models.Resource.created_at.desc())
    )

    paginated = paginate(query, page, size)
    result_items = []
    for r in paginated.items:
        try:
            url = generate_presigned_get_url(
                s3_key=r.s3_key, expiry_seconds=3600, filename=r.file_name
            )

            u_name = r.user.full_name if r.user else "Unknown User"

            result_items.append(
                {
                    "id": int(r.id),
                    "file_name": str(r.file_name),
                    "description": str(r.description or ""),
                    "category": str(r.category or "General"),
                    "uploaded_by": str(u_name),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "view_url": str(url),
                    "view_url_expires_at": (
                        datetime.datetime.now(datetime.timezone.utc)
                        + datetime.timedelta(seconds=3600)
                    ).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"S3 URL Gen Error for resource {r.id}: {e}")
            continue

    return {
        "items": result_items,
        "total": paginated.total,
        "page": paginated.page,
        "size": paginated.size,
        "pages": paginated.pages,
    }


@router.patch("/{resource_id}")
def update_resource_metadata(
    resource_id: int,
    updates: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Allows owners or admins to update resource description/category."""
    resource = (
        db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    )
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    # Resources belong to a group; bind that group to the caller's org.
    assert_group_in_org(resource.group_id, db, current_user)

    # Auth: owner, LDAdmin, or GroupAdmin of same group
    is_owner = str(current_user["sub"]) == str(resource.user_id)
    is_admin = current_user["role"] in ["LDAdmin", "Admin"]

    if not (is_owner or is_admin):
        raise HTTPException(status_code=403, detail="Forbidden")

    allowed_fields = ["description", "category"]
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(resource, key, value)

    db.commit()
    return {"success": True, "message": "Resource updated successfully"}


@router.delete("/{resource_id}")
def delete_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """
    Deletes a resource from both the database AND S3.
    User can delete their own files. Admin can delete any file within their group.
    """
    resource = (
        db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    )
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    assert_group_in_org(resource.group_id, db, current_user)

    # Authorization: must be owner, LDAdmin (global), or GroupAdmin of same group
    is_owner = str(current_user["sub"]) == str(resource.user_id)
    user_role = current_user.get("user_role") or current_user.get("role")

    is_ld_admin = user_role == "LDAdmin"
    is_group_admin = user_role == "GroupAdmin" and int(current_user["group_id"]) == int(
        resource.group_id
    )

    if not (is_owner or is_ld_admin or is_group_admin):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this resource (cross-group or insufficient role)",
        )

    # Delete from S3 first (cleanup orphaned files)
    try:
        delete_s3_object(resource.s3_key)
    except Exception as e:
        # Log but don't block DB deletion — S3 object may already be gone
        print(f"S3 delete failed for key {resource.s3_key}: {e}")

    # Remove from DB
    db.delete(resource)
    db.commit()

    from services.audit_service import log_admin_action

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=str(current_user.get("role") or current_user.get("user_role") or "Unknown"),
        action="DELETE_RESOURCE",
        resource_type="RESOURCE",
        resource_id=resource_id,
        details={"file_name": resource.file_name, "group_id": resource.group_id},
    )

    return {"success": True, "message": "Resource deleted successfully"}


@router.patch("/attempts/{attempt_id}/review")
def mark_attempt_reviewed(
    attempt_id: int,
    req: MarkReviewedRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """
    Allows an Admin to mark/unmark an attempt as reviewed. (L&D Feature X)
    """
    attempt = db.query(models.Attempt).filter(models.Attempt.id == attempt_id).first()
    assert_same_org(attempt, current_user, "Attempt")

    attempt.is_reviewed = req.is_reviewed
    db.commit()

    from services.audit_service import log_admin_action

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="MARK_ATTEMPT_REVIEWED",
        resource_type="ATTEMPT",
        resource_id=attempt_id,
        details={"is_reviewed": req.is_reviewed},
    )

    return {"success": True, "is_reviewed": attempt.is_reviewed}


class CommentCreate(BaseModel):
    content: str


@router.post("/{resource_id}/comments")
async def add_resource_comment(
    resource_id: int,
    data: CommentCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """FUNC-008: Mentors and members can provide feedback on PDF resources."""
    resource = await db.get(models.Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    await db.run_sync(
        lambda sd: assert_group_in_org(resource.group_id, sd, current_user)
    )

    comment = models.ResourceComment(
        resource_id=resource_id, user_id=int(current_user["sub"]), comment=data.content
    )
    db.add(comment)
    await db.commit()

    try:
        await redis_client.delete(f"resources:comments:{resource_id}")
    except Exception as e:
        logging.warning(f"Resource comment cache purge failed: {e}")

    return {"success": True, "message": "Feedback added successfully"}


@router.get("/{resource_id}/comments")
async def get_resource_comments(
    resource_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """Retrieve all feedback/comments for a specific resource."""
    import json

    from sqlalchemy.orm import joinedload

    _res = await db.get(models.Resource, resource_id)
    if not _res:
        raise HTTPException(status_code=404, detail="Resource not found")
    await db.run_sync(
        lambda sd: assert_group_in_org(_res.group_id, sd, current_user)
    )

    redis_key = f"resources:comments:{resource_id}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logging.warning(f"Resource comment cache lookup failed: {e}")

    rows = await db.execute(
        select(models.ResourceComment)
        .options(joinedload(models.ResourceComment.user))
        .where(models.ResourceComment.resource_id == resource_id)
        .order_by(models.ResourceComment.created_at.desc())
    )
    comments = rows.scalars().unique().all()
    res = [
        {
            "id": c.id,
            "content": c.comment,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "user_name": c.user.full_name if c.user else "Unknown",
            "role": c.user.role if c.user else "Member",
        }
        for c in comments
    ]

    try:
        await redis_client.set(redis_key, json.dumps(res), ex=300)
    except Exception:
        pass

    return res
