
from typing import List, Optional
from pydantic import BaseModel, Field


class ChapterOutlineItem(BaseModel):
    title: str
    chapter_number: int = Field(..., ge=1)
    chapter_goal: str
    project_milestone: Optional[str] = Field(
        default=None,
        description="What the reader has built/achieved by end of this chapter.",
    )


class ChapterOutlinePlan(BaseModel):
    title: str
    audience: str
    tone: str
    depth: str
    running_project: Optional[str] = Field(
        default=None,
        description="Description of the evolving project across all chapters.",
    )
    chapters: List[ChapterOutlineItem] = Field(default_factory=list)