from typing import List
from pydantic import BaseModel, Field


class SectionPlan(BaseModel):
    title: str
    goal: str
    key_questions: List[str] = Field(default_factory=list)
    estimated_words: int = Field(..., ge=150, le=2000)


class ChapterSectionPlan(BaseModel):
    chapter_number: int = Field(..., ge=1)
    chapter_title: str
    chapter_goal: str
    sections: List[SectionPlan] = Field(default_factory=list)
