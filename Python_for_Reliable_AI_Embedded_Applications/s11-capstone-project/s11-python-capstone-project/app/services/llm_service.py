from google import genai
from app.config.settings import GEMINI_API_KEY, GEMINI_MODEL
from app.utils.logger import logger #N
from app.utils.error_handler import handle_llm_error #N
from app.utils.error_handler import raise_ai_service_error

client = genai.Client(api_key=GEMINI_API_KEY)


def call_gemini(prompt: str) -> str:
    """
    Calls Gemini API and returns response.
    Handles errors gracefully for gRPC compatibility.
    """
    try:

        logger.info("Sending request to Gemini") #N


        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        logger.info("Gemini response received") #N

        return response.text

    except Exception as e:
        logger.error(f"Gemini API error: {str(e)}") #N
        raise_ai_service_error() 


def stream_gemini(prompt: str):
    """
    Send a prompt to Gemini API and return the generated response.

    This function:
    - Sends request to Gemini model
    - Logs request and response
    - Handles API errors

    Args:
        prompt (str): Input prompt for the AI model

    Returns:
        str: Generated response text

    Raises:
        HTTPException: If AI service fails
    """
    try:

        logger.info("Starting Gemini stream") #N

        response = client.models.generate_content_stream(
            model=GEMINI_MODEL,
            contents=prompt
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text

    except Exception as e:
        logger.error(f"Streaming error: {str(e)}") #N
        raise_ai_service_error() 