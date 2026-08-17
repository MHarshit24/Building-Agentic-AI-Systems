"""
FinDoc Analyzer — SQL Service for Structured Financial Data
Dual .env loader: root .env (secrets) + project .env (config).
sql_service.py: main/services/sql_service.py
  parents[5] = Building_Agentic_AI_Systems  -> root .env
  parents[2] = FinDoc Analyzer              -> project .env

Real schema from techvision_financial_data.sql:
  financial_statements        — header (statement_id, company_name, fiscal_year,
                                fiscal_quarter, statement_type, filing_date)
  income_statement_line_items — line_item_name, amount_usd, percentage_of_revenue
                                JOIN financial_statements ON statement_id
  quarterly_revenue_breakdown — company_name, fiscal_year, fiscal_quarter,
                                segment_name, revenue_usd, yoy_growth_percent
  balance_sheet_items         — account_name, amount_usd
                                JOIN financial_statements ON statement_id
  risk_disclosures            — risk_title, risk_description, severity_level
                                JOIN financial_statements ON statement_id
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import quote_plus
from dotenv import load_dotenv

from sqlalchemy import create_engine, text, inspect as sa_inspect
from llama_index.core import SQLDatabase, Settings
from llama_index.core.query_engine import NLSQLTableQueryEngine

logger = logging.getLogger(__name__)

FINANCIAL_TABLES = [
    "financial_statements",
    "income_statement_line_items",
    "quarterly_revenue_breakdown",
    "balance_sheet_items",
    "risk_disclosures",
    "financial_ratios",
    "risk_factors",
]

# System prompt that teaches the LLM the exact schema and join patterns
SQL_SYSTEM_PROMPT = """You are a financial SQL expert for the FinDoc Analyzer system.
The database contains TechVision Corporation financial data with these tables:

1. financial_statements (statement_id, company_name, fiscal_year, fiscal_quarter, statement_type, filing_date)
   - statement_type values: 'income', 'balance', 'cashflow'
   - company_name is 'TechVision Corporation'

2. income_statement_line_items (line_item_id, statement_id, line_item_name, line_item_category, amount_usd, percentage_of_revenue, notes)
   - JOIN with financial_statements ON statement_id
   - line_item_name examples: 'Total Revenue', 'Net Income', 'Gross Profit', 'Operating Income', 'EPS Basic'
   - amount_usd is in USD millions

3. quarterly_revenue_breakdown (revenue_id, company_name, fiscal_year, fiscal_quarter, segment_name, revenue_usd, yoy_growth_percent, segment_margin_percent)
   - segment_name examples: 'Cloud Services', 'Enterprise Software', 'AI Solutions'
   - revenue_usd is in USD millions

4. balance_sheet_items (balance_item_id, statement_id, account_category, account_name, amount_usd, is_debit)
   - JOIN with financial_statements ON statement_id

5. risk_disclosures (risk_id, statement_id, risk_category, risk_title, risk_description, severity_level, first_disclosed_date)
   - JOIN with financial_statements ON statement_id

IMPORTANT RULES:
- For revenue/income/profit questions: use income_statement_line_items JOIN financial_statements
- For quarterly/segment questions: use quarterly_revenue_breakdown directly
- For risk questions: use risk_disclosures JOIN financial_statements
- Always filter by company_name = 'TechVision Corporation' where applicable
- fiscal_year 2024 is the most recent year
- Return clear, formatted answers with the actual numbers

Example for "What was total revenue in 2024?":
SELECT i.line_item_name, i.amount_usd
FROM income_statement_line_items i
JOIN financial_statements s ON i.statement_id = s.statement_id
WHERE s.company_name = 'TechVision Corporation'
  AND s.fiscal_year = 2024
  AND LOWER(i.line_item_name) LIKE '%revenue%'
"""

_sql_query_engine: Optional[NLSQLTableQueryEngine] = None


def _load_env():
    """
    Dual .env loader.
    sql_service.py: main/services/sql_service.py
      parents[5] = Building_Agentic_AI_Systems  -> root .env
      parents[2] = FinDoc Analyzer              -> project .env
    """
    if "pytest" in sys.modules:
        return

    base_dir = Path(__file__).resolve().parents[5]
    base_env_path = base_dir / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()
        logger.warning(f"Root .env not found at {base_env_path}")

    _preserved = {
        "DB_PASSWORD":           os.getenv("DB_PASSWORD"),
        "AZURE_OPENAI_API_KEY":  os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "LANGFUSE_PUBLIC_KEY":   os.getenv("LANGFUSE_PUBLIC_KEY"),
        "LANGFUSE_SECRET_KEY":   os.getenv("LANGFUSE_SECRET_KEY"),
        "LANGFUSE_HOST":         os.getenv("LANGFUSE_HOST"),
    }

    proj_dir = Path(__file__).resolve().parents[2]
    proj_env_path = proj_dir / ".env"

    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
    else:
        load_dotenv()
        logger.warning(f"Project .env not found at {proj_env_path}")

    for key, val in _preserved.items():
        if val:
            os.environ[key] = val

    for var in ["DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
                "PGUSER", "PGPASSWORD", "PGDATABASE"]:
        os.environ.pop(var, None)


def get_db_engine():
    """Create SQLAlchemy engine with quote_plus-encoded password."""
    _load_env()
    user     = os.getenv("DB_USER",     "postgres")
    password = quote_plus(os.getenv("DB_PASSWORD", ""))
    host     = os.getenv("DB_HOST",     "localhost")
    port     = os.getenv("DB_PORT",     "5432")
    dbname   = os.getenv("DB_NAME",     "findoc_db")
    url      = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(url)


def setup_financial_tables():
    """
    Ensure runtime tables exist. Seed tables already exist from SQL file.
    Called from ingest_routes.py background task.
    """
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("""
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
        """))
        conn.execute(text("""
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
        """))
        conn.commit()
    logger.info("Financial tables verified")


def get_sql_query_engine() -> NLSQLTableQueryEngine:
    """
    Get or create NLSQLTableQueryEngine singleton.
    Uses SQL_SYSTEM_PROMPT to teach the LLM the exact schema and join patterns.
    """
    global _sql_query_engine

    if _sql_query_engine is not None:
        return _sql_query_engine

    engine    = get_db_engine()
    inspector = sa_inspect(engine)
    existing  = set(inspector.get_table_names())
    tables_to_use = [t for t in FINANCIAL_TABLES if t in existing]
    logger.info(f"SQL engine using tables: {tables_to_use}")

    sql_database = SQLDatabase(engine, include_tables=tables_to_use)

    _sql_query_engine = NLSQLTableQueryEngine(
        sql_database=sql_database,
        tables=tables_to_use,
        verbose=True,
        synthesize_response=True,
        # Inject schema knowledge so LLM generates correct JOINs
        text_to_sql_prompt=_build_text_to_sql_prompt(),
    )
    logger.info(f"SQL query engine initialized with {len(tables_to_use)} tables")
    return _sql_query_engine


def _build_text_to_sql_prompt():
    """Build a PromptTemplate that includes our schema context."""
    try:
        from llama_index.core.prompts import PromptTemplate
        template = (
            SQL_SYSTEM_PROMPT
            + "\n\nGiven the question below, write a valid PostgreSQL query.\n"
            + "Question: {query_str}\n"
            + "SQLQuery: "
        )
        return PromptTemplate(template)
    except Exception as e:
        logger.warning(f"Could not build custom SQL prompt ({e}), using default")
        return None


def execute_sql_query(question: str) -> Dict[str, Any]:
    """
    Execute a natural-language SQL query against financial tables.
    Returns answer and generated SQL for auditability.
    Falls back to direct query if NLSQLTableQueryEngine fails.
    """
    # Try NLSQLTableQueryEngine first
    try:
        qe       = get_sql_query_engine()
        response = qe.query(question)
        answer   = str(response).strip()

        sql_query = None
        if hasattr(response, "metadata") and response.metadata:
            sql_query = response.metadata.get("sql_query")

        # Detect when LLM returned a narrative explanation instead of executing SQL
        NARRATIVE_SIGNALS = [
            "cannot execute", "please run", "run the query", "run this query",
            "in your database", "your database environment", "i cannot assist",
            "here is the sql", "here's the sql", "the following sql",
            "sql query to", "you would need to", "based on the structure",
        ]
        if any(signal in answer.lower() for signal in NARRATIVE_SIGNALS):
            logger.warning("NLSQLTableQueryEngine returned narrative — trying direct lookup")
            return _direct_sql_lookup(question)

        # If answer is empty or unhelpful, fall back to direct lookup
        if not answer or answer.lower() in ("none", "empty response", ""):
            logger.warning("NLSQLTableQueryEngine returned empty — trying direct lookup")
            return _direct_sql_lookup(question)

        logger.info(f"SQL query executed | sql={sql_query}")
        return {"answer": answer, "sql_query": sql_query, "success": True}

    except Exception as e:
        logger.error(f"NLSQLTableQueryEngine failed ({e}), trying direct lookup")
        return _direct_sql_lookup(question)


def _direct_sql_lookup(question: str) -> Dict[str, Any]:
    """
    Direct SQL fallback — matches common financial questions to
    handcrafted queries so answers are always available even if
    NL-to-SQL generation fails.
    """
    q = question.lower()
    engine = get_db_engine()

    try:
        with engine.connect() as conn:

            # Revenue questions
            if any(w in q for w in ["total revenue", "revenue in", "revenue for"]):
                year = _extract_year(q) or 2024
                rows = conn.execute(text("""
                    SELECT i.line_item_name, i.amount_usd, i.percentage_of_revenue
                    FROM income_statement_line_items i
                    JOIN financial_statements s ON i.statement_id = s.statement_id
                    WHERE s.company_name = 'TechVision Corporation'
                      AND s.fiscal_year  = :year
                      AND LOWER(i.line_item_name) LIKE '%revenue%'
                    ORDER BY i.amount_usd DESC
                """), {"year": year}).fetchall()
                if rows:
                    lines = [f"{r[0]}: ${r[1]:,.1f}M" for r in rows]
                    return {"answer": f"TechVision Corporation revenue ({year}):\n" + "\n".join(lines),
                            "sql_query": "direct revenue lookup", "success": True}

            # Net income questions
            if any(w in q for w in ["net income", "profit", "earnings"]):
                year = _extract_year(q) or 2024
                rows = conn.execute(text("""
                    SELECT i.line_item_name, i.amount_usd
                    FROM income_statement_line_items i
                    JOIN financial_statements s ON i.statement_id = s.statement_id
                    WHERE s.company_name = 'TechVision Corporation'
                      AND s.fiscal_year  = :year
                      AND (LOWER(i.line_item_name) LIKE '%net income%'
                           OR LOWER(i.line_item_name) LIKE '%net profit%')
                """), {"year": year}).fetchall()
                if rows:
                    lines = [f"{r[0]}: ${r[1]:,.1f}M" for r in rows]
                    return {"answer": f"TechVision Corporation ({year}):\n" + "\n".join(lines),
                            "sql_query": "direct net income lookup", "success": True}

            # Quarterly / segment questions
            if any(w in q for w in ["quarterly", "segment", "quarter", "breakdown",
                                     "drove", "growth driver", "cloud services",
                                     "enterprise software", "ai solutions", "what drove",
                                     "revenue growth", "performance", "driven by"]):
                year = _extract_year(q) or 2024
                rows = conn.execute(text("""
                    SELECT fiscal_quarter, segment_name, revenue_usd, yoy_growth_percent
                    FROM quarterly_revenue_breakdown
                    WHERE company_name = 'TechVision Corporation'
                      AND fiscal_year  = :year
                    ORDER BY fiscal_quarter, segment_name
                """), {"year": year}).fetchall()
                if rows:
                    lines = [f"Q{r[0]} {r[1]}: ${r[2]:,.1f}M (YoY: {r[3]}%)" for r in rows]
                    return {"answer": f"TechVision quarterly breakdown ({year}):\n" + "\n".join(lines),
                            "sql_query": "direct quarterly lookup", "success": True}

            # EPS questions
            if "eps" in q or "earnings per share" in q:
                year = _extract_year(q) or 2024
                rows = conn.execute(text("""
                    SELECT i.line_item_name, i.amount_usd
                    FROM income_statement_line_items i
                    JOIN financial_statements s ON i.statement_id = s.statement_id
                    WHERE s.company_name = 'TechVision Corporation'
                      AND s.fiscal_year  = :year
                      AND LOWER(i.line_item_name) LIKE '%eps%'
                """), {"year": year}).fetchall()
                if rows:
                    lines = [f"{r[0]}: ${r[1]}" for r in rows]
                    return {"answer": f"TechVision EPS ({year}):\n" + "\n".join(lines),
                            "sql_query": "direct EPS lookup", "success": True}

            # Gross profit / margin questions
            if any(w in q for w in ["gross profit", "gross margin", "operating income"]):
                year = _extract_year(q) or 2024
                rows = conn.execute(text("""
                    SELECT i.line_item_name, i.amount_usd, i.percentage_of_revenue
                    FROM income_statement_line_items i
                    JOIN financial_statements s ON i.statement_id = s.statement_id
                    WHERE s.company_name = 'TechVision Corporation'
                      AND s.fiscal_year  = :year
                      AND (LOWER(i.line_item_name) LIKE '%gross%'
                           OR LOWER(i.line_item_name) LIKE '%operating%')
                    ORDER BY i.amount_usd DESC
                """), {"year": year}).fetchall()
                if rows:
                    lines = [f"{r[0]}: ${r[1]:,.1f}M ({r[2]}% of revenue)" for r in rows]
                    return {"answer": f"TechVision profitability ({year}):\n" + "\n".join(lines),
                            "sql_query": "direct profitability lookup", "success": True}

            # Full income statement
            if any(w in q for w in ["income statement", "financial summary", "all metrics"]):
                year = _extract_year(q) or 2024
                rows = conn.execute(text("""
                    SELECT i.line_item_name, i.amount_usd, i.percentage_of_revenue
                    FROM income_statement_line_items i
                    JOIN financial_statements s ON i.statement_id = s.statement_id
                    WHERE s.company_name = 'TechVision Corporation'
                      AND s.fiscal_year  = :year
                    ORDER BY i.line_item_id
                """), {"year": year}).fetchall()
                if rows:
                    lines = [f"{r[0]}: ${r[1]:,.1f}M" for r in rows]
                    return {"answer": f"TechVision income statement ({year}):\n" + "\n".join(lines),
                            "sql_query": "direct income statement lookup", "success": True}

        return {"answer": "No structured data found for this query.", "sql_query": None, "success": False}

    except Exception as e:
        logger.error(f"Direct SQL lookup failed: {e}")
        return {"answer": f"SQL lookup failed: {str(e)}", "sql_query": None, "success": False}


def _extract_year(text: str) -> Optional[int]:
    """Extract a 4-digit year from a query string."""
    import re
    match = re.search(r"\b(20\d{2})\b", text)
    return int(match.group(1)) if match else None


def insert_financial_metric(
    company_name:    str,
    fiscal_year:     int,
    statement_type:  str,
    metric_name:     str,
    metric_value:    float,
    ticker:          str = None,
    fiscal_quarter:  str = None,
    currency:        str = "USD",
    unit:            str = "millions",
    source_document: str = None,
):
    """Insert a structured financial metric into income_statement_line_items."""
    engine = get_db_engine()
    with engine.connect() as conn:
        # Get or create statement header
        row = conn.execute(text("""
            SELECT statement_id FROM financial_statements
            WHERE company_name   = :company
              AND fiscal_year    = :year
              AND statement_type = :stype
            LIMIT 1
        """), {"company": company_name, "year": fiscal_year, "stype": statement_type}).fetchone()

        if not row:
            result = conn.execute(text("""
                INSERT INTO financial_statements
                  (company_name, fiscal_year, fiscal_quarter, statement_type, filing_date)
                VALUES (:company, :year, :quarter, :stype, CURRENT_DATE)
                RETURNING statement_id
            """), {
                "company": company_name, "year": fiscal_year,
                "quarter": int(fiscal_quarter) if fiscal_quarter else None,
                "stype":   statement_type,
            })
            stmt_id = result.fetchone()[0]
        else:
            stmt_id = row[0]

        # Skip duplicate metric for same statement
        existing = conn.execute(text("""
            SELECT 1 FROM income_statement_line_items
            WHERE statement_id = :stmt_id AND line_item_name = :name
            LIMIT 1
        """), {"stmt_id": stmt_id, "name": metric_name}).fetchone()

        if existing:
            logger.debug(f"Metric already exists: {metric_name} for {company_name} {fiscal_year}")
            return

        conn.execute(text("""
            INSERT INTO income_statement_line_items
              (statement_id, line_item_name, line_item_category, amount_usd)
            VALUES (:stmt_id, :name, :category, :amount)
        """), {"stmt_id": stmt_id, "name": metric_name,
               "category": statement_type, "amount": metric_value})
        conn.commit()

    logger.info(f"Inserted: {metric_name}={metric_value} for {company_name} {fiscal_year}")