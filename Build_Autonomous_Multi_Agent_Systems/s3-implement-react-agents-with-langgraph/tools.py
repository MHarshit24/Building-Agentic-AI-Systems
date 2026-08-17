from langchain_core.tools import tool

# Simulated account database
ACCOUNT_DB = {
    "ACC001": {
        "account_type": "Savings",
        "balance": 150000,
        "interest_rate": 5.5
    },
    "ACC002": {
        "account_type": "Fixed Deposit",
        "balance": 200000,
        "interest_rate": 6.5
    },
    "ACC003": {
        "account_type": "Savings",
        "balance": 125000,
        "interest_rate": 5.5
    }
}

@tool
def get_account_info(account_id: str) -> str:
    """
    Get account information including account type, balance, and interest rate.
    
    Use this tool when the user asks about:
    - Account balance
    - Account details
    - Account information
    - Interest rate for an account
    
    Args:
        account_id: The account ID (e.g., "ACC001", "ACC002")
    
    Returns:
        A string with account type, balance, and interest rate
    
    TODO:
    1. Get account from ACCOUNT_DB using account_id.upper() as key
    2. If account not found, return f"Account {account_id} not found."
    3. If found, return formatted string with:
       - Account Type: {account_type}
       - Balance: ₹{balance:,} (formatted with commas)
       - Interest Rate: {interest_rate}%
    """
    # TODO: Implement get_account_info logic
    account = ACCOUNT_DB.get(account_id.upper())
    if not account:
        return f"Account {account_id} not found."
    return (
        f"Account Type: {account['account_type']}\n"
        f"Balance: ₹{account['balance']:,}\n"
        f"Interest Rate: {account['interest_rate']}%"
    )

@tool
def calculate(expression: str) -> str:
    """
    Evaluate a mathematical expression and return the result.
    
    Use this tool when you need to:
    - Calculate interest amounts
    - Perform mathematical operations
    - Compute totals or differences
    - Do any numerical calculations
    
    Args:
        expression: A mathematical expression as a string (e.g., "200000 * 6.5 * 2 / 100")
    
    Returns:
        The computed result as a string
    
    TODO:
    1. Use try-except block to safely evaluate the expression
    2. Use eval(expression) to compute the result
    3. Return f"Result: {result}"
    4. If exception occurs, return f"Error calculating: {str(e)}"
    """
    # TODO: Implement calculate logic
    try:
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error calculating: {str(e)}"