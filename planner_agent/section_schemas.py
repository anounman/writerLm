from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SectionContentRequirements(BaseModel):
    """Content requirements for a section, mirroring the main schemas version."""

    model_config = ConfigDict(extra="ignore")

    must_include_code: bool = False
    must_include_example: bool = True
    must_include_diagram: bool = False
    suggested_diagram_type: Optional[str] = None


class SectionPlan(BaseModel):
    title: str
    goal: str
    key_questions: List[str] = Field(default_factory=list)
    estimated_words: int = Field(..., ge=150, le=2000)
    content_requirements: SectionContentRequirements = Field(
        default_factory=SectionContentRequirements,
    )
    builds_on: Optional[str] = Field(
        default=None,
        description="Title of a previous section this one builds upon.",
    )


class ChapterSectionPlan(BaseModel):
    chapter_number: int = Field(..., ge=1)
    chapter_title: str
    chapter_goal: str
    project_milestone: Optional[str] = None
    sections: List[SectionPlan] = Field(default_factory=list)
