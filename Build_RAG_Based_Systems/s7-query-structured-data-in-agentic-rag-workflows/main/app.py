"""
FastAPI Application - Healthcare Analytics Platform
"""
from fastapi import FastAPI
from main.routes import query_routes, ingestion_routes

app = FastAPI(
    title="Healthcare Analytics Platform API",
    description="An intelligent agentic RAG system that combines hospital operational database queries with policy document search",
    version="1.0.0",
    openapi_version="3.0.3"
)

from fastapi.openapi.utils import get_openapi


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    try:
        upload_schema = (
            schema["components"]["schemas"]
            ["Body_upload_documents_api_documents_upload_post"]
            ["properties"]["files"]["items"]
        )

        upload_schema.pop("contentMediaType", None)

        upload_schema["format"] = "binary"

    except Exception as e:
        print(f"OpenAPI patch skipped: {e}")

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi

# Include routers
app.include_router(query_routes.router, prefix="/api", tags=["Query"])
app.include_router(ingestion_routes.router, prefix="/api", tags=["Ingestion"])

@app.get("/")
def root():
    return {
        "message": "Healthcare Analytics Platform API",
        "docs": "/docs",
        "endpoints": {
            "query": "/api/query",
            "upload_documents": "/api/documents/upload",
        }
    }