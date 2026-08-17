"""Responsible for prompt templates used by the manager agent."""

# Currently unused by the code and reserved for a future version where the manager may reason about task splitting.
DECOMPOSITION_PROMPT = """Context only: this text is for future manager-side decomposition reasoning. Event type: {event_type}. Objective: {objective}. Audience size: {audience_size}. Budget: {budget_currency} {budget_max_amount}. Constraints: {constraints}."""

SYNTHESIS_PROMPT = """Write a short 2-3 sentence natural-language overview of the event plan formed by combining the logistics, budget, marketing, schedule, and risk outputs. Summarize the plan clearly and concisely for the event type {event_type} with objective {objective} and audience size {audience_size}, and briefly note how the stated constraints ({constraints}) are addressed by the plan. Use the following specialist outputs as context: logistics plan {logistics_plan}; budget plan {budget_plan}; marketing plan {marketing_plan}; schedule timeline {schedule_timeline}; risk register {risk_register}. Respond with plain text only, with no markdown formatting and no preamble."""
