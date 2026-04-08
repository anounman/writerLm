
from typing import List
from pydantic import BaseModel , Field

class ChapterOutlineItem(BaseModel):
    title: str
    chapter_number: int = Field(... , ge=1)
    chapter_goal: str

class ChapterOutlinePlan(BaseModel):
    title: str
    audience: str
    tone: str
    depth: str
    chapters: List[ChapterOutlineItem] = Field(default_factory=list)