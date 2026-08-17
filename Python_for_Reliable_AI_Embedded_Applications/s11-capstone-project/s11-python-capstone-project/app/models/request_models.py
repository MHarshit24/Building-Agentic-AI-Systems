from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ExperienceLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class CodeRequest(BaseModel):
    code: str = Field(..., min_length=1, description="The code to analyze")
    language: Optional[str] = Field(None, description="Programming language")
    experience_level: ExperienceLevel = Field(..., description="User's experience level")