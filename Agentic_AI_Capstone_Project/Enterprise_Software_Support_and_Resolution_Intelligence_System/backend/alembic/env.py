from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from app.config import get_settings
from app.db.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

settings = get_settings()
# The instruction explicitly says: "using get_settings().database_url (the sync/psycopg one, not async) for migrations."
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# customers, support_tickets, incident_logs, knowledge_article_usage were
# previously excluded here on the assumption they were pre-existing tables
# outside this project's control. That assumption was false (§22.2 of
# Blueprint.md) — they are now first-class Alembic-managed tables with no
# exclusion needed.
#
# checkpoint_blobs/checkpoint_writes/checkpoints/checkpoint_migrations ARE
# correctly excluded, for a real and different reason (§40): they're
# self-managed by langgraph-checkpoint-postgres's own AsyncPostgresSaver.
# setup() call, not by Alembic — confirmed the hard way when Stage 8's
# evaluation_runs migration autogenerate saw them (since .setup() had
# already run against this dev DB) and proposed dropping them as "removed"
# tables. Excluding them here means every future autogenerate run ignores
# them entirely, instead of needing the same manual strip-out each time.
EXCLUDED_TABLES: set[str] = {
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoints",
    "checkpoint_migrations",
}

def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in EXCLUDED_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
