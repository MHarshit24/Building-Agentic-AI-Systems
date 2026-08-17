def personal_loan_reviewer(state):
    """
    Independently reviews credit and income details for personal loans.
    
    TODO:
    1. Get monthly_income and credit_score from state["applicant_info"]
    2. Review both income and credit score
    3. Create multiple findings based on the review
    4. Return {"findings": [finding1, finding2, ...]} format
    Note: This runs independently (not in parallel with other nodes)
    """
    # TODO: Implement personal_loan_reviewer logic
    monthly_income = state["applicant_info"].get("monthly_income", 0)
    credit_score = state["applicant_info"].get("credit_score", 0)

    if monthly_income >= 5000:
        income_finding = f"Monthly income ${monthly_income:,.2f}: Strong income level. Loan repayment capacity is adequate."
    elif monthly_income >= 2500:
        income_finding = f"Monthly income ${monthly_income:,.2f}: Moderate income level. Repayment capacity is acceptable."
    else:
        income_finding = f"Monthly income ${monthly_income:,.2f}: Low income level. Repayment capacity is a concern."

    if credit_score >= 700:
        credit_finding = f"Credit score {credit_score}: Good standing. Personal loan eligibility confirmed."
    elif credit_score >= 550:
        credit_finding = f"Credit score {credit_score}: Marginal standing. Personal loan may require additional review."
    else:
        credit_finding = f"Credit score {credit_score}: Poor standing. Personal loan approval not recommended."

    return {"findings": [income_finding, credit_finding]}