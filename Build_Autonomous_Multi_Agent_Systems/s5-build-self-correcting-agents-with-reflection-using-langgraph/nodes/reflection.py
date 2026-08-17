import json
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage
from state import DocumentationReflectionState
from llm import llm

BASE_DIR = Path(__file__).resolve().parents[3]
base_env_path = BASE_DIR / ".env"
if base_env_path.exists():
    load_dotenv(dotenv_path=base_env_path)
else:
    load_dotenv()

# TODO: Implement reflection_node
# 
# INSTRUCTIONS:
# 1. Get current state: task, draft_output, iteration_count, etc.
# 
# 2. Create a prompt for the LLM that:
#    - Acts as an expert technical reviewer
#    - Evaluates the current draft against criteria:
#      - Completeness (0-10)
#      - Clarity (0-10)
#      - Examples (0-10)
#    - PROVIDES A JSON OUTPUT with:
#      - scores for each criterion and an overall_score
#      - "refined_content": The improved documentation IF overall_score < threshold
#      - "summary": A brief summary of the critique
# 
# 3. Invoke the LLM:
#    - Use `llm.invoke([SystemMessage(...), HumanMessage(...)])`
# 
# 4. Parse the JSON response:
#    - Handle potential markdown wrapping (```json ... ```)
# 
# 5. Update the state:
#    - Append feedback to state["reflection_feedback"]
#    - Update state["quality_score"]
#    - IF score < threshold and iterations < max:
#        - Update state["draft_output"] with "refined_content"
#        - Increment iteration_count
#        - Set output_approved = False
#    - ELSE:
#        - Set output_approved = True
# 
# 6. Return the updated state

def reflection_node(state: DocumentationReflectionState):
    """Critique generated documentation."""
    # TODO: Implement reflection logic
    task_description = state["task_description"]
    draft_output = state["draft_output"]
    iteration_count = state["iteration_count"]
    quality_threshold = state["quality_threshold"]
    max_iterations = state["max_iterations"]

    system_prompt = (
        "You are an expert technical documentation reviewer. "
        "You evaluate documentation rigorously and provide structured JSON feedback. "
        "You MUST respond with valid JSON only — no prose, no markdown outside the JSON block."
    )

    human_prompt = (
        f"Review the following technical documentation written for this task:\n\n"
        f"TASK:\n{task_description}\n\n"
        f"DOCUMENTATION DRAFT:\n{draft_output}\n\n"
        "Evaluate the documentation on these three criteria (each scored 0-10):\n"
        "  - Completeness: Does it cover all necessary sections and information?\n"
        "  - Clarity: Is it easy to understand, especially for beginners?\n"
        "  - Examples: Are there sufficient, correct, and helpful code examples?\n\n"
        "Respond ONLY with a valid JSON object with exactly these keys:\n"
        "{\n"
        '  "completeness": <float 0-10>,\n'
        '  "clarity": <float 0-10>,\n'
        '  "examples": <float 0-10>,\n'
        '  "overall_score": <float 0-10, average of the three>,\n'
        '  "issues": [<list of specific issues found>],\n'
        '  "suggestions": [<list of concrete improvement suggestions>],\n'
        '  "summary": "<one-sentence summary of the critique>",\n'
        f'  "refined_content": "<improved full README.md if overall_score < {quality_threshold}, otherwise empty string>"\n'
        "}"
    )

    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])

    raw = response.content.strip()
    # Remove markdown code fences if present
    if raw.startswith("```json"):
        raw = raw[len("```json"):].strip()
    if raw.startswith("```"):
        raw = raw[3:].strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()

    try:
        critique = json.loads(raw)
        overall_score = float(critique.get("overall_score", 5.0))
    except json.JSONDecodeError:
        critique = {}
        overall_score = 5.0

    summary = critique.get("summary", "No summary available.")
    feedback_entry = f"Iteration {iteration_count + 1}: score={overall_score:.1f} — {summary}"

    # Determine whether to refine or approve
    needs_refinement = overall_score < quality_threshold and iteration_count < max_iterations
    refined_content = critique.get("refined_content", "").strip()

    updated: dict = {
        "quality_score": overall_score,
        "reflection_feedback": [feedback_entry],
    }

    if needs_refinement and refined_content:
        # Clean fences from refined_content in case LLM wrapped it
        if refined_content.startswith("```markdown"):
            refined_content = refined_content[len("```markdown"):].strip()
        if refined_content.startswith("```"):
            refined_content = refined_content[3:].strip()
        if refined_content.endswith("```"):
            refined_content = refined_content[:-3].strip()

        updated["draft_output"] = refined_content
        updated["iteration_count"] = iteration_count + 1
        updated["output_approved"] = False
    else:
        updated["output_approved"] = True

    return updated