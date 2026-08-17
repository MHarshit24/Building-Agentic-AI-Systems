from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv
from pathlib import Path
from tools.tools import search_web, calculate
import os

# Load root .env from Building_Agentic_AI_Systems/ (4 levels up from this file)
_BASE_DIR = Path(__file__).resolve().parents[2]
_base_env_path = _BASE_DIR / ".env"
if _base_env_path.exists():
    load_dotenv(dotenv_path=_base_env_path)
else:
    load_dotenv()

# Azure OpenAI configuration
azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_model = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT", os.getenv("AZURE_OPENAI_MODEL", "gpt-4o-mini"))
azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# Base LLM (for planning, verification, replanning)
llm = AzureChatOpenAI(
    api_key=azure_api_key,
    azure_endpoint=azure_endpoint,
    model=azure_model,
    api_version=azure_api_version,
    temperature=0,
)

# LLM with tools bound (for execution phase only)
llm_with_tools = llm.bind_tools([
    search_web,
    calculate
])