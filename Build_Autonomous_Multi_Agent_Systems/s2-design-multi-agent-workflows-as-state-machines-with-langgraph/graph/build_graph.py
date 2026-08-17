def build_graph():
    """
    Builds the LangGraph workflow for loan application assessment.
    
    TODO:
    1. Import all necessary modules (StateGraph, END, state, nodes, routing)
    2. Create StateGraph with LoanApplicationState
    3. Register all nodes using add_node (triage_agent, home_loan_reviewer, credit_score_reviewer, property_assessor, personal_loan_reviewer, auto_loan_reviewer, final_aggregator)
    4. Set entry point to "triage_agent"
    5. Add conditional edges from triage_agent using route_loan_type function
    6. For home loans: add separate edges from home_loan_reviewer to credit_score_reviewer and property_assessor (fan-out)
    7. Add edge from [credit_score_reviewer, property_assessor] to final_aggregator (fan-in using list syntax)
    8. Add edges from personal_loan_reviewer and auto_loan_reviewer directly to final_aggregator
    9. Add edge from final_aggregator to END
    10. Return compiled graph
    
    Important notes:
    - Use separate add_edge calls for parallel fan-out (not list syntax for end_key)
    - Use list syntax add_edge([node1, node2], target) for fan-in/join (list for start_key)
    """
    # TODO: Implement build_graph logic
    from langgraph.graph import StateGraph, END
    from state.loan_state import LoanApplicationState
    from nodes.triage_agent import triage_agent
    from nodes.home_loan_reviewer import home_loan_reviewer
    from nodes.credit_score_reviewer import credit_score_reviewer
    from nodes.property_assessor import property_assessor
    from nodes.personal_loan_reviewer import personal_loan_reviewer
    from nodes.auto_loan_reviewer import auto_loan_reviewer
    from nodes.final_aggregator import final_aggregator
    from routing.route_loan_type import route_loan_type

    builder = StateGraph(LoanApplicationState)

    # Register all nodes
    builder.add_node("triage_agent", triage_agent)
    builder.add_node("home_loan_reviewer", home_loan_reviewer)
    builder.add_node("credit_score_reviewer", credit_score_reviewer)
    builder.add_node("property_assessor", property_assessor)
    builder.add_node("personal_loan_reviewer", personal_loan_reviewer)
    builder.add_node("auto_loan_reviewer", auto_loan_reviewer)
    builder.add_node("final_aggregator", final_aggregator)

    # Entry point
    builder.set_entry_point("triage_agent")

    # Conditional routing from triage_agent
    builder.add_conditional_edges(
        "triage_agent",
        route_loan_type,
        {
            "home_loan_reviewer": "home_loan_reviewer",
            "personal_loan_reviewer": "personal_loan_reviewer",
            "auto_loan_reviewer": "auto_loan_reviewer",
            "final_aggregator": "final_aggregator",
        }
    )

    # Fan-out: home_loan_reviewer → parallel sub-agents (separate add_edge calls)
    builder.add_edge("home_loan_reviewer", "credit_score_reviewer")
    builder.add_edge("home_loan_reviewer", "property_assessor")

    # Fan-in: parallel sub-agents → final_aggregator (list syntax for start_key)
    builder.add_edge(["credit_score_reviewer", "property_assessor"], "final_aggregator")

    # Direct edges for personal and auto paths
    builder.add_edge("personal_loan_reviewer", "final_aggregator")
    builder.add_edge("auto_loan_reviewer", "final_aggregator")

    # Final edge to END
    builder.add_edge("final_aggregator", END)

    return builder.compile()