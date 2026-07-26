"""banks endpoints (moved verbatim from routers/quiz.py)."""
from fastapi import APIRouter

from modules.assessment.routers.quiz_shared import *  # noqa: F401,F403
from modules.assessment.routers.quiz_shared import (  # noqa: F401
    _certificate_token,
    _verify_certificate_token,
)

router = APIRouter()

@router.get("/topics")
async def get_unique_topics(db: AsyncSession = Depends(get_async_db)):
    """Returns a unique list of chapters/topics from all question banks for suggestions."""
    import json

    from cache_manager import redis_client

    redis_key = "quiz:topics"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    topics = await db.run_sync(lambda s: s.query(models.QuestionBank.chapter).distinct().all())
    res = [t[0] for t in topics if t[0]]

    try:
        await redis_client.set(redis_key, json.dumps(res), ex=3600)
    except Exception:
        pass

    return res

@router.get("/banks")
def get_banks(
    course_id: Optional[int] = None,
    page: int = 1,
    size: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    query = (
        db.query(
            models.QuestionBank,
            func.count(models.Question.id.distinct()).label("question_count"),
            func.count(models.Attempt.id.distinct()).label("attempt_count"),
        )
        .outerjoin(models.Question, models.QuestionBank.id == models.Question.bank_id)
        .outerjoin(models.Attempt, models.QuestionBank.id == models.Attempt.bank_id)
    )

    if course_id:
        query = query.filter(models.QuestionBank.course_id == course_id)

    # For LDAdmin, return all banks
    if current_user.get("role") == "LDAdmin":
        pass  # no additional filter
    else:
        # Get accessible course IDs for this user's group
        user_group = (
            db.query(models.Group)
            .filter(models.Group.id == current_user["group_id"])
            .first()
        )
        accessible_course_ids = []
        if user_group and user_group.batch_id:
            batch = (
                db.query(models.Batch)
                .filter(models.Batch.id == user_group.batch_id)
                .first()
            )
            if batch:
                vc_list = (
                    db.query(models.VerticalCourse)
                    .filter(models.VerticalCourse.vertical_id == batch.vertical_id)
                    .all()
                )
                accessible_course_ids = [vc.course_id for vc in vc_list]

        # V2 fallback: if no batch_id, show all banks linked to any group course (backward compat)
        if not accessible_course_ids:
            # Find courses that have banks linked to them (V2 behavior)
            courses = (
                db.query(models.Course)
                .join(models.QuestionBank)
                .filter(models.Course.is_active.is_(True))
                .distinct()
                .all()
            )
            accessible_course_ids = [c.id for c in courses]

        # Strictly enforce visibility scoping
        query = query.filter(
            or_(
                models.QuestionBank.bank_type == "Official",
                models.QuestionBank.visibility_scope == "org-public",
                and_(
                    models.QuestionBank.visibility_scope == "group-private",
                    models.QuestionBank.subscriber_groups.contains(
                        [int(current_user["group_id"])]
                    ),
                ),
                and_(
                    models.QuestionBank.visibility_scope == "vertical",
                    models.QuestionBank.course_id.in_(accessible_course_ids),
                ),
                (
                    db.query(models.User.role)
                    .filter(models.User.id == models.QuestionBank.created_by)
                    .as_scalar()
                    == "LDAdmin"
                ),
                models.QuestionBank.created_by == int(current_user["sub"]),
            )
        )

    query = query.group_by(models.QuestionBank.id).order_by(
        models.QuestionBank.id.desc()
    )
    paginated = paginate(query, page, size)

    banks = []
    for bank, q_count, a_count in paginated.items:
        bank_dict = {c.name: getattr(bank, c.name) for c in bank.__table__.columns}
        bank_dict["question_count"] = q_count
        bank_dict["attempt_count"] = a_count
        bank_dict["total_attempts"] = a_count  # the Library UI reads total_attempts
        banks.append(bank_dict)

    return {
        "items": banks,
        "total": paginated.total,
        "page": paginated.page,
        "size": paginated.size,
        "pages": paginated.pages,
    }

@router.post("/banks")
def create_bank(
    bank_data: schemas.QuestionBankCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    if not bank_data.questions:
        raise HTTPException(
            status_code=400, detail="At least one question is required."
        )

    if bank_data.bank_type == "Official" and current_user.get("role") != "LDAdmin":
        raise HTTPException(
            status_code=403, detail="Only LDAdmin can create Official banks"
        )

    new_bank = models.QuestionBank(
        organization_id=caller_org_id(current_user),
        super_organization_id=caller_super_org_id(current_user, db),
        course_id=bank_data.course_id,
        name=bank_data.name,
        sprint_name=bank_data.sprint_name,
        chapter=bank_data.chapter,
        difficulty=bank_data.difficulty,
        # created_by is NOT NULL and must be the authenticated author, not a
        # client-supplied value (which defaulted to None → 500, and let a caller
        # spoof authorship). Take it from the token.
        created_by=int(current_user["sub"]),
        description=bank_data.description,
        time_per_question=bank_data.time_per_question,
        max_questions=bank_data.max_questions,
        show_timer=bank_data.show_timer,
        shuffle=bank_data.shuffle,
        allow_descriptive=bank_data.allow_descriptive,
        bank_type=bank_data.bank_type,
        is_org_public=True if current_user.get("role") == "LDAdmin" else False,
    )
    db.add(new_bank)
    db.commit()
    db.refresh(new_bank)

    for q in bank_data.questions:
        resolved_ans = resolve_answer(q.answer, q.options)
        db_q = models.Question(
            organization_id=new_bank.organization_id,
            super_organization_id=new_bank.super_organization_id,
            bank_id=new_bank.id,
            question=q.question,
            options=q.options,
            answer=resolved_ans,
            difficulty=q.difficulty or bank_data.difficulty,
            user_description=q.user_description,
            has_code=q.has_code,
            code_language=q.code_language,
            concept_tags=q.concept_tags,
        )
        db.add(db_q)

    db.commit()

    log_admin_action(
        db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="CREATE_BANK",
        resource_type="BANK",
        resource_id=new_bank.id,
        details={"name": new_bank.name, "course_id": new_bank.course_id},
    )

    return {"id": new_bank.id, "message": "Bank created successfully!"}

@router.post("/banks/import")
async def import_bank(
    course_id: int,
    name: str = Query(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """Import a question bank from CSV or Excel."""
    if current_user["role"] not in ["LDAdmin", "Mentor", "GroupAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    questions = []
    content = await file.read()

    if file.filename and file.filename.endswith(".csv"):
        stream = io.StringIO(content.decode("utf-8"))
        reader = csv.DictReader(stream)
        for row in reader:
            q_text = row.get("Question", "").strip()
            if not q_text:
                continue

            options = [row.get(f"Option {i}", "").strip() for i in range(1, 5)]
            options = [o for o in options if o]

            questions.append(
                {
                    "question": q_text,
                    "options": options,
                    "answer": row.get("Answer", "").strip(),
                    "difficulty": row.get("Difficulty", "Medium"),
                    "concept_tags": [
                        t.strip() for t in row.get("Tags", "").split(",") if t.strip()
                    ],
                }
            )

    elif file.filename and file.filename.endswith((".xlsx", ".xls")):
        if not openpyxl:
            raise HTTPException(status_code=500, detail="Excel parser not installed")

        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active
        assert ws is not None
        headers = [str(cell.value) for cell in ws[1]]

        for row in ws.iter_rows(min_row=2, values_only=True):
            data = dict(zip(headers, row))
            q_text = str(data.get("Question", "")).strip()
            if not q_text or q_text == "None":
                continue

            options = [str(data.get(f"Option {i}", "")).strip() for i in range(1, 5)]
            options = [o for o in options if o and o != "None"]

            questions.append(
                {
                    "question": q_text,
                    "options": options,
                    "answer": str(data.get("Answer", "")).strip(),
                    "difficulty": str(data.get("Difficulty", "Medium")),
                    "concept_tags": str(data.get("Tags", "")).split(",")
                    if data.get("Tags")
                    else [],
                }
            )

    if not questions:
        raise HTTPException(status_code=400, detail="No valid questions found in file")

    # Reuse create_bank logic
    bank_data = schemas.QuestionBankCreate(
        name=name,
        course_id=course_id,
        bank_type="Standard",
        created_by=int(current_user["sub"]),
        questions=[schemas.QuestionCreate(**q) for q in questions],
    )
    return create_bank(bank_data, db, current_user)

@router.get("/banks/{bank_id}")
def get_bank(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    bank = (
        db.query(models.QuestionBank).filter(models.QuestionBank.id == bank_id).first()
    )
    # Banks are shared CONTENT: a caller may only act on their customer's banks.
    # (was role-only via require_admin/verify_token — an admin in org A could
    # read/edit/delete org B's bank.)
    assert_same_super_org(bank, current_user, db, "Bank")

    # Permission check for non-admins
    if current_user.get("role") not in ["LDAdmin", "Admin", "GroupAdmin", "Mentor"]:
        user_group = (
            db.query(models.Group)
            .filter(models.Group.id == current_user["group_id"])
            .first()
        )
        if user_group and user_group.batch_id:
            # Check if this bank's course belongs to the user's vertical
            accessible = (
                db.query(models.VerticalCourse)
                .filter(
                    models.VerticalCourse.vertical_id == user_group.batch.vertical_id,
                    models.VerticalCourse.course_id == bank.course_id,
                )
                .first()
            )
            if not accessible and not bank.is_org_public:
                raise HTTPException(status_code=403, detail="Forbidden")

    return bank

@router.patch("/banks/{bank_id}")
def update_bank_metadata(
    bank_id: int,
    updates: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """VI: Bank Metadata Editor — Admin can edit bank metadata."""
    bank = (
        db.query(models.QuestionBank).filter(models.QuestionBank.id == bank_id).first()
    )
    # Banks are shared CONTENT: a caller may only act on their customer's banks.
    # (was role-only via require_admin/verify_token — an admin in org A could
    # read/edit/delete org B's bank.)
    assert_same_super_org(bank, current_user, db, "Bank")
    if bank.course_id and current_user.get("role") not in ["LDAdmin", "Admin"]:
        course = (
            db.query(models.Course).filter(models.Course.id == bank.course_id).first()
        )
        if (
            course
            and hasattr(course, "group_id")
            and course.group_id
            and course.group_id != current_user.get("group_id")
        ):
            raise HTTPException(status_code=403, detail="Forbidden")

    allowed_fields = [
        "name",
        "description",
        "difficulty",
        "sprint_name",
        "chapter",
        "time_per_question",
        "max_questions",
        "show_timer",
        "shuffle",
        "allow_descriptive",
    ]
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(bank, key, value)
    db.commit()
    return {"success": True}

@router.delete("/banks/{bank_id}")
def delete_bank(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    bank = (
        db.query(models.QuestionBank).filter(models.QuestionBank.id == bank_id).first()
    )
    # Banks are shared CONTENT: a caller may only act on their customer's banks.
    # (was role-only via require_admin/verify_token — an admin in org A could
    # read/edit/delete org B's bank.)
    assert_same_super_org(bank, current_user, db, "Bank")
    bank_name = bank.name
    bank_id_val = bank.id
    db.delete(bank)
    db.commit()

    log_admin_action(
        db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="DELETE_BANK",
        resource_type="BANK",
        resource_id=bank_id_val,
        details={"name": bank_name},
    )

    return {"success": True}

@router.get("/banks/{bank_id}/questions", response_model=List[schemas.QuestionResponse])
def get_bank_questions(
    bank_id: int,
    max_qs: Optional[int] = Query(None, alias="max"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    bank = (
        db.query(models.QuestionBank).filter(models.QuestionBank.id == bank_id).first()
    )
    # Banks are shared CONTENT: a caller may only act on their customer's banks.
    # (was role-only via require_admin/verify_token — an admin in org A could
    # read/edit/delete org B's bank.)
    assert_same_super_org(bank, current_user, db, "Bank")

    # ENFORCEMENT: Check if user is eligible for this bank (Task limits, Assignment mandates)
    # JWT payload uses "sub" for user ID
    user_id = int(current_user["sub"])
    eligible, reason = check_attempt_eligibility(user_id, bank_id, db)
    if not eligible:
        raise HTTPException(status_code=403, detail=reason)

    query = db.query(models.Question).filter(models.Question.bank_id == bank_id)
    if bank.shuffle:
        query = query.order_by(func.random())

    limit = max_qs or bank.max_questions
    if limit and limit > 0:
        query = query.limit(limit)

    # QuestionResponse schema will strip out the "answer" field automatically — zero leakage
    return query.all()

@router.get("/bank-library")
def get_bank_library(
    difficulty: Optional[str] = None,
    course_name: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """List all org-public banks available for cloning."""
    if current_user.get("role") not in ["GroupAdmin", "Mentor", "LDAdmin", "Admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only admins and mentors can access the bank library",
        )

    query = db.query(models.QuestionBank).filter(models.QuestionBank.is_org_public)
    if difficulty:
        query = query.filter(models.QuestionBank.difficulty == difficulty)

    # Defensive cap (rule §12.7): the org-public library grows unbounded.
    # QuestionBank has no created_at column; id is monotonic, so newest-first.
    banks = query.order_by(models.QuestionBank.id.desc()).limit(500).all()
    result = []
    for bank in banks:
        q_count = (
            db.query(func.count(models.Question.id))
            .filter(models.Question.bank_id == bank.id)
            .scalar()
        )
        bank_dict = {c.name: getattr(bank, c.name) for c in bank.__table__.columns}
        bank_dict["question_count"] = q_count
        result.append(bank_dict)
    return result

@router.post("/banks/{bank_id}/clone")
def clone_bank(
    bank_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Clone an org-public bank into the current user's course."""
    if current_user.get("role") not in ["GroupAdmin", "Mentor", "LDAdmin", "Admin"]:
        raise HTTPException(status_code=403)

    source_bank = (
        db.query(models.QuestionBank).filter(models.QuestionBank.id == bank_id).first()
    )
    assert_same_super_org(source_bank, current_user, db, "Bank")
    if not source_bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    if not source_bank.is_org_public and current_user.get("role") != "LDAdmin":
        raise HTTPException(
            status_code=403, detail="This bank is not available for cloning"
        )

    target_course_id = body.get("target_course_id")

    new_bank = models.QuestionBank(
        organization_id=caller_org_id(current_user),
        super_organization_id=caller_super_org_id(current_user, db),
        course_id=target_course_id,
        name=f"{source_bank.name} (Clone)",
        sprint_name=source_bank.sprint_name,
        chapter=source_bank.chapter,
        description=source_bank.description,
        difficulty=source_bank.difficulty,
        created_by=int(current_user["sub"]),
        bank_type="practice",
        time_per_question=source_bank.time_per_question,
        max_questions=source_bank.max_questions,
        show_timer=source_bank.show_timer,
        shuffle=source_bank.shuffle,
        allow_descriptive=source_bank.allow_descriptive,
        is_org_public=False,
        cloned_from_bank_id=bank_id,
    )
    db.add(new_bank)
    db.flush()

    source_questions = (
        db.query(models.Question).filter(models.Question.bank_id == bank_id).all()
    )
    for q in source_questions:
        new_q = models.Question(
            organization_id=new_bank.organization_id,
            super_organization_id=new_bank.super_organization_id,
            bank_id=new_bank.id,
            question=q.question,
            options=q.options,
            answer=q.answer,
            difficulty=q.difficulty,
            user_description=q.user_description,
            has_code=q.has_code,
            code_language=q.code_language,
            concept_tags=q.concept_tags,
        )
        db.add(new_q)
    db.commit()

    log_admin_action(
        db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="CLONE_BANK",
        resource_type="BANK",
        resource_id=new_bank.id,
        details={"source_bank_id": bank_id, "target_course_id": target_course_id},
    )

    return {"message": "Bank cloned successfully", "new_bank_id": new_bank.id}

@router.patch("/banks/{bank_id}/publish")
def publish_bank(
    bank_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """LDAdmin can publish banks to the entire organization."""
    if current_user.get("role") != "LDAdmin":
        raise HTTPException(
            status_code=403, detail="Only LDAdmin can publish banks to org"
        )

    bank = (
        db.query(models.QuestionBank).filter(models.QuestionBank.id == bank_id).first()
    )
    assert_same_super_org(bank, current_user, db, "Bank")

    is_org_public = body.get("is_org_public", True)
    bank.is_org_public = is_org_public
    db.commit()

    from services.audit_service import log_admin_action

    log_admin_action(
        db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="PUBLISH_BANK",
        resource_type="BANK",
        resource_id=bank_id,
        details={"is_org_public": is_org_public},
    )

    return {"success": True, "is_org_public": is_org_public}

@router.post("/report")
def report_question(
    report: schemas.QuestionReportCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """PHASE-3: Enables users to flag issues with specific questions."""
    db_report = models.QuestionReport(
        question_id=report.question_id,
        reporter_id=int(current_user["sub"]),
        reason=report.reason,
        comment=report.comment,
    )
    db.add(db_report)
    db.commit()
    return {"success": True, "message": "Report submitted for administrative review."}

@router.put("/questions/{question_id}")
def update_question(  # noqa: F811
    question_id: int,
    updates: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """
    Granular Question Editor. Fix typos or update options without re-uploading banks.
    """
    q = db.query(models.Question).filter(models.Question.id == question_id).first()
    assert_same_super_org(q, current_user, db, "Question")

    # Permission check: must own the bank or be LDAdmin
    bank = q.bank
    if current_user["role"] != "LDAdmin" and bank.created_by != int(
        current_user["sub"]
    ):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You can only edit questions in banks you created.",
        )

    allowed_fields = [
        "question",
        "options",
        "answer",
        "difficulty",
        "user_description",
        "has_code",
        "code_language",
        "concept_tags",
    ]
    for key, value in updates.items():
        if key in allowed_fields:
            if key == "answer" and q.options:
                # Re-resolve if answer is A/B/C/D
                value = resolve_answer(value, q.options)
            setattr(q, key, value)

    db.commit()
    return {"success": True, "message": "Question updated successfully."}

@router.delete("/questions/{question_id}")
def delete_question(  # noqa: F811
    question_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """
    Remove a single question from a bank.
    """
    q = db.query(models.Question).filter(models.Question.id == question_id).first()
    assert_same_super_org(q, current_user, db, "Question")

    bank = q.bank
    if current_user["role"] != "LDAdmin" and bank.created_by != int(
        current_user["sub"]
    ):
        raise HTTPException(status_code=403, detail="Forbidden")

    db.delete(q)
    db.commit()
    return {"success": True, "message": "Question deleted."}
