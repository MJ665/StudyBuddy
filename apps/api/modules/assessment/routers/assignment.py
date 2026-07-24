import datetime
from typing import Optional

import models
import schemas
from auth_utils import assert_group_in_org, verify_token
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

router = APIRouter(prefix="/assignments", tags=["assignments"])


class AssignmentCreate(BaseModel):
    title: Optional[str] = None
    assignment_type: Optional[str] = "quiz"  # "quiz" | "coding"
    target_type: str  # "group" | "batch" | "vertical" | "dept" | "org"
    target_id: int
    bank_id: Optional[int] = None
    coding_question_id: Optional[int] = None
    due_date: Optional[datetime.datetime] = None
    instructions: Optional[str] = None
    max_attempts: Optional[int] = None
    passing_score_percent: Optional[int] = None
    lock_after_due: bool = False
    is_compulsory: bool = True


@router.post(
    ""
)  # matches /api/assignments  (no trailing slash – required by Next.js proxy)
@router.post("/")  # matches /api/assignments/
def create_assignment(
    data: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    if current_user.get("role") not in ["LDAdmin", "Mentor", "GroupAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    if data.bank_id:
        bank = (
            db.query(models.QuestionBank)
            .filter(models.QuestionBank.id == data.bank_id)
            .first()
        )
        if not bank:
            raise HTTPException(status_code=404, detail="Bank not found")

        if (
            current_user.get("role") != "LDAdmin"
            and bank.visibility_scope == "group-private"
        ):
            if (
                not bank.subscriber_groups
                or data.target_id not in bank.subscriber_groups
            ):
                # Bypass if the user created it? They should still only assign to allowed groups.
                raise HTTPException(
                    status_code=403, detail="Bank is not scoped to this group"
                )

    assignment = models.Assignment(
        assignment_type=data.assignment_type or "quiz",
        target_type=data.target_type,
        target_id=data.target_id,
        bank_id=data.bank_id,
        coding_question_id=data.coding_question_id,
        due_date=data.due_date,
        instructions=data.instructions or data.title,
        max_attempts=data.max_attempts,
        passing_score_percent=data.passing_score_percent,
        lock_after_due=data.lock_after_due,
        is_compulsory=data.is_compulsory,
        created_by=int(current_user["sub"]),
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    # 12. Notification System: Trigger on Assignment Created (RECURSIVE-RESOLVE)
    try:
        users_to_notify = []
        if data.target_type == "group":
            users_to_notify = (
                db.query(models.User)
                .filter(models.User.group_id == data.target_id, models.User.is_active.is_(True))
                .all()
            )
        elif data.target_type == "batch":
            users_to_notify = (
                db.query(models.User)
                .join(models.Group)
                .filter(models.Group.batch_id == data.target_id, models.User.is_active.is_(True))
                .all()
            )
        elif data.target_type == "vertical":
            users_to_notify = (
                db.query(models.User)
                .join(models.Group)
                .join(models.Batch)
                .filter(
                    models.Batch.vertical_id == data.target_id, models.User.is_active.is_(True)
                )
                .all()
            )
        elif data.target_type == "dept":
            users_to_notify = (
                db.query(models.User)
                .join(models.Group)
                .join(models.Batch)
                .join(models.Vertical)
                .filter(
                    models.Vertical.department_id == data.target_id,
                    models.User.is_active.is_(True),
                )
                .all()
            )
        elif data.target_type == "org":
            users_to_notify = (
                db.query(models.User)
                .join(models.Group)
                .join(models.Batch)
                .join(models.Vertical)
                .join(models.Department)
                .filter(
                    models.Department.organization_id == data.target_id,
                    models.User.is_active.is_(True),
                )
                .all()
            )

        item_name = "New Assignment"
        link_type = "bank"
        link_id = data.bank_id

        if data.bank_id:
            bank = (
                db.query(models.QuestionBank)
                .filter(models.QuestionBank.id == data.bank_id)
                .first()
            )
            if bank:
                item_name = bank.name
        elif data.coding_question_id:
            coding_q = (
                db.query(models.CodingQuestion)
                .filter(models.CodingQuestion.id == data.coding_question_id)
                .first()
            )
            if coding_q:
                item_name = coding_q.title
            link_type = "coding"
            link_id = data.coding_question_id

        from services.push_service import send_push_to_user

        for u in users_to_notify:
            notif = models.Notification(
                user_id=u.id,
                notification_type="new_assignment",
                title=f"📋 New Assignment: {item_name}",
                body=data.instructions or "Please complete the new assignment.",
                link_type=link_type,
                link_id=link_id,
            )
            db.add(notif)

            # Mobile push (best-effort; never blocks the assignment).
            try:
                send_push_to_user(
                    db,
                    u.id,
                    f"New Assignment: {item_name}",
                    data.instructions or "Please complete the new assignment.",
                    url="/assignments",
                )
            except Exception:
                pass

            # TRIGGER-003: Email Mandate Notification
            if u.email:
                try:
                    from services.email_service import send_assignment_email

                    send_assignment_email(
                        to_email=u.email,
                        full_name=u.full_name,
                        bank_name=item_name,
                        due_date=data.due_date.strftime("%Y-%m-%d %H:%M")
                        if data.due_date
                        else None,
                        max_attempts=data.max_attempts,
                    )
                except Exception as e:
                    print(f"Email mandate failed for {u.email}: {e}")

        db.commit()
    except Exception as e:
        print("Failed to dispatch notifications:", e)
        db.rollback()

    from services.audit_service import log_admin_action

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="CREATE_ASSIGNMENT",
        resource_type="ASSIGNMENT",
        resource_id=assignment.id,
        details={
            "target_type": data.target_type,
            "target_id": data.target_id,
            "bank_id": data.bank_id,
            "coding_id": data.coding_question_id,
        },
    )

    return assignment


@router.get("/my")
def get_my_assignments(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    user_id = int(current_user["sub"])
    if user_id == 0:
        return []

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    group = user.group
    if not group:
        return []

    # Build list of targets the user belongs to
    targets = [("person", user.id), ("group", group.id)]
    if group.batch_id:
        targets.append(("batch", group.batch_id))
        if group.batch.vertical_id:
            targets.append(("vertical", group.batch.vertical_id))
            if group.batch.vertical.department_id:
                targets.append(("dept", group.batch.vertical.department_id))
                if group.batch.vertical.department.organization_id:
                    targets.append(
                        ("org", group.batch.vertical.department.organization_id)
                    )

    # Efficiently fetch assignments for any of these targets
    filters = [
        (models.Assignment.target_type == t[0]) & (models.Assignment.target_id == t[1])
        for t in targets
    ]

    # Use outer join with AssignmentCompletion to get status in one go
    # We filter by or_(*filters) which are the targets the user belongs to
    # Eager load bank and coding_question to avoid N+1 inside the results loop
    from models.assignment import Assignment, AssignmentCompletion
    from sqlalchemy.orm import joinedload

    results = (
        db.query(Assignment, AssignmentCompletion)
        .options(joinedload(Assignment.bank), joinedload(Assignment.coding_question))
        .outerjoin(
            AssignmentCompletion,
            (Assignment.id == AssignmentCompletion.assignment_id)
            & (AssignmentCompletion.user_id == user_id),
        )
        .filter(or_(*filters), Assignment.is_active == True)
        .all()
    )

    my_assignments = []
    for a, comp in results:
        my_assignments.append(
            {
                "assignment_id": a.id,
                "bank_id": a.bank_id,
                "coding_question_id": a.coding_question_id,
                "assignment_type": a.assignment_type,
                "bank_name": a.bank.name
                if a.bank
                else (
                    a.coding_question.title
                    if a.coding_question
                    else f"Assignment #{a.id}"
                ),
                "due_date": a.due_date,
                "instructions": a.instructions,
                "is_completed": comp.status in ["passed", "completed"]
                if comp
                else False,
                "status": comp.status if comp else "not_started",
                "score": comp.best_score if comp else None,
                "attempts_used": comp.attempts_used if comp else 0,
                "max_attempts": a.max_attempts,
                "passing_score_percent": a.passing_score_percent,
                "lock_after_due": a.lock_after_due,
            }
        )

    return my_assignments


@router.post("/{assignment_id}/complete/{user_id}")
def manually_complete_assignment(
    assignment_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """FUNC-002: Mentors/Admins can manually mark an assignment as complete for a user."""
    if current_user.get("role") not in ["LDAdmin", "Mentor", "GroupAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    assignment = (
        db.query(models.Assignment)
        .filter(models.Assignment.id == assignment_id)
        .first()
    )

    if not user or not assignment:
        raise HTTPException(status_code=404, detail="User or Assignment not found")

    # Scope Authorization Verification
    if current_user.get("role") != "LDAdmin":
        actor_id = int(current_user.get("sub", 0) or 0)
        if (
            current_user.get("role") == "GroupAdmin"
            and int(current_user.get("group_id", -1)) != user.group_id
        ):
            raise HTTPException(
                status_code=403,
                detail="Scope Violation: Cannot verify outside assigned node.",
            )
        elif current_user.get("role") == "Mentor":
            from models.auth import MentorGroupAssignment

            is_assigned = (
                db.query(MentorGroupAssignment)
                .filter_by(mentor_id=actor_id, group_id=user.group_id, is_active=True)
                .first()
            )
            if not is_assigned:
                raise HTTPException(
                    status_code=403,
                    detail="Scope Violation: Mentor not assigned to this entity's group.",
                )

    # 1. Update the official assignment lifecycle status
    from services.assignment_service import update_assignment_completion

    update_assignment_completion(
        db=db,
        user_id=user_id,
        bank_id=assignment.bank_id,
        coding_question_id=assignment.coding_question_id,
        score=assignment.bank.total_marks if assignment.bank else 100,
        total=assignment.bank.total_marks if assignment.bank else 100,
    )

    # 2. Create a manual "Verified" attempt for historical record keeping
    manual_attempt = models.Attempt(
        user_id=user_id,
        bank_id=assignment.bank_id,
        user_name=user.full_name,
        score=assignment.bank.total_marks if assignment.bank else 10,
        total=assignment.bank.total_marks if assignment.bank else 10,
        time_taken=0,
        is_anonymous=False,
        comment=f"Manually verified by {current_user.get('full_name')} (ID: {current_user['sub']})",
    )
    db.add(manual_attempt)
    db.commit()

    from services.audit_service import log_admin_action

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="MANUAL_COMPLETE_ASSIGNMENT",
        resource_type="ASSIGNMENT",
        resource_id=assignment_id,
        details={"user_id": user_id, "score": manual_attempt.score},
    )

    return {
        "message": "Success: Assignment marked as manually verified",
        "status": "verified",
    }


# ─── Assignment Governance (Full CRUD) ──────────────────────────────────────


@router.get("/group/{group_id}")
def get_group_assignments(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Retrieve all assignments targeting a group (direct or inherited from batch/vertical)."""
    assert_group_in_org(group_id, db, current_user)
    # Verify group exists
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Authorization: Admins/Mentors assigned to this group
    if current_user["role"] not in ["LDAdmin", "Mentor", "GroupAdmin"]:
        raise HTTPException(status_code=403)
    if (
        current_user["role"] == "GroupAdmin"
        and int(current_user.get("group_id", -1)) != group_id
    ):
        raise HTTPException(status_code=403)

    batch_id = group.batch_id
    vertical_id = group.batch.vertical_id if group.batch else None

    target_filters = [
        (models.Assignment.target_type == "group")
        & (models.Assignment.target_id == group_id)
    ]
    if batch_id:
        target_filters.append(
            (models.Assignment.target_type == "batch")
            & (models.Assignment.target_id == batch_id)
        )
    if vertical_id:
        target_filters.append(
            (models.Assignment.target_type == "vertical")
            & (models.Assignment.target_id == vertical_id)
        )

    assignments = (
        db.query(models.Assignment)
        .filter(models.Assignment.is_active.is_(True), or_(*target_filters))
        .all()
    )

    # FIX #4: missing return — function never returned the queried assignments
    return [
        {
            "assignment_id": a.id,
            "target_type": a.target_type,
            "target_id": a.target_id,
            "bank_id": a.bank_id,
            "coding_question_id": a.coding_question_id,
            "due_date": a.due_date,
            "instructions": a.instructions,
            "max_attempts": a.max_attempts,
            "lock_after_due": a.lock_after_due,
            "is_compulsory": a.is_compulsory,
            "created_at": a.created_at,
        }
        for a in assignments
    ]


@router.get("")  # matches /api/assignments
@router.get("/")  # matches /api/assignments/
def list_assignments(
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    page: int = 1,
    size: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """
    Strategic Oversight: Paginated list of assignments across the organization.
    Supports filtering by target entity (Vertical/Batch/Group).
    """
    if current_user.get("role") not in ["LDAdmin", "Mentor", "GroupAdmin"]:
        raise HTTPException(
            status_code=403,
            detail="Strategic Boundary: Unauthorized access to global assignment registry.",
        )

    from pagination import paginate

    query = db.query(models.Assignment).filter(models.Assignment.is_active.is_(True))

    # FIX #5: Scope filters for Mentor/GroupAdmin MUST run before paginate()
    # They were previously dead code because return paginate() was called first.
    if current_user.get("role") == "GroupAdmin":
        query = query.filter(
            models.Assignment.target_id == int(current_user["group_id"])
        )
    elif current_user.get("role") == "Mentor":
        from models.auth import MentorGroupAssignment

        mentor_id = int(current_user["sub"])
        assigned_group_ids = (
            db.query(MentorGroupAssignment.group_id)
            .filter(
                MentorGroupAssignment.mentor_id == mentor_id,
                MentorGroupAssignment.is_active == True,
            )
            .all()
        )
        assigned_group_ids = [g[0] for g in assigned_group_ids]
        query = query.filter(
            (models.Assignment.target_type == "group")
            & (models.Assignment.target_id.in_(assigned_group_ids))
        )

    if target_type:
        query = query.filter(models.Assignment.target_type == target_type)
    if target_id:
        query = query.filter(models.Assignment.target_id == target_id)

    return paginate(query.order_by(models.Assignment.created_at.desc()), page, size)


@router.patch("/{assignment_id}")
def update_assignment(
    assignment_id: int,
    updates: schemas.AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Allows administrators to refine assignment parameters (deadlines, attempts)."""
    if current_user.get("role") not in ["LDAdmin", "Mentor", "GroupAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    assignment = (
        db.query(models.Assignment)
        .filter(models.Assignment.id == assignment_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Permission check (Ownership/Scope)
    if current_user.get("role") != "LDAdmin" and assignment.created_by != int(
        current_user["sub"]
    ):
        raise HTTPException(
            status_code=403,
            detail="Scope Violation: You can only update assignments you created.",
        )

    for k, v in updates.model_dump(exclude_unset=True).items():
        setattr(assignment, k, v)

    db.commit()
    return assignment


@router.delete("/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Soft-delete an assignment to preserve historical completion data."""
    if current_user.get("role") not in ["LDAdmin", "Mentor", "GroupAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    assignment = (
        db.query(models.Assignment)
        .filter(models.Assignment.id == assignment_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404)

    if current_user.get("role") != "LDAdmin" and assignment.created_by != int(
        current_user["sub"]
    ):
        raise HTTPException(status_code=403, detail="Forbidden")

    assignment.is_active = False
    db.commit()
    return {"success": True, "message": "Assignment deactivated."}
