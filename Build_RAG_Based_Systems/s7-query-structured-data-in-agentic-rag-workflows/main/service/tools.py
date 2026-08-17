"""
Tools Module - Provides SQL and Vector tools for the healthcare analytics agentic RAG system
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

from llama_index.core import Document, StorageContext, VectorStoreIndex, Settings
from llama_index.core.query_engine import NLSQLTableQueryEngine
from llama_index.core.tools import QueryEngineTool
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.ingestion import IngestionPipeline
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding

from .sql_database import get_sql_database
from .ingestion_service import DocumentIngestionPipeline

# Configure logging
logger = logging.getLogger(__name__)


def _load_env():
    """
    Load environment variables using dual .env pattern.
    Root .env (parents[4]) is loaded first for secrets: DB_PASSWORD, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT.
    Project .env (parents[2]) is loaded second with override=True for DB config, deployment names, etc.
    Secrets are preserved across the second load so they are never overwritten.
    """
    if "pytest" in sys.modules:
        return

    # This file: main/service/tools.py -> parents[0]=service/, parents[1]=main/, parents[2]=project root, parents[4]=root
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

    # This file: main/service/tools.py -> parents[2] = project root
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


def get_vector_tool():
    """
    Create a QueryEngineTool for querying policy documents stored in pgvector.
    
    Returns:
        QueryEngineTool configured for vector document search
    
    TODO: Implement the following steps:
    1. Initialize Azure OpenAI embeddings if Settings._embed_model is None
    2. Load the vector index from the database using DocumentIngestionPipeline
    3. Check if vector_index is None and raise RuntimeError if no index found
    4. Create a query engine from the vector_index
    5. Return a QueryEngineTool configured with the query engine
    """
    logger.info("Creating vector tool...")
    
    # TODO: Step 1 - Initialize Azure embeddings if not already set
    # Hint: Check whether the Settings object has an embed model already configured by checking if Settings._embed_model is None.
    # If it is None, you need to create a new AzureOpenAIEmbedding instance. You should retrieve all the necessary configuration values
    # from environment variables using os.getenv. The embedding deployment name, API key, endpoint, and API version all need to be
    # retrieved from the environment. Once you create the embedding model instance, assign it to Settings.embed_model so it can be
    # used throughout the application.
    if Settings._embed_model is None:
        embed_model = AzureOpenAIEmbedding(
            model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            deployment_name=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        )
        Settings.embed_model = embed_model
    
    # TODO: Step 2 - Load vector index from database
    # Hint: You need to load the previously stored vector index from the PostgreSQL database. Use the static method load_from_db on
    # the DocumentIngestionPipeline class. This method requires a table name parameter, which you should retrieve from the environment
    # variable DB_TABLE_NAME, with a default fallback value of "policy_document_embeddings" if the environment variable is not set.
    # Store the returned vector index in a variable so you can use it in the next steps.
    vector_index = DocumentIngestionPipeline.load_from_db(
        table_name=os.getenv("DB_TABLE_NAME", "policy_document_embeddings")
    )
    
    # TODO: Step 3 - Check if vector index is None and raise error
    # Hint: Verify that the vector index was successfully loaded. If the vector_index variable
    # is None, it means no index was found in the database. In this case, you should raise a RuntimeError with a clear error message
    # that informs the user that they need to ingest documents before they can use this tool.
    if vector_index is None:
        raise RuntimeError(
            "No vector index found in the database. Please ingest documents first using POST /api/documents/upload."
        )
    
    # TODO: Step 4 - Create query engine from vector index
    # Hint: You need to create a query engine from the vector index. The vector index object has a method
    # called as_query_engine that will create a query engine instance. Call this method on your vector_index variable and store the
    # result in a variable, as you will need to pass it to the QueryEngineTool in the next step.
    query_engine = vector_index.as_query_engine()
    
    # TODO: Step 5 - Return QueryEngineTool
    # Hint: You need to create and return a QueryEngineTool instance. Use the from_defaults class method of QueryEngineTool
    # to create a tool from a query engine. You need to provide three parameters: the query_engine you created
    # in the previous step, a name for the tool which should be "policy_documents", and a description string that explains what this tool
    # contains and when to use it. The description should mention that it contains healthcare policy documents, quality metrics targets,
    # patient safety protocols, capacity management guidelines, and regulatory compliance information, and that it should be used for
    # questions about targets, benchmarks, protocols, guidelines, or policy information.
    return QueryEngineTool.from_defaults(
        query_engine=query_engine,
        name="policy_documents",
        description=(
            "Contains healthcare policy documents including quality metrics targets, patient safety protocols, "
            "capacity management guidelines, and regulatory compliance information. "
            "Use this tool for questions about targets, benchmarks, protocols, guidelines, or any policy information."
        ),
    )


def get_sql_tool():
    """
    Create a QueryEngineTool for querying the hospital operations SQL database.
    
    Returns:
        QueryEngineTool configured for SQL database queries
    
    TODO: Implement the following steps:
    1. Get the SQL database using get_sql_database() function
    2. Create an NLSQLTableQueryEngine with the database and tables
    3. Return a QueryEngineTool configured with the query engine
    """
    logger.info("Creating SQL tool...")
    
    # TODO: Step 1 - Get SQL database
    # Hint: You need to retrieve the SQL database connection object. There is a function called get_sql_database that has already been
    # imported at the top of this file. Call this function to get the database connection, and store the result in a variable so you
    # can use it in the next step to create the query engine.
    sql_database = get_sql_database()
    
    # TODO: Step 2 - Create NLSQLTableQueryEngine
    # Hint: You need to create a natural language SQL query engine that can translate questions into SQL queries. Instantiate the
    # NLSQLTableQueryEngine class, passing in the SQL database you retrieved in the previous step. You also need to specify which tables
    # should be accessible through this query engine by providing a list containing the table names "patients" and "department_capacity".
    # Additionally, set the verbose parameter to True so that the query engine will provide detailed output during query execution.
    # Store the created query engine instance in a variable for use in the next step.
    query_engine = NLSQLTableQueryEngine(
        sql_database=sql_database,
        tables=["patients", "department_capacity"],
        verbose=True,
    )
    
    # TODO: Step 3 - Return QueryEngineTool
    # Hint: You need to wrap your query engine in a QueryEngineTool so it can be used by the agent. Use the from_defaults class
    # method of QueryEngineTool to create the tool instance. You need to provide three parameters: the query_engine you created in the
    # previous step, a name for the tool which should be "hospital_database", and a description string that clearly explains what data
    # this tool contains and when the agent should use it. The description should mention that this tool contains patient admission data,
    # discharge information, readmission rates, department capacity metrics, bed utilization rates, and operational statistics, and that
    # it should be used for questions about actual patient counts, utilization rates, readmission statistics, or any quantitative
    # operational metrics.
    return QueryEngineTool.from_defaults(
        query_engine=query_engine,
        name="hospital_database",
        description=(
            "Contains hospital operational data including patient admission data, discharge information, readmission rates, "
            "department capacity metrics, bed utilization rates, and operational statistics. "
            "Use this tool for questions about actual patient counts, utilization rates, readmission statistics, "
            "or any quantitative operational metrics."
        ),
    )


# ----- Public API: Document Ingestion -----

def add_documents(documents: list[Document]) -> dict:
    """
    Ingest documents into the pgvector-backed vector store.
    
    This function:
    1. Initializes Azure OpenAI embeddings
    2. Chunks documents into nodes
    3. Stores embeddings in PostgreSQL using pgvector
    
    Args:
        documents: List of Document objects to ingest
        
    Returns:
        dict with keys: documents_count, nodes_count, table_name
    """
    logger.info(f"=== add_documents called with {len(documents)} document(s) ===")
    
    if not documents:
        logger.warning("No documents provided, returning early")
        return {"documents_count": 0, "nodes_count": 0, "table_name": None}

    # Initialize Azure embeddings if not already set
    if Settings._embed_model is None:
        logger.info("Initializing Azure OpenAI embeddings...")
        embed_model = AzureOpenAIEmbedding(
            model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            deployment_name=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        )
        Settings.embed_model = embed_model
    
    # Chunk the documents
    logger.info("Chunking documents...")
    text_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    pipeline = IngestionPipeline(transformations=[text_splitter])
    nodes = pipeline.run(documents=documents)
    logger.info(f"✓ Chunked {len(documents)} document(s) into {len(nodes)} node(s)")
    
    # Use DocumentIngestionPipeline's vector store
    table_name = os.getenv("DB_TABLE_NAME", "policy_document_embeddings")
    logger.info(f"Storing embeddings in table: {table_name}")
    
    ingestion_pipeline = DocumentIngestionPipeline(table_name=table_name)
    vector_store = ingestion_pipeline._get_vector_store()
    
    # Create index and persist to PostgreSQL
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex(nodes=nodes, storage_context=storage_context)
    
    logger.info(f"✓ Documents ingested successfully into table: {table_name}")
    
    return {
        "documents_count": len(documents),
        "nodes_count": len(nodes),
        "table_name": table_name
    }