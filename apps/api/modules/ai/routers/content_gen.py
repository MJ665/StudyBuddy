"""content_gen endpoints (moved verbatim from modules/ai/routers/generation.py)."""
from fastapi import APIRouter

from modules.ai.routers.generation_shared import *  # noqa: F401,F403
from modules.ai.routers.generation_shared import (  # noqa: F401
    _check_rate_limit,
    _get_llm,
    _repair_json,
    _strip_fences,
)

router = APIRouter()

@router.post("/review")
async def review_answer(
    query: AIQuery,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """Evaluates a user's answer using the LangGraph Review Engine."""
    user_id_str = str(current_user["sub"])
    await _check_rate_limit(user_id_str, "review")

    attempt = (
        await db.run_sync(lambda s: s.query(models.Attempt).filter(models.Attempt.id == query.attempt_id).first())
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if str(attempt.user_id) != user_id_str:
        role = current_user.get("role")
        if role not in ["LDAdmin", "GroupAdmin", "Mentor"]:
            raise HTTPException(status_code=403, detail="Unauthorized")

    question = (
        await db.run_sync(lambda s: s.query(models.Question)
        .filter(models.Question.id == query.question_id)
        .first())
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    user_answer_detail = None
    if attempt.descriptive_answers:
        for detail in attempt.descriptive_answers:
            if detail.get("question_id") == query.question_id:
                user_answer_detail = detail
                break

    if not user_answer_detail:
        raise HTTPException(status_code=404, detail="Answer details not found")

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 2) Redis Cache (STRAT-STABILIZE: Fast path)
    redis_key = f"ai:review:{query.question_id}:{hashlib.md5(user_answer_detail.get('user_answer', '').encode()).hexdigest()}:{hashlib.md5(query.user_query.encode()).hexdigest()}"
    try:
        cached_redis = await redis_client.get(redis_key)
        if cached_redis:
            # Proactive Intelligence Cache Invalidation (STRAT-CACHE-SYNC)
            try:
                user_id = current_user.get("id") or current_user.get("sub")
                if user_id:
                    await redis_client.delete(f"user_vectors:{user_id}")
                    await redis_client.delete(f"user_intel:{user_id}")
                    await redis_client.delete(f"user_atlas:{user_id}")
                    logger.info(f"Sync: Intelligence cache purged for user {user_id}")
            except Exception as e:
                logger.warning(f"Sync: Cache purge failed: {e}")
            return {
                "ai_generated": True,
                "fallback_reason": None,
                "data": {
                    "response": cached_redis,
                    "is_out_of_context": False,
                    "from_cache": True,
                    "cache_layer": "redis",
                },
                "generated_at": now_iso,
            }
    except Exception as e:
        logger.warning(f"Redis cache lookup failed for explain_quiz_answer: {e}")
        pass

    # 3) Postgres Cache (Section 1.1)
    cached = (
        await db.run_sync(lambda s: s.query(models.AICache)
        .filter(
            models.AICache.question_id == query.question_id,
            models.AICache.user_answer == (user_answer_detail.get("user_answer") or ""),
            models.AICache.user_query == query.user_query,
        )
        .first())
    )

    if cached:
        # Repopulate Redis
        try:
            await redis_client.set(redis_key, cached.ai_response, ex=86400)
        except Exception:
            pass
        return {
            "ai_generated": True,
            "fallback_reason": None,
            "data": {
                "response": cached.ai_response,
                "is_out_of_context": False,
                "from_cache": True,
                "cache_layer": "postgres",
            },
            "generated_at": now_iso,
        }

    try:
        # ── Vector Context Retrieval (SEC-6.2)
        from services.vector_service import vector_service

        relevant_context = await vector_service.retrieve_relevant_context(
            user_id=int(current_user["sub"]), query=query.user_query
        )

        result = run_review_graph(
            question_text=question.question,
            user_answer=user_answer_detail.get("user_answer") or "Skipped",
            correct_answer=user_answer_detail.get("correct_answer") or "N/A",
            user_query=query.user_query,
            user_note=user_answer_detail.get("note"),
            relevant_context=relevant_context,
        )

        ai_text = result.get("response_text", "No response generated.")

        # ── Vector Context Persistence (SEC-6.2)
        await vector_service.upsert_chat_memory(
            session_id=f"review:{query.attempt_id}",
            user_id=int(current_user["sub"]),
            role="user",
            content=query.user_query,
        )
        await vector_service.upsert_chat_memory(
            session_id=f"review:{query.attempt_id}",
            user_id=int(current_user["sub"]),
            role="assistant",
            content=ai_text,
        )

        # Save to both layers
        db.add(
            models.AICache(
                question_id=query.question_id,
                user_answer=user_answer_detail.get("user_answer") or "",
                user_query=query.user_query,
                ai_response=ai_text,
            )
        )
        await db.commit()

        try:
            await redis_client.set(redis_key, ai_text, ex=86400)
        except Exception:
            pass

        return {
            "ai_generated": True,
            "fallback_reason": None,
            "data": {
                "response": ai_text,
                "is_out_of_context": result.get("is_out_of_context", False),
                "from_cache": False,
            },
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"AI review error: {traceback.format_exc()}")  # noqa: F821
        if "429" in str(e) or "quota" in str(e).lower():
            raise HTTPException(status_code=429, detail="AI quota exceeded.")
        raise HTTPException(status_code=500, detail="AI request failed")

@router.post("/smart-quiz")
async def generate_smart_quiz(
    req: SmartQuizRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """
    AI-powered quiz generator. Creates MCQ questions on any topic using Gemini.
    Accessible to LDAdmin and GroupAdmin for content creation.
    """
    if current_user.get("role") not in ["LDAdmin", "GroupAdmin", "Mentor"]:
        raise HTTPException(
            status_code=403, detail="Only admins/mentors can generate AI quizzes"
        )

    if is_injection(req.topic):
        raise HTTPException(status_code=400, detail="Prompt injection detected.")

    await _check_rate_limit(str(current_user["sub"]), "quiz_gen")

    # STRAT-AI-CACHE: Redis first for AI Quiz Gen
    cache_hash = hashlib.sha256(
        f"{req.topic}|{req.difficulty}|{req.num_questions}|{req.language}|{req.question_type}".encode()
    ).hexdigest()
    redis_key = f"ai:quiz:{cache_hash}"

    # STRAT-FIX: Deduplication (Section 5.4) - Check for existing draft bank
    if req.save_as_draft:
        bank_name = f"AI Draft: {req.topic} ({req.difficulty})"
        existing = (
            await db.run_sync(lambda s: s.query(models.QuestionBank)
            .filter(models.QuestionBank.name == bank_name)
            .first())
        )
        if existing:
            q_count = (
                await db.run_sync(lambda s: s.query(models.Question)
                .filter(models.Question.bank_id == existing.id)
                .count())
            )
            if q_count >= req.num_questions:
                return {
                    "ai_generated": True,
                    "fallback_reason": None,
                    "data": {
                        "topic": req.topic,
                        "bank_id": existing.id,
                        "status": "existing_draft_found",
                        "generated_count": q_count,
                        "from_cache": True,
                    },
                    "generated_at": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                }

    _qt = getattr(req, "question_type", "mcq_single")
    if _qt in ("short_answer", "essay"):
        _kind = "short-answer (brief)" if _qt == "short_answer" else "essay"
        _schema = (
            '{\n'
            '  "question": "The full question text",\n'
            '  "model_answer": "A concise ideal answer used for AI grading",\n'
            '  "rubric": "The key points a good answer must cover",\n'
            '  "explanation": "Why this is the expected answer",\n'
            f'  "difficulty": "{req.difficulty}"\n'
            '}'
        )
        _rules = "- Provide a clear model_answer and a rubric of key points\n- These are free-text questions: do NOT include options"
        _intro = f'Generate exactly {req.num_questions} {_kind} questions on the topic: "{req.topic}".'
    elif _qt == "true_false":
        _schema = (
            '{\n'
            '  "question": "A statement to judge as true or false",\n'
            '  "options": ["True", "False"],\n'
            '  "correct_answer": "True or False",\n'
            '  "explanation": "Why",\n'
            f'  "difficulty": "{req.difficulty}"\n'
            '}'
        )
        _rules = "- correct_answer must be exactly 'True' or 'False'"
        _intro = f'Generate exactly {req.num_questions} true/false questions on the topic: "{req.topic}".'
    else:
        _schema = (
            '{\n'
            '  "question": "The full question text",\n'
            '  "options": ["Option A text", "Option B text", "Option C text", "Option D text"],\n'
            '  "correct_answer": "Full text of the correct option (not just the letter)",\n'
            '  "explanation": "Brief explanation (1-2 sentences)",\n'
            f'  "difficulty": "{req.difficulty}"\n'
            '}'
        )
        _rules = "- All 4 options must be plausible (no obviously wrong distractors)"
        _intro = f'Generate exactly {req.num_questions} multiple-choice quiz questions on the topic: "{req.topic}".'

    prompt = f"""{_intro}
Difficulty: {req.difficulty}
Language: {req.language}

Return ONLY a JSON array. Each element must have:
{_schema}

Rules:
- Questions must be factual and directly related to the topic
{_rules}
- The explanation must be clear and educational
- Return ONLY the JSON array, no surrounding text or markdown code fences
- Ensure the JSON is structurally complete and valid
- DO NOT truncate the response; generate all requested questions fully
"""

    raw = None
    cached_q = None
    try:
        try:
            cached_str = await redis_client.get(redis_key)
            if cached_str:
                cached_q = json.loads(cached_str)
        except Exception:
            pass

        envelope: dict[str, Any] = {
            "ai_generated": True,
            "fallback_reason": None,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        if cached_q:
            questions = cached_q
        else:
            envelope = await ai_executive.generate_ai_response(prompt)
            if not envelope["ai_generated"]:
                return envelope

            raw = _repair_json(_strip_fences(envelope["data"]))
            raw_qs = json.loads(raw)
            from schemas_ai import AIQuizQuestionBase

            questions = []
            for item in raw_qs:
                try:
                    if _qt in ("short_answer", "essay"):
                        # Free-text: require question + model_answer (no options).
                        if not item.get("question") or not item.get("model_answer"):
                            raise ValueError("missing question/model_answer")
                        questions.append(item)
                    else:
                        q_val = AIQuizQuestionBase(**item)
                        # Preserve the generated question_type if the model set one.
                        questions.append({**q_val.model_dump(), "question_type": item.get("question_type", _qt)})
                except Exception as e:
                    logger.warning(f"AI Quiz JSON array element validation failed: {e}")

            if not questions:
                return {
                    "ai_generated": False,
                    "fallback_reason": "AI response failed strict structural validation.",
                }

            try:
                await redis_client.set(redis_key, json.dumps(questions), ex=86400)
            except Exception:
                pass

        # Persistence (Section 5.4): Save as Draft Question Bank
        if req.save_as_draft:
            try:
                group_id = req.group_id or current_user.get("group_id")
                new_bank = models.QuestionBank(
                    organization_id=caller_org_id(current_user),
                    super_organization_id=caller_super_org_id(current_user, db),
                    name=f"AI Draft: {req.topic} ({req.difficulty})",
                    description=f"AI-generated questions for {req.topic}. Review before publishing.",
                    subscriber_groups=[group_id] if group_id else [],
                    bank_type="practice",
                    created_by=int(current_user["sub"]),
                    icon_slug="brain",
                )
                db.add(new_bank)
                await db.flush()

                for q in questions:
                    # Robust Deduplication
                    existing_q = (
                        await db.run_sync(lambda s: s.query(models.Question)
                        .filter(
                            models.Question.bank_id == new_bank.id,
                            models.Question.question == q["question"],
                        )
                        .first())
                    )
                    if existing_q:
                        continue

                    _is_free = _qt in ("short_answer", "essay")
                    new_q = models.Question(
                        organization_id=new_bank.organization_id,
                        super_organization_id=new_bank.super_organization_id,
                        bank_id=new_bank.id,
                        question=q["question"],
                        options=[] if _is_free else q.get("options", []),
                        answer="" if _is_free else q.get("correct_answer", ""),
                        question_type=_qt,
                        model_answer=q.get("model_answer") if _is_free else None,
                        rubric={"criteria": q.get("rubric")} if (_is_free and q.get("rubric")) else None,
                        difficulty=q.get("difficulty", req.difficulty),
                        concept_tags=[req.topic],
                        needs_review=True,
                    )
                    db.add(new_q)

                await db.commit()
                # Return standard envelope with draft info
                envelope["data"] = {
                    "topic": req.topic,
                    "bank_id": new_bank.id,
                    "status": "draft_created",
                    "generated_count": len(questions),
                }
                return envelope
            except Exception:
                logger.error(f"Failed to save AI draft: {traceback.format_exc()}")  # noqa: F821
                await db.rollback()
                # Fall through to return questions anyway

        envelope["data"] = {
            "topic": req.topic,
            "difficulty": req.difficulty,
            "questions": questions,
            "generated_count": len(questions),
        }
        return envelope
    except json.JSONDecodeError as e:
        logger.error(f"Smart quiz JSON decode error. Raw output: {repr(raw)[:500]}")
        raise HTTPException(
            status_code=500, detail=f"AI returned invalid JSON: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Smart quiz generation error: {traceback.format_exc()}")  # noqa: F821
        raise HTTPException(status_code=500, detail=f"Quiz generation failed: {str(e)}")

@router.post("/explain")
async def explain_question(
    req: ExplainRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """
    Deep explanation of a quiz question using the unified Review Engine.
    """
    if is_injection(req.question_text) or (
        req.user_answer and is_injection(req.user_answer)
    ):
        raise HTTPException(status_code=400, detail="Prompt injection detected.")

    await _check_rate_limit(str(current_user["sub"]), "explain")

    # STRAT-AI-CACHE (Section 5.3): Multi-vector composite hash for explanations
    composite_payload = (
        f"{req.question_text}|{req.correct_answer}|{req.user_answer or ''}"
    )
    cache_hash = hashlib.sha256(composite_payload.encode()).hexdigest()
    redis_key = f"ai:explain:{cache_hash}"

    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return {
                "ai_generated": True,
                "fallback_reason": None,
                "data": {"explanation": cached, "from_cache": True},
                "generated_at": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            }
    except Exception as e:
        logger.warning(f"Redis cache lookup failed: {e}")
        pass

    try:
        # Use the unified ReviewEngine with a synthesized deep-explanation query
        query_text = "Provide a deep explanation: 1) Why the correct answer is right. 2) A real-world analogy. 3) One common misconception."
        if req.user_answer and req.user_answer != req.correct_answer:
            query_text += f" Also explain why the student's answer '{req.user_answer}' was incorrect."

        result = run_review_graph(
            question_text=req.question_text,
            user_answer=req.user_answer or "Skipped",
            correct_answer=req.correct_answer,
            user_query=query_text,
            user_note=req.context,
        )

        content = result.get("response_text", "No response generated.")

        # Cache successful response
        if content and not result.get("is_out_of_context"):
            try:
                await redis_client.set(redis_key, content, ex=86400)  # 24h cache
            except Exception:
                pass

        return {
            "ai_generated": True,
            "fallback_reason": None,
            "data": {
                "explanation": content,
                "from_cache": False,
                "is_out_of_context": result.get("is_out_of_context", False),
            },
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Explanation error: {traceback.format_exc()}")  # noqa: F821
        return {
            "ai_generated": False,
            "fallback_reason": f"Logic Error: {str(e)}",
            "data": None,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

@router.post("/summarize")
async def summarize_content(
    req: SummarizeRequest, current_user: dict = Depends(verify_token)
):
    """
    Converts raw text (from a PDF/resource) into study notes, flashcards,
    or practice questions using Gemini.
    """
    await _check_rate_limit(str(current_user["sub"]), "summarize")

    if len(req.content) > 8000:
        req.content = req.content[:8000] + "\n[Content truncated for processing]"

    # STRAT-AI-CACHE: Redis first
    cache_hash = hashlib.sha256(
        f"{req.content}|{req.summary_type}".encode()
    ).hexdigest()
    redis_key = f"ai:summarize:{cache_hash}"
    try:
        cached_str = await redis_client.get(redis_key)
        if cached_str:
            data = json.loads(cached_str)
            return {
                "ai_generated": True,
                "fallback_reason": None,
                "data": data,
                "generated_at": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            }
    except Exception:
        pass

    # Refactored to use centralized ExecutiveAIService

    if req.summary_type == "study_notes":
        prompt = f"""Convert the following content into clear, structured study notes.
Use bullet points, bold key terms, and organize by topic.

Content:
{req.content}

Format:
# Topic Title
## Key Concepts
- **Term**: Definition
## Important Points
- Point 1
## Summary
One paragraph summary"""
        json_output = False

    elif req.summary_type == "flashcards":
        prompt = f"""Generate 10-15 flashcards from this content as a JSON array.
Each flashcard: {{"front": "Question/Term", "back": "Answer/Definition"}}

Content:
{req.content}"""
        json_output = True

    else:  # quiz_questions
        prompt = f"""Generate 5 multiple-choice questions from this content as a JSON array.
Each: {{"question": "...", "options": ["A", "B", "C", "D"], "correct_answer": "Full answer text", "explanation": "..."}}

Content:
{req.content}"""
        json_output = True

    try:
        envelope = await ai_executive.generate_ai_response(prompt)
        if not envelope["ai_generated"]:
            return envelope

        raw = envelope["data"]

        if json_output:
            raw = _repair_json(_strip_fences(raw))
            try:
                data = json.loads(raw)
                envelope["data"] = {"type": req.summary_type, "content": data}
            except Exception:
                envelope["data"] = {
                    "type": req.summary_type,
                    "content": {"raw": raw, "error": "JSON parsing failed"},
                }
        else:
            envelope["data"] = {"type": req.summary_type, "content": raw}

        # Cache in Redis for 24h
        try:
            await redis_client.set(redis_key, json.dumps(envelope["data"]), ex=86400)
        except Exception:
            pass

        return envelope

    except Exception as e:
        logger.error(f"Summarize error: {traceback.format_exc()}")  # noqa: F821
        return {
            "ai_generated": False,
            "fallback_reason": f"Logic Error: {str(e)}",
            "data": None,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

@router.post("/leaderboard")
async def summarize_leaderboard(
    req: LeaderboardSummaryRequest, current_user: dict = Depends(verify_token)
):
    """
    AI synthesizes the current leaderboard to highlight top performers and trends.
    """
    await _check_rate_limit(str(current_user["sub"]), "leaderboard")

    if not req.leaderboard_data:
        return {
            "summary": "Not enough data on the leaderboard yet to generate a summary."
        }

    prompt = f"""You are the StudyBuddy Chief Performance Analyst.
Analyze this snapshot of the {req.group_name} leaderboard and write a 2-3 sentence executive summary.
Highlight the top performer and mention if it's a tight race or a runaway lead.

Leaderboard Data:
{json.dumps(req.leaderboard_data[:10], indent=2)}

Keep the tone encouraging, professional, and slightly competitive."""

    try:
        envelope = await ai_executive.generate_ai_response(prompt)
        if not envelope["ai_generated"]:
            return {
                "summary": "The AI is currently analyzing other performance metrics. Check back later."
            }

        return {"summary": _strip_fences(envelope["data"])}
    except Exception as e:
        logger.error(f"Leaderboard summary error: {e}")
        return {"summary": "Could not generate summary at this time."}
