from typing import List

from pydantic import BaseModel, Field


class AIQuizQuestionBase(BaseModel):
    question: str
    options: List[str] = Field(..., min_length=2, max_length=6)
    correct_answer: str
    explanation: str
    difficulty: str
