"""
SQL Database Service - Provides SQLDatabase wrapper for hospital operations
"""
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv
from llama_index.core import SQLDatabase
from sqlalchemy import create_engine


def _load_env():
    """
    Load environment variables using dual .env pattern.
    Root .env (parents[4]) is loaded first for secrets: DB_PASSWORD, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT.
    Project .env (parents[2]) is loaded second with override=True for DB config, deployment names, etc.
    Secrets are preserved across the second load so they are never overwritten.
    """
    if "pytest" in sys.modules:
        return

    # This file: main/service/sql_database.py -> parents[0]=service/, parents[1]=main/, parents[2]=project root, parents[4]=root
    base_dir = Path(__file__).resolve().parents[4]
    base_env_path = base_dir / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()

    # Preserve secrets before loading project .env
    db_password = os.getenv("DB_PASSWORD")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

    # This file: main/service/sql_database.py -> parents[2] = project root
    proj_dir = Path(__file__).resolve().parents[2]
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


def get_db_engine():
    """
    Create a SQLAlchemy engine for the configured Postgres database.
    
    Returns:
        SQLAlchemy engine instance
    
    TODO: Implement the following steps:
    1. Retrieve database connection parameters from environment variables
    2. Construct the database connection URL string
    3. Create and return a SQLAlchemy engine using the connection URL
    """
    # TODO: Step 1 - Retrieve database connection parameters from environment variables
    # Hint: You need to retrieve all the database connection parameters using os.getenv. Get the database user with a default
    # value of "postgres", the password with a default value of "password", the host with a default value of "localhost", the port
    # with a default value of "5432", and the database name with a default value of "hospital_analytics_db". Store each value in
    # appropriately named variables.
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "password")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "hospital_analytics_db")
    
    # TODO: Step 2 - Construct the database connection URL string
    # Hint: You need to build a PostgreSQL connection URL string in the format "postgresql://user:password@host:port/dbname".
    # Use an f-string to construct this URL by inserting the variables you retrieved in the previous step. Store the complete
    # connection URL string in a variable.
    connection_url = f"postgresql://{db_user}:{quote_plus(db_password)}@{db_host}:{db_port}/{db_name}"
    
    # TODO: Step 3 - Create and return a SQLAlchemy engine
    # Hint: Use the create_engine function from sqlalchemy, passing in the connection URL string you constructed in the previous step.
    # The create_engine function will return a SQLAlchemy engine instance that can be used to connect to the database. Return this
    # engine instance from the function.
    return create_engine(connection_url)


def get_sql_database(engine=None, include_tables=None):
    """
    Return a LlamaIndex SQLDatabase wrapper over the Postgres engine.
    
    By default it exposes the hospital operations tables.
    
    Args:
        engine: Optional SQLAlchemy engine. If None, will be created automatically.
        include_tables: Optional list of table names to include. If None, defaults to hospital operations tables.
    
    Returns:
        SQLDatabase instance configured with the engine and tables
    
    TODO: Implement the following steps:
    1. Check if engine parameter is None and create one if needed
    2. Check if include_tables parameter is None and set default table list
    3. Create and return a SQLDatabase instance with the engine and tables
    """
    # TODO: Step 1 - Check if engine parameter is None and create one if needed
    # Hint: Check whether the engine parameter passed to this function is None. If it is None, you need to create a database engine
    # by calling the get_db_engine function that is defined in this same file. Store the result in the engine variable so it can be
    # used in the subsequent steps.
    if engine is None:
        engine = get_db_engine()
    
    # TODO: Step 2 - Check if include_tables parameter is None and set default table list
    # Hint: Check whether the include_tables parameter passed to this function is None. If it is None, you need to set it to a list
    # containing the default table names that should be exposed. The default tables are "patients" and "department_capacity". Store
    # this list in the include_tables variable.
    if include_tables is None:
        include_tables = ["patients", "department_capacity"]
    
    # TODO: Step 3 - Create and return a SQLDatabase instance
    # Hint: Create a SQLDatabase instance from the llama_index.core module, passing in the engine and include_tables parameters.
    # The SQLDatabase class constructor takes the engine as the first argument and include_tables as a keyword argument. Return the
    # created SQLDatabase instance from the function.
    return SQLDatabase(engine, include_tables=include_tables)