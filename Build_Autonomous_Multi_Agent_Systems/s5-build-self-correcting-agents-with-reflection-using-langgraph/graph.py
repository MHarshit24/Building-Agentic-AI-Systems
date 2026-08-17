from langgraph.graph import StateGraph, END
from state import DocumentationReflectionState
from nodes.generation import generation_node
from nodes.reflection import reflection_node
# TODO: Build the reflection graph
# 
# INSTRUCTIONS:
# 1. Initialize the StateGraph with DocumentationReflectionState
# 
# 2. Add nodes:
#    - "generator": generation_node
#    - "reflector": reflection_node
# 
# 3. Define the flow:
#    - Set entry point to "generator"
#    - Add edge from "generator" to "reflector"
# 
# 4. Add conditional edges from "reflector":
#    - Use the `should_continue` function (you need to import it!)
#    - Dictionary mapping:
#      - "refine": "reflector" (Loop back)
#      - "approve": END (Finish)
# 
# 5. Compile the graph
# 
# 6. Return the compiled app

from routing import should_continue # Ensure this import is executed

def build_graph():
    """Build and compile the documentation reflection graph."""
    # TODO: Implement graph building
    graph = StateGraph(DocumentationReflectionState)

    graph.add_node("generator", generation_node)
    graph.add_node("reflector", reflection_node)

    graph.set_entry_point("generator")
    graph.add_edge("generator", "reflector")

    graph.add_conditional_edges(
        "reflector",
        should_continue,
        {
            "refine": "reflector",
            "approve": END,
        },
    )

    app = graph.compile()
    return app