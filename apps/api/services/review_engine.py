"""
AI Review Engine — StudyHub Phase 4
Uses LangGraph for refined question review, LangChain for model invocation,
and Pydantic Guardrails for state-of-the-art accuracy and relevancy.
"""

from __future__ import annotations

import logging
import os
from typing import List, Literal, Optional, TypedDict

from config import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    HarmBlockThreshold,
    HarmCategory,
)
from langgraph.graph import END, START, StateGraph  # type: ignore
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Pydantic Guardrails ───────────────────────────────────────────────────


class RelevancyScore(BaseModel):
    """Guardrail: Classifies whether the query is suitable for a study platform."""

    classification: Literal["RELEVANT", "EDUCATIONAL_GENERAL", "SPAM", "OFFENSIVE"] = (
        Field(description="The classification of the user query.")
    )
    reasoning: str = Field(description="Brief reasoning for the classification.")


class ReviewResult(BaseModel):
    """Guardrail: The final structured response from the AI Reviewer."""

    response_text: str = Field(description="The actual answer to the user query.")
    is_out_of_context: bool = Field(
        default=False, description="Flag indicating if the query was blocked."
    )


# ── LangGraph State ───────────────────────────────────────────────────────


class ReviewState(TypedDict):
    question_text: str
    user_answer: str
    correct_answer: str
    user_query: str
    user_note: Optional[str]
    relevant_context: Optional[List[dict]]

    relevancy: Optional[RelevancyScore]
    raw_response: Optional[str]
    final_result: Optional[ReviewResult]

    error: Optional[str]
    retries: int


# ── LLM Configuration ─────────────────────────────────────────────────────


def _get_llm(temperature: float = 0.2):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    return ChatGoogleGenerativeAI(
        model=settings.PRIMARY_AI_MODEL,
        temperature=temperature,
        safety_settings=safety_settings,
        api_key=api_key,
    )


relevancy_parser = PydanticOutputParser(pydantic_object=RelevancyScore)
review_parser = PydanticOutputParser(pydantic_object=ReviewResult)

# ── LangGraph Nodes ───────────────────────────────────────────────────────


def node_check_relevancy(state: ReviewState) -> ReviewState:
    """Node 1: Guardrail node to verify if the query should be answered."""
    llm = _get_llm(temperature=0.1)
    if not llm:
        state["error"] = "AI service unavailable"
        return state

    format_instructions = relevancy_parser.get_format_instructions()

    system_msg = SystemMessage(
        content=(
            "You are a StudyHub Relevancy Guardrail. Your job is to classify user queries.\n"
            "RELEVANT: Questions directly about the quiz question, its logic, or options.\n"
            "EDUCATIONAL_GENERAL: Broad technical or academic questions (e.g., 'What is 2+2?', 'How does a stack work?', 'Explain React'). These are allowed.\n"
            "SPAM: Gibberish, unrelated personal questions, or non-academic noise.\n"
            "OFFENSIVE: Harassment, hate speech, or dangerous content.\n\n"
            f"{format_instructions}"
        )
    )

    human_msg = HumanMessage(
        content=(
            f"Quiz Context: {state['question_text']}\nUser Query: {state['user_query']}"
        )
    )

    try:
        response = llm.invoke([system_msg, human_msg])
        content_str = response.content if isinstance(response.content, str) else str(response.content)
        state["relevancy"] = relevancy_parser.parse(content_str)
    except Exception as e:
        logger.error(f"Relevancy check failed: {e}")
        # Default to safe fallback
        state["relevancy"] = RelevancyScore(
            classification="RELEVANT", reasoning="Fallback allowed"
        )

    return state


def node_generate_review(state: ReviewState) -> ReviewState:
    """Node 2: Generates the actual explanation/review."""
    relevancy = state.get("relevancy")
    if not relevancy or relevancy.classification in ["SPAM", "OFFENSIVE"]:
        state["raw_response"] = None
        return state

    llm = _get_llm(temperature=0.4)
    if not llm:
        state["error"] = "AI service unavailable"
        return state

    # Tailor the system prompt based on classification
    if relevancy.classification == "EDUCATIONAL_GENERAL":
        instruction = (
            "You are a versatile academic mentor. The user has asked a general educational or technical question "
            "that may be outside the immediate quiz context. Answer their question accurately and clearly. "
            "Maintain a helpful, professional tone."
        )
    else:
        instruction = (
            "You are a brilliant corporate study mentor. The user is asking about the specific quiz question. "
            "Explain the logic, discuss why the answer is correct/incorrect, and provide depth to their learning."
        )

    # Augment with historical context if available
    context_str = ""
    relevant_context = state.get("relevant_context")
    if relevant_context:
        context_str = "--- HISTORICAL CONTEXT (Past Interactions) ---\n"
        for i, c in enumerate(relevant_context):
            context_str += f"- Past {c['role'].capitalize()}: {c['content']}\n"
        context_str += "\n"

    system_msg = SystemMessage(
        content=f"{instruction} Limit your response to 4-6 sentences. If historical context is provided, use it for continuity."
    )

    # Structure the prompt to ensure the User's Query is the clear priority
    prompt = (
        f"--- PRIMARY TASK ---\n"
        f"Answer this specific user question: {state['user_query']}\n\n"
        f"{context_str}"
        f"--- CONTEXT FOR REFERENCE ---\n"
        f"Quiz Question: {state['question_text']}\n"
        f"Correct Answer: {state['correct_answer']}\n"
        f"User's Attempt: {state['user_answer']}\n"
        f"User's Logic/Note: {state.get('user_note', 'None provided')}\n"
    )

    try:
        response = llm.invoke([system_msg, HumanMessage(content=prompt)])
        state["raw_response"] = response.content if isinstance(response.content, str) else str(response.content)
    except Exception as e:
        logger.error(f"Review generation failed: {e}")
        state["error"] = str(e)

    return state


def node_finalize_review(state: ReviewState) -> ReviewState:
    """Node 3: Formats the final output for the UI."""
    relevancy = state.get("relevancy")

    if not relevancy or relevancy.classification in ["SPAM", "OFFENSIVE"]:
        state["final_result"] = ReviewResult(
            response_text="I can only assist with academic or study-related queries. Please ask something related to the quiz or professional growth.",
            is_out_of_context=True,
        )
        return state

    if state.get("error"):
        state["final_result"] = ReviewResult(
            response_text="Our AI mentor is taking a short break. Please try again in a moment.",
            is_out_of_context=False,
        )
        return state

    state["final_result"] = ReviewResult(
        response_text=state.get("raw_response") or "I'm sorry, I couldn't generate a response.",
        is_out_of_context=False,
    )
    return state


# ── LangGraph Construction ────────────────────────────────────────────────


def run_review_graph(
    question_text: str,
    user_answer: str,
    correct_answer: str,
    user_query: str,
    user_note: Optional[str] = None,
    relevant_context: Optional[List[dict]] = None,
) -> dict:
    """
    Executes the AI Review LangGraph pipeline.
    Returns a dictionary matching ReviewResult.
    """
    initial_state: ReviewState = {
        "question_text": question_text,
        "user_answer": user_answer,
        "correct_answer": correct_answer,
        "user_query": user_query,
        "user_note": user_note,
        "relevant_context": relevant_context,
        "relevancy": None,
        "raw_response": None,
        "final_result": None,
        "error": None,
        "retries": 0,
    }

    builder = StateGraph(ReviewState)
    builder.add_node("check_relevancy", node_check_relevancy)
    builder.add_node("generate_review", node_generate_review)
    builder.add_node("finalize", node_finalize_review)

    builder.add_edge(START, "check_relevancy")
    builder.add_edge("check_relevancy", "generate_review")
    builder.add_edge("generate_review", "finalize")
    builder.add_edge("finalize", END)

    graph = builder.compile()
    final_state = graph.invoke(initial_state)

    return final_state.get(
        "final_result",
        ReviewResult(
            response_text="Initialization error in AI Engine.", is_out_of_context=False
        ),
    ).model_dump()
