from fastapi import FastAPI, Query
from langchain_core.messages import HumanMessage
from graph.graph import app_graph
import asyncio
import uvicorn

app = FastAPI(
    title="Market Research Agent",
    description="Plan-Act-Check agent for market research with web search and analysis",
    version="0.1.0"
)


@app.post("/research")
async def research(
    query: str = Query(..., description="Market research query")
):
    """Run the graph-driven research workflow for a provided query.
    
    TODO:
    1. If query.strip() is empty, return {"status": "error", "message": "Query cannot be empty"}
    2. Initialize state: messages=[HumanMessage(content=query)], plan=[], current_step=1, execution_results=[], verification_status=[], task_complete=False, needs_replanning=False, replan_attempts=0
    3. Use asyncio.wait_for(asyncio.to_thread(app_graph.invoke, state, {"recursion_limit": 25}), timeout=60)
    4. Catch TimeoutError, return {"status": "timeout", "message": "Request timed out..."}
    5. Catch Exception, return {"status": "error", "message": f"Execution error: {str(e)}"}
    6. Return {"status": "success", "task_complete": result.get("task_complete", False), "plan": result["plan"], "execution_results": result["execution_results"], "verification_status": result["verification_status"]}
    """
    # TODO: Step 1 - Validate query
    if not query.strip():
        return {"status": "error", "message": "Query cannot be empty"}

    # TODO: Step 2 - Initialize state
    state = {
        "messages": [HumanMessage(content=query)],
        "plan": [],
        "current_step": 1,
        "execution_results": [],
        "verification_status": [],
        "task_complete": False,
        "needs_replanning": False,
        "replan_attempts": 0
    }

    # TODO: Step 3 - Invoke graph
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(app_graph.invoke, state, {"recursion_limit": 25}),
            timeout=180
        )
    # TODO: Step 4 - Handle timeout
    except asyncio.TimeoutError:
        return {"status": "timeout", "message": "Request timed out after 180 seconds. The research query took too long to process."}
    # TODO: Step 5 - Handle exception
    except Exception as e:
        return {"status": "error", "message": f"Execution error: {str(e)}"}

    # TODO: Step 6 - Return success
    return {
        "status": "success",
        "task_complete": result.get("task_complete", False),
        "plan": result["plan"],
        "execution_results": result["execution_results"],
        "verification_status": result["verification_status"]
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)