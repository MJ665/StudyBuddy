"""AI code-evaluation engine (LangGraph eval/hint flows).

Language/prompt configuration lives in services/ai_languages.py; this
module keeps the graph logic. All public names remain importable from
here (routers/code.py, system_config.py are unchanged).
"""
from __future__ import annotations

from services.ai_languages import *  # noqa: F401,F403



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


class HintResult(BaseModel):
    hint_text: str = Field(
        default="Consider breaking the problem into smaller sub-problems."
    )
    hint_level: int = Field(default=1)
    from_cache: bool = False

    @field_validator("hint_text", mode="before")
    @classmethod
    def clean_hint(cls, v):
        text = str(v or "").strip()
        if len(text) < 5:
            return "Consider the core algorithm needed for this problem."
        forbidden = [
            "complete solution",
            "full answer",
            "here's the answer",
            "def solution",
        ]
        for f in forbidden:
            if f.lower() in text.lower():
                return "Think about the data structure best suited for this type of problem."
        return text[:1500]


# ── LangGraph State Types ─────────────────────────────────────────────────────


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


class HintState(TypedDict):
    question_title: str
    question_description: str
    hint_level: int
    user_code: str
    language_id: str
    language_ai_context: str
    topic: Optional[str]
    raw_hint: Optional[str]
    parsed_hint: Optional[dict]
    system_instruction: Optional[str]
    prompt: Optional[str]
    error: Optional[str]
    retries: int


# ── LLM Factory ──────────────────────────────────────────────────────────────


def _get_llm(max_tokens: int = 1200, json_mode: bool = False):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set — AI evaluation disabled")
        return None

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    model_kwargs = {}
    if json_mode:
        model_kwargs["response_mime_type"] = "application/json"

    return ChatGoogleGenerativeAI(
        model=settings.PRIMARY_AI_MODEL,
        temperature=0.15,
        max_output_tokens=max_tokens,
        safety_settings=safety_settings,
        model_kwargs=model_kwargs,
        api_key=api_key,
    )


eval_parser = PydanticOutputParser(pydantic_object=EvaluationResult)
hint_parser = PydanticOutputParser(pydantic_object=HintResult)


# ── Helper: Get Language Entry ────────────────────────────────────────────────


def get_language_entry(language_id: str) -> Dict:
    """Find language entry from registry, fallback to generic."""
    lang_id = (language_id or "").lower()
    for lang in ENTERPRISE_LANGUAGES:
        if lang["id"] == lang_id:
            return lang
    return {
        "id": lang_id,
        "name": lang_id.upper(),
        "monaco_language": lang_id,
        "category": "General",
        "ai_context": f"General {lang_id} programming best practices",
    }


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


# ── LangGraph Nodes: Hint Pipeline ────────────────────────────────────────────


def _node_build_hint_prompt(state: HintState) -> HintState:
    """Hint Node 1: Build context-rich hint prompt."""
    lang_context = state.get("language_ai_context", "")
    topic = state.get("topic", "")

    strategy_map = {
        1: (
            "CONCEPTUAL HINT: Point to the underlying concept or algorithm pattern ONLY. "
            "DO NOT write code. DO NOT write pseudocode. Help them identify the problem category "
            "(e.g., 'This is a sliding window problem' or 'Think about idempotency here'). "
            "Maximum 2 sentences."
        ),
        2: (
            "ALGORITHMIC HINT: Describe the high-level approach with pseudocode if helpful. "
            "You may reference language-specific constructs by name (e.g., 'consider using a defaultdict') "
            "but DO NOT provide the implementation. Maximum 4 sentences."
        ),
        3: (
            "IMPLEMENTATION HINT: Provide a concrete 2-5 line code snippet that solves one specific "
            "sub-problem or demonstrates the key pattern. Leave the complete integration to the student. "
            "Include a brief explanation of what this snippet does and why."
        ),
    }
    strategy = strategy_map.get(state["hint_level"], strategy_map[1])

    topic_context = f"\nDomain/Topic: {topic}" if topic else ""
    lang_context_line = f"\nLanguage Context: {lang_context}" if lang_context else ""

    state["system_instruction"] = (
        f"You are an expert {state.get('language_id', 'programming').upper()} mentor and educator.\n"
        f"{lang_context_line}\n"
        f"{topic_context}\n\n"
        f"HINT LEVEL {state['hint_level']}/3 — STRATEGY:\n{strategy}\n\n"
        "ABSOLUTE RULES:\n"
        "  • NEVER reveal the complete solution\n"
        "  • NEVER solve the entire problem for the student\n"
        "  • Keep hints progressive — each level reveals slightly more\n"
        "  • Be specific to the language and domain context provided\n"
        "  • For infrastructure/config problems, hint about the specific resource type or directive\n"
        "  • For data problems, hint about the transformation approach, not the code\n"
    )

    user_code = state.get("user_code", "").strip()
    code_section = ""
    if user_code and len(user_code) > 3:
        if len(user_code) > 2000:
            user_code = user_code[:2000] + "\n# [Truncated]"
        code_section = f"\nStudent's Current Code:\n```{state.get('language_id', '')}\n{user_code}\n```\n"

    desc = (state.get("question_description") or "")[:1500]

    state["prompt"] = (
        f"Problem Title: {state['question_title']}\n"
        f"Problem Description: {desc}\n"
        f"{code_section}\n"
        f"Generate a Level {state['hint_level']}/3 hint for this student. "
        f"Be specific to {state.get('language_id', 'the language')} and the problem context."
    )

    state["raw_hint"] = None
    state["error"] = None
    return state


def _node_call_ai_hint(state: HintState) -> HintState:
    """Hint Node 2: Call Gemini for hint generation."""
    llm = _get_llm(max_tokens=400, json_mode=False)
    if not llm:
        state["error"] = "AI service unavailable"
        return state

    messages = [
        SystemMessage(content=state.get("system_instruction", "")),
        HumanMessage(content=state.get("prompt", "")),
    ]

    try:
        response = llm.invoke(messages)
        raw_text = response.content or ""
        if not isinstance(raw_text, str):
            raw_text = str(raw_text)
        raw_text = raw_text.strip()

        if not raw_text:
            state["error"] = "empty_hint_response"
            return state

        state["raw_hint"] = raw_text

    except Exception as e:
        err_str = str(e).lower()
        if any(x in err_str for x in ["safety", "blocked"]):
            state["error"] = "safety_block"
        elif "quota" in err_str or "429" in err_str:
            state["error"] = "quota_exceeded"
        else:
            state["error"] = f"api_error: {str(e)}"

    return state


def _node_validate_hint(state: HintState) -> HintState:
    """Hint Node 3: Validate hint is appropriate (not a solution giveaway)."""
    raw_hint = (state.get("raw_hint") or "").strip()

    # Detect if AI accidentally gave full solution
    giveaway_patterns = [
        "here is the complete solution",
        "here's the full implementation",
        "complete code:",
        "def solution(",
        "```python\ndef ",
        "the answer is:",
    ]

    is_giveaway = any(p.lower() in raw_hint.lower() for p in giveaway_patterns)
    is_too_short = len(raw_hint) < 10
    has_error = bool(state.get("error"))

    if has_error or is_giveaway or is_too_short:
        fallback_map = {
            "safety_block": "Review the problem constraints and think about the input/output relationship.",
            "quota_exceeded": "AI hints are temporarily unavailable. Review the problem description carefully.",
            "empty_hint_response": "Think about which data structure or pattern best fits the problem requirements.",
        }
        error = state.get("error", "")
        hint_text = fallback_map.get(
            error or "", "Consider the algorithmic approach before writing code."
        )

        if is_giveaway:
            hint_text = "Think about the core algorithm step-by-step. Break the problem into sub-problems."

        state["parsed_hint"] = HintResult(
            hint_text=hint_text, hint_level=state["hint_level"], from_cache=False
        ).model_dump()
        return state

    try:
        validated = HintResult(
            hint_text=raw_hint, hint_level=state["hint_level"], from_cache=False
        )
        state["parsed_hint"] = validated.model_dump()
    except Exception:
        state["parsed_hint"] = HintResult(
            hint_text="Consider the core algorithm step-by-step.",
            hint_level=state["hint_level"],
        ).model_dump()

    return state


# ── Public API ────────────────────────────────────────────────────────────────


def sanitize_input(text: str, max_length: int = 32000) -> str:
    if not text:
        return ""
    return str(text).strip()[:max_length]


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


def run_hint_graph(
    question_title: str,
    question_description: str,
    hint_level: int,
    user_code: str = "",
    language: str = "python",
    topic: Optional[str] = None,
) -> dict:
    """
    AI-powered progressive hint system. Three levels, language-aware.
    Returns AIResponseEnvelope-compatible dict.
    """
    lang_entry = get_language_entry(language)

    initial_state: HintState = {
        "question_title": sanitize_input(question_title, 200),
        "question_description": sanitize_input(question_description, 1500),
        "hint_level": max(1, min(3, hint_level)),
        "user_code": sanitize_input(user_code or "", 2000),
        "language_id": lang_entry["id"],
        "language_ai_context": lang_entry["ai_context"],
        "topic": sanitize_input(topic or "", 100),
        "raw_hint": None,
        "parsed_hint": None,
        "system_instruction": None,
        "prompt": None,
        "error": None,
        "retries": 0,
    }

    builder = StateGraph(HintState)
    builder.add_node("build_prompt", _node_build_hint_prompt)
    builder.add_node("call_ai", _node_call_ai_hint)
    builder.add_node("validate", _node_validate_hint)

    builder.add_edge(START, "build_prompt")
    builder.add_edge("build_prompt", "call_ai")
    builder.add_edge("call_ai", "validate")
    builder.add_edge("validate", END)

    start_time = time.time()
    graph = builder.compile()
    final_state = graph.invoke(initial_state)

    hint_data = final_state.get("parsed_hint") or {
        "hint_text": "Think carefully about the approach.",
        "hint_level": hint_level,
    }

    return {
        "ai_generated": not bool(final_state.get("error")),
        "fallback_reason": final_state.get("error"),
        "data": hint_data,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model_used": settings.PRIMARY_AI_MODEL,
        "execution_time_ms": int((time.time() - start_time) * 1000),
    }


def get_all_languages() -> List[Dict]:
    """Returns the full enterprise language registry for the frontend."""
    return ENTERPRISE_LANGUAGES


def get_languages_by_category() -> Dict[str, List[Dict]]:
    """Returns languages grouped by category for the frontend dropdown."""
    from collections import defaultdict

    grouped = defaultdict(list)
    for lang in ENTERPRISE_LANGUAGES:
        grouped[lang["category"]].append(
            {
                "id": lang["id"],
                "name": lang["name"],
                "monaco_language": lang["monaco_language"],
            }
        )
    return dict(grouped)

