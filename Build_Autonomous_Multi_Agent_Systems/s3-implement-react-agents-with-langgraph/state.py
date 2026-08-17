from typing import TypedDict, List, Dict, Annotated
import operator

class CustomerSupportState(TypedDict):
    """
    State schema with ReAct tracking fields.
    
    TODO: Define the state schema with the following fields:
    1. messages: Annotated[List, operator.add] - Conversation history
    2. thought_history: Annotated[List[str], operator.add] - Agent's reasoning traces
    3. action_log: Annotated[List[Dict], operator.add] - Tools called and their inputs
    4. observation_results: Annotated[List[str], operator.add] - Tool outputs
    5. task_complete: bool - Termination flag
    
    Note: Use Annotated with operator.add for list fields to ensure they append rather than overwrite.
    """
    messages: Annotated[List, operator.add]
    thought_history: Annotated[List[str], operator.add]
    action_log: Annotated[List[Dict], operator.add]
    observation_results: Annotated[List[str], operator.add]
    task_complete: bool