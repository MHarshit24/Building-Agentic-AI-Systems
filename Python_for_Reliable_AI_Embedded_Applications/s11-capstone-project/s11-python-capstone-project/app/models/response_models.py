from pydantic import BaseModel
from typing import List, Optional

class ExplainResponse(BaseModel):
    explanation: str
    complexity_level: str
    key_concepts: List[str]

class ImproveResponse(BaseModel):
    current_code_summary: str
    suggested_improvements: List[str]
    optimized_code: Optional[str] = None
    performance_gain: Optional[str] = None

class AnalyzeResponse(BaseModel):
    code_summary: str
    detected_issues: List[str]
    improvements: List[str]
    best_practices: List[str]

class ReviewResponse(BaseModel):
    overall_score: int
    explanation: str
    detected_issues: List[str]
    improvements: List[str]
    best_practices: List[str]
    security_concerns: List[str]
    maintainability_score: int

# For backward compatibility or fallback
class MentorResponse(BaseModel):
    explanation: str
    detected_issues: List[str]
    improvements: List[str]
    best_practices: List[str]