import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from state import DocumentationReflectionState
from llm import llm

BASE_DIR = Path(__file__).resolve().parents[3]
base_env_path = BASE_DIR / ".env"
if base_env_path.exists():
    load_dotenv(dotenv_path=base_env_path)
else:
    load_dotenv()

# TODO: Implement generation_node
# 
# INSTRUCTIONS:
# 1. Get the task description from state["task_description"]
# 
# 2. Create a prompt for the LLM that:
#    - Acts as an expert technical writer
#    - Asks to generate a README.md for the provided Python code
#    - Requires sections: Overview, Installation, Usage, API Documentation
#    - Enforces markdown format
# 
# 3. Invoke the LLM:
#    - Use `llm.invoke([SystemMessage(...), HumanMessage(...)])`
# 
# 4. Process the response:
#    - Extract the content
#    - Clean up any markdown code blocks if necessary (e.g. remove ```markdown ... ```)
# 
# 5. Connect to the graph:
#    - Update state["draft_output"] with the generated documentation
#    - Initialize state["iteration_count"] to 0 (or reset it)
#    - Set state["output_approved"] to False
# 
# 6. Return the updated state

def generation_node(state: DocumentationReflectionState):
    """Generate initial technical documentation."""
    # TODO: Implement generation logic
    task_description = state["task_description"]

    system_prompt = (
        "You are an expert technical writer who specializes in creating clear, "
        "comprehensive, and beginner-friendly documentation for Python projects. "
        "Always produce output in valid Markdown format suitable for a README.md file."
    )

    human_prompt = (
        f"Generate a complete README.md for the following Python code or task:\n\n"
        f"{task_description}\n\n"
        "The README.md must contain these sections:\n"
        "1. Overview — what the code does and why it is useful\n"
        "2. Installation — step-by-step setup instructions\n"
        "3. Usage — concrete examples showing how to use the code\n"
        "4. API Documentation — descriptions of all public functions/classes/endpoints\n\n"
        "Write in a beginner-friendly style. Output only the Markdown content, "
        "without any surrounding explanation."
    )

    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])

    documentation = response.content
    # Clean up any markdown code fences that the LLM may have wrapped around the output
    if documentation.startswith("```markdown"):
        documentation = documentation[len("```markdown"):].strip()
    if documentation.startswith("```"):
        documentation = documentation[3:].strip()
    if documentation.endswith("```"):
        documentation = documentation[:-3].strip()

    return {
        "draft_output": documentation,
        "iteration_count": 0,
        "output_approved": False,
    }