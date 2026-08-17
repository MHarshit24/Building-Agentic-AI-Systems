def assess_complexity(description: str) -> str:
    """
    TASK 1: Implement heuristic-based routing for support tickets.
    
    Heuristic Rules:
    1. Check for Complex Keywords:
       If the description contains words like '500', 'error', 'bug', 'crash', 
       'analyze', 'failed', 'deployment', 'critical', 'api', etc.
       -> Return "complex"
       
    2. Check for Simple Keywords:
       If the description contains words like 'billing', 'invoice', 
       'address', 'update', 'status', 'account', 'reset', etc.
       -> Return "simple"
       
    3. Length Metric:
       If the word count of the description is > 50 words.
       -> Return "complex"
       
    Default: Return "simple"
    """
    
    # TODO: Implement the heuristic logic here
    # 1. Lowercase the content
    # 2. Define keyword lists
    # 3. Apply the rules

    # 1. Lowercase the content for case-insensitive matching
    lowered = description.lower()

    # 2. Define keyword lists
    complex_keywords = [
        "500", "error", "bug", "crash", "analyze", "failed", "deployment",
        "critical", "api", "exception", "traceback", "timeout", "outage",
        "latency", "memory", "cpu", "server", "database", "connection", "null"
    ]

    simple_keywords = [
        "billing", "invoice", "address", "update", "status", "account",
        "reset", "password", "refund", "payment", "subscription", "plan",
        "cancel", "upgrade", "downgrade", "profile", "email", "phone"
    ]

    # 3. Apply the rules

    # Rule 1: Check for complex keywords
    for keyword in complex_keywords:
        if keyword in lowered:
            return "complex"

    # Rule 2: Check for simple keywords
    for keyword in simple_keywords:
        if keyword in lowered:
            return "simple"

    # Rule 3: Length metric — descriptions longer than 50 words go to complex tier
    if len(description.split()) > 50:
        return "complex"

    # Default fallback
    return "simple"