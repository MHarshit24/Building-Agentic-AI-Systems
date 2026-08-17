# TODO: Implement should_continue function
# 
# INSTRUCTIONS:
# 1. Check the state for:
#    - iteration_count
#    - max_iterations
#    - quality_score
#    - quality_threshold
# 
# 2. Determine the path:
#    - IF iteration_count >= max_iterations: return "approve"
#    - IF quality_score >= quality_threshold: return "approve"
#    - IF quality_score is close to threshold (e.g. >= 7.0): return "approve"
#    - ELSE: return "refine"

from state import DocumentationReflectionState


def should_continue(state: DocumentationReflectionState) -> str:
    """Determine next step based on quality and iterations."""
    # TODO: Implement routing logic
    quality_score = state["quality_score"]
    iteration_count = state["iteration_count"]
    max_iterations = state["max_iterations"]
    quality_threshold = state["quality_threshold"]

    if iteration_count >= max_iterations:
        state["output_approved"] = True
        return "approve"

    if quality_score >= quality_threshold:
        state["output_approved"] = True
        return "approve"

    # Borderline case: close enough to threshold
    if quality_score >= 7.0:
        state["output_approved"] = True
        return "approve"

    return "refine"