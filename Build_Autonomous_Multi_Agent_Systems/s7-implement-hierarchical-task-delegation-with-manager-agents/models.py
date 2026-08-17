from pydantic import BaseModel, Field


# TODO: Step 1 - Define ExpensePolicyRequest BaseModel
# Hint: Use BaseModel with fields for expense_type, amount, policy_limit, receipt_provided, business_purpose.
class ExpensePolicyRequest(BaseModel):
    """Request model for expense policy validation."""
    expense_type: str = Field(..., description="Type of expense (e.g., travel, meals, equipment)")
    amount: float = Field(..., description="Claimed expense amount in USD")
    policy_limit: float = Field(..., description="Maximum allowed amount for this expense type under company policy")
    receipt_provided: bool = Field(..., description="Whether a receipt was provided for the expense")
    business_purpose: str = Field(..., description="Business justification for the expense")


class ExpensePolicyResponse(BaseModel):
    """Response model for expense policy validation."""
    # TODO: Step 2 - Define response fields
    # Hint: Include success flag, decision text, and message string.
    success: bool = Field(..., description="Whether the validation completed successfully")
    decision: str = Field(..., description="The final decision and reasoning produced by the crew")
    message: str = Field(..., description="A short status message summarizing the outcome")