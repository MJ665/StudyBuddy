"""AI code-evaluation engine (LangGraph eval/hint flows) — FACADE.

This module re-exports the public API from the modularized ai_eval_graph,
ai_hint_graph, and ai_shared modules. All existing imports continue to work.

Language/prompt configuration lives in services/ai_languages.py.
"""
from __future__ import annotations

from services.ai_languages import *  # noqa: F401,F403
from services.ai_shared import (  # noqa: F401
    _get_llm,
    get_all_languages,
    get_language_entry,
    get_languages_by_category,
    sanitize_input,
)
from services.ai_eval_graph import (  # noqa: F401
    CodeEvalState,
    EvaluationResult,
    RubricDetail,
    eval_parser,
    run_evaluation_graph,
)
from services.ai_hint_graph import (  # noqa: F401
    HintResult,
    HintState,
    hint_parser,
    run_hint_graph,
)

