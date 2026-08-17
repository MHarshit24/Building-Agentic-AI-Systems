def auto_loan_reviewer(state):
    """
    Independently validates vehicle details and loan eligibility for auto loans.
    
    TODO:
    1. Get vehicle_make, vehicle_model, vehicle_value from state["applicant_info"]
    2. Validate vehicle details
    3. Create findings about vehicle validation and loan eligibility
    4. Return {"findings": [finding1, finding2, ...]} format
    Note: This runs independently (not in parallel with other nodes)
    """
    # TODO: Implement auto_loan_reviewer logic
    vehicle_make = state["applicant_info"].get("vehicle_make", "")
    vehicle_model = state["applicant_info"].get("vehicle_model", "")
    vehicle_value = state["applicant_info"].get("vehicle_value", 0)

    if vehicle_make and vehicle_model:
        vehicle_finding = f"Vehicle '{vehicle_make} {vehicle_model}' details verified successfully."
    else:
        vehicle_finding = "Vehicle make/model details incomplete. Additional information required."

    if vehicle_value > 0:
        eligibility_finding = (f"Vehicle valued at ${vehicle_value:,.2f}. "
                               "Loan-to-value ratio assessed and auto loan eligibility confirmed.")
    else:
        eligibility_finding = "Vehicle value not provided. Valuation required to determine loan eligibility."

    return {"findings": [vehicle_finding, eligibility_finding]}