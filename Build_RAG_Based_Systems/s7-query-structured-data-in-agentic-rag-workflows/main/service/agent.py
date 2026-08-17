"""
Agent Service - Creates and manages the OpenAI agent for healthcare analytics
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
try:
    from llama_index.agent.openai import OpenAIAgent

    def create_agent(tools, llm, system_prompt):
        return OpenAIAgent.from_tools(
            tools=tools,
            llm=llm,
            verbose=True,
            system_prompt=system_prompt,
        )

except ImportError:
    from llama_index.core.agent.workflow import ReActAgent

    def create_agent(tools, llm, system_prompt):
        return ReActAgent(
            tools=tools,
            llm=llm,
            verbose=True,
            system_prompt=system_prompt,
        )
from llama_index.core import Settings
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding

from main.service.tools import get_sql_tool, get_vector_tool


def _load_env():
    """
    Load environment variables using dual .env pattern.
    Root .env (parents[4]) is loaded first for secrets: DB_PASSWORD, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT.
    Project .env (parents[2]) is loaded second with override=True for DB config, deployment names, etc.
    Secrets are preserved across the second load so they are never overwritten.
    """
    if "pytest" in sys.modules:
        return

    # This file: main/service/agent.py -> parents[0]=service/, parents[1]=main/, parents[2]=project root, parents[4]=root
    base_dir = Path(__file__).resolve().parents[4]
    base_env_path = base_dir / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()

    # Preserve secrets before loading project .env
    db_password = os.getenv("DB_PASSWORD")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

    # This file: main/service/agent.py -> parents[2] = project root
    proj_dir = Path(__file__).resolve().parents[2]
    proj_env_path = proj_dir / ".env"

    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
    else:
        load_dotenv()

    # Restore preserved secrets so project .env cannot overwrite them
    if db_password:
        os.environ["DB_PASSWORD"] = db_password
    if azure_api_key:
        os.environ["AZURE_OPENAI_API_KEY"] = azure_api_key
    if azure_endpoint:
        os.environ["AZURE_OPENAI_ENDPOINT"] = azure_endpoint

    # Remove conflicting PostgreSQL variables that may come from root .env
    conflicting_pg_vars = [
        "DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
        "PGUSER", "PGPASSWORD", "PGDATABASE",
    ]
    for var in conflicting_pg_vars:
        os.environ.pop(var, None)


_load_env()


# Global agent instance (initialized once)
_agent = None


def get_agent():
    """
    Get or create the OpenAI agent with SQL and Vector tools.
    
    Returns:
        OpenAIAgent instance configured with SQL and Vector tools
    
    TODO: Implement the following steps:
    1. Check if the global agent instance is None
    2. Initialize the Azure OpenAI LLM and set it in Settings
    3. Initialize the Azure OpenAI embedding model and set it in Settings
    4. Get the SQL tool and Vector tool instances
    5. Create a list containing both tools
    6. Create the OpenAIAgent with tools, verbose mode, and system prompt
    7. Store the agent in the global variable and return it
    """
    global _agent

    # TODO: Step 1 - Check if the global agent instance is None
    # Hint: Check whether the global _agent variable is None. This function uses a singleton pattern, so it should only create
    # the agent once. If _agent is not None, it means the agent has already been created and you should skip the initialization
    # steps and return the existing agent. If _agent is None, proceed with the initialization steps below.
    if _agent is not None:
        return _agent
    
    # TODO: Step 2 - Initialize the Azure OpenAI LLM and set it in Settings
    # Hint: Create an AzureOpenAI instance by instantiating the AzureOpenAI class. You need to provide several parameters by
    # retrieving them from environment variables using os.getenv. The model parameter should use "AZURE_OPENAI_LLM_DEPLOYMENT",
    # the deployment_name should also use "AZURE_OPENAI_LLM_DEPLOYMENT", the api_key should use "AZURE_OPENAI_API_KEY",
    # the azure_endpoint should use "AZURE_OPENAI_ENDPOINT", and the api_version should use "AZURE_OPENAI_API_VERSION".
    # Store the created LLM instance in a variable, then assign it to Settings.llm so it can be used throughout the application.
    llm = AzureOpenAI(
        model=os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT"),
        deployment_name=os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )
    Settings.llm = llm
    
    # TODO: Step 3 - Initialize the Azure OpenAI embedding model and set it in Settings
    # Hint: Create an AzureOpenAIEmbedding instance by instantiating the AzureOpenAIEmbedding class. Similar to the LLM, you need
    # to provide parameters from environment variables. The model parameter should use "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", the
    # deployment_name should also use "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", the api_key should use "AZURE_OPENAI_API_KEY",
    # the azure_endpoint should use "AZURE_OPENAI_ENDPOINT", and the api_version should use "AZURE_OPENAI_API_VERSION".
    # Store the created embedding model instance in a variable, then assign it to Settings.embed_model.
    embed_model = AzureOpenAIEmbedding(
        model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        deployment_name=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )
    Settings.embed_model = embed_model
    
    # TODO: Step 4 - Get the SQL tool and Vector tool instances
    # Hint: Call the get_sql_tool function that has been imported at the top of this file to retrieve the SQL database tool.
    # Store the result in a variable. Call the get_vector_tool function that has also been imported to retrieve the vector
    # document search tool. Store this result in another variable. Both of these functions return QueryEngineTool instances that
    # will be used by the agent.
    sql_tool = get_sql_tool()
    vector_tool = get_vector_tool()
    
    # TODO: Step 5 - Create a list containing both tools
    # Hint: Create a list that contains both the SQL tool and the vector tool you retrieved in the previous step. This list will
    # be passed to the agent constructor so the agent knows which tools are available for use.
    tools = [sql_tool, vector_tool]
    
    # TODO: Step 6 - Create the OpenAIAgent with tools, verbose mode, and system prompt
    # Hint: Use the OpenAIAgent.from_tools class method to create an agent instance. Pass the tools list you created in the previous
    # step as the first argument. Set the verbose parameter to True so the agent will provide detailed output during execution.
    # Provide a system_prompt parameter with a multi-line string that defines the agent's role and behavior. The system prompt should
    # explain that the agent is a healthcare analytics assistant, provide tool usage guidelines explaining when to use each tool,
    # and include important instructions about comparing metrics, citing sources, protecting patient privacy, and providing actionable
    # insights. Store the created agent instance in the global _agent variable.
    system_prompt = """You are a Healthcare Analytics Assistant for a hospital system.
You help hospital administrators answer questions by combining patient database metrics with policy documents and clinical guidelines.

Tool usage guidelines:
- Use the 'hospital_database' tool for questions about actual patient counts, admission/discharge data, readmission rates, department capacity metrics, bed utilization rates, or any quantitative operational statistics.
- Use the 'policy_documents' tool for questions about targets, benchmarks, protocols, guidelines, regulatory compliance, or policy information from healthcare documents.
- Use both tools when a question requires comparing actual metrics against policy targets or benchmarks (e.g. "Are we meeting our readmission targets?").

Important instructions:
- Always cite which data source (database or policy document) you used to answer each part of the question.
- When comparing metrics, clearly state both the actual value and the target value.
- Protect patient privacy — never expose individual patient identifiers in your responses.
- Provide actionable insights where possible, noting whether performance is above or below target.
- Be concise and clear in your responses, suitable for hospital administrators."""
    _agent = create_agent(
        tools=tools,
        llm=llm,
        system_prompt=system_prompt,
    )
        
    
    # TODO: Step 7 - Store the agent in the global variable and return it
    # Hint: Return the _agent variable. Since you stored the agent in _agent in the previous step, you can simply return it.
    # If the agent was already created (Step 1 check passed), return the existing _agent without going through the initialization steps.
    return _agent