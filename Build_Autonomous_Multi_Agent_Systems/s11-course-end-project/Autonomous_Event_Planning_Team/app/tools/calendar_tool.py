"""Responsible for calendar-related tool functionality.

Self-contained deterministic scheduling logic (no external calendar API is
configured for this project) used by ScheduleAgent to build a milestone
timeline and flag conflicts, and by MarketingAgent to pick an outreach date.
"""

from datetime import date, timedelta

_BLACKOUT_DATES = {
    (1, 1): "New Year's Day",
    (7, 4): "Independence Day",
    (12, 25): "Christmas Day",
}

_MILESTONE_OFFSETS = [
    ("Kickoff & vendor booking", -60),
    ("Marketing launch", -30),
    ("Final walkthrough", -7),
    ("Event day", 0),
]


def build_milestones(preferred_date: date, duration_days: int) -> list[dict[str, str]]:
    """Standard milestone timeline anchored on preferred_date, ISO date
    strings to match ScheduleTimeline.milestones."""
    offsets = _MILESTONE_OFFSETS + [("Wrap-up & feedback", duration_days + 3)]
    return [
        {"name": name, "date": (preferred_date + timedelta(days=offset)).isoformat()}
        for name, offset in offsets
    ]


def outreach_start_date(preferred_date: date, lead_days: int = 30) -> date:
    """Marketing outreach lead time ahead of the event date."""
    return preferred_date - timedelta(days=lead_days)


def check_conflicts(preferred_date: date, milestones: list[dict[str, str]]) -> list[str]:
    """Flag blackout-date collisions, past dates, and milestones that
    collapse onto the same day."""
    conflicts: list[str] = []

    blackout = _BLACKOUT_DATES.get((preferred_date.month, preferred_date.day))
    if blackout:
        conflicts.append(f"Preferred date {preferred_date.isoformat()} falls on {blackout}")

    if preferred_date < date.today():
        conflicts.append(f"Preferred date {preferred_date.isoformat()} is in the past")

    seen_dates: dict[str, str] = {}
    for milestone in milestones:
        milestone_date = milestone["date"]
        if milestone_date in seen_dates:
            conflicts.append(
                f"Milestones '{seen_dates[milestone_date]}' and '{milestone['name']}' "
                f"both fall on {milestone_date}"
            )
        else:
            seen_dates[milestone_date] = milestone["name"]

    return conflicts
