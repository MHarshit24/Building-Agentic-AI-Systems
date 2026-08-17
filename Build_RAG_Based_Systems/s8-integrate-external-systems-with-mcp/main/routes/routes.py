from fastapi import APIRouter, HTTPException
from typing import Optional, List
from enum import Enum
import logging
from pydantic import BaseModel, Field


# Models
class SentimentLabel(str, Enum):
    """Sentiment classification labels"""
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"


class ReviewRequest(BaseModel):
    """Request model for single review analysis"""
    review_text: str = Field(..., min_length=1, max_length=5000, description="Product review text to analyze")
    product_id: Optional[str] = Field(None, description="Optional product identifier")
    product_name: Optional[str] = Field(None, description="Optional product name for context")


class SentimentAnalysisResult(BaseModel):
    """Single review analysis result"""
    review_text: str
    sentiment: SentimentLabel
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    model_used: str
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    aspects: Optional[List[str]] = Field(None, description="Key aspects mentioned in the review")


class SentimentResponse(BaseModel):
    """Single review analysis response"""
    result: SentimentAnalysisResult




# AgentService import 
from main.services.agent_service import AgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["reviews"])

# Global agent service
agent_service: Optional[AgentService] = None


def set_agent_service(service: AgentService):
    """Set the global agent service instance"""
    global agent_service
    agent_service = service


@router.post("/reviews/analyze", response_model=SentimentResponse)
async def analyze_review(request: ReviewRequest):
    """
    Analyze sentiment of a single product review.
    
    Returns sentiment classification (POSITIVE/NEGATIVE/NEUTRAL/MIXED),
    confidence score, model used, and key aspects mentioned in the review.
    
    TODO: Implement the following steps:
    1. Check if agent_service is initialized (raise HTTPException with status 503 if not)
    2. Call agent_service.analyze_review_sentiment() with the request data
    3. Check if the result indicates success
    4. Handle error cases appropriately
    5. Construct and return a SentimentResponse with the analysis result
    """
    # TODO: Step 1 - Check if agent_service is initialized
    # Hint: Use agent_service.is_initialized() method
    # If not initialized, raise HTTPException with status_code=503
    # Error message: "Service not ready. Please wait for initialization."
    try:
        if not agent_service or not agent_service.is_initialized():
            raise HTTPException(status_code=503, detail="Service not ready. Please wait for initialization.")
        
        # TODO: Step 2 - Call the agent service to analyze the review
        # Hint: Use await agent_service.analyze_review_sentiment()
        # Pass: review_text, product_id, and product_name from the request
        # Store the result in a variable
        result = await agent_service.analyze_review_sentiment(
            review_text=request.review_text,
            product_id=request.product_id,
            product_name=request.product_name
        )
        
        # TODO: Step 3 - Check if the analysis was successful
        # Hint: Check result.get("success")
        # If not successful, raise HTTPException with status_code=500
        # Use result.get("error", "Analysis failed") as the detail message
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Analysis failed"))
        
        # TODO: Step 4 - Construct the response
        # Hint: Create a SentimentResponse object with a SentimentAnalysisResult
        # Extract all required fields (review_text, sentiment, confidence, model_used, product_id, product_name, aspects) from the result dictionary and map them to the response model
        # Return the SentimentResponse
        return SentimentResponse(
            result=SentimentAnalysisResult(
                review_text=result["review_text"],
                sentiment=result["sentiment"],
                confidence=result["confidence"],
                model_used=result["model_used"],
                product_id=result.get("product_id"),
                product_name=result.get("product_name"),
                aspects=result.get("aspects")
            )
        )
    
    # TODO: Step 5 - Handle exceptions
    # Hint: Re-raise HTTPException
    # For other exceptions, raise HTTPException with status_code=500 and appropriate error message
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in analyze_review: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")