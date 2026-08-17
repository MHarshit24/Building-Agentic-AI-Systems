import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

def get_llm():
    """Helper function to initialize AzureChatOpenAI using environment variables."""
    BASE_DIR = Path(__file__).resolve().parents[4]

    base_env_path = BASE_DIR / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()

    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT", os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"))
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")

    if not all([api_key, endpoint, deployment, api_version]):
        raise ValueError("Azure OpenAI environment variables are not fully configured. "
                         "Please set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, "
                         "AZURE_OPENAI_LLM_DEPLOYMENT, and AZURE_OPENAI_API_VERSION.")

    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        azure_deployment=deployment,
        api_version=api_version,
    )

def triage_agent(state):
    """
    LLM-based triage agent that determines the loan type based on application details.
    
    TODO:
    1. Get loan_purpose from state["applicant_info"]
    2. Use Azure OpenAI LLM to classify loan type (home, personal, or auto)
    3. Validate LLM response - ensure it's one of: "home", "personal", "auto"
    4. Default to "personal" if response is invalid
    5. Update state["loan_type"] with the classified type
    6. Return updated state
    """
    # TODO: Implement triage_agent logic
    loan_purpose = state["applicant_info"].get("loan_purpose", "")

    llm = get_llm()

    prompt = (
        "Classify the following loan purpose into exactly one of these categories: "
        "home, personal, auto.\n"
        "Respond with only one word — the category name.\n\n"
        f"Loan purpose: {loan_purpose}"
    )

    response = llm.invoke(prompt)
    loan_type = response.content.strip().lower()

    valid_types = ["home", "personal", "auto"]
    if loan_type not in valid_types:
        loan_type = "personal"

    state["loan_type"] = loan_type
    return state