"""
User Intelligence Router — StudyBuddy Enterprise
Provides 30 intelligence dimensions per user:
  GET /intel/user/{user_id}          → Full 30-metric intelligence panel
  GET /intel/user/{user_id}/ai-summary → AI-generated natural language narrative
  GET /intel/user/{user_id}/roles    → All scoped roles for a user (multi-group)
  POST /intel/user/{user_id}/roles   → Assign scoped role to user
  DELETE /intel/user/{user_id}/roles/{role_id} → Remove scoped role
  GET /intel/hierarchy/with-users    → Org tree with users at each node
"""

import logging
import os
from typing import Optional

import models
from auth_utils import assert_user_in_org, verify_token
from cache_manager import cache_manager
from services.s3_service import sign_media_url
from database import get_async_db, get_db
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from schemas import CommentRequest
from services.ai_reporting import ai_executive
from services.performance_engine import performance_engine
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intel", tags=["intelligence"])


async def _resolve_user_by_slug_async(slug: str, db: AsyncSession):
    """Resolve a profile slug to a user (custom slug, reserved name, id, or email prefix).

    The same four-branch lookup was duplicated in several handlers; keeping one
    async copy avoids the branches drifting apart as routers migrate.
    """
    res = await db.execute(
        select(models.User).where(models.User.custom_slug == slug)
    )
    user = res.scalars().first()
    if not user and slug in ["system", "admin"]:
        user = await db.get(models.User, 0)
    elif not user and slug.isdigit():
        user = await db.get(models.User, int(slug))
    if not user:
        res = await db.execute(
            select(models.User).where(models.User.email.ilike(f"{slug}@%"))
        )
        user = res.scalars().first()
    return user
security = HTTPBearer(auto_error=False)


async def get_optional_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    if not auth:
        return None
    try:
        # verify_token is imported from auth_utils
        return verify_token(auth.credentials)
    except Exception:
        return None


# ─── Request Schemas ─────────────────────────────────────────────────────────


class AssignRoleRequest(BaseModel):
    role: str  # "LDAdmin" | "Mentor" | "GroupAdmin" | "Member"
    scope_type: str = "group"  # "group" | "batch" | "org"
    scope_id: Optional[int] = None  # group_id / batch_id etc.


# ─── Utility: Compute all 30 intelligence metrics ────────────────────────────


@router.get("/user/{user_id}/insights")
@cache_manager.cached("user_intel", ttl=129600)  # 36h cache
async def get_user_intelligence(
    user_id: int,
    refresh: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """Returns full 30-dimension intelligence profile for a specific user."""
    role = current_user.get("role")
    requester_id = int(current_user["sub"])

    if role not in ["LDAdmin", "Mentor", "GroupAdmin"] and requester_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # performance_engine handles caching internally if refresh=False
    # Tenancy (404-not-403): role gates alone allowed cross-org reads.
    await db.run_sync(lambda s: assert_user_in_org(user_id, s, current_user))
    intel = await performance_engine.get_user_vectors(user_id, db, refresh=refresh)
    if not intel:
        raise HTTPException(status_code=404, detail="User not found")

    # Add basic user info that PerformanceEngine might not include
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    intel["user"] = {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "profile_photo_url": sign_media_url(user.profile_photo_url),
        "streak_count": user.streak_count or 0,
        "last_active_date": user.last_active_date.isoformat()
        if user.last_active_date
        else None,
    }

    return intel


# ─── Route: AI Summary Narrative ─────────────────────────────────────────────


@router.get("/user/{user_id}/ai-summary")
@cache_manager.cached("user_ai_summary", ttl=86400)  # 24h cache
async def get_ai_intelligence_summary(
    user_id: int,
    refresh: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """
    AI-powered natural language intelligence summary for this user.
    Uses Gemini to synthesize all 30 metrics into a 5-point coaching narrative.
    """
    role = current_user.get("role")
    if role not in ["LDAdmin", "Mentor", "GroupAdmin", "Member"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI unavailable")

    # Tenancy (404-not-403): role gates alone allowed cross-org reads.
    await db.run_sync(lambda s: assert_user_in_org(user_id, s, current_user))
    intel = await performance_engine.get_user_vectors(user_id, db, refresh=refresh)
    if not intel:
        raise HTTPException(status_code=404, detail="User not found")

    m = intel["metrics"]
    c = intel["charts"]
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    f"""
Learner: {user.full_name} | Role: {user.role}
Overall Quiz Accuracy: {m["m02_overall_accuracy"]["value"]}
Total Attempts: {m["m01_total_quiz_attempts"]["value"]}  |  Last 7 Days: {m["m05_quiz_7d"]["value"]}
Current Streak: {m["m07_streak"]["value"]}
Learning Trajectory: {m["m17b_velocity_label"]["value"]} ({m["m17_velocity"]["value"]})
Consistency Profile: {m["m18b_consistency_label"]["value"]} (Score: {m["m18_consistency"]["value"]})
Coding Lab: {m["m12_coding_attempts"]["value"]} attempts, Avg Score: {m["m13_avg_ai_score"]["value"]}
Assignment Completion: {m["m16_assignment_rate"]["value"]}
Best Topic: {(c["best_topic"]["topic"] + " (" + str(c["best_topic"]["avg_accuracy"]) + "% accuracy)") if c.get("best_topic") else "N/A"}
Weakest Topic: {(c["worst_topic"]["topic"] + " (" + str(c["worst_topic"]["avg_accuracy"]) + "% accuracy)") if c.get("worst_topic") else "N/A"}
Engagement Profile: {m["m28_engagement"]["value"]}
Risk Assessment: {m["m29_risk"]["value"]}
Group Percentile: {m["m26_percentile"]["value"]}
Speed Rating: {m["m09_speed_rating"]["value"]}
Active Days: {m["m20_active_days"]["value"]}
"""

    # Use centralized ExecutiveAIService
    summary = await ai_executive.generate_member_summary(user.full_name, intel)
    return {"summary": summary.get("data", "")}


# ─── Route: Multi-Role Management ────────────────────────────────────────────


@router.get("/user/{user_id}/roles")
def get_user_roles(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Returns all scoped roles for a user (multi-group role assignments)."""
    if current_user.get("role") not in ["LDAdmin", "GroupAdmin", "Mentor"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Tenancy (404-not-403): scope to the caller's org.
    assert_user_in_org(user_id, db, current_user)

    scoped_roles = (
        db.query(models.UserRole)
        .filter(models.UserRole.user_id == user_id)
        .all()
    )
    result = []
    for sr in scoped_roles:
        scope_name = None
        if sr.scope_type == "group" and sr.scope_id:
            grp = db.query(models.Group).filter(models.Group.id == sr.scope_id).first()
            scope_name = grp.name if grp else f"Group #{sr.scope_id}"
        elif sr.scope_type == "batch" and sr.scope_id:
            bat = db.query(models.Batch).filter(models.Batch.id == sr.scope_id).first()
            scope_name = bat.name if bat else f"Batch #{sr.scope_id}"

        result.append(
            {
                "id": sr.id,
                "role": sr.role,
                "scope_type": sr.scope_type,
                "scope_id": sr.scope_id,
                "scope_name": scope_name,
                "granted_at": sr.created_at.isoformat() if sr.created_at else None,
            }
        )

    return {
        "user_id": user_id,
        "user_name": user.full_name,
        "primary_role": user.role,
        "primary_group_id": user.group_id,
        "scoped_roles": result,
    }


@router.post("/user/{user_id}/roles")
def assign_user_role(
    user_id: int,
    req: AssignRoleRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Assign a scoped role to a user (enables multi-group participation)."""
    if current_user.get("role") not in ["LDAdmin"]:
        raise HTTPException(
            status_code=403, detail="Only LDAdmin can assign multi-group roles"
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Tenancy (404-not-403): scope to the caller's org.
    assert_user_in_org(user_id, db, current_user)

    # Check if already assigned
    existing = (
        db.query(models.UserRole)
        .filter(
            models.UserRole.user_id == user_id,
            models.UserRole.role == req.role,
            models.UserRole.scope_type == req.scope_type,
            models.UserRole.scope_id == req.scope_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(status_code=409, detail="Role already assigned")

    new_role = models.UserRole(
        user_id=user_id, role=req.role, scope_type=req.scope_type, scope_id=req.scope_id
    )
    db.add(new_role)

    # If mentor role + group scope → also add MentorGroupAssignment
    if req.role == "Mentor" and req.scope_type == "group" and req.scope_id:
        exists_assign = (
            db.query(models.MentorGroupAssignment)
            .filter_by(mentor_id=user_id, group_id=req.scope_id)
            .first()
        )
        if not exists_assign:
            db.add(
                models.MentorGroupAssignment(
                    mentor_id=user_id, group_id=req.scope_id, is_active=True
                )
            )

    db.commit()

    from services.audit_service import log_admin_action

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="ASSIGN_SCOPED_ROLE",
        resource_type="USER_ROLE",
        resource_id=new_role.id,
        details={
            "target_user_id": user_id,
            "role": req.role,
            "scope": f"{req.scope_type}:{req.scope_id}",
        },
    )

    return {
        "success": True,
        "message": f"Role '{req.role}' assigned for {req.scope_type} #{req.scope_id}",
    }


@router.delete("/user/{user_id}/roles/{role_id}")
def remove_user_role(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Remove a scoped role from a user."""
    if current_user.get("role") != "LDAdmin":
        raise HTTPException(status_code=403, detail="Forbidden")

    # Tenancy (404-not-403): an LDAdmin can only manage users in their org.
    assert_user_in_org(user_id, db, current_user)

    role = (
        db.query(models.UserRole)
        .filter(models.UserRole.id == role_id, models.UserRole.user_id == user_id)
        .first()
    )
    if not role:
        raise HTTPException(status_code=404, detail="Role assignment not found")

    db.delete(role)
    db.commit()

    from services.audit_service import log_admin_action

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="REMOVE_SCOPED_ROLE",
        resource_type="USER_ROLE",
        resource_id=role_id,
        details={
            "target_user_id": user_id,
            "role": role.role,
            "scope": f"{role.scope_type}:{role.scope_id}",
        },
    )

    return {"success": True, "message": "Role removed"}


# ─── Route: Org Hierarchy + Users ────────────────────────────────────────────


@router.get("/hierarchy/with-users")
@cache_manager.cached("org_hierarchy", ttl=600)
def get_hierarchy_with_users(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """
    Returns the full org tree with users embedded at each group node.
    Used by the LDAdmin hierarchy view to show who is where.
    """
    if current_user.get("role") not in ["LDAdmin", "GroupAdmin", "Mentor"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    from sqlalchemy.orm import joinedload

    # Load entire hierarchy tree with eager relationships to avoid N+1
    orgs = (
        db.query(models.Organization)
        .options(
            joinedload(models.Organization.departments)
            .joinedload(models.Department.verticals)
            .joinedload(models.Vertical.batches)
            .joinedload(models.Batch.groups)
        )
        .all()
    )
    result = []
    for org in orgs:
        org_data = {"id": org.id, "name": org.name, "type": "org", "departments": []}
        for dept in org.departments or []:
            dept_data = {
                "id": dept.id,
                "name": dept.name,
                "type": "department",
                "verticals": [],
            }
            for vert in dept.verticals or []:
                vert_data = {
                    "id": vert.id,
                    "name": vert.name,
                    "type": "vertical",
                    "batches": [],
                }
                for batch in vert.batches or []:
                    batch_data = {
                        "id": batch.id,
                        "name": batch.name,
                        "type": "batch",
                        "groups": [],
                    }
                    for group in batch.groups or []:
                        users = (
                            db.query(models.User)
                            .filter(
                                models.User.group_id == group.id, models.User.is_active.is_(True)
                            )
                            .all()
                        )
                        user_list = [
                            {
                                "id": u.id,
                                "full_name": u.full_name,
                                "email": u.email,
                                "role": u.role,
                                "streak_count": u.streak_count or 0,
                                "profile_photo_url": sign_media_url(u.profile_photo_url),
                                "scoped_roles": [
                                    {
                                        "role": sr.role,
                                        "scope_type": sr.scope_type,
                                        "scope_id": sr.scope_id,
                                    }
                                    for sr in (u.scoped_roles or [])
                                ],
                            }
                            for u in users
                        ]
                        # Group stats
                        total_members = len([u for u in users if u.role == "Member"])
                        mentors = [u for u in users if u.role == "Mentor"]
                        batch_data["groups"].append(
                            {
                                "id": group.id,
                                "name": group.name,
                                "type": "group",
                                "member_count": total_members,
                                "mentor_count": len(mentors),
                                "users": user_list,
                            }
                        )
                    vert_data["batches"].append(batch_data)
                dept_data["verticals"].append(vert_data)
            org_data["departments"].append(dept_data)
        result.append(org_data)
    return result


@router.get("/profile/{slug}")
async def get_profile_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """PHASE-3: Strategic profile resolution via custom slugs. Consolidated for Public UI."""
    user = await db.run_sync(lambda s: s.query(models.User).filter(models.User.custom_slug == slug).first())
    if not user:
        if slug in ["system", "admin"]:
            user = await db.run_sync(lambda s: s.query(models.User).filter(models.User.id == 0).first())
        elif slug.isdigit():
            user = await db.run_sync(lambda s: s.query(models.User).filter(models.User.id == int(slug)).first())
        else:
            # Fallback: check email prefix
            user = (
                await db.run_sync(lambda s: s.query(models.User)
                .filter(models.User.email.ilike(f"{slug}@%"))
                .first())
            )

    if not user:
        raise HTTPException(
            status_code=404, detail="Entity not found in global registry."
        )

    from services.user_service import user_service

    # Aggregate ALL data required for the PublicProfile dashboard
    vectors = await performance_engine.get_user_vectors(user.id, db)
    registry = await user_service.get_user_registry(user.id, db)
    atlas = await user_service.get_user_atlas(user.id, db)
    heatmap = await user_service.get_user_heatmap(user.id, db)

    # Comments/Endorsements
    raw_comments = (
        await db.run_sync(lambda s: s.query(models.ProfileComment)
        .filter(models.ProfileComment.target_user_id == user.id)
        .order_by(models.ProfileComment.created_at.desc())
        .all())
    )

    comments = []
    for c in raw_comments:
        comments.append(
            {
                "id": c.id,
                "content": c.content,
                "created_at": c.created_at.isoformat(),
                "author": {
                    "id": c.author.id,
                    "full_name": c.author.full_name,
                    "email_prefix": c.author.email.split("@")[0]
                    if c.author.email
                    else "anon",
                    "profile_photo_url": sign_media_url(c.author.profile_photo_url),
                },
            }
        )

    # Hierarchy resolution
    hierarchy = {
        "organization": "Independent Operation",
        "vertical": "Standard Vertical",
        "batch": "General Cohort",
        "group": "External Operator",
        "department": "Engineering",
    }

    if user.group:
        hierarchy["group"] = user.group.name
        batch = (
            await db.run_sync(lambda s: s.query(models.Batch)
            .filter(models.Batch.id == user.group.batch_id)
            .first())
        )
        if batch:
            hierarchy["batch"] = batch.name
            vertical = (
                await db.run_sync(lambda s: s.query(models.Vertical)
                .filter(models.Vertical.id == batch.vertical_id)
                .first())
            )
            if vertical:
                hierarchy["vertical"] = vertical.name
                department = (
                    await db.run_sync(lambda s: s.query(models.Department)
                    .filter(models.Department.id == vertical.department_id)
                    .first())
                )
                if department:
                    hierarchy["department"] = department.name
                    org = (
                        await db.run_sync(lambda s: s.query(models.Organization)
                        .filter(models.Organization.id == department.organization_id)
                        .first())
                    )
                    if org:
                        hierarchy["organization"] = org.name

    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email
        if (
            current_user
            and current_user.get("role") in ["LDAdmin", "Mentor", "GroupAdmin"]
        )
        else None,
        "role": user.role,
        "bio": user.bio,
        "custom_slug": user.custom_slug,
        "profile_photo_url": sign_media_url(user.profile_photo_url),
        "cover_photo_url": sign_media_url(user.cover_photo_url),
        "intro_video_url": user.intro_video_url,
        "github_url": user.github_url,
        "linkedin_url": user.linkedin_url,
        "leetcode_url": user.leetcode_url,
        "codolio_url": user.codolio_url,
        "expertise_json": user.expertise_json or {},
        "streak_count": user.streak_count,
        "hierarchy": hierarchy,
        "vectors": vectors,
        "registry": registry,
        "atlas": atlas,
        "heatmap": heatmap,
        "comments": comments,
    }


@router.post("/profile/{slug}/comment")
def post_profile_comment(
    slug: str,
    req: CommentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """PHASE-3: Allow authenticated users to leave endorsements on profiles."""
    user = db.query(models.User).filter(models.User.custom_slug == slug).first()
    if not user:
        if slug in ["system", "admin"]:
            user = db.query(models.User).filter(models.User.id == 0).first()
        elif slug.isdigit():
            user = db.query(models.User).filter(models.User.id == int(slug)).first()
        else:
            user = (
                db.query(models.User)
                .filter(models.User.email.ilike(f"{slug}@%"))
                .first()
            )

    if not user:
        raise HTTPException(status_code=404, detail="Target profile not found")

    author_id = int(current_user["sub"])
    author_user = db.query(models.User).filter(models.User.id == author_id).first()

    # Basic XSS Sanitization
    safe_content = req.content.replace("<", "&lt;").replace(">", "&gt;")

    new_comment = models.ProfileComment(
        target_user_id=user.id, author_id=author_id, content=safe_content
    )
    db.add(new_comment)

    # Audit Logging
    audit = models.AdminAuditLog(
        actor_id=author_id,
        actor_role=current_user.get("role", "Member"),
        action="POST_PROFILE_COMMENT",
        resource_type="USER_PROFILE",
        resource_id=user.id,
        details={
            "author_name": author_user.full_name if author_user else "Unknown",
            "comment_length": len(safe_content),
        },
    )
    db.add(audit)

    db.commit()
    db.refresh(new_comment)

    return {"success": True, "comment_id": new_comment.id}


@router.get("/profile/{slug}/atlas")
@cache_manager.cached("profile_atlas", ttl=129600)  # 36h cache
async def get_profile_atlas(
    slug: str,
    refresh: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """
    SECTION 12: Generate 30 AI Insights (Growth Atlas).
    Consolidated route for profile-centric AI growth strategy.
    """
    user = await _resolve_user_by_slug_async(slug, db)
    if not user:
        raise HTTPException(status_code=404, detail="Member not found in registry")

    from services.user_service import user_service

    return await user_service.get_user_atlas(user.id, db)


@router.get("/profile/{slug}/registry")
async def get_profile_registry(
    slug: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """PHASE-3: Strategic usage registry via slug/ID resolution."""
    if slug in ["system", "admin"]:
        return {
            "id": 0,
            "full_name": "System Registry",
            "quiz_attempts": [],
            "coding_attempts": [],
            "averages": {"quiz": 0, "coding": 0},
            "completion_rate": 0,
            "assignments_completed": 0,
            "group_rank": "—",
            "group_size": "—",
            "percentile": 0,
            "topic_breakdown": {},
            "pros": [],
            "cons": [],
        }

    user = await _resolve_user_by_slug_async(slug, db)
    if not user:
        raise HTTPException(status_code=404, detail="Member not found")

    from services.user_service import user_service

    return await user_service.get_user_registry(user.id, db)
