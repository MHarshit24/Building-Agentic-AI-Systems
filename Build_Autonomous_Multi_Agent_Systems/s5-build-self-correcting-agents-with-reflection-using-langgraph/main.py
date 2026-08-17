import logging
import time
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from graph import build_graph
import uvicorn

# TODO: Implement FastAPI application
# - Create FastAPI app
# - Build graph at startup
# - Create DocumentationRequest and DocumentationResponse
# - POST /generate endpoint:
#   - Accept DocumentationRequest (task_description, quality_threshold, max_iterations)
#   - Initialize state
#   - Run graph
#   - Return DocumentationResponse
# - GET /health endpoint
# - Print results to console



# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('agent.log')
    ]
)

logger = logging.getLogger(__name__)

# TODO: Create FastAPI app
# 
# INSTRUCTIONS:
# 1. Initialize FastAPI app:
#    - title="Technical Documentation Generator"
#    - description="..."
#    - version="0.1.0"

app = FastAPI(
    title="Technical Documentation Generator with Self-Correction",
    description="AI agent that generates technical documentation for Python code and iteratively improves it through self-reflection",
    version="0.1.0"
)


# TODO: Build graph at startup
# 
# INSTRUCTIONS:
# 1. Call build_graph() and assign to doc_graph
# 2. Add logging to indicate startup

logger.info("Building documentation generation graph...")
doc_graph = build_graph()
logger.info("Graph built successfully")


# TODO: Implement DocumentationRequest and DocumentationResponse
# 
# INSTRUCTIONS:
# 1. DocumentationRequest(BaseModel):
#    - task_description: str (required)
#    - quality_threshold: float (default 8.0)
#    - max_iterations: int (default 3)
# 
# 2. DocumentationResponse(BaseModel):
#    - status: str
#    - task_description: str
#    - generated_documentation: str
#    - reflection_history: List[str]
#    - iterations: int
#    - final_quality_score: float
#    - approved: bool
#    - execution_time: float

class DocumentationRequest(BaseModel):
    task_description: str
    quality_threshold: float = 8.0
    max_iterations: int = 3

class DocumentationResponse(BaseModel):
    status: str
    task_description: str
    generated_documentation: str
    reflection_history: list[str]
    iterations: int
    final_quality_score: float
    approved: bool
    execution_time: float


# TODO: Implement POST /generate endpoint
@app.post("/generate", response_model=DocumentationResponse)
async def generate_documentation(request: DocumentationRequest):
    """Generate technical documentation for Python code."""
    # TODO: Implement endpoint logic
    # 
    # INSTRUCTIONS:
    # 1. Initialize state dictionary with:
    #    - task_description from request
    #    - quality_threshold from request
    #    - max_iterations from request
    #    - default values for other fields
    # 
    # 2. Invoke the graph:
    #    - Use `await asyncio.to_thread(doc_graph.invoke, ...)` to avoid blocking
    #    - Handle timeouts (optional but recommended)
    # 
    # 3. Process result:
    #    - Extract final state values
    #    - Calculate execution time
    # 
    # 4. Return DocumentationResponse

    initial_state = {
        "messages": [],
        "task_description": request.task_description,
        "draft_output": "",
        "reflection_feedback": [],
        "iteration_count": 0,
        "quality_score": 0.0,
        "quality_threshold": request.quality_threshold,
        "max_iterations": request.max_iterations,
        "output_approved": False,
    }

    start_time = time.time()

    try:
        result = await asyncio.to_thread(doc_graph.invoke, initial_state)
    except Exception as e:
        logger.error(f"Graph execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {str(e)}")

    execution_time = time.time() - start_time

    return DocumentationResponse(
        status="completed",
        task_description=request.task_description,
        generated_documentation=result.get("draft_output", ""),
        reflection_history=result.get("reflection_feedback", []),
        iterations=result.get("iteration_count", 0),
        final_quality_score=result.get("quality_score", 0.0),
        approved=result.get("output_approved", False),
        execution_time=round(execution_time, 2),
    )

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Technical Documentation Generator with Self-Correction"
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)