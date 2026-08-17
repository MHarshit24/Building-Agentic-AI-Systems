"""
LLM service for initializing Azure OpenAI Chat models.

TODO: Complete the implementation of initialize_llm() function.
This function should initialize an Azure OpenAI Chat model using LangChain's AzureChatOpenAI class.
"""

# TODO: Import necessary modules
# Verify these imports are correct for your implementation:
from typing import Dict, Any
from langchain_openai import AzureChatOpenAI
from ..config import logger


def initialize_llm(config: Dict[str, Any]) -> AzureChatOpenAI:
    """
    Initialize Azure ChatOpenAI LLM with GPT-4o-mini.
    
    This function creates and configures an Azure OpenAI Chat model instance
    that will be used for generating answers in the RAG pipeline.
    
    Args:
        config: Configuration dictionary containing Azure OpenAI settings.
                Expected keys:
                - 'azure_endpoint': Azure OpenAI endpoint URL
                - 'azure_llm_deployment': Deployment name (e.g., 'gpt-4o-mini')
                - 'azure_api_key': Azure OpenAI API key
                - 'api_version': API version (e.g., '2024-02-01')
        
    Returns:
        Initialized AzureChatOpenAI instance ready for use
        
    Raises:
        Exception: If LLM initialization fails
        
    Hints:
        1. Wrap the initialization in a try-except block for error handling
        2. Create an AzureChatOpenAI instance with the following parameters:
           - azure_endpoint: from config['azure_endpoint']
           - azure_deployment: from config['azure_llm_deployment']
           - api_key: from config['azure_api_key']
           - api_version: from config['api_version']
           - temperature: 0.1 (low temperature for factual, consistent responses)
           - max_tokens: 1000 (maximum response length)
        3. Return the initialized LLM instance
        4. In the except block, re-raise the exception
    """
    try:
        # TODO: Step 1 - Create AzureChatOpenAI instance
        # Initialize the LLM with parameters from config dictionary
        # Remember to set:
        #   - azure_endpoint
        #   - azure_deployment
        #   - api_key
        #   - api_version
        #   - temperature=0.1 (for factual accuracy)
        #   - max_tokens=1000

        logger.info(
            "Initializing Azure OpenAI LLM"
        )

        llm = AzureChatOpenAI(
            azure_endpoint=config[
                'azure_endpoint'
            ],
            azure_deployment=config[
                'azure_llm_deployment'
            ],
            api_key=config[
                'azure_api_key'
            ],
            api_version=config[
                'api_version'
            ],
            temperature=0.1,
            max_tokens=1000
        )

        logger.info(
            "Azure OpenAI LLM initialized successfully"
        )

        # TODO: Step 2 - Return the initialized LLM instance

        return llm

    except Exception as e:

        logger.error(
            f"LLM initialization failed: {e}",
            exc_info=True
        )

        # TODO: Step 3 - Handle errors
        # Re-raise the exception

        raise