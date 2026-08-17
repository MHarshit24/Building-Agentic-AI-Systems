"""Responsible for pricing-related tool functionality.

Self-contained per-head + fixed cost model (no external pricing API is
configured for this project) so BudgetAgent gets grounded, reproducible
numbers instead of hallucinated ones.
"""

# Per-audience-member cost, by category, in the brief's currency units.
_PER_HEAD_COSTS = {
    "venue": 150.0,
    "catering": 400.0,
    "marketing": 60.0,
    "equipment": 40.0,
}

# Flat costs incurred regardless of audience size.
_FIXED_COSTS = {
    "misc": 5000.0,
}

# Multiplier applied to the whole estimate for larger productions.
_EVENT_TYPE_MULTIPLIERS = {
    "conference": 1.2,
    "concert": 1.4,
    "wedding": 1.3,
}


def estimate_costs(audience_size: int, event_type: str, currency: str) -> dict:
    """Return {"category_breakdown": {...}, "total_estimated_cost": float,
    "currency": currency}. Deterministic given the same inputs."""
    multiplier = _EVENT_TYPE_MULTIPLIERS.get(event_type.strip().lower(), 1.0)

    category_breakdown = {
        category: round(per_head * audience_size * multiplier, 2)
        for category, per_head in _PER_HEAD_COSTS.items()
    }
    for category, flat_cost in _FIXED_COSTS.items():
        category_breakdown[category] = round(flat_cost * multiplier, 2)

    total_estimated_cost = round(sum(category_breakdown.values()), 2)

    return {
        "category_breakdown": category_breakdown,
        "total_estimated_cost": total_estimated_cost,
        "currency": currency,
    }
