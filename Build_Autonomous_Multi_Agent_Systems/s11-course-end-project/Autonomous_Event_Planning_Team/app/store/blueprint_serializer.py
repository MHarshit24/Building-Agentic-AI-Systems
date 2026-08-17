"""Responsible for serializing and deserializing plan blueprints.

Central place for turning EventBlueprint / CritiqueNote (pydantic models,
possibly with date fields) into JSON-safe plain dicts for storage and API
responses, and back again.
"""

from app.schemas.domain import CritiqueNote, EventBlueprint


def blueprint_to_dict(blueprint: EventBlueprint) -> dict:
    return blueprint.model_dump(mode="json")


def blueprint_from_dict(data: dict) -> EventBlueprint:
    return EventBlueprint.model_validate(data)


def critique_history_to_list(critique_history: list[CritiqueNote]) -> list[dict]:
    return [note.model_dump(mode="json") for note in critique_history]


def critique_history_from_list(data: list[dict]) -> list[CritiqueNote]:
    return [CritiqueNote.model_validate(item) for item in data]
