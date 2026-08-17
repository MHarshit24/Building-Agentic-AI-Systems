from fastapi import FastAPI
from .schemas import ConceptRequest, ExplanationResponse
from .llm_app_service import generate_explanation
from .db_operations import insert_query
import os

app = FastAPI(title="AI Tutor Modular API")

MODEL = os.getenv("GEMINI_MODEL")


@app.post("/explain", response_model=ExplanationResponse)
def explain(concept_request: ConceptRequest):

    explanation = generate_explanation(concept_request.concept)

    insert_query(
        concept_request.concept,
        explanation,
        MODEL
    )

    return ExplanationResponse(
        concept=concept_request.concept,
        explanation=explanation,
        model=MODEL
    )