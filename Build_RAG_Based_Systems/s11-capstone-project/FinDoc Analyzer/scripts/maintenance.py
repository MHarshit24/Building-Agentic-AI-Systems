"""
FinDoc Analyzer — Maintenance & Troubleshooting Scripts
Includes:
  - Verify SQL metric insertion
  - Clean duplicate PDFs from vector store
  - Check database connectivity
  - Check Langfuse configuration
  - Generate debug report
"""

import os
import sys
import logging
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment
base_dir = Path(__file__).resolve().parents[2]
load_dotenv(base_dir / ".env")

proj_dir = Path(__file__).resolve().parents[1]
load_dotenv(proj_dir / ".env", override=True)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def check_sql_insertion():
    """Verify that financial metrics are actually being inserted into SQL."""
    logger.info("=" * 70)
    logger.info("CHECKING SQL METRIC INSERTION")
    logger.info("=" * 70)
    
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "findoc_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
        
        with conn.cursor() as cur:
            # Check financial_statements table
            cur.execute("SELECT COUNT(*) FROM financial_statements;")
            stmt_count = cur.fetchone()[0]
            logger.info(f"✓ financial_statements: {stmt_count} records")
            
            if stmt_count > 0:
                cur.execute("SELECT statement_id, company_name, fiscal_year, statement_type FROM financial_statements LIMIT 3;")
                for row in cur.fetchall():
                    logger.info(f"  Sample: ID={row[0]}, Company={row[1]}, Year={row[2]}, Type={row[3]}")
            
            # Check income_statement_line_items
            cur.execute("SELECT COUNT(*) FROM income_statement_line_items;")
            items_count = cur.fetchone()[0]
            logger.info(f"✓ income_statement_line_items: {items_count} records")
            
            if items_count > 0:
                cur.execute("SELECT line_item_name, amount_usd FROM income_statement_line_items LIMIT 5;")
                for row in cur.fetchall():
                    logger.info(f"  Sample: {row[0]}: ${row[1]:,.2f}" if row[1] else f"  Sample: {row[0]}: {row[1]}")
            
            # Check other tables
            for table in ["quarterly_revenue_breakdown", "balance_sheet_items", "risk_disclosures", "financial_ratios"]:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {table};")
                    count = cur.fetchone()[0]
                    logger.info(f"✓ {table}: {count} records")
                except Exception as e:
                    logger.warning(f"  {table}: Table may not exist or error: {e}")
        
        conn.close()
        logger.info("✓ SQL insertion verification complete\n")
        
    except Exception as e:
        logger.error(f"✗ SQL check failed: {e}\n")


def clean_duplicate_pdfs():
    """Remove duplicate PDFs from vector store, keeping only latest by document_id."""
    logger.info("=" * 70)
    logger.info("CLEANING DUPLICATE PDFS FROM VECTOR STORE")
    logger.info("=" * 70)
    
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "findoc_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
        
        vector_table = os.getenv("DB_TABLE_NAME", "documents_index")
        
        with conn.cursor() as cur:
            # Find duplicates
            try:
                cur.execute(f"""
                    SELECT metadata->>'source_file' as source_file, 
                           metadata->>'document_id' as doc_id,
                           COUNT(*) as count
                    FROM {vector_table}
                    GROUP BY metadata->>'source_file', metadata->>'document_id'
                    HAVING COUNT(*) > 1
                    ORDER BY source_file;
                """)
                
                duplicates = cur.fetchall()
                
                if not duplicates:
                    logger.info("✓ No duplicates found\n")
                    conn.close()
                    return
                
                logger.info(f"Found {len(duplicates)} duplicate document groups:")
                for source_file, doc_id, count in duplicates:
                    logger.info(f"  {source_file}: {count} copies (doc_id={doc_id})")
                
                # Delete duplicates, keeping only the first occurrence
                cur.execute(f"""
                    DELETE FROM {vector_table} t1
                    WHERE id NOT IN (
                        SELECT MIN(id) 
                        FROM {vector_table} t2
                        WHERE t1.metadata->>'source_file' = t2.metadata->>'source_file'
                        GROUP BY metadata->>'source_file'
                    );
                """)
                
                conn.commit()
                logger.info(f"✓ Cleaned duplicate vectors\n")
                
            except Exception as e:
                logger.warning(f"Could not check duplicates (table may differ): {e}\n")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"✗ Clean failed: {e}\n")


def check_langfuse_connection():
    """Verify Langfuse configuration and connectivity."""
    logger.info("=" * 70)
    logger.info("CHECKING LANGFUSE CONFIGURATION")
    logger.info("=" * 70)
    
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    if not public_key or not secret_key:
        logger.warning("✗ Langfuse credentials NOT SET — tracing disabled")
        logger.info("  Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable\n")
        return
    
    try:
        from langfuse import Langfuse
        
        lf = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        logger.info(f"✓ Langfuse client created successfully")
        logger.info(f"  Host: {host}")
        
        # Try to create a test trace
        test_trace = lf.trace(name="findoc_maintenance_check")
        logger.info(f"✓ Test trace created: {test_trace.id}")
        lf.flush()
        logger.info(f"✓ Langfuse connection verified\n")
        
    except Exception as e:
        logger.error(f"✗ Langfuse check failed: {e}\n")


def check_database_connectivity():
    """Test database connectivity."""
    logger.info("=" * 70)
    logger.info("CHECKING DATABASE CONNECTIVITY")
    logger.info("=" * 70)
    
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "findoc_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
        
        with conn.cursor() as cur:
            # Check pgvector extension
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            logger.info(f"✓ PostgreSQL connected: {version.split(',')[0]}")
            
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
            if cur.fetchone():
                logger.info("✓ pgvector extension installed")
            else:
                logger.warning("✗ pgvector extension NOT installed")
        
        conn.close()
        logger.info("✓ Database connectivity verified\n")
        
    except Exception as e:
        logger.error(f"✗ Database check failed: {e}\n")


def check_vector_store_health():
    """Check vector store health."""
    logger.info("=" * 70)
    logger.info("CHECKING VECTOR STORE HEALTH")
    logger.info("=" * 70)
    
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "findoc_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
        
        with conn.cursor() as cur:
            vector_table = os.getenv("DB_TABLE_NAME", "documents_index")
            
            try:
                cur.execute(f"SELECT COUNT(*) FROM {vector_table};")
                count = cur.fetchone()[0]
                logger.info(f"✓ Vector embeddings: {count} total chunks")
                
                # Check unique source files
                cur.execute(f"SELECT COUNT(DISTINCT metadata->>'source_file') FROM {vector_table};")
                unique_files = cur.fetchone()[0]
                logger.info(f"✓ Unique source files: {unique_files}")
                
                # Show sample metadata values
                cur.execute(f"SELECT DISTINCT metadata->>'company_name' FROM {vector_table} LIMIT 5;")
                companies = [row[0] for row in cur.fetchall()]
                logger.info(f"✓ Companies in vector store: {', '.join(companies)}")
                
            except Exception as e:
                logger.warning(f"Vector store check incomplete (table may differ): {e}")
        
        conn.close()
        logger.info()
        
    except Exception as e:
        logger.error(f"✗ Vector store check failed: {e}\n")


def generate_debug_report():
    """Generate comprehensive debug report."""
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " " * 15 + "FINDOC ANALYZER — DEBUG REPORT" + " " * 25 + "║")
    logger.info("╚" + "═" * 68 + "╝\n")
    
    logger.info("1. DATABASE CONNECTIVITY:")
    check_database_connectivity()
    
    logger.info("2. VECTOR STORE HEALTH:")
    check_vector_store_health()
    
    logger.info("3. SQL METRIC INSERTION:")
    check_sql_insertion()
    
    logger.info("4. LANGFUSE TRACING:")
    check_langfuse_connection()
    
    logger.info("=" * 70)
    logger.info("RECOMMENDATIONS:")
    logger.info("=" * 70)
    logger.info("1. If SQL metric count = 0:")
    logger.info("   - Check that PDFs were ingested via POST /api/v1/ingest")
    logger.info("   - Verify metrics are extracted from financial tables in PDFs")
    logger.info("   - Check application logs for extract_and_store_financial_data errors\n")
    
    logger.info("2. If Langfuse check fails:")
    logger.info("   - Verify LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env")
    logger.info("   - Check network connectivity to https://cloud.langfuse.com")
    logger.info("   - Verify credentials in Langfuse dashboard\n")
    
    logger.info("3. If duplicates found:")
    logger.info("   - Run: python scripts/maintenance.py --clean-duplicates\n")
    
    logger.info("4. To test handoff triggering:")
    logger.info("   - Query: 'Should I invest my entire retirement savings in a single stock?'")
    logger.info("   - Expected: handoff_triggered=true with reference ID\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="FinDoc Analyzer Maintenance", 
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="""
Examples:
  python scripts/maintenance.py                    # Full debug report
  python scripts/maintenance.py --check-sql        # Check SQL insertion only
  python scripts/maintenance.py --check-langfuse   # Check Langfuse
  python scripts/maintenance.py --clean-duplicates # Clean vector store
  python scripts/maintenance.py --check-db         # Check database connectivity
    """)
    parser.add_argument("--check-sql", action="store_true", help="Check SQL metric insertion")
    parser.add_argument("--clean-duplicates", action="store_true", help="Clean duplicate PDFs from vector store")
    parser.add_argument("--check-langfuse", action="store_true", help="Check Langfuse configuration")
    parser.add_argument("--check-db", action="store_true", help="Check database connectivity")
    parser.add_argument("--full-report", action="store_true", help="Generate full debug report (default)")
    
    args = parser.parse_args()
    
    if args.check_sql:
        check_sql_insertion()
    elif args.clean_duplicates:
        clean_duplicate_pdfs()
    elif args.check_langfuse:
        check_langfuse_connection()
    elif args.check_db:
        check_database_connectivity()
    elif args.full_report or not any(vars(args).values()):
        generate_debug_report()
