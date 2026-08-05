import models
import schemas
from auth_utils import verify_token
from database import get_async_db
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/profile", tags=["Public Profile"])


@router.get("/{slug}")
async def get_public_profile(slug: str, db: AsyncSession = Depends(get_async_db)):
    """
    Public endpoint to fetch user profile by email-prefix or custom slug.
    No authentication required.
    """
    import json

    from cache_manager import redis_client

    redis_key = f"profile:public:{slug}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    # 1. Look for user by custom_slug OR email prefix.
    # The hierarchy walk below (group -> batch -> vertical -> department ->
    # organization) is a lazy chain; an AsyncSession cannot resolve those
    # implicitly, so the whole path is eager-loaded here.
    _res = await db.execute(
        select(models.User)
        .options(
            selectinload(models.User.group)
            .selectinload(models.Group.batch)
            .selectinload(models.Batch.vertical)
            .selectinload(models.Vertical.department)
            .selectinload(models.Department.organization)
        )
        .where(
            or_(models.User.custom_slug == slug, models.User.email.like(f"{slug}@%"))
        )
    )
    user = _res.scalars().first()

    if not user:
        raise HTTPException(
            status_code=404, detail="Tactical operator profile not found in registry."
        )

    # 2. Fetch comments
    _c = await db.execute(
        select(models.ProfileComment)
        .where(models.ProfileComment.target_user_id == user.id)
        .order_by(models.ProfileComment.created_at.desc())
    )
    comments = _c.scalars().all()

    # 3. Fetch Full Intelligence Suite
    from services.performance_engine import performance_engine
    from services.user_service import user_service

    registry = await user_service.get_user_registry(user.id, db)
    atlas = await user_service.get_user_atlas(user.id, db)
    vectors = await performance_engine.get_user_vectors(user.id, db)
    heatmap = await user_service.get_user_heatmap(user.id, db)

    # 4. Fetch Hierarchy
    hierarchy = {
        "organization": "StudyBuddy Global",
        "department": "Core Intelligence",
        "batch": "Foundation",
        "group": "General Registry",
    }
    if user.group:
        hierarchy["group"] = user.group.name
        # V3 Hierarchy Traversal
        batch = user.group.batch
        if batch:
            hierarchy["batch"] = batch.name
            vert = batch.vertical
            if vert:
                dept = vert.department
                if dept:
                    hierarchy["department"] = dept.name
                    org = dept.organization
                    if org:
                        hierarchy["organization"] = org.name

    # 5. Format public data
    res = {
        "id": user.id,
        "full_name": user.full_name,
        "role": user.role,
        "email": user.email,
        "hierarchy": hierarchy,
        "profile_photo_url": user.profile_photo_url,
        "cover_photo_url": user.cover_photo_url,
        "bio": user.bio,
        "github_url": user.github_url,
        "linkedin_url": user.linkedin_url,
        "leetcode_url": user.leetcode_url,
        "codolio_url": user.codolio_url,
        "expertise_json": user.expertise_json,
        "streak_count": user.streak_count,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "registry": registry,
        "atlas": atlas,
        "vectors": vectors,
        "heatmap": heatmap,
        "comments": [
            {
                "id": c.id,
                "content": c.content,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "author": {
                    "id": c.author.id,
                    "full_name": c.author.full_name,
                    "profile_photo_url": c.author.profile_photo_url,
                    "email_prefix": c.author.email.split("@")[0]
                    if c.author.email
                    else "anonymous",
                },
            }
            for c in comments
        ],
    }

    try:
        await redis_client.set(redis_key, json.dumps(res), ex=300)
    except Exception:
        pass

    return res


class CommentCreate(schemas.BaseModel):
    content: str


@router.post("/{slug}/comment")
async def post_profile_comment(
    slug: str,
    data: CommentCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """
    Drops a comment on a user's profile.
    Requires authentication.
    """
    # 1. Find target user
    _res = await db.execute(
        select(models.User).where(
            or_(models.User.custom_slug == slug, models.User.email.like(f"{slug}@%"))
        )
    )
    user = _res.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="Target registry entry not found.")

    if not data.content.strip():
        raise HTTPException(status_code=400, detail="Comment content cannot be empty.")

    # 2. Create comment
    new_comment = models.ProfileComment(
        target_user_id=user.id, author_id=int(current_user["sub"]), content=data.content
    )
    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)

    from cache_manager import redis_client

    try:
        await redis_client.delete(f"profile:public:{slug}")
        await redis_client.delete(f"profile:public:{user.custom_slug}")
        await redis_client.delete(f"profile:public:{user.email.split('@')[0]}")
    except Exception:
        pass

    return {"success": True, "message": "Feedback transmission successful."}
