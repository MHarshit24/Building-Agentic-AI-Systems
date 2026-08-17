"""
FinDoc Analyzer — Database setup script.
Run once: python scripts/setup_db.py
Dual .env loader: root .env (secrets) + project .env (config).
setup_db.py lives at scripts/setup_db.py
  parents[4] = Building_Agentic_AI_Systems  -> root .env
  parents[1] = FinDoc Analyzer              -> project .env
"""

import os
import sys
import logging
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _load_env():
    """
    Dual .env loader.
    setup_db.py: scripts/setup_db.py
      parents[4] = Building_Agentic_AI_Systems  -> root .env (secrets)
      parents[1] = FinDoc Analyzer              -> project .env (config)
    """
    if "pytest" in sys.modules:
        return

    base_dir = Path(__file__).resolve().parents[4]
    base_env_path = base_dir / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
        logger.debug(f"Loaded root .env from {base_env_path}")
    else:
        load_dotenv()
        logger.warning(f"Root .env not found at {base_env_path}, falling back to default load_dotenv()")

    _preserved = {
        "DB_PASSWORD":           os.getenv("DB_PASSWORD"),
        "AZURE_OPENAI_API_KEY":  os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "LANGFUSE_PUBLIC_KEY":   os.getenv("LANGFUSE_PUBLIC_KEY"),
        "LANGFUSE_SECRET_KEY":   os.getenv("LANGFUSE_SECRET_KEY"),
        "LANGFUSE_HOST":         os.getenv("LANGFUSE_HOST"),
    }

    proj_dir = Path(__file__).resolve().parents[1]
    proj_env_path = proj_dir / ".env"

    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
        logger.debug(f"Loaded project .env from {proj_env_path}")
    else:
        load_dotenv()
        logger.warning(f"Project .env not found at {proj_env_path}, falling back to default load_dotenv()")

    for key, val in _preserved.items():
        if val:
            os.environ[key] = val

    for var in ["DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
                "PGUSER", "PGPASSWORD", "PGDATABASE"]:
        os.environ.pop(var, None)


def get_connection():
    """Get psycopg2 connection using raw password (not quote_plus — psycopg2 handles it)."""
    import psycopg2
    return psycopg2.connect(
        host=os.getenv("DB_HOST",     "localhost"),
        port=os.getenv("DB_PORT",     "5432"),
        dbname=os.getenv("DB_NAME",   "findoc_db"),
        user=os.getenv("DB_USER",     "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def get_sqlalchemy_engine():
    """Get SQLAlchemy engine using quote_plus-encoded password."""
    from sqlalchemy import create_engine
    user     = os.getenv("DB_USER",     "postgres")
    password = quote_plus(os.getenv("DB_PASSWORD", ""))
    host     = os.getenv("DB_HOST",     "localhost")
    port     = os.getenv("DB_PORT",     "5432")
    dbname   = os.getenv("DB_NAME",     "findoc_db")
    url      = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(url)


def setup_extensions(conn):
    """Enable pgvector extension."""
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    conn.commit()
    logger.info("pgvector extension enabled")


def setup_financial_tables(conn):
    """Create all financial data tables."""
    with conn.cursor() as cur:

        cur.execute("""
            CREATE TABLE IF NOT EXISTS financial_statements (
                id              SERIAL PRIMARY KEY,
                company_name    VARCHAR(255) NOT NULL,
                ticker          VARCHAR(20),
                fiscal_year     INTEGER NOT NULL,
                fiscal_quarter  VARCHAR(5),
                statement_type  VARCHAR(50) NOT NULL,
                metric_name     VARCHAR(255) NOT NULL,
                metric_value    NUMERIC(20, 4),
                currency        VARCHAR(10)  DEFAULT 'USD',
                unit            VARCHAR(50)  DEFAULT 'millions',
                source_document VARCHAR(500),
                created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("  financial_statements table ready")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS financial_ratios (
                id              SERIAL PRIMARY KEY,
                company_name    VARCHAR(255) NOT NULL,
                ticker          VARCHAR(20),
                fiscal_year     INTEGER NOT NULL,
                ratio_name      VARCHAR(255) NOT NULL,
                ratio_value     NUMERIC(20, 6),
                benchmark       NUMERIC(20, 6),
                source_document VARCHAR(500),
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("  financial_ratios table ready")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS risk_factors (
                id              SERIAL PRIMARY KEY,
                company_name    VARCHAR(255) NOT NULL,
                ticker          VARCHAR(20),
                fiscal_year     INTEGER NOT NULL,
                risk_category   VARCHAR(100),
                risk_description TEXT,
                severity        VARCHAR(20),
                source_document VARCHAR(500),
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("  risk_factors table ready")

    conn.commit()
    logger.info("All financial tables created")


def verify_setup(conn):
    """Verify tables and pgvector are working."""
    with conn.cursor() as cur:
        # Check pgvector
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        pgv = cur.fetchone()
        logger.info(f"pgvector: {'installed' if pgv else 'NOT found'}")

        # Check tables
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = [r[0] for r in cur.fetchall()]
        logger.info(f"Tables in findoc_db: {tables}")

        # Check seeded data
        cur.execute("SELECT COUNT(*) FROM financial_statements;")
        count = cur.fetchone()[0]
        logger.info(f"financial_statements rows: {count}")


def main():
    _load_env()

    logger.info("=" * 50)
    logger.info("FinDoc Analyzer — Database Setup")
    logger.info("=" * 50)
    logger.info(f"DB: {os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")

    try:
        conn = get_connection()
        logger.info("Connected to findoc_db")

        setup_extensions(conn)
        setup_financial_tables(conn)
        verify_setup(conn)

        conn.close()
        logger.info("=" * 50)
        logger.info("Setup complete!")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Setup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()