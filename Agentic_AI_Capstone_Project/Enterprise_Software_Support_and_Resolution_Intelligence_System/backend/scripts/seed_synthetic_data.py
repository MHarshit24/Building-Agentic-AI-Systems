"""
backend/scripts/seed_synthetic_data.py

The ONE script in this repository (§22, §42) — deliberately kept as a
script rather than an endpoint, because it's a course-mandated
benchmark-data fixture, not a runtime component. It NEVER issues DDL —
Alembic owns schema, this script owns rows only (§22.2's clean split).

Seeds, in this order, into tables Alembic already created:
  1. capstone_software_support_dataset.md Part 2's starter validation
     rows — fixed IDs, transcribed exactly as the course document gives
     them (customers 1-4, tickets 1-3, incidents 1-2, articles 1-3).
  2. Scaled synthetic volume on top of the starter rows, for SLA/perf
     benchmarking — Part 2 itself notes the starter set alone isn't
     enough for that.
  3. A fixed demo/test user roster (2 admin, 3 support_agent) — resolves
     the user-provisioning conflict in §22.1: there is no
     POST /auth/register, so this is the only way to get a testable
     user into the system, using this SAME script rather than a new one
     or a hand-typed psql insert.

Safe to re-run: if the course tables already have rows, the whole run is
skipped unless --force. The user roster is independently idempotent via
ON CONFLICT (email) DO NOTHING, regardless of --force, since resetting
demo users has no reason to be tied to resetting ticket/incident volume.

--force only truncates the four course tables (customers/support_tickets/
incident_logs/knowledge_article_usage) — it deliberately does NOT touch
`users`, since users.user_id is FK-referenced by conversations.handled_by_
user_id (Stage 2); cascading a truncate through that would silently wipe
conversation/message data this script has no business touching.
"""

import argparse
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2

# Allow running this script directly (python scripts/seed_synthetic_data.py
# from backend/, or python backend/scripts/seed_synthetic_data.py from
# anywhere) without needing a package install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings  # noqa: E402
from app.auth.security import hash_password  # noqa: E402 — single source of truth for hashing, not reimplemented here

# ---------- CONFIG ----------
settings = get_settings()
DB_CONFIG = {
    "dbname": settings.db_name,
    "user": settings.db_user,
    "password": settings.db_password,  # passed as a direct kwarg to psycopg2 — quote_plus not needed here
    "host": settings.db_host,
    "port": settings.db_port,
}

NUM_CUSTOMERS = 120   # scaled volume ADDED ON TOP of the 4 starter customers, not inclusive of them
NUM_TICKETS = 1000
NUM_INCIDENTS = 50
NUM_ARTICLES = 120

# Fixed demo/test roster (§22.1). Single shared password for local/dev
# convenience — document this value in backend/.env.example and README.md
# so anyone on the project knows it, since it's intentionally not a secret.
DEMO_USER_PASSWORD = "DevPassword123!"
DEMO_USERS = [
    ("admin1@enterprise-support.local", "admin"),
    ("admin2@enterprise-support.local", "admin"),
    ("agent1@enterprise-support.local", "support_agent"),
    ("agent2@enterprise-support.local", "support_agent"),
    ("agent3@enterprise-support.local", "support_agent"),
]

random.seed(42)
# ----------------------------

def random_date(start_year=2023, end_year=2026):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    return start + timedelta(days=random.randint(0, (end - start).days))

def random_recent_datetime():
    now = datetime.now()
    return now - timedelta(days=random.randint(0, 180),
                           hours=random.randint(0, 23))

def determine_escalation(severity, sla):
    if severity == "Critical":
        return True
    if severity == "High" and sla == "Priority":
        return True
    return False

def _already_seeded(cur) -> bool:
    """Idempotency guard: reports whether the course tables already have data."""
    cur.execute("SELECT COUNT(*) FROM customers")
    return cur.fetchone()[0] > 0

def _clear_existing_data(cur) -> None:
    """
    Used only when --force is passed. Scoped to the four course tables
    ONLY — deliberately excludes `users`, since it's FK-referenced by
    `conversations` (Stage 2); truncating it would cascade into data this
    script has no business touching.
    """
    cur.execute(
        "TRUNCATE TABLE support_tickets, incident_logs, knowledge_article_usage, customers "
        "RESTART IDENTITY CASCADE"
    )

def _seed_starter_rows(cur) -> None:
    """
    capstone_software_support_dataset.md Part 2, transcribed exactly —
    fixed IDs, not generated. This is the correctness-validation dataset
    every team is required to use as-given.
    """
    # -------- Starter customers (Part 2, Table 1) --------
    cur.execute("""
        INSERT INTO customers
        (customer_id, company_name, subscription_tier, account_status,
         sla_level, renewal_date, region)
        VALUES
        (1, 'Alpha Corp', 'Enterprise', 'Active', 'Priority', '2026-03-01', 'US'),
        (2, 'Beta Systems', 'Premium', 'Active', 'Enhanced', '2025-11-15', 'EU'),
        (3, 'Gamma Retail', 'Standard', 'Trial', 'Basic', '2025-08-01', 'APAC'),
        (4, 'Delta Logistics', 'Enterprise', 'Suspended', 'Priority', '2025-06-30', 'MEA')
    """)

    # -------- Starter support tickets (Part 2, Table 2) --------
    cur.execute("""
        INSERT INTO support_tickets
        (ticket_id, customer_id, issue_category, severity_level,
         ticket_status, created_at, resolved_at, assigned_team, escalation_flag)
        VALUES
        (1, 1, 'Integration', 'High', 'Open',
         '2025-03-01 10:00:00', NULL, 'L2', TRUE),
        (2, 2, 'Performance', 'Medium', 'Resolved',
         '2025-02-25 09:30:00', '2025-02-25 18:30:00', 'Engineering', FALSE),
        (3, 1, 'Security', 'Critical', 'Escalated',
         '2025-03-02 11:00:00', NULL, 'Security', TRUE)
    """)

    # -------- Starter incident logs (Part 2, Table 3) --------
    cur.execute("""
        INSERT INTO incident_logs
        (incident_id, incident_type, severity, affected_region,
         start_time, end_time, resolution_status, root_cause, escalation_flag)
        VALUES
        (1, 'Outage', 'Critical', 'EU',
         '2025-03-01 08:00:00', NULL, 'Investigating',
         'Database cluster overload', TRUE),
        (2, 'API Failure', 'High', 'US',
         '2025-02-20 14:00:00', '2025-02-20 16:30:00',
         'Resolved', 'Rate limit misconfiguration', FALSE)
    """)

    # -------- Starter knowledge base articles (Part 2, Table 4) --------
    cur.execute("""
        INSERT INTO knowledge_article_usage
        (article_id, article_title, product_version, category,
         last_updated, known_issue_flag, internal_confidence_score)
        VALUES
        (1, 'API Authentication Troubleshooting', 'v3.2',
         'API', '2025-02-10', FALSE, 0.94),
        (2, 'Resolving High Latency in EU Region', 'v3.0',
         'Performance', '2025-01-25', TRUE, 0.88),
        (3, 'Handling Security Alert Notifications', 'v3.2',
         'Security', '2025-02-15', FALSE, 0.97)
    """)

    # Starter rows used explicit IDs — bump each SERIAL sequence past them
    # so the scaled-generation inserts below (which rely on auto-assigned
    # IDs) don't collide with 1-4 / 1-3 / 1-2 / 1-3.
    for table, pk in [
        ("customers", "customer_id"),
        ("support_tickets", "ticket_id"),
        ("incident_logs", "incident_id"),
        ("knowledge_article_usage", "article_id"),
    ]:
        cur.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', '{pk}'), "
            f"(SELECT MAX({pk}) FROM {table}))"
        )

def _seed_scaled_data(cur) -> None:
    """Scaled synthetic volume, added on top of the starter rows above."""
    customer_ids = []

    # -------- Customers --------
    for i in range(NUM_CUSTOMERS):
        cur.execute("""
            INSERT INTO customers
            (company_name, subscription_tier, account_status,
             sla_level, renewal_date, region, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            RETURNING customer_id
        """, (
            f"Company_{i}",
            random.choice(["Free", "Standard", "Premium", "Enterprise"]),
            random.choice(["Active", "Suspended", "Trial", "Cancelled"]),
            random.choice(["Basic", "Enhanced", "Priority"]),
            random_date(2025, 2026),
            random.choice(["US", "EU", "APAC", "MEA"]),
            random_date(2023, 2024)
        ))
        customer_ids.append(cur.fetchone()[0])

    # -------- Support Tickets --------
    for _ in range(NUM_TICKETS):
        customer_id = random.choice(customer_ids)
        severity = random.choice(["Low", "Medium", "High", "Critical"])
        sla = random.choice(["Basic", "Enhanced", "Priority"])
        escalation = determine_escalation(severity, sla)

        created = random_recent_datetime()
        resolved = None
        status = random.choice(["Open", "In Progress", "Resolved"])

        if status == "Resolved":
            resolved = created + timedelta(hours=random.randint(2, 72))

        cur.execute("""
            INSERT INTO support_tickets
            (customer_id, issue_category, severity_level,
             ticket_status, created_at, resolved_at,
             assigned_team, escalation_flag)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            customer_id,
            random.choice([
                "Usage",
                "Integration",
                "Billing",
                "Performance",
                "Security"
            ]),
            severity,
            status,
            created,
            resolved,
            random.choice(["L1", "L2", "Engineering", "Security"]),
            escalation
        ))

    # -------- Incident Logs --------
    for _ in range(NUM_INCIDENTS):
        start_time = random_recent_datetime()
        end_time = None
        resolution_status = random.choice(["Open", "Investigating", "Resolved"])

        if resolution_status == "Resolved":
            end_time = start_time + timedelta(hours=random.randint(1, 48))

        severity = random.choice(["Medium", "High", "Critical"])
        escalation_flag = severity == "Critical"

        cur.execute("""
            INSERT INTO incident_logs
            (incident_type, severity, affected_region,
             start_time, end_time, resolution_status,
             root_cause, escalation_flag)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            random.choice([
                "Outage",
                "API Failure",
                "Data Loss",
                "Security Alert"
            ]),
            severity,
            random.choice(["US", "EU", "APAC", "MEA"]),
            start_time,
            end_time,
            resolution_status,
            "Synthetic generated incident root cause",
            escalation_flag
        ))

    # -------- Knowledge Articles --------
    for i in range(NUM_ARTICLES):
        cur.execute("""
            INSERT INTO knowledge_article_usage
            (article_title, product_version, category,
             last_updated, known_issue_flag, internal_confidence_score)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            f"Article_{i}_Troubleshooting_Guide",
            random.choice(["v1.0", "v2.1", "v3.0", "v3.2"]),
            random.choice([
                "Installation",
                "Configuration",
                "API",
                "Security"
            ]),
            random_date(2024, 2026),
            random.choice([True, False]),
            round(random.uniform(0.70, 0.99), 2)
        ))

def _seed_demo_users(cur) -> None:
    """
    Fixed demo/test roster (§22.1). Independently idempotent via
    ON CONFLICT — always safe to call, regardless of --force, since demo
    users have no reason to be reset alongside ticket/incident volume.
    """
    for email, role in DEMO_USERS:
        cur.execute("""
            INSERT INTO users (email, password_hash, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO NOTHING
        """, (email, hash_password(DEMO_USER_PASSWORD), role))

def main():
    parser = argparse.ArgumentParser(description="Seed course-provided tables, scaled synthetic data, and the demo user roster.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Wipe and re-seed the four course tables even if they already have data. Never touches `users`.",
    )
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    if _already_seeded(cur):
        if not args.force:
            print(
                f"Database '{settings.db_name}' already has customer rows — "
                "skipping course-table seed to avoid duplicates. Re-run with --force to wipe and reseed. "
                "(Demo users are checked independently below regardless.)"
            )
        else:
            print(f"--force passed: clearing course tables in '{settings.db_name}' before reseeding.")
            _clear_existing_data(cur)
            conn.commit()
            _seed_starter_rows(cur)
            _seed_scaled_data(cur)
            conn.commit()
    else:
        _seed_starter_rows(cur)
        _seed_scaled_data(cur)
        conn.commit()
        print(f"Course-table dataset generated successfully in '{settings.db_name}'.")

    _seed_demo_users(cur)
    conn.commit()
    print(
        f"Demo user roster ensured (idempotent). Shared local/dev password: {DEMO_USER_PASSWORD!r} "
        "— documented in .env.example/README.md, not a real secret."
    )

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()