"""Responsible for persistent storage of planning state and plans.

The LangGraph checkpointer (app/orchestrator/checkpointer.py) already
persists in-flight EventPlanState after every node. This module stores the
plan's lifecycle record (brief summary, terminal artifact, or a failure) in
its own table in the same SQLite file, so a plan history list and completed
plans stay queryable without replaying the graph's checkpoint history, and
survive a process restart.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import get_settings
from app.store.blueprint_serializer import (
    blueprint_from_dict,
    blueprint_to_dict,
    critique_history_from_list,
    critique_history_to_list,
)

_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS finalized_plans (
    plan_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT '',
    objective TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT '',
    quality_gate_threshold REAL,
    blueprint_json TEXT,
    critique_history_json TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

# Columns that may not exist in a database created before they were added;
# SQLite has no "ADD COLUMN IF NOT EXISTS", so each is attempted and any
# "duplicate column" failure is swallowed.
_MIGRATION_COLUMNS = [
    ("error_message", "TEXT"),
    ("event_type", "TEXT NOT NULL DEFAULT ''"),
    ("objective", "TEXT NOT NULL DEFAULT ''"),
    ("provider", "TEXT NOT NULL DEFAULT ''"),
    ("quality_gate_threshold", "REAL"),
    ("created_at", "TEXT NOT NULL DEFAULT ''"),
    ("updated_at", "TEXT NOT NULL DEFAULT ''"),
]


def _db_path() -> str:
    return get_settings().database_url.removeprefix("sqlite:///")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connection():
    conn = sqlite3.connect(_db_path(), timeout=5)
    try:
        conn.execute(_TABLE_DDL)
        for column, column_type in _MIGRATION_COLUMNS:
            try:
                conn.execute(f"ALTER TABLE finalized_plans ADD COLUMN {column} {column_type}")
            except sqlite3.OperationalError:
                pass
        yield conn
        conn.commit()
    finally:
        conn.close()


def register_plan(
    plan_id: str,
    event_type: str,
    objective: str,
    provider: str | None = None,
    quality_gate_threshold: float | None = None,
) -> None:
    """Called at plan creation, before the background task starts, so the
    plan appears in list_plans() immediately with status "in_progress"
    instead of only once it reaches a terminal state."""
    now = _now()
    with _connection() as conn:
        conn.execute(
            """
            INSERT INTO finalized_plans
                (plan_id, status, event_type, objective, provider, quality_gate_threshold, blueprint_json, critique_history_json, error_message, created_at, updated_at)
            VALUES (?, 'in_progress', ?, ?, ?, ?, NULL, '[]', NULL, ?, ?)
            ON CONFLICT(plan_id) DO UPDATE SET
                status = 'in_progress',
                event_type = excluded.event_type,
                objective = excluded.objective,
                provider = excluded.provider,
                quality_gate_threshold = excluded.quality_gate_threshold,
                updated_at = excluded.updated_at
            """,
            (plan_id, event_type, objective, provider or "", quality_gate_threshold, now, now),
        )


def save_plan(
    plan_id: str,
    status: str,
    blueprint,
    critique_history: list,
    error_message: str | None = None,
) -> None:
    blueprint_json = json.dumps(blueprint_to_dict(blueprint)) if blueprint is not None else None
    critique_history_json = json.dumps(critique_history_to_list(critique_history))
    now = _now()

    with _connection() as conn:
        conn.execute(
            """
            INSERT INTO finalized_plans
                (plan_id, status, event_type, objective, provider, quality_gate_threshold, blueprint_json, critique_history_json, error_message, created_at, updated_at)
            VALUES (?, ?, '', '', '', NULL, ?, ?, ?, ?, ?)
            ON CONFLICT(plan_id) DO UPDATE SET
                status = excluded.status,
                blueprint_json = excluded.blueprint_json,
                critique_history_json = excluded.critique_history_json,
                error_message = excluded.error_message,
                updated_at = excluded.updated_at
            """,
            (plan_id, status, blueprint_json, critique_history_json, error_message, now, now),
        )


def _row_to_dict(row: tuple) -> dict:
    (
        plan_id, status, event_type, objective, provider, quality_gate_threshold,
        blueprint_json, critique_history_json, error_message,
        created_at, updated_at,
    ) = row
    blueprint = blueprint_from_dict(json.loads(blueprint_json)) if blueprint_json else None
    critique_history = critique_history_from_list(json.loads(critique_history_json)) if critique_history_json else []

    return {
        "plan_id": plan_id,
        "status": status,
        "event_type": event_type or "",
        "objective": objective or "",
        "provider": provider or None,
        "quality_gate_threshold": quality_gate_threshold,
        "blueprint": blueprint,
        "critique_history": critique_history,
        "error_message": error_message,
        "created_at": created_at or "",
        "updated_at": updated_at or "",
    }


_COLUMNS = (
    "plan_id, status, event_type, objective, provider, quality_gate_threshold, "
    "blueprint_json, critique_history_json, error_message, created_at, updated_at"
)


def get_plan(plan_id: str) -> dict | None:
    with _connection() as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM finalized_plans WHERE plan_id = ?",
            (plan_id,),
        ).fetchone()

    if row is None:
        return None
    return _row_to_dict(row)


def list_plans() -> list[dict]:
    """Most recently created plans first."""
    with _connection() as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM finalized_plans ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_dict(row) for row in rows]
