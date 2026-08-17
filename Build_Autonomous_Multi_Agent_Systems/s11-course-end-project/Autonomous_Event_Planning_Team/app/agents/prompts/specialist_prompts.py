"""Responsible for prompt templates used by specialist agents.

Each specialist grounds its numeric/structural output in a deterministic
tool call (app/tools/*) and asks the LLM only for the bounded, qualitative
part of its schema. Every prompt demands a single strict JSON object, same
convention as app.agents.prompts.reflection_prompts.CRITIQUE_PROMPT.

Every prompt also takes a {feedback} slot filled by build_feedback_context()
below, so a revision pass tells the LLM *why* the previous draft was
rejected instead of silently re-deriving the same answer from an unchanged
brief — without this, active_revision_targets re-runs a specialist but
gives it no reason to change anything."""

LOGISTICS_PROMPT = """Act as an event logistics planner. The event type is {event_type} with objective "{objective}" for an audience of {audience_size}. The venue selected is {venue} (capacity {capacity}). Constraints to respect: {constraints} — every constraint listed must be visibly reflected in your catering, vendors, or equipment choices; do not just restate a constraint without acting on it. Scale the formality and scope of your choices to the audience size and event type: a plan for a handful of guests should look different from one for thousands. Feedback from the previous review round, if any (address it where relevant): {feedback} Respond with nothing but a single valid JSON object with exactly these keys: catering (a short string describing the catering approach, sized and styled to the audience and event type), vendors (a JSON array of 2-5 short vendor category strings specific to what this event actually needs), equipment (a JSON array of 2-5 short equipment strings needed for this event). Do not include any other text, markdown code fences, or explanation outside the JSON object."""

MARKETING_PROMPT = """Act as an event marketing planner. The event type is {event_type} with objective "{objective}" for an audience of {audience_size}. Outreach should begin on {outreach_start_date}, ahead of the event on {preferred_date}. Constraints to respect: {constraints} — reflect each one in your channel or content choices where relevant. Choose channels and content scaled to the audience size and event type: a small private gathering needs lighter-weight outreach than a public event expecting thousands of attendees. Feedback from the previous review round, if any (address it where relevant): {feedback} Respond with nothing but a single valid JSON object with exactly these keys: channels (a JSON array of 2-5 short marketing channel strings, e.g. "email", "social media"), content_calendar (a JSON array of 2-5 short content-item strings in a sensible chronological order). Do not include any other text, markdown code fences, or explanation outside the JSON object."""

RISK_PROMPT = """Act as an event risk analyst. The event type is {event_type} with objective "{objective}" for an audience of {audience_size}. The budget limit is {budget_max_amount} {budget_currency}. Constraints to respect: {constraints}. Identify 3-5 realistic risks specific to this event's scale, venue type, and constraints — avoid generic risks that could apply to any event, and make each mitigation a concrete, actionable step rather than a platitude. Feedback from the previous review round, if any (address it where relevant): {feedback} Respond with nothing but a single valid JSON object with exactly these keys: risks (a JSON array of objects, each with exactly the keys "name", "likelihood" (one of "low", "medium", "high"), "impact" (one of "low", "medium", "high"), and "mitigation"), contingency_notes (a short string summarizing overall contingency planning). Do not include any other text, markdown code fences, or explanation outside the JSON object."""

BUDGET_PROMPT = """Act as an event budget analyst. The event type is {event_type} for an audience of {audience_size}. A cost estimation tool has produced a baseline total of {baseline_total} {budget_currency} against a budget limit of {budget_max_amount} {budget_currency}. Constraints to respect: {constraints}. Feedback from the previous review round, if any (address it where relevant, especially if the plan was flagged as over budget): {feedback} Decide a cost adjustment factor to apply to the baseline: 1.0 means no change, above 1.0 (up to 1.5) adds a contingency buffer for extra risk, below 1.0 (down to 0.5) reflects real cost-cutting measures (e.g. simpler catering, a smaller venue) needed to fit the budget. If the baseline is already at or under the budget limit, do not cut further — pick a factor at or near 1.0, moving above it only if a constraint (e.g. "premium catering") justifies a modest contingency buffer. If the baseline is well above the budget limit, pick a low factor now (as low as 0.5) rather than leaving it for a later revision round to catch. Respond with nothing but a single valid JSON object with exactly this key: cost_adjustment_factor (a number between 0.5 and 1.5). Do not include any other text, markdown code fences, or explanation outside the JSON object."""

SCHEDULE_PROMPT = """Act as an event schedule planner. The event type is {event_type} with objective "{objective}", running for {duration_days} day(s) starting {preferred_date}. Constraints to respect: {constraints}. A baseline milestone timeline has already been generated; suggest any additional event-specific milestones it may be missing, especially any tied directly to the stated constraints. Feedback from the previous review round, if any (address it where relevant): {feedback} Respond with nothing but a single valid JSON object with exactly this key: additional_milestones (a JSON array of 0-3 short milestone name strings; return an empty array if the baseline timeline already looks complete). Do not include any other text, markdown code fences, or explanation outside the JSON object."""


def build_feedback_context(state) -> str:
    """The "why was this rejected last time" context injected into every
    specialist prompt. Empty-first-draft message when there's no critique
    yet (state["critique_history"] is empty on the first decompose pass)."""
    critique_history = state.get("critique_history") or []
    if not critique_history:
        return "None — this is the first draft."

    latest = critique_history[-1]
    notes = latest["notes"] if isinstance(latest, dict) else latest.notes
    return " | ".join(f"{dimension}: {note}" for dimension, note in notes.items())
