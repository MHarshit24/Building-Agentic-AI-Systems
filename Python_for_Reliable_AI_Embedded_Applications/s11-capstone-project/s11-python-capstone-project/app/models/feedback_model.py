from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    code: str = Field(..., min_length=1, description="The code that was analyzed")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: str | None = Field(None, description="Optional feedback comment")