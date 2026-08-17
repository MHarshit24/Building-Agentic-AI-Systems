"""
Database Setup for Healthcare Analytics Platform
Creates hospital_operations database with patients and department_capacity tables
"""
import os
import sys
import logging
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


def _load_env():
    """
    Load environment variables using dual .env pattern.
    Root .env (parents[3]) is loaded first for secrets: DB_PASSWORD, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT.
    Project .env (parents[1]) is loaded second with override=True for DB config, deployment names, etc.
    Secrets are preserved across the second load so they are never overwritten.
    """
    if "pytest" in sys.modules:
        return

    # This file: main/db_setup.py -> parents[0]=main/, parents[1]=project root, parents[3]=Building_Agentic_AI_Systems root
    base_dir = Path(__file__).resolve().parents[3]
    base_env_path = base_dir / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()

    # Preserve secrets before loading project .env
    db_password = os.getenv("DB_PASSWORD")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

    # This file: main/db_setup.py -> parents[1] = project root
    proj_dir = Path(__file__).resolve().parents[1]
    proj_env_path = proj_dir / ".env"

    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
    else:
        load_dotenv()

    # Restore preserved secrets so project .env cannot overwrite them
    if db_password:
        os.environ["DB_PASSWORD"] = db_password
    if azure_api_key:
        os.environ["AZURE_OPENAI_API_KEY"] = azure_api_key
    if azure_endpoint:
        os.environ["AZURE_OPENAI_ENDPOINT"] = azure_endpoint

    # Remove conflicting PostgreSQL variables that may come from root .env
    conflicting_pg_vars = [
        "DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
        "PGUSER", "PGPASSWORD", "PGDATABASE",
    ]
    for var in conflicting_pg_vars:
        os.environ.pop(var, None)


_load_env()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database credentials
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "hospital_analytics_db")


def get_connection_string(db_name):
    return f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{db_name}"


def setup_database():
    """Setup hospital operations database with schema and sample data"""
    # Connect to default 'postgres' database to create the target database if it doesn't exist
    engine = create_engine(get_connection_string("postgres"), isolation_level="AUTOCOMMIT")
    
    with engine.connect() as conn:
        # Check if database exists
        result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'"))
        if not result.fetchone():
            logger.info(f"Creating database {DB_NAME}...")
            conn.execute(text(f"CREATE DATABASE {DB_NAME}"))
        else:
            logger.info(f"Database {DB_NAME} already exists.")

    # Now connect to the target database
    engine = create_engine(get_connection_string(DB_NAME))
    
    with engine.connect() as conn:
        logger.info("Creating hospital operations tables...")
        
        # Enable pgvector extension (required for PGVectorStore)
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        
        # 1. Patients table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id INTEGER PRIMARY KEY,
                admission_date DATE NOT NULL,
                discharge_date DATE,
                department VARCHAR(50) NOT NULL,
                age_group VARCHAR(10) NOT NULL,
                readmitted BOOLEAN DEFAULT FALSE
            );
        """))
        
        # 2. Department Capacity table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS department_capacity (
                department VARCHAR(50) PRIMARY KEY,
                total_beds INTEGER NOT NULL,
                avg_utilization_rate FLOAT NOT NULL,
                target_utilization FLOAT NOT NULL
            );
        """))
        
        logger.info("Tables created or verified.")

        # Insert sample data
        logger.info("Inserting sample data...")
        
        # Clear existing data (for idempotency)
        conn.execute(text("DELETE FROM patients;"))
        conn.execute(text("DELETE FROM department_capacity;"))
        
        # Insert department capacity data
        conn.execute(text("""
            INSERT INTO department_capacity (department, total_beds, avg_utilization_rate, target_utilization) VALUES
            ('Cardiology', 120, 0.82, 0.80),
            ('Orthopedics', 80, 0.78, 0.82),
            ('Emergency', 60, 0.88, 0.75),
            ('Pediatrics', 50, 0.72, 0.78)
            ON CONFLICT (department) DO UPDATE SET
                total_beds = EXCLUDED.total_beds,
                avg_utilization_rate = EXCLUDED.avg_utilization_rate,
                target_utilization = EXCLUDED.target_utilization;
        """))
        
        # Generate sample patient data
        # Calculate dates relative to today
        today = date.today()
        last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_month_end = today.replace(day=1) - timedelta(days=1)
        
        # Sample patient admissions for last month
        departments = ['Cardiology', 'Orthopedics', 'Emergency', 'Pediatrics']
        age_groups = ['<18', '18-45', '46-65', '65+']
        
        patient_data = []
        patient_id = 1
        
        # Generate realistic sample data
        # Cardiology: 45 patients, ~12% readmission rate
        for i in range(45):
            admission = last_month_start + timedelta(days=i % 28)
            stay_days = 4 if i % 10 != 0 else 6  # Most 4 days, some 6
            discharge = admission + timedelta(days=stay_days)
            readmitted = (i % 8 == 0)  # ~12.5% readmission
            age = '65+' if i % 3 == 0 else ('46-65' if i % 2 == 0 else '18-45')
            patient_data.append((patient_id, admission, discharge, 'Cardiology', age, readmitted))
            patient_id += 1
        
        # Orthopedics: 30 patients, ~8% readmission rate
        for i in range(30):
            admission = last_month_start + timedelta(days=i % 28)
            stay_days = 6 if i % 5 != 0 else 8
            discharge = admission + timedelta(days=stay_days)
            readmitted = (i % 12 == 0)  # ~8% readmission
            age = '46-65' if i % 2 == 0 else '18-45'
            patient_data.append((patient_id, admission, discharge, 'Orthopedics', age, readmitted))
            patient_id += 1
        
        # Emergency: 80 patients, ~5% readmission rate
        for i in range(80):
            admission = last_month_start + timedelta(days=i % 28)
            stay_days = 1 if i % 3 != 0 else 2
            discharge = admission + timedelta(days=stay_days)
            readmitted = (i % 20 == 0)  # ~5% readmission
            age = age_groups[i % 4]
            patient_data.append((patient_id, admission, discharge, 'Emergency', age, readmitted))
            patient_id += 1
        
        # Pediatrics: 25 patients, ~4% readmission rate
        for i in range(25):
            admission = last_month_start + timedelta(days=i % 28)
            stay_days = 3 if i % 4 != 0 else 4
            discharge = admission + timedelta(days=stay_days)
            readmitted = (i == 5)  # 1 out of 25 = 4% readmission
            patient_data.append((patient_id, admission, discharge, 'Pediatrics', '<18', readmitted))
            patient_id += 1
        
        # Insert patient data
        for p in patient_data:
            conn.execute(text("""
                INSERT INTO patients (patient_id, admission_date, discharge_date, department, age_group, readmitted)
                VALUES (:pid, :admit, :discharge, :dept, :age, :readmit)
            """), {
                "pid": p[0],
                "admit": p[1],
                "discharge": p[2],
                "dept": p[3],
                "age": p[4],
                "readmit": p[5]
            })
        
        conn.commit()
        logger.info(f"✓ Inserted {len(patient_data)} patient records")
        logger.info("Sample data inserted successfully.")


if __name__ == "__main__":
    setup_database()