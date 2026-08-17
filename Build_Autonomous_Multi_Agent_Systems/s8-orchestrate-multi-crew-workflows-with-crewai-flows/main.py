from fastapi import FastAPI, HTTPException
from models import ResumeRequest, ResumeResponse
from services import process_resume

app = FastAPI(
    title="Resume Screening API",
    description="API for screening resumes using CrewAI Flows",
    version="1.0.0"
)

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {"message": "Resume Screening API Boilerplate is running"}

@app.post("/screen", response_model=ResumeResponse)
async def screen_resume(request: ResumeRequest):
    """
    Screen a resume and provide AI-based feedback.
    
    TODOs:
    1. Validate required fields (optional if Pydantic handles it, but good practice).
    2. Call the process_resume service function.
    3. Map the flow state to the ResumeResponse model.
    4. Handle errors with HTTPException.
    """
    # TODO: Step 1 - Call Service
    # Hint: await process_resume(request.candidate_name, request.resume_text, request.applying_for)

    # Basic validation — Pydantic enforces types, but we guard against blank strings
    if not request.candidate_name.strip():
        raise HTTPException(status_code=422, detail="candidate_name must not be empty.")
    if not request.resume_text.strip():
        raise HTTPException(status_code=422, detail="resume_text must not be empty.")
    if not request.applying_for.strip():
        raise HTTPException(status_code=422, detail="applying_for must not be empty.")

    try:
        flow, _ = await process_resume(
            request.candidate_name,
            request.resume_text,
            request.applying_for,
        )
    except ValueError as e:
        # Configuration errors (missing env vars, etc.)
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")
    except Exception as e:
        # TODO: Step 3 - Handle Errors
        raise HTTPException(status_code=500, detail=f"Resume screening failed: {str(e)}")

    # TODO: Step 2 - Create Response
    # Hint: Return ResumeResponse with data from the flow state (flow.state.candidate_name, etc.)
    return ResumeResponse(
        success=True,
        candidate_name=flow.state.candidate_name,
        classified_role=flow.state.classified_role,
        evaluator=flow.state.evaluator_role,
        feedback=flow.state.justification,
    )

    raise NotImplementedError("This route is not yet implemented. Please complete the TODO steps above.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)