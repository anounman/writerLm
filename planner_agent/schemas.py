from typing import List , Literal , Optional
from pydantic import BaseModel , Field


    

class UserBookRequest(BaseModel):
    topic: str = Field(..., min_length=3)
    audience: str = Field(..., min_length=3)
    tone: str = "clear , practical , project-based"
    depth: Literal["introductory" , "intermediate" , "advanced"] = "intermediate"
    chapter_count : Optional[int] = Field(default=None  , ge=3 , le=20)
    max_section_words: Optional[int] = Field(default=None, ge=150, le=2000)


class SectionPlan(BaseModel):
    title : str
    goal : str
    key_questions : List[str] = Field(default_factory=list)
    estimated_words : int = Field(... , ge=150 , le=1200)

class ChapterPlan(BaseModel):
    chapter_number: int = Field(... , ge=1)
    title: str
    chapter_goal: str
    sections: List[SectionPlan] = Field(default_factory=list)

class BookPlan(BaseModel):
    title: str 
    audience: str
    tone : str
    depth: str
    chapters: List[ChapterPlan] = Field(default_factory=list)

    def get_chapter_count(self) -> int:
        return len(self.chapters)


class PlanningContext(BaseModel):
    book_purpose: str = ""
    audience_needs: List[str] = Field(default_factory=list)
    core_idea: str = ""
    main_questions: List[str] = Field(default_factory=list)
    scope_includes: List[str] = Field(default_factory=list)
    scope_excludes: List[str] = Field(default_factory=list)
    key_themes: List[str] = Field(default_factory=list)
    sequence_logic: List[str] = Field(default_factory=list)
    structure_options: List[str] = Field(default_factory=list)
    evidence_examples: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)