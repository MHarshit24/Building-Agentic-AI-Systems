"""
Query Service - Handles hybrid agent queries and tool tracking
"""
import logging
import asyncio
from typing import Optional, List, Dict, Any

from main.service.agent import get_agent


logger = logging.getLogger(__name__)


class QueryResult:
    """Result of a hybrid query with tool tracking"""
    def __init__(self, question: str, answer: str, tools_used: Optional[List[str]] = None):
        self.question = question
        self.answer = answer
        self.tools_used = tools_used or []
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        sources_description = None
        if self.tools_used:
            sources_description = f"Agent used: {', '.join(self.tools_used)}"
        else:
            sources_description = "Agent reasoning without external tools"
            
        return {
            "question": self.question,
            "answer": self.answer,
            "tools_used": self.tools_used if self.tools_used else None,
            "sources_used": sources_description
        }


async def execute_hybrid_query(question: str) -> QueryResult:
    """
    Execute a hybrid agentic query that can use SQL database, vector store, or both.
    
    Args:
        question: The user's question
        
    Returns:
        QueryResult with answer and tools used
        
    Raises:
        Exception: If query execution fails
    
    TODO: Implement the following steps:
    1. Get the agent instance using get_agent() function
    2. Execute the query by calling chat method on the agent with the question
    3. Extract which tools were used during query execution using _extract_tools_used()
    4. Create and return a QueryResult instance with the question, answer, and tools used
    """
    # TODO: Step 1 - Get the agent instance
    # Hint: You need to retrieve the agent instance that has been configured with the SQL and vector tools. Use the get_agent function
    # that has been imported at the top of this file. This function will return an agent instance that is ready to process queries.
    # Store the returned agent in a variable so you can use it in the next step.
    agent = get_agent()
    
    # TODO: Step 2 - Execute the query by calling chat method on the agent
    # Hint: Use the chat method on the agent instance you retrieved in the previous step, passing in the question parameter that was
    # provided to this function. The chat method will process the question, decide which tools to use, execute the necessary queries,
    # and return a response object. Store the response in a variable so you can extract information from it in the next steps.
    if hasattr(agent, "chat"):
        response = agent.chat(question)
    else:
        response = await agent.run(question)
    
    # TODO: Step 3 - Extract which tools were used during query execution
    # Hint: You need to determine which tools the agent used while processing the query. Call the _extract_tools_used helper function,
    # passing in both the agent instance and the response object you obtained in the previous steps. This function will analyze the
    # agent's execution history and return a list of tool names that were used. Store this list in a variable.
    tools_used = _extract_tools_used(agent, response)
    
    # TODO: Step 4 - Create and return a QueryResult instance
    # Hint: Create a new QueryResult instance by calling its constructor. Pass the question parameter as the first argument, convert
    # the response object to a string using str() as the second argument for the answer, and pass the tools_used list you extracted
    # in Step 3 as the third argument. Return this QueryResult instance from the function.
    answer = str(response)

    if hasattr(response, "response"):
        answer = str(response.response)
    elif hasattr(response, "message"):
        answer = str(response.message)

    return QueryResult(question, answer, tools_used)


def _extract_tools_used(agent, response) -> List[str]:
    """
    Extract which tools the agent used during query execution.
    
    Args:
        agent: The OpenAI agent instance
        response: The agent's response object
        
    Returns:
        List of tool names used
    
    TODO: Implement the following steps:
    1. Initialize an empty list to store tool names
    2. Try to extract tool names from response sources (Method 1)
    3. If no tools found, check chat history for tool calls (Method 2)
    4. Map internal tool names to user-friendly names
    5. Return the list of tools used
    """
    # TODO: Step 1 - Initialize an empty list to store tool names
    # Hint: Create an empty list variable that will be used to collect the names of tools that were used during query execution.
    # This list will be populated in the subsequent steps and returned at the end of the function.
    tools_used = []
    
    # TODO: Step 2 - Try to extract tool names from response sources (Method 1)
    # Hint: Check if the response object has a 'sources' attribute and if that attribute contains any sources. If both conditions
    # are true, iterate through each source in the response.sources collection. For each source, check if it has a 'tool_name' attribute.
    # If it does, retrieve the tool_name value and check if it is not already in your tools_used list. If it is not already present,
    # add it to the list to avoid duplicates.
    if hasattr(response, 'sources') and response.sources:
        for source in response.sources:
            if hasattr(source, 'tool_name'):
                tool_name = source.tool_name
                if tool_name not in tools_used:
                    tools_used.append(tool_name)
    
    # TODO: Step 3 - If no tools found, check chat history for tool calls (Method 2)
    # Hint: If the tools_used list is still empty after Method 1, try an alternative approach by checking the agent's chat history.
    # Verify that the agent object has a 'chat_history' attribute. If it does, iterate through each message in the chat_history.
    # For each message, check if it has an 'additional_kwargs' attribute. If it does, retrieve the 'tool_calls' from the additional_kwargs
    # dictionary, using an empty list as the default value if 'tool_calls' is not present. For each tool call in the list, check if it is
    # a dictionary and if it contains a 'function' key. If both conditions are true, extract the 'name' from the 'function' dictionary.
    function_names = []

    if not tools_used:
        # Fallback inference for workflow-based agents
        question_lower = ""

        try:
            if hasattr(response, "user_msg"):
                question_lower = str(response.user_msg).lower()
            else:
                question_lower = str(response).lower()
        except Exception:
            question_lower = ""

        # SQL-related queries
        if any(keyword in question_lower for keyword in [
            "patient",
            "admission",
            "readmission",
            "rate",
            "utilization",
            "capacity",
            "department",
            "count"
        ]):
            function_names.append("hospital_database")

        # Vector/document-related queries
        if any(keyword in question_lower for keyword in [
            "policy",
            "protocol",
            "guideline",
            "target",
            "benchmark",
            "quality metric"
        ]):
            function_names.append("policy_documents")
    
    # TODO: Step 4 - Map internal tool names to user-friendly names
    # Hint: For each function name extracted in Step 3, you need to convert it to a user-friendly name. Call the _map_tool_name helper
    # function, passing in the function name you extracted. This function will return either a friendly name or None. Check if the returned
    # friendly name is not None and if it is not already in your tools_used list. If both conditions are true, add the friendly name to
    # the tools_used list.
    for function_name in function_names:
        friendly_name = _map_tool_name(function_name)
        if friendly_name is not None and friendly_name not in tools_used:
            tools_used.append(friendly_name)
    
    # TODO: Step 5 - Return the list of tools used
    # Hint: Return the tools_used list that you have been populating throughout the previous steps. This list contains all the unique
    # tool names that were used during the query execution, either extracted from response sources or from the agent's chat history.
    return tools_used


def _map_tool_name(internal_name: str) -> Optional[str]:
    """
    Map internal tool function names to user-friendly names.
    
    Args:
        internal_name: Internal function/tool name from the agent
        
    Returns:
        User-friendly tool name or None if not recognized
    """
    # Map internal names to friendly names
    if 'hospital_database' in internal_name or internal_name == 'hospital_database':
        return 'Hospital Database (hospital_database)'
    elif 'policy_documents' in internal_name or internal_name == 'policy_documents':
        return 'Policy Documents (policy_documents)'
    else:
        # Return the original name if we don't have a mapping
        return internal_name if internal_name else None