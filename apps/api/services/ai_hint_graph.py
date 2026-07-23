"""AI hint-generation pipeline (LangGraph hint flow).

This module contains the hint graph nodes and the run_hint_graph
public API.
"""
from __future__ import annotations

from services.ai_languages import *  # noqa: F401,F403
from services.ai_shared import (
    _get_llm,
    get_language_entry,
    sanitize_input,
)


# ── Pydantic Output Schema ────────────────────────────────────────────────────


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


hint_parser = PydanticOutputParser(pydantic_object=HintResult)


# ── LangGraph State Type ──────────────────────────────────────────────────────


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
        # Business rule §12.3: every LLM call is metered.
        from services.ai_meter import record_langchain_sync

        record_langchain_sync("code_hint", settings.PRIMARY_AI_MODEL, response)
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
