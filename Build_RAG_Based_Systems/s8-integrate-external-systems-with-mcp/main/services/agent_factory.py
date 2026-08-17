import logging
import os
from typing import List
from llama_index.core.tools import BaseTool
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.core.agent.workflow import ReActAgent

logger = logging.getLogger(__name__)

def create_llm():
    """
    Factory to create the Azure OpenAI LLM instance.
    """
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    
    if not endpoint or not deployment:
        raise ValueError("Azure OpenAI configuration required. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_LLM_DEPLOYMENT.")
    
    if not api_key:
        raise ValueError("Azure OpenAI API key required. Set AZURE_OPENAI_API_KEY.")
    
    logger.info("Initializing Azure OpenAI LLM...")
    
    return AzureOpenAI(
        engine=deployment,
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
        temperature=0
    )

def create_agent(tools: List[BaseTool], verbose: bool = True) -> ReActAgent:
    """
    Creates a ReActAgent configured with the provided tools and LLM.
    Uses the 0.14.10 workflow API.

    Args:
        tools (List[BaseTool]): The list of MCP-derived tools.
        verbose (bool): Whether to print chain-of-thought reasoning.

    Returns:
        ReActAgent: An initialized agent ready for use.
    
    TODO: Implement the following steps:
    1. Create an LLM instance using the create_llm() function
    2. Create and configure a ReActAgent with the provided tools and LLM
    3. Return the configured agent
    """
    # TODO: Step 1 - Create LLM instance
    # Hint: Use the create_llm() function to get an LLM instance
    # Store the result in a variable
    llm = create_llm()
    
    # TODO: Step 2 - Create ReActAgent
    # Hint: Instantiate ReActAgent with the tools and llm parameters
    # The tools parameter should be the tools argument passed to this function
    # The llm parameter should be the LLM instance created in Step 1
    agent = ReActAgent(tools=tools, llm=llm)
    
    # TODO: Step 3 - Return the agent
    # Hint: Return the ReActAgent instance created in Step 2
    return agent