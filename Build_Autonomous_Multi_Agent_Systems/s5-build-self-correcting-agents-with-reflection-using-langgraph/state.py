# TODO: Define DocumentationReflectionState TypedDict
# Required fields:
# - messages: Annotated[list, operator.add]
# - task_description: str
# - draft_output: str
# - reflection_feedback: Annotated[List[str], operator.add]
# - iteration_count: int
# - quality_score: float
# - quality_threshold: float
# - max_iterations: int
# - output_approved: bool

from typing import TypedDict, Annotated, List
import operator


class DocumentationReflectionState(TypedDict):
    """
    State schema for technical documentation generation agent with self-reflection.
    
    INSTRUCTIONS:
    Define the following fields in the TypedDict:
    
    1. messages: Annotated[list, operator.add]
       - List of messages in the conversation history
       
    2. task_description: str
       - The initial python code or task description provided by the user
       
    3. draft_output: str
       - The current draft of the generated documentation
       
    4. reflection_feedback: Annotated[List[str], operator.add]
       - List of feedback/critiques from previous iterations
       
    5. iteration_count: int
       - Current iteration number (starts at 0)
       
    6. quality_score: float
       - Current quality score (0-10) assigned by the reflector
       
    7. quality_threshold: float
       - Minimum score required for approval (default from request)
       
    8. max_iterations: int
       - Maximum number of refinement iterations allowed
       
    9. output_approved: bool
       - Boolean flag indicating if the documentation is approved
    """
    # TODO: content...
    messages: Annotated[list, operator.add]
    task_description: str
    draft_output: str
    reflection_feedback: Annotated[List[str], operator.add]
    iteration_count: int
    quality_score: float
    quality_threshold: float
    max_iterations: int
    output_approved: bool