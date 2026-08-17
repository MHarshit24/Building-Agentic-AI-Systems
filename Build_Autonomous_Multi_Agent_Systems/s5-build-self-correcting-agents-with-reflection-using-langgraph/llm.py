# TODO: Initialize Azure OpenAI LLM
# 
# INSTRUCTIONS:
# 1. Load environment variables using `load_dotenv()`
# 
# 2. Get the required environment variables:
#    - AZURE_OPENAI_API_KEY
#    - AZURE_OPENAI_ENDPOINT
#    - AZURE_OPENAI_API_VERSION
#    - AZURE_OPENAI_DEPLOYMENT_NAME (or MODEL_NAME)
# 
# 3. Initialize `AzureChatOpenAI` with:
#    - api_key
#    - azure_endpoint
#    - api_version
#    - azure_deployment (or validation logic)
#    - temperature=0
#    - max_retries=3
#    - timeout=60
# 
# 4. Export the instance as `llm`

import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

BASE_DIR = Path(__file__).resolve().parents[2]
base_env_path = BASE_DIR / ".env"
if base_env_path.exists():
    load_dotenv(dotenv_path=base_env_path)
else:
    load_dotenv()

api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_version = os.getenv("AZURE_OPENAI_API_VERSION")
azure_deployment = (
    os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")
    or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    or os.getenv("MODEL_NAME")
)

llm = AzureChatOpenAI(
    api_key=api_key,
    azure_endpoint=azure_endpoint,
    api_version=api_version,
    azure_deployment=azure_deployment,
    temperature=0,
    max_retries=3,
    timeout=60,
)