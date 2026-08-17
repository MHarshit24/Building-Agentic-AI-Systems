from typing import TypedDict, List, Dict, Annotated
import operator


class MarketResearchState(TypedDict):
    """State schema for Plan-Act-Check Market Research Agent."""
    messages: Annotated[list, operator.add]
    
    # Planning phase
    plan: List[Dict]
    current_step: int
    
    # Execution phase
    execution_results: Annotated[List[Dict], operator.add]
    
    # Verification phase
    verification_status: Annotated[List[Dict], operator.add]
    
    # Control flags
    task_complete: bool
    needs_replanning: bool
    replan_attempts: int

