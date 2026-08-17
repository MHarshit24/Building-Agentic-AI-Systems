from pydantic import BaseModel, Field
from typing import Optional

# TODO: Step 1 - Define ResumeFlowState BaseModel
# Hint: This model holds the internal state of the flow (inputs and outputs).
class ResumeFlowState(BaseModel):
    """Flow state model for resume screening."""
    # TODO: Add state fields
    # Hint: candidate_name, resume_text, applying_for, classified_role, justification, evaluator_role
    candidate_name: str = Field(default="")
    resume_text: str = Field(default="")
    applying_for: str = Field(default="")
    classified_role: str = Field(default="")
    justification: str = Field(default="")
    evaluator_role: str = Field(default="")

# TODO: Step 2 - Define ResumeRequest BaseModel
# Hint: This is the input payload for the API endpoint.
class ResumeRequest(BaseModel):
    """Request model for resume screening."""
    # TODO: Add request fields
    # Hint: candidate_name, resume_text, applying_for (all strings)
    candidate_name: str = Field(..., description="Full name of the candidate")
    resume_text: str = Field(..., description="Full text content of the resume")
    applying_for: str = Field(..., description="The role or position the candidate is applying for")

# TODO: Step 3 - Define ResumeResponse BaseModel
# Hint: This is the structured response returned by the API.
class ResumeResponse(BaseModel):
    """Response model for resume screening."""
    # TODO: Add response fields
    # Hint: success, candidate_name, classified_role, evaluator, feedback
    success: bool = Field(..., description="Whether the screening was completed successfully")
    candidate_name: str = Field(..., description="Full name of the candidate")
    classified_role: str = Field(..., description="The role the resume was classified into")
    evaluator: str = Field(..., description="The evaluator agent role that assessed the resume")
    feedback: str = Field(..., description="Detailed AI-generated feedback on the candidate")