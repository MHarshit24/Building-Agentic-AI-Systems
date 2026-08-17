import os
from pathlib import Path

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM

from models import ExpensePolicyRequest

# Load environment variables from root .env (4 levels up from this file inside the s7 folder)
BASE_DIR = Path(__file__).resolve().parents[4]
base_env_path = BASE_DIR / ".env"
if base_env_path.exists():
    load_dotenv(dotenv_path=base_env_path)
else:
    load_dotenv()


def _build_azure_llm() -> "LLM":
    """
    Build and return a configured Azure OpenAI LLM instance.

    TODOs:
    1. Read required Azure OpenAI configuration from environment variables.
    2. Validate that required values are present and raise ValueError if any are missing.
    3. Construct and return a CrewAI LLM configured for the Azure OpenAI provider.

    """
    # TODO: Step 1 - Read Azure OpenAI settings from environment
    # Hint: Use os.getenv for AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME, AZURE_OPENAI_API_VERSION.
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT", os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"))
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")

    # TODO: Step 2 - Validate required configuration
    # Hint: Ensure API key, endpoint, and deployment name are not empty before proceeding.
    missing = [name for name, val in [
        ("AZURE_OPENAI_API_KEY", api_key),
        ("AZURE_OPENAI_ENDPOINT", endpoint),
        ("AZURE_OPENAI_LLM_DEPLOYMENT / AZURE_OPENAI_DEPLOYMENT_NAME", deployment),
    ] if not val]
    if missing:
        raise ValueError(f"Missing required Azure OpenAI environment variables: {', '.join(missing)}")

    # TODO: Step 3 - Create and return the LLM instance
    # Hint: Use the LLM class from CrewAI with provider set to "azure_openai".
    return LLM(
        model=f"azure/{deployment}",
        api_key=api_key,
        api_base=endpoint,
        api_version=api_version,
    )


def validate_expense_policy(request: ExpensePolicyRequest) -> str:
    """
    Create and execute the Expense Policy Validator hierarchical crew.

    Returns the final decision as a string.

    TODOs:
    1. Build the shared Azure OpenAI LLM using the helper function.
    2. Define specialist agents for Policy Interpreter and Expense Validator.
    3. Define the Finance Manager manager_agent.
    4. Build a single high-level Task that includes policy text and expense details from the request.
    5. Assemble a hierarchical Crew with the specialists and manager_agent.
    6. Execute the crew and return the final decision text.

    """
    # TODO: Step 1 - Build the Azure OpenAI LLM
    # Hint: Call the helper in this module to obtain the configured LLM instance.
    llm = _build_azure_llm()

    # TODO: Step 2 - Create specialist agents
    # Hint: Define Policy Interpreter and Expense Validator agents using the shared LLM.
    policy_interpreter = Agent(
        role="Policy Interpreter",
        goal=(
            "Accurately interpret company expense policy rules and determine "
            "the applicable limits, receipt requirements, and compliance criteria "
            "for any given expense type."
        ),
        backstory=(
            "You are a meticulous compliance expert with deep knowledge of corporate "
            "expense policies. You translate policy language into clear, actionable "
            "rules that can be applied to individual expense claims."
        ),
        llm=llm,
        verbose=True,
    )

    expense_validator = Agent(
        role="Expense Validator",
        goal=(
            "Evaluate individual expense claims against interpreted policy rules, "
            "calculate any excess amounts, and produce a clear compliance verdict "
            "with detailed reasoning."
        ),
        backstory=(
            "You are a detail-oriented financial analyst specialising in expense "
            "auditing. You apply policy rules to real claims, flag violations, "
            "compute reimbursable vs excess amounts, and document your findings "
            "in a structured, auditable format."
        ),
        llm=llm,
        verbose=True,
    )

    # TODO: Step 3 - Create the Finance Manager manager_agent
    # Hint: Use an Agent with a manager role and goal; do not include it in the specialists list.
    finance_manager = Agent(
        role="Finance Manager",
        goal=(
            "Coordinate the Policy Interpreter and Expense Validator to produce "
            "a complete, auditable expense decision that includes policy interpretation, "
            "compliance check, excess calculation, and a final approve/reject verdict."
        ),
        backstory=(
            "You are a senior Finance Manager responsible for overseeing expense "
            "approvals. You delegate analytical tasks to your specialist team and "
            "synthesise their findings into a final, authoritative decision."
        ),
        llm=llm,
        verbose=True,
    )

    # TODO: Step 4 - Build the high-level Task
    # Hint: Combine a short policy summary with fields from the ExpensePolicyRequest into the description.
    policy_summary = (
        "Company Expense Policy Summary:\n"
        "- Expenses must not exceed the policy limit for the given expense type.\n"
        "- A receipt is required for all expense claims.\n"
        "- Every claim must have a clear and valid business purpose.\n"
        "- Any amount exceeding the policy limit will not be reimbursed.\n"
    )

    expense_details = (
        f"Expense Claim Details:\n"
        f"- Expense Type    : {request.expense_type}\n"
        f"- Claimed Amount  : ${request.amount:.2f}\n"
        f"- Policy Limit    : ${request.policy_limit:.2f}\n"
        f"- Receipt Provided: {'Yes' if request.receipt_provided else 'No'}\n"
        f"- Business Purpose: {request.business_purpose}\n"
    )

    validation_task = Task(
        description=(
            f"{policy_summary}\n"
            f"{expense_details}\n"
            "Using the policy and claim details above:\n"
            "1. Interpret the applicable policy rules for this expense type.\n"
            "2. Check whether the claim complies with every policy rule.\n"
            "3. Calculate the reimbursable amount and any excess.\n"
            "4. Produce a final decision (APPROVED or REJECTED) with full reasoning."
        ),
        expected_output=(
            "A structured expense decision report containing:\n"
            "- Policy interpretation for the expense type\n"
            "- Compliance check results for each policy rule\n"
            "- Reimbursable amount and excess amount (if any)\n"
            "- Final verdict: APPROVED or REJECTED with justification"
        ),
        output_file="expense_decision.md",
        agent=finance_manager,
    )

    # TODO: Step 5 - Assemble the hierarchical Crew
    # Hint: Use Process.hierarchical and pass manager_agent plus the specialists and single Task.
    crew = Crew(
        agents=[policy_interpreter, expense_validator],
        tasks=[validation_task],
        process=Process.hierarchical,
        manager_agent=finance_manager,
        verbose=True,
    )

    # TODO: Step 6 - Execute and return the decision
    # Hint: Run kickoff() on the Crew and return the string form of the result.
    result = crew.kickoff()
    return str(result)