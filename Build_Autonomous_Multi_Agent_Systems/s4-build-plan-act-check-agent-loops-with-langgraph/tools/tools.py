from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool

# TODO: Step 1 - Initialize DuckDuckGo search with timeout
# Hint: Use DuckDuckGoSearchRun with a timeout parameter (e.g., 10 seconds) to prevent hanging
# Store it in a variable like ddg_search
# Example: ddg_search = DuckDuckGoSearchRun(timeout=10)
ddg_search = DuckDuckGoSearchRun(timeout=10)


@tool
def search_web(query: str) -> str:
    """Search the web for current information using DuckDuckGo.
    
    TODO:
    1. Invoke ddg_search.invoke(query)
    2. Check if result is empty, return "No results found. Try a different search query."
    3. Handle exceptions, return error message
    4. Return the search result
    """
    # TODO: Step 1 - Invoke search
    # TODO: Step 2 - Check empty result
    # TODO: Step 3 - Handle exceptions
    # TODO: Step 4 - Return result
    try:
        result = ddg_search.invoke(query)
        if not result or not result.strip():
            return "No results found. Try a different search query."
        return result
    except Exception as e:
        return f"Search error: {str(e)}"


@tool
def calculate(expression: str) -> str:
    """Evaluate mathematical expressions.
    
    TODO:
    1. Evaluate expression using eval(expression, {"__builtins__": {}}, {})
    2. Format as "Result: {round(result, 2)}"
    3. Handle exceptions, return "Calculation error: {error}"
    4. Return formatted result
    """
    # TODO: Step 1 - Evaluate expression
    # TODO: Step 2 - Format result
    # TODO: Step 3 - Handle exceptions
    # TODO: Step 4 - Return result
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"Result: {round(result, 2)}"
    except Exception as e:
        return f"Calculation error: {str(e)}"