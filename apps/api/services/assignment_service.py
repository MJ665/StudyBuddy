from datetime import datetime, timezone

import models
from sqlalchemy import or_
from sqlalchemy.orm import Session


def update_assignment_completion(
    db: Session,
    user_id: int,
    bank_id: int | None = None,
    coding_question_id: int | None = None,
    score: int = 0,
    total: int = 1,
):
    """
    Updates or creates AssignmentCompletion for a user when they finish a task.
    Supports both quiz (bank_id) and coding (coding_question_id).
    """
    user_obj = db.query(models.User).filter(models.User.id == user_id).first()
    if not (user_obj and user_obj.group_id):
        return

    group = user_obj.group
    # 1. Direct group assignments
    target_filters_list = [
        (
            models.Assignment.target_type == "group",
            models.Assignment.target_id == user_obj.group_id,
        )
    ]

    # 2. Batch assignments (if group is in a batch)
    if group.batch_id:
        target_filters_list.append(
            (
                models.Assignment.target_type == "batch",
                models.Assignment.target_id == group.batch_id,
            )
        )

    # 3. Vertical assignments (via group or batch)
    vertical_id = group.vertical_id
    if not vertical_id and group.batch and group.batch.vertical_id:
        vertical_id = group.batch.vertical_id

    if vertical_id:
        target_filters_list.append(
            (
                models.Assignment.target_type == "vertical",
                models.Assignment.target_id == vertical_id,
            )
        )

    # 4. Department assignments (via group or vertical)
    department_id = group.department_id
    if not department_id and vertical_id:
        vertical = (
            db.query(models.Vertical).filter(models.Vertical.id == vertical_id).first()
        )
        if vertical:
            department_id = vertical.department_id

    if department_id:
        target_filters_list.append(
            (
                models.Assignment.target_type == "department",
                models.Assignment.target_id == department_id,
            )
        )

    # Combined filter for efficiency
    from sqlalchemy import and_

    conditions = [and_(t_type, t_id) for t_type, t_id in target_filters_list]

    # Find active assignments matching the resource
    query = db.query(models.Assignment).filter(
        models.Assignment.is_active.is_(True), or_(*conditions)
    )
    if bank_id:
        query = query.filter(models.Assignment.bank_id == bank_id)
    elif coding_question_id:
        query = query.filter(models.Assignment.coding_question_id == coding_question_id)
    else:
        return

    active_assignments = query.all()

    for assignment in active_assignments:
        # Check deadline lockout
        due_date = assignment.due_date
        if due_date and due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)

        if (
            assignment.lock_after_due
            and due_date
            and due_date < datetime.now(timezone.utc)
        ):
            continue

        completion = (
            db.query(models.AssignmentCompletion)
            .filter(
                models.AssignmentCompletion.assignment_id == assignment.id,
                models.AssignmentCompletion.user_id == user_id,
            )
            .first()
        )

        accuracy_pct = (score / total * 100) if total > 0 else 0
        passed = (
            assignment.passing_score_percent is None
            or accuracy_pct >= assignment.passing_score_percent
        )
        new_status = "passed" if passed else "failed"

        if completion:
            completion.attempts_used += 1
            if completion.best_score is None or score > completion.best_score:
                completion.best_score = score

            # Update status: once 'passed', stay 'passed'. Otherwise update to new_status.
            if completion.status != "passed":
                completion.status = new_status

            # Record first completion time regardless of pass/fail
            if completion.completed_at is None:
                completion.completed_at = datetime.now(timezone.utc)
        else:
            completion = models.AssignmentCompletion(
                assignment_id=assignment.id,
                user_id=user_id,
                best_score=score,
                attempts_used=1,
                status=new_status,
                completed_at=datetime.now(timezone.utc),
            )
            db.add(completion)

    db.commit()
