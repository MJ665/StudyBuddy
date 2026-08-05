"""advisory endpoints (moved verbatim from modules/ai/routers/generation.py)."""
from fastapi import APIRouter

from modules.ai.routers.generation_shared import *  # noqa: F401,F403
from modules.ai.routers.generation_shared import (  # noqa: F401
    _check_rate_limit,
    _get_llm,
    _repair_json,
    _strip_fences,
)

router = APIRouter()

@router.get("/learning-paths")
def get_saved_learning_paths(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """Retrieves all saved learning paths for the current user."""
    user_id = int(current_user["sub"])
    paths = (
        db.query(models.UserLearningPath)
        .filter(
            models.UserLearningPath.user_id == user_id,
            models.UserLearningPath.is_active.is_(True),
        )
        .order_by(models.UserLearningPath.created_at.desc())
        .all()
    )

    return [
        {
            "id": p.id,
            "topic": p.topic,
            "roadmap": json.loads(p.roadmap_json),
            "created_at": p.created_at,
        }
        for p in paths
    ]

@router.post("/learning-path")
async def generate_learning_path(
    req: LearningPathRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """
    Generates a personalised, week-by-week learning path for a given goal.
    """
    await _check_rate_limit(str(current_user["sub"]), "learning_path")

    # Refactored to use centralized ExecutiveAIService

    # ── Vector Context Retrieval (SEC-6.2)
    from services.vector_service import vector_service

    relevant_context = await vector_service.retrieve_relevant_context(
        user_id=int(current_user["sub"]), query=req.goal, top_k=3
    )

    context_str = ""
    if relevant_context:
        context_str = "\nUser's past learning history and preferences:\n"
        for c in relevant_context:
            context_str += f"- {c['content']}\n"

    prompt = f"""Create a personalised learning path for someone who wants to: "{req.goal}"
Current Level: {req.current_level}
Available Study Time: {req.available_hours_per_week} hours/week
{context_str}

Return a JSON object:
{{
  "goal": "the goal",
  "estimated_weeks": <number>,
  "phases": [
    {{
      "week_range": "Week 1-2",
      "title": "Phase title",
      "topics": ["topic1", "topic2"],
      "activities": ["activity1", "activity2"],
      "milestone": "What they'll be able to do at the end"
    }}
  ],
  "resources": ["book/course name", ...],
  "success_metric": "How to know you have achieved the goal"
}}

Make it practical, actionable, and achievable given the time constraint and their learning history."""

    # STRAT-AI-CACHE (Section 5.5): Redis first
    redis_key = f"ai:roadmap:{hashlib.sha256(req.goal.encode()).hexdigest()}"
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

    try:
        envelope = await ai_executive.generate_ai_response(prompt)
        if not envelope["ai_generated"]:
            return envelope

        raw = _repair_json(_strip_fences(envelope["data"]))
        path_data = json.loads(raw)

        # Persistence
        try:
            user_id = int(current_user["sub"])
            # Remove old ones if they exist. run_sync keeps the legacy bulk
            # delete working on an AsyncSession without a query rewrite.
            await db.run_sync(
                lambda sync_db: sync_db.query(models.UserLearningPath)
                .filter(
                    models.UserLearningPath.user_id == user_id,
                    models.UserLearningPath.topic == req.goal,
                )
                .delete()
            )

            new_path = models.UserLearningPath(
                user_id=user_id,
                topic=req.goal,
                roadmap_json=json.dumps(path_data),
                is_active=True,
            )
            db.add(new_path)
            await db.commit()
        except Exception as pe:
            await db.rollback()
            logger.error(f"Failed to save learning path: {pe}")

        # Cache in Redis
        try:
            await redis_client.set(
                redis_key, json.dumps(path_data), ex=604800
            )  # 1 week
        except Exception:
            pass

        envelope["data"] = path_data
        return envelope

    except Exception as e:
        logger.error(f"Learning path error: {traceback.format_exc()}")  # noqa: F821
        return {
            "ai_generated": False,
            "fallback_reason": f"Logic Error: {str(e)}",
            "data": None,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

@router.post("/next-topic")
def recommend_next_topic(
    req: NextTopicRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """
    Analyzes a user's quiz history and recommends the most valuable next topic to study.
    Uses performance gaps and attempt frequency for data-driven recommendations.
    """
    user_id = int(current_user["sub"])

    # Gather all user attempts with topic data
    attempts = (
        db.query(models.Attempt, models.QuestionBank)
        .join(models.QuestionBank, models.Attempt.bank_id == models.QuestionBank.id)
        .filter(models.Attempt.user_id == user_id)
        .all()
    )

    if not attempts:
        return {
            "recommendation": None,
            "reason": "No attempts yet. Start with any topic to get personalized recommendations!",
            "weak_topics": [],
            "strong_topics": [],
        }

    # Build topic performance map
    topic_data: dict = defaultdict(
        lambda: {"scores": [], "attempts": 0, "chapters": set()}
    )
    for attempt, bank in attempts:
        topic = bank.chapter or bank.name or "General"
        if attempt.total > 0:
            acc = (attempt.score / attempt.total) * 100
            topic_data[topic]["scores"].append(acc)
            topic_data[topic]["attempts"] += 1

    topic_summary = []
    for topic, data in topic_data.items():
        avg_acc = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
        topic_summary.append(
            {
                "topic": topic,
                "avg_accuracy": round(avg_acc, 1),
                "attempt_count": data["attempts"],
            }
        )

    # Sort: weakest first (performance gap)
    weak_topics = sorted(
        [t for t in topic_summary if t["avg_accuracy"] < 70],
        key=lambda x: x["avg_accuracy"],
    )
    strong_topics = sorted(
        [t for t in topic_summary if t["avg_accuracy"] >= 70],
        key=lambda x: x["avg_accuracy"],
        reverse=True,
    )

    # Simple rule-based recommendation (fast, no AI cost)
    if weak_topics:
        rec = weak_topics[0]
        reason = f"You're averaging only {rec['avg_accuracy']}% in '{rec['topic']}'. Focused practice here will have the highest impact on your overall score."
        return {
            "recommendation": rec["topic"],
            "reason": reason,
            "weak_topics": weak_topics[:3],
            "strong_topics": strong_topics[:3],
        }

    # All strong — recommend least-attempted
    least_practiced = sorted(topic_summary, key=lambda x: x["attempt_count"])
    if least_practiced:
        rec = least_practiced[0]
        return {
            "recommendation": rec["topic"],
            "reason": f"You're doing well across all topics! Practice '{rec['topic']}' more to maintain consistency.",
            "weak_topics": [],
            "strong_topics": strong_topics[:3],
        }

    return {
        "recommendation": None,
        "reason": "Keep practicing to unlock personalized recommendations!",
        "weak_topics": [],
        "strong_topics": [],
    }

@router.post("/ask")
async def ask_ai(
    req: AIAskRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """
    Generalized AI assistant endpoint with context fallback.
    """
    if is_injection(req.user_query):
        raise HTTPException(status_code=400, detail="Prompt injection detected.")

    user_id_str = str(current_user["sub"])
    await _check_rate_limit(user_id_str, "ask")

    # Gather context if possible
    context = ""
    if req.question_id:
        q = (
            await db.run_sync(lambda s: s.query(models.Question)
            .filter(models.Question.id == req.question_id)
            .first())
        )
        if q:
            context += f"Question context: {q.question}\nCorrect Option: {q.answer}\nExplanation: {q.user_description}\n"
    if req.attempt_id:
        att = (
            await db.run_sync(lambda s: s.query(models.Attempt).filter(models.Attempt.id == req.attempt_id).first())
        )
        if att:
            context += f"Attempt details: Score {att.score}/{att.total}.\n"

    # Call LLM
    llm = _get_llm(temperature=0.7)
    if not llm:
        # Fallback to predefined/rule-based answer
        return {
            "ai_generated": False,
            "fallback_reason": "Gemini API key not configured",
            "data": {
                "response": f"Thanks for asking! I'm here to help you study. You asked: '{req.user_query}'"
            },
        }

    from langchain_core.messages import HumanMessage, SystemMessage

    sys_prompt = "You are StudyBuddy AI, a highly encouraging and extremely knowledgeable learning assistant. Answer the user's questions clearly, accurately, and thoroughly. Format your response in clean Markdown."
    if context:
        sys_prompt += f"\nUse the following context to help answer the user query if relevant:\n{context}"

    messages = [SystemMessage(content=sys_prompt), HumanMessage(content=req.user_query)]

    try:
        res = llm.invoke(messages)
        return {"ai_generated": True, "data": {"response": res.content}}
    except Exception as e:
        logger.error(f"General AI assistant failed: {e}")
        return {
            "ai_generated": False,
            "fallback_reason": str(e),
            "data": {
                "response": f"I'm sorry, I'm having trouble connecting to my brain right now. You asked: '{req.user_query}'"
            },
        }
