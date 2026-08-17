from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
# TODO: Step 1 - Import ProductReviewRequest and ProductReviewResponse from models
from models import ProductReviewRequest, ProductReviewResponse
# TODO: Step 2 - Import create_review_analysis_crew from services
from services import create_review_analysis_crew

app = FastAPI(
    title="Product Review Analysis API",
    description="API for analyzing product reviews and generating actionable insights using CrewAI",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Product Review Analysis API",
        "version": "1.0.0",
        "endpoints": {
            "POST /analyze": "Analyze product reviews and generate insights",
            "GET /health": "Health check endpoint"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/analyze", response_model=ProductReviewResponse)  # TODO: Add response_model=ProductReviewResponse after implementing models
async def analyze_product_reviews(request: ProductReviewRequest):  # TODO: Add type hint: request: ProductReviewRequest after implementing models
    # TODO: Uncomment the import statements at the top of the file after implementing models and services
    """
    Analyze product reviews and generate actionable insights.
    
    Args:
        request: ProductReviewRequest containing the product name
        
    Returns:
        ProductReviewResponse with generated insights report
    """
    try:
        # TODO: Step 3 - Validate product name is not empty
        # Hint: Check if request.product is empty or whitespace, raise HTTPException with status_code=400 if invalid
        if not request.product or not request.product.strip():
            raise HTTPException(status_code=400, detail="Product name cannot be empty or whitespace")
        
        # TODO: Step 4 - Create and execute the review analysis crew
        # Hint: Call create_review_analysis_crew(request.product) and store result
        result = create_review_analysis_crew(request.product)
        
        # TODO: Step 5 - Return ProductReviewResponse
        # Hint: Create ProductReviewResponse with insights=result.raw, status="success", 
        # message="Review analysis completed successfully"
        return ProductReviewResponse(
            insights=result.raw,
            status="success",
            message="Review analysis completed successfully",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing product reviews: {str(e)}"
        )