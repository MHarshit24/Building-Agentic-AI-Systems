def route_loan_type(state):
    """
    Routing function that determines the next node based on loan type.
    Returns the name of the next node to execute.
    
    TODO:
    1. Get loan_type from state
    2. Check if loan_type contains "home" - return "home_loan_reviewer"
    3. Check if loan_type contains "personal" - return "personal_loan_reviewer"
    4. Check if loan_type contains "auto" - return "auto_loan_reviewer"
    5. Default fallback - return "final_aggregator"
    Note: This function is used in add_conditional_edges
    """
    # TODO: Implement route_loan_type logic
    loan_type = state.get("loan_type", "").lower()

    if "home" in loan_type:
        return "home_loan_reviewer"
    elif "personal" in loan_type:
        return "personal_loan_reviewer"
    elif "auto" in loan_type:
        return "auto_loan_reviewer"
    else:
        return "final_aggregator"