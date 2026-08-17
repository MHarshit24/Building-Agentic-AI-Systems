def credit_score_reviewer(state):
    """
    Checks applicant's credit profile and repayment history.
    This node runs in parallel with property_assessor for home loans.
    
    TODO:
    1. Get credit_score from state["applicant_info"]
    2. Analyze credit score and create an appropriate finding message
    3. Return {"findings": [finding]} format
    Note: This runs in parallel with property_assessor for home loans
    """
    # TODO: Implement credit_score_reviewer logic
    credit_score = state["applicant_info"].get("credit_score", 0)

    if credit_score >= 750:
        finding = f"Credit score {credit_score}: Excellent credit profile. Strong repayment history indicated."
    elif credit_score >= 650:
        finding = f"Credit score {credit_score}: Good credit profile. Acceptable repayment history."
    elif credit_score >= 550:
        finding = f"Credit score {credit_score}: Fair credit profile. Some repayment concerns noted."
    else:
        finding = f"Credit score {credit_score}: Poor credit profile. High risk — loan approval not recommended."

    return {"findings": [finding]}