"""Responsible for venue-related tool functionality.

Self-contained deterministic mock catalog (no external venue-search API is
configured for this project) so LogisticsAgent gets grounded, reproducible
numbers instead of hallucinated ones.
"""

_VENUE_CATALOG = [
    {"name": "Community Meeting Room", "capacity": 50, "layout_notes": "single room, theater seating"},
    {"name": "Downtown Conference Center", "capacity": 200, "layout_notes": "modular halls, theater or classroom seating"},
    {"name": "Metro Convention Hall", "capacity": 800, "layout_notes": "large hall, banquet or theater seating with breakout rooms"},
    {"name": "Grand Exhibition Arena", "capacity": 3000, "layout_notes": "arena floor plus tiered seating, needs staged AV"},
]


def find_venue(audience_size: int, venue_preference: str | None = None) -> dict:
    """Pick the smallest catalog venue that fits audience_size. Falls back
    to the largest venue (flagged in layout_notes) if nothing fits."""
    fitting = [v for v in _VENUE_CATALOG if v["capacity"] >= audience_size]
    if fitting:
        choice = min(fitting, key=lambda v: v["capacity"])
        layout_notes = choice["layout_notes"]
    else:
        choice = max(_VENUE_CATALOG, key=lambda v: v["capacity"])
        layout_notes = f"{choice['layout_notes']} (over capacity — needs an overflow venue or split sessions)"

    name = choice["name"]
    if venue_preference:
        name = f"{choice['name']} ({venue_preference})"

    return {
        "venue": name,
        "capacity": choice["capacity"],
        "layout_notes": layout_notes,
    }
