from typing import TypedDict, Annotated
import operator

class LoanApplicationState(TypedDict):
    """
    State schema for the loan application assessment workflow.
    
    TODO:
    1. Define loan_type: str field
    2. Define applicant_info: dict field
    3. Define findings: Annotated[list, operator.add] field (important for parallel merging)
    4. Define final_decision: str field
    """
    # TODO: Implement LoanApplicationState fields
    loan_type: str
    applicant_info: dict
    findings: Annotated[list, operator.add]
    final_decision: str