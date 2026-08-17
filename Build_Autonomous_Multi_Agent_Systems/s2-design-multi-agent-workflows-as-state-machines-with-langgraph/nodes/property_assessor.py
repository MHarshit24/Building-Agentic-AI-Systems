def property_assessor(state):
    """
    Validates property documents and market valuation.
    This node runs in parallel with credit_score_reviewer for home loans.
    
    TODO:
    1. Get property_value and property_address from state["applicant_info"]
    2. Create a finding message about property validation
    3. Return {"findings": [finding]} format
    Note: This runs in parallel with credit_score_reviewer for home loans
    """
    # TODO: Implement property_assessor logic
    property_value = state["applicant_info"].get("property_value", 0)
    property_address = state["applicant_info"].get("property_address", "")

    if property_value > 0 and property_address:
        finding = (f"Property at '{property_address}' valued at ${property_value:,.2f}. "
                   "Documents verified and market valuation confirmed.")
    elif property_value > 0:
        finding = f"Property valued at ${property_value:,.2f} but no address provided. Address verification required."
    else:
        finding = "Property details incomplete. Value and address must be provided for home loan assessment."

    return {"findings": [finding]}