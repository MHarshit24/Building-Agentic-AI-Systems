from pydantic import BaseModel, Field


# TODO: Step 1 - Define ProductReviewRequest BaseModel
# Hint: Use BaseModel with product field (str, required, description="Product name to analyze reviews for")
class ProductReviewRequest(BaseModel):
    """Request model for product review analysis."""
    product: str = Field(..., description="Product name to analyze reviews for")  # TODO: Add product field


# TODO: Step 2 - Define ProductReviewResponse BaseModel
# Hint: Use BaseModel with insights (str, required), status (str, default="success"), 
# message (str, default="Review analysis completed successfully")
class ProductReviewResponse(BaseModel):
    """Response model for product review analysis."""
    insights: str  # TODO: Add insights, status, and message fields
    status: str = "success"
    message: str = "Review analysis completed successfully"