def final_aggregator(state):
    """
    Aggregates results from all reviewer agents into a consolidated loan decision report.
    This node runs after all parallel branches complete (fan-in/join pattern).
    
    TODO:
    1. Get findings list from state
    2. Optionally deduplicate findings (workaround for state merge edge cases)
    3. Create a formatted decision report with:
       - Loan type
       - Total findings count
       - List of all findings
    4. Update state["final_decision"] with the formatted report
    5. Return updated state
    """
    # TODO: Implement final_aggregator logic
    findings = state.get("findings", [])

    # Deduplicate findings while preserving order
    seen = set()
    unique_findings = []
    for f in findings:
        if f not in seen:
            seen.add(f)
            unique_findings.append(f)

    loan_type = state.get("loan_type", "unknown")
    total = len(unique_findings)
    numbered = "\n".join(f"{i+1}. {f}" for i, f in enumerate(unique_findings))

    report = (
        f"Loan Assessment Decision Report\n"
        f"================================\n"
        f"Loan Type: {loan_type.capitalize()}\n"
        f"Total Findings: {total}\n\n"
        f"Findings:\n{numbered}"
    )

    state["final_decision"] = report
    return state