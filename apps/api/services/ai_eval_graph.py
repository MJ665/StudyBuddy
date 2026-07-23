"""AI code-evaluation pipeline (LangGraph eval flow).

This module contains the evaluation graph nodes and the run_evaluation_graph
public API.
"""
from __future__ import annotations

from services.ai_languages import *  # noqa: F401,F403
from services.ai_shared import (
    _get_llm,
    get_language_entry,
    sanitize_input,
)


# ── Pydantic Output Schemas (Guardrails) ──────────────────────────────────────


class RubricDetail(BaseModel):
    correctness: int = Field(default=0, ge=0, le=100)
    code_quality: int = Field(default=0, ge=0, le=100)
    best_practices: int = Field(default=0, ge=0, le=100)
    completeness: int = Field(default=0, ge=0, le=100)
    language_idioms: int = Field(default=0, ge=0, le=100)

    @field_validator("*", mode="before")
    @classmethod
    def clamp(cls, v):
        try:
            return max(0, min(100, int(float(v or 0))))
        except (TypeError, ValueError):
            return 0


class EvaluationResult(BaseModel):
    """
    Guardrails: enforces structured, validated output from Gemini for every evaluation.
    The AI score is the primary score. Mentor can override with mentor_score later.
    """

    is_correct: bool = Field(default=False)
    passed: bool = Field(default=False)
    score: int = Field(default=0, ge=0, le=100)
    grade: str = Field(default="F")
    feedback: str = Field(default="Unable to evaluate. Please try again.")
    language_specific_feedback: Optional[str] = Field(default=None)
    criteria_met: List[str] = Field(default_factory=list)
    criteria_failed: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    time_complexity: Optional[str] = Field(default=None)
    space_complexity: Optional[str] = Field(default=None)
    security_issues: List[str] = Field(default_factory=list)
    best_practice_violations: List[str] = Field(default_factory=list)
    rubric: RubricDetail = Field(default_factory=RubricDetail)
    estimated_production_readiness: Optional[str] = Field(default=None)
    # Honesty flag: this platform evaluates code with AI review only (no sandbox
    # execution). `passed`/`is_correct` are AI judgments, NOT real test results.
    ai_assessed: bool = Field(default=True)
    test_cases_total: int = Field(default=0)

    @field_validator(
        "criteria_met",
        "criteria_failed",
        "suggestions",
        "security_issues",
        "best_practice_violations",
        mode="before",
    )
    @classmethod
    def ensure_list(cls, v):
        if isinstance(v, str):
            return [v] if v.strip() else []
        return v or []

    @field_validator("feedback", "language_specific_feedback", mode="before")
    @classmethod
    def sanitize_text(cls, v):
        if not v or len(str(v).strip()) < 5:
            return "Your code has been reviewed. Check the detailed suggestions."
        return str(v).strip()[:3000]

    @field_validator("score", mode="before")
    @classmethod
    def coerce_score(cls, v):
        try:
            return max(0, min(100, int(float(v or 0))))
        except (TypeError, ValueError):
            return 0

    @field_validator("grade", mode="before")
    @classmethod
    def derive_grade(cls, v, info):
        score = info.data.get("score", 0)
        if score >= 90:
            return "A+"
        if score >= 80:
            return "A"
        if score >= 70:
            return "B"
        if score >= 60:
            return "C"
        if score >= 50:
            return "D"
        return "F"

    @field_validator("passed", mode="before")
    @classmethod
    def sync_passed(cls, v, info):
        score = info.data.get("score", 0)
        return score >= 70


eval_parser = PydanticOutputParser(pydantic_object=EvaluationResult)


# ── LangGraph State Type ──────────────────────────────────────────────────────


class CodeEvalState(TypedDict):
    question_title: str
    question_description: str
    language_id: str
    language_name: str
    language_ai_context: str
    code_submitted: str
    evaluation_criteria: Optional[str]
    sample_solution: Optional[str]
    topic: Optional[str]
    mentor_evaluation_criteria: Optional[str]
    prompt: Optional[str]
    system_instruction: Optional[str]
    raw_ai_response: Optional[str]
    parsed_result: Optional[dict]
    error: Optional[str]
    retries: int


# ── LangGraph Nodes: AI Evaluation Pipeline ───────────────────────────────────


def _node_build_eval_prompt(state: CodeEvalState) -> CodeEvalState:
    """Node 1: Build the evaluation prompt with language-specific context."""

    lang_name = state.get("language_name", state.get("language_id", "Unknown"))
    lang_context = state.get(
        "language_ai_context", "General programming best practices"
    )
    topic = state.get("topic", "")
    format_instructions = eval_parser.get_format_instructions()

    # Build criteria section
    criteria_section = ""
    if state.get("evaluation_criteria"):
        crit = state["evaluation_criteria"]
        if isinstance(crit, list):
            criteria_section = "\nInstructor Evaluation Criteria:\n" + "\n".join(
                f"  • {c}" for c in crit
            )
        else:
            criteria_section = f"\nInstructor Evaluation Criteria: {crit}"

    mentor_criteria = ""
    if state.get("mentor_evaluation_criteria"):
        mentor_criteria = (
            f"\nMentor-Specific Requirements:\n{state['mentor_evaluation_criteria']}"
        )

    topic_section = f"\nDomain/Topic: {topic}" if topic else ""

    state["system_instruction"] = (
        f"You are a Senior {lang_name} Engineer and Expert Code Reviewer with 15+ years of enterprise experience.\n"
        f"Language Specialization Context: {lang_context}\n\n"
        "YOUR TASK: Perform a comprehensive, enterprise-grade evaluation of the submitted code.\n\n"
        "EVALUATION DIMENSIONS:\n"
        "  1. CORRECTNESS — Does the code correctly solve the stated problem?\n"
        "  2. CODE QUALITY — Naming, structure, readability, maintainability\n"
        "  3. LANGUAGE IDIOMS — Does it use language-specific best practices and idioms?\n"
        "  4. BEST PRACTICES — SOLID principles, DRY, error handling, security\n"
        "  5. COMPLETENESS — Are all requirements addressed?\n\n"
        "SCORING RUBRIC:\n"
        "  90-100: Production-ready, exemplary enterprise code\n"
        "  80-89: High quality, minor improvements possible\n"
        "  70-79: Correct but needs refactoring for production\n"
        "  60-69: Partially correct, significant issues\n"
        "  50-59: Major logic errors but shows understanding\n"
        "  0-49: Incorrect or completely off-topic\n\n"
        "STRICT RULES:\n"
        "  • If the code is completely irrelevant to the problem, score = 0\n"
        "  • If the code has syntax errors but valid structure, score ≤ 40\n"
        "  • Evaluate security implications for infrastructure/config code\n"
        "  • For DevOps/IaC code, check for hardcoded secrets, missing validation\n"
        "  • Be specific in feedback — reference exact line patterns or constructs\n\n"
        f"{format_instructions}"
    )

    desc = state.get("question_description", "")
    if len(desc) > 3000:
        desc = desc[:3000] + "\n[Description truncated]"

    submitted_code = state.get("code_submitted", "")
    if len(submitted_code) > 8000:
        submitted_code = (
            submitted_code[:8000] + "\n# [Code truncated — first 8000 chars evaluated]"
        )

    sample_solution = state.get("sample_solution", "")
    sample_section = ""
    if sample_solution:
        if len(sample_solution) > 2000:
            sample_solution = sample_solution[:2000] + "\n# [Solution truncated]"
        sample_section = f"\nReference Solution (for evaluation guidance only):\n```{state.get('language_id', '')}\n{sample_solution}\n```"

    state["prompt"] = (
        f"PROBLEM TITLE: {state['question_title']}\n"
        f"{topic_section}\n"
        f"LANGUAGE: {lang_name}\n"
        f"LANGUAGE CONTEXT: {lang_context}\n"
        f"{criteria_section}\n"
        f"{mentor_criteria}\n\n"
        f"PROBLEM DESCRIPTION:\n{desc}\n\n"
        f"SUBMITTED CODE:\n```{state.get('language_id', '')}\n{submitted_code}\n```\n"
        f"{sample_section}\n\n"
        "Evaluate the submitted code comprehensively against all dimensions listed. "
        f"Pay special attention to {lang_name}-specific patterns and enterprise best practices. "
        "Return the complete JSON evaluation object now."
    )

    state["raw_ai_response"] = None
    state["error"] = None
    return state


def _node_call_ai_eval(state: CodeEvalState) -> CodeEvalState:
    """Node 2: Call Gemini for evaluation."""
    if "retries" not in state:
        state["retries"] = 0

    llm = _get_llm(max_tokens=1500, json_mode=True)
    if not llm:
        state["error"] = "AI service unavailable"
        state["retries"] = 99
        return state

    logger.info(
        f"[AI EVAL] Evaluating {state.get('language_id')} code for: {state['question_title']}"
    )

    messages = [
        SystemMessage(content=state.get("system_instruction", "")),
        HumanMessage(content=state.get("prompt", "")),
    ]

    try:
        response = llm.invoke(messages)
        # Business rule §12.3: every LLM call is metered.
        from services.ai_meter import record_langchain_sync

        record_langchain_sync("code_eval", settings.PRIMARY_AI_MODEL, response)
        raw_text = response.content
        if not isinstance(raw_text, str):
            raw_text = str(raw_text)

        if not raw_text or len(raw_text.strip()) < 20:
            state["error"] = "empty_response"
            state["retries"] = 99
            return state

        logger.info(f"[AI EVAL] Response received ({len(raw_text)} chars)")
        state["raw_ai_response"] = raw_text
        state["error"] = None

    except Exception as e:
        err_str = str(e).lower()
        if any(x in err_str for x in ["safety", "blocked", "harm"]):
            state["error"] = "safety_block"
            state["retries"] = 99
        elif "quota" in err_str or "429" in err_str:
            state["error"] = "quota_exceeded"
            state["retries"] = 99
        else:
            logger.error(f"[AI EVAL] API error: {e}")
            state["error"] = f"api_error: {str(e)}"
            state["retries"] = state.get("retries", 0) + 1

    return state


def _node_validate_eval_output(state: CodeEvalState) -> CodeEvalState:
    """Node 3: Parse and validate Gemini output with Guardrails."""

    if state.get("error"):
        error = state["error"]
        feedback_map = {
            "safety_block": "Your submission was flagged by content filters. Please submit valid code related to the problem.",
            "quota_exceeded": "AI evaluation quota exceeded. Please try again in a few minutes.",
            "empty_response": "The AI engine returned an empty response. Please retry your submission.",
            "AI service unavailable": "The AI evaluation service is currently offline. Please contact your administrator.",
        }
        feedback = feedback_map.get(
            error or "", f"Evaluation service error: {error}. Please retry."
        )
        state["parsed_result"] = EvaluationResult(
            score=0,
            passed=False,
            is_correct=False,
            grade="F",
            feedback=feedback,
            suggestions=["Retry your submission."],
        ).model_dump()
        return state

    raw_text = (state.get("raw_ai_response") or "").strip()

    try:
        # Strip markdown fences if present
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip())

        try:
            validated = eval_parser.parse(cleaned)
        except Exception:
            # Manual JSON extraction fallback
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                data = json.loads(match.group())
                # Build RubricDetail from nested or flat rubric
                rubric_data = data.get("rubric", {})
                if not isinstance(rubric_data, dict):
                    rubric_data = {}
                data["rubric"] = RubricDetail(
                    **{
                        k: rubric_data.get(k, data.get("score", 0))
                        for k in [
                            "correctness",
                            "code_quality",
                            "best_practices",
                            "completeness",
                            "language_idioms",
                        ]
                    }
                )
                validated = EvaluationResult(**data)
            else:
                raise ValueError("No valid JSON object found in AI response")

        # Ensure rubric is populated
        if validated.rubric.correctness == 0 and validated.score > 0:
            validated.rubric = RubricDetail(
                correctness=validated.score,
                code_quality=max(0, validated.score - 5),
                best_practices=max(0, validated.score - 10),
                completeness=validated.score,
                language_idioms=max(0, validated.score - 8),
            )

        # Derive production readiness label
        if validated.score >= 85:
            validated.estimated_production_readiness = "Production Ready"
        elif validated.score >= 70:
            validated.estimated_production_readiness = "Production with Minor Revisions"
        elif validated.score >= 55:
            validated.estimated_production_readiness = (
                "Requires Significant Refactoring"
            )
        else:
            validated.estimated_production_readiness = "Not Production Ready"

        result = validated.model_dump()
        result["_raw_ai_response"] = raw_text
        result["language_evaluated"] = state.get("language_id")
        result["language_name"] = state.get("language_name")
        state["parsed_result"] = result
        logger.info(
            f"[AI EVAL] Success: Score={validated.score}, Grade={validated.grade}"
        )

    except Exception as e:
        logger.critical(f"[AI EVAL] Guardrails validation failed: {e}")
        state["parsed_result"] = EvaluationResult(
            score=0,
            passed=False,
            is_correct=False,
            grade="F",
            feedback=f"AI returned an unstructured response. Raw output: {raw_text[:200]}",
            suggestions=[
                "Ensure your code is syntactically valid and relevant to the problem."
            ],
        ).model_dump()

    return state


# ── Public API ────────────────────────────────────────────────────────────────


def run_evaluation_graph(
    question_title: str,
    question_description: str,
    language: str,
    code_submitted: str,
    evaluation_criteria=None,
    sample_solution: Optional[str] = None,
    test_cases: Optional[List[dict]] = None,
    topic: Optional[str] = None,
    mentor_evaluation_criteria: Optional[str] = None,
) -> dict:
    """
    Pure AI code evaluation. No sandbox. No subprocess.
    Supports all 50+ enterprise languages via Gemini.
    Returns AIResponseEnvelope-compatible dict.
    """
    # Sanitize
    question_title = sanitize_input(question_title, 300)
    question_description = sanitize_input(question_description, 3000)
    code_submitted = sanitize_input(code_submitted, 8000)
    sample_solution = sanitize_input(sample_solution or "", 2000)
    topic = sanitize_input(topic or "", 200)

    if isinstance(evaluation_criteria, list):
        criteria_str = "; ".join(str(c) for c in evaluation_criteria)
    else:
        criteria_str = sanitize_input(str(evaluation_criteria or ""), 1000)

    # Get language details
    lang_entry = get_language_entry(language)

    # Build and run graph
    initial_state: CodeEvalState = {
        "question_title": question_title,
        "question_description": question_description,
        "language_id": lang_entry["id"],
        "language_name": lang_entry["name"],
        "language_ai_context": lang_entry["ai_context"],
        "code_submitted": code_submitted,
        "evaluation_criteria": criteria_str or None,
        "sample_solution": sample_solution or None,
        "topic": topic or None,
        "mentor_evaluation_criteria": mentor_evaluation_criteria,
        "prompt": None,
        "system_instruction": None,
        "raw_ai_response": None,
        "parsed_result": None,
        "error": None,
        "retries": 0,
    }

    def route_after_call(state: CodeEvalState) -> str:
        error = state.get("error", "")
        retries = state.get("retries", 0)
        if not error:
            return "validate"
        if retries >= 99 or any(
            x in (error or "") for x in ["safety", "quota", "empty"]
        ):
            return "validate"
        if retries < 1:
            return "retry"
        return "validate"

    builder = StateGraph(CodeEvalState)
    builder.add_node("build_prompt", _node_build_eval_prompt)
    builder.add_node("call_ai", _node_call_ai_eval)
    builder.add_node("validate", _node_validate_eval_output)

    builder.add_edge(START, "build_prompt")
    builder.add_edge("build_prompt", "call_ai")
    builder.add_conditional_edges(
        "call_ai", route_after_call, {"retry": "call_ai", "validate": "validate"}
    )
    builder.add_edge("validate", END)

    start_time = time.time()
    graph = builder.compile()
    final_state = graph.invoke(initial_state)

    result = final_state.get("parsed_result") or EvaluationResult().model_dump()
    is_fallback = bool(final_state.get("error"))

    return {
        "ai_generated": not is_fallback,
        "fallback_reason": final_state.get("error") if is_fallback else None,
        "data": {
            "evaluation": result,
            "language": lang_entry,
        },
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model_used": settings.PRIMARY_AI_MODEL,
        "execution_time_ms": int((time.time() - start_time) * 1000),
    }
