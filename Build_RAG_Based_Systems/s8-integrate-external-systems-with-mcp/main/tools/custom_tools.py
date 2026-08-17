import json
import os
import time
from llama_index.core.tools import FunctionTool

# Import HuggingFace library with fallback
try:
    from huggingface_hub import InferenceClient
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False
    import requests

def hf_inference_api(model_id: str, text: str) -> str:
    """
    Runs inference on a specific Hugging Face model using the Inference API.
    This tool is optimized for product review sentiment analysis.
    
    Use this ONLY when you have a specific model ID from the model_search MCP tool.
    If a model fails, ask the agent to search for a different model instead of 
    using hardcoded fallbacks.
    
    Args:
        model_id (str): The exact model ID from Hugging Face Hub (e.g., 'distilbert-base-uncased-finetuned-sst-2-english').
        text (str): The product review text to analyze.
        
    Returns:
        str: JSON-formatted response containing results and scores, or an error message.
    
    TODO: Implement the following steps:
    1. Check if HuggingFace Hub library is available
    2. Call the appropriate helper function based on availability
    """
    # TODO: Step 1 - Check library availability
    # Hint: Check if HF_HUB_AVAILABLE is True
    
    # TODO: Step 2 - Call appropriate helper function
    # Hint: If HF_HUB_AVAILABLE is True, call _call_with_hub_client(model_id, text)
    # Otherwise, call _call_with_requests(model_id, text)
    # Return the result
    if HF_HUB_AVAILABLE:
        return _call_with_hub_client(model_id, text)
    else:
        return _call_with_requests(model_id, text)

def _call_with_hub_client(model_id: str, text: str) -> str:
    """
    Call inference using the HuggingFace Hub client library.
    
    Args:
        model_id (str): The ID of the model.
        text (str): The product review text to analyze.
        
    Returns:
        str: JSON-formatted response or error message.
    
    TODO: Implement the following steps:
    1. Get HF_TOKEN from environment variables
    2. Validate token and return error if not set
    3. Create InferenceClient instance
    4. Call text_classification method and format the response
    5. Handle exceptions and return error with suggestions
    """
    # TODO: Step 1 - Get token from environment
    # Hint: Use os.getenv("HF_TOKEN") to get the token
    token = os.getenv("HF_TOKEN")
    
    # TODO: Step 2 - Validate token
    # Hint: If token is not set, return a JSON string with error information
    # Use json.dumps() to format the error dictionary with:
    #   - error: "HF_TOKEN not configured"
    #   - details: "HF_TOKEN environment variable is not set"
    #   - suggestion: Include link to https://huggingface.co/settings/tokens
    # Use indent=2 for readable JSON
    if not token:
        return json.dumps({
            "error": "HF_TOKEN not configured",
            "details": "HF_TOKEN environment variable is not set",
            "suggestion": "Set HF_TOKEN with a token from https://huggingface.co/settings/tokens"
        }, indent=2)
    
    # TODO: Step 3 - Create InferenceClient
    # Hint: Create an InferenceClient instance with token=token parameter
    # Store it in a variable named client
    client = InferenceClient(token=token)
    
    # TODO: Step 4 - Call text classification
    # Hint: Use client.text_classification(text, model=model_id) to get results
    # Format the results as a list of dictionaries with "label" and "score" keys
    # Convert to JSON string using json.dumps() with indent=2
    # Wrap in try-except block
    try:
        results = client.text_classification(text, model=model_id)
        formatted = [{"label": r.label, "score": r.score} for r in results]
        return json.dumps(formatted, indent=2)
    
    # TODO: Step 5 - Handle exceptions
    # Hint: In the except block, catch Exception and get error message
    # Return a JSON string with:
    #   - error: f"Model '{model_id}' failed"
    #   - details: error message
    #   - suggestion: Message about using model_search to find different models
    except Exception as e:
        return json.dumps({
            "error": f"Model '{model_id}' failed",
            "details": str(e),
            "suggestion": "Use model_search tool to find a different sentiment analysis model and retry."
        }, indent=2)

def _call_with_requests(model_id: str, text: str) -> str:
    """
    Fallback method using requests library directly.
    
    Args:
        model_id (str): The ID of the model.
        text (str): The product review text to analyze.
        
    Returns:
        str: JSON-formatted response or error message.
    
    TODO: Implement the following steps:
    1. Import requests library
    2. Get HF_TOKEN from environment and validate
    3. Build API URL and set up headers and payload
    4. Make POST request to HuggingFace Inference API
    5. Handle different status codes (200, 503, others)
    6. Handle exceptions and return appropriate error messages
    """
    # TODO: Step 1 - Import requests
    # Hint: Use import requests at the beginning of the function
    import requests
    
    # TODO: Step 2 - Get and validate token
    # Hint: Use os.getenv("HF_TOKEN") to get the token
    # If token is not set, return JSON error similar to _call_with_hub_client
    token = os.getenv("HF_TOKEN")
    if not token:
        return json.dumps({
            "error": "HF_TOKEN not configured",
            "details": "HF_TOKEN environment variable is not set",
            "suggestion": "Set HF_TOKEN with a token from https://huggingface.co/settings/tokens"
        }, indent=2)
    
    # TODO: Step 3 - Build request components
    # Hint: Create api_url as f-string: f"https://api-inference.huggingface.co/models/{model_id}"
    # Create headers dictionary with:
    #   - "Authorization": f"Bearer {token}"
    #   - "Content-Type": "application/json"
    # Create payload dictionary with: {"inputs": text}
    api_url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {"inputs": text}
    
    # TODO: Step 4 - Make POST request
    # Hint: Use requests.post() with api_url, json=payload, headers=headers, timeout=30
    # Store response in a variable
    # Wrap in try-except block
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        
        # TODO: Step 5 - Handle status codes
        # Hint: Check response.status_code:
        #   - If 200: return response.text
        #   - If 503: wait 5 seconds (use time.sleep(5)), retry the request once
        #     If retry succeeds (200), return response.text
        #     If retry fails, return JSON error about model loading
        #   - Otherwise: return JSON error with status code and suggestion
        if response.status_code == 200:
            return response.text
        elif response.status_code == 503:
            time.sleep(5)
            retry = requests.post(api_url, json=payload, headers=headers, timeout=30)
            if retry.status_code == 200:
                return retry.text
            return json.dumps({
                "error": f"Model '{model_id}' is still loading",
                "details": "Model returned 503 after retry",
                "suggestion": "Use model_search tool to find a different sentiment analysis model and retry."
            }, indent=2)
        else:
            return json.dumps({
                "error": f"Request failed with status code {response.status_code}",
                "details": response.text,
                "suggestion": "Use model_search tool to find a different sentiment analysis model and retry."
            }, indent=2)
    
    # TODO: Step 6 - Handle exceptions
    # Hint: In except block, catch Exception and return JSON error with:
    #   - error: "Request failed"
    #   - details: error message string
    #   - suggestion: Message about using model_search
    except Exception as e:
        return json.dumps({
            "error": "Request failed",
            "details": str(e),
            "suggestion": "Use model_search tool to find a different sentiment analysis model and retry."
        }, indent=2)

# TODO: Create the LlamaIndex tool
# Hint: Use FunctionTool.from_defaults() to create a tool from hf_inference_api function
# Parameters:
#   - fn: hf_inference_api function
#   - name: "hf_inference"
#   - description: A detailed description string (multi-line) explaining:
#     * Use this tool ONLY after getting a specific model ID from model_search
#     * Optimized for product review sentiment analysis
#     * Instructions for what to do if inference fails
#     * Args: model_id and text
#     * Returns: JSON with results or error with suggestions
# Store the result in custom_inference_tool variable

# Note: This will be None until you implement it above
# You must create the tool using FunctionTool.from_defaults() before it can be used
custom_inference_tool = FunctionTool.from_defaults(
    fn=hf_inference_api,
    name="hf_inference",
    description=(
        "Use this tool ONLY after obtaining a specific model ID from the model_search MCP tool. "
        "This tool is optimized for product review sentiment analysis using Hugging Face models. "
        "If inference fails for a given model, do NOT use hardcoded fallbacks — instead use "
        "model_search to find a different model and retry with the new model ID. "
        "Args: "
        "  model_id (str): The exact Hugging Face model ID (e.g., 'distilbert-base-uncased-finetuned-sst-2-english'). "
        "  text (str): The product review text to analyze. "
        "Returns: JSON string with a list of label/score results on success, "
        "or a JSON error object with an error message and suggestions on failure."
    )
)