"""State and API request/response schemas for the support agent with checkpointing."""

from typing import TypedDict, Annotated, List, Optional
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class SupportAgentState(TypedDict):
    """
    State schema for the support agent conversation.
    
    TODO:
    1. Define messages: Annotated[list, add_messages]
    2. Define user_name: str
    3. Define issue_type: str
    4. Define conversation_stage: str
    """
    # TODO: Implement SupportAgentState fields
    messages: Annotated[list, add_messages]
    user_name: str
    issue_type: str
    conversation_stage: str


class MessageRequest(BaseModel):
    """
    Request model for sending a message to the graph.
    
    TODO:
    1. Define message: str
    2. Define thread_id: Optional[str]
    """
    # TODO: Implement MessageRequest fields
    message: str
    thread_id: Optional[str] = None


class MessageResponse(BaseModel):
    """
    Response model containing the graph execution result.
    
    TODO:
    1. Define messages: List[dict]
    2. Define user_name: str
    3. Define issue_type: str
    4. Define conversation_stage: str
    5. Define thread_id: str
    """
    # TODO: Implement MessageResponse fields
    messages: List[dict]
    user_name: Optional[str] = None
    issue_type: Optional[str] = None
    conversation_stage: Optional[str] = None
    thread_id: str


class ConversationStateResponse(BaseModel):
    """
    Response model for retrieving conversation state.
    
    TODO:
    1. Define thread_id: str
    2. Define user_name: str
    3. Define issue_type: str
    4. Define conversation_stage: str
    5. Define message_count: int
    """
    # TODO: Implement ConversationStateResponse fields
    thread_id: str
    user_name: Optional[str] = None
    issue_type: Optional[str] = None
    conversation_stage: Optional[str] = None
    message_count: int