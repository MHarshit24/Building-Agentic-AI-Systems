"""Core RAG service orchestrating multi-modal document processing and querying."""
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import quote_plus

from dotenv import load_dotenv
from llama_parse import LlamaParse
from llama_index.core import VectorStoreIndex, Document, Settings, StorageContext
from llama_index.core.schema import TextNode
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.vector_stores.postgres import PGVectorStore

from .metadata import get_file_metadata, extract_diet_metadata_from_filename
from .semantic_chunking import SemanticChunker
from .table_extraction import find_markdown_tables
from .table_processing import build_nodes_from_tables
from .image_extraction import extract_images_from_pdf
from .captioning import generate_caption
from .query_engine import create_query_engine

logger = logging.getLogger(__name__)


def _load_env():
    """
    Load environment variables with the same secret-preservation pattern
    used in previous assignments.

    - Root .env (4 levels up from this file) is loaded first for secrets:
      AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, DB_PASSWORD, LLAMA_CLOUD_API_KEY
    - Project .env (2 levels up) is loaded second with override=True for
      deployment names, DB config, API server settings, etc.
    - Secrets preserved across the second load so they are never overwritten.
    - Conflicting PostgreSQL env vars from root .env are removed to avoid
      mix-ups with the project DB config.
    """
    # Skip loading .env when tests intentionally clear environment
    if "pytest" in sys.modules:
        return
    # Locate root .env (Building_Agentic_AI_Systems/.env)
    # This file: <project>/main/service/rag_service.py  -> parents[4] = root
    base_dir = Path(__file__).resolve().parents[4]
    base_env_path = base_dir / ".env"

    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
        logger.debug(f"Loaded root .env from {base_env_path}")
    else:
        load_dotenv()
        logger.warning(f"Root .env not found at {base_env_path}, falling back to default load_dotenv()")

    # Preserve secret values before loading project .env
    db_password = os.getenv("DB_PASSWORD")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    llama_cloud_api_key = os.getenv("LLAMA_CLOUD_API_KEY")

    # Locate project .env (s5 project root/.env)
    # This file: <project>/main/service/rag_service.py  -> parents[2] = project root
    proj_dir = Path(__file__).resolve().parents[2]
    proj_env_path = proj_dir / ".env"

    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
        logger.debug(f"Loaded project .env from {proj_env_path}")
    else:
        load_dotenv()
        logger.warning(f"Project .env not found at {proj_env_path}, falling back to default load_dotenv()")

    # Restore preserved secrets so project .env cannot overwrite them
    if db_password:
        os.environ["DB_PASSWORD"] = db_password
    if azure_api_key:
        os.environ["AZURE_OPENAI_API_KEY"] = azure_api_key
    if azure_endpoint:
        os.environ["AZURE_OPENAI_ENDPOINT"] = azure_endpoint
    if llama_cloud_api_key:
        os.environ["LLAMA_CLOUD_API_KEY"] = llama_cloud_api_key

    # Remove conflicting PostgreSQL variables that may come from root .env
    conflicting_pg_vars = [
        "DATABASE_URL",
        "POSTGRES_URL",
        "PGHOST",
        "PGPORT",
        "PGUSER",
        "PGPASSWORD",
        "PGDATABASE",
    ]
    for var in conflicting_pg_vars:
        os.environ.pop(var, None)


def configure_llm_and_embeddings() -> Tuple[AzureOpenAI, AzureOpenAIEmbedding]:
    """
    Configure LLM and embedding models from environment variables.

    Returns:
        Tuple of (llm, embed_model)

    Raises:
        EnvironmentError: If required environment variables are missing
    """
    _load_env()
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    llm_deployment = os.environ.get("AZURE_OPENAI_LLM_DEPLOYMENT")
    embedding_deployment = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

    missing = [
        name
        for name, val in [
            ("AZURE_OPENAI_API_KEY", api_key),
            ("AZURE_OPENAI_ENDPOINT", endpoint),
            ("AZURE_OPENAI_LLM_DEPLOYMENT", llm_deployment),
            ("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", embedding_deployment),
        ]
        if not val
    ]
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        raise EnvironmentError("Missing environment variables: " + ", ".join(missing))

    logger.info(f"Configuring Azure OpenAI LLM: deployment={llm_deployment}, endpoint={endpoint}")
    llm = AzureOpenAI(
        model="gpt-4o-mini",
        deployment_name=llm_deployment,
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
    )

    logger.info(f"Configuring Azure OpenAI Embedding: deployment={embedding_deployment}")
    embed_model = AzureOpenAIEmbedding(
        model=embedding_deployment,
        deployment_name=embedding_deployment,
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
    )

    try:
        Settings.llm = llm
        Settings.embed_model = embed_model
    except Exception as e:
        logger.warning(f"Could not set global Settings: {e}, models will be passed directly")

    logger.info("LLM and embedding models configured successfully")
    return llm, embed_model


def load_documents(pdf_path: str) -> str:
    """
    Load and parse PDF document to markdown using LlamaParse.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Full markdown text from the document
    """
    logger.info(f"Loading PDF document: {pdf_path}")
    llama_parse_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not llama_parse_api_key:
        logger.error("Missing LLAMA_CLOUD_API_KEY in environment")
        raise SystemExit(
            "Missing LLAMA_CLOUD_API_KEY in environment. Get one from https://cloud.llamaindex.ai/"
        )

    logger.info("Initializing LlamaParse parser...")
    parser_lp = LlamaParse(result_type="markdown", verbose=True)
    documents = parser_lp.load_data(pdf_path)

    if not documents:
        logger.error("No content returned by LlamaParse")
        raise SystemExit("No content returned by LlamaParse.")

    full_text = "\n\n".join(doc.text for doc in documents if getattr(doc, "text", ""))
    if not full_text.strip():
        logger.error("Parsed document appears empty")
        raise SystemExit("Parsed document appears empty.")

    logger.info(f"Document parsed successfully, extracted {len(full_text)} characters of text")
    return full_text


def create_vector_store(embed_dim: int = 1536) -> PGVectorStore:
    """
    Create a PostgreSQL vector store instance.

    Args:
        embed_dim: Dimension of the embeddings

    Returns:
        PGVectorStore instance
    """
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    database = os.getenv("DB_NAME", "rag_db")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD")
    table_name = os.getenv("DB_TABLE_NAME")

    if not password:
        logger.error("DB_PASSWORD environment variable is required")
        raise EnvironmentError("DB_PASSWORD environment variable is required")

    if not table_name:
        logger.error("DB_TABLE_NAME environment variable is required")
        raise EnvironmentError(
            "DB_TABLE_NAME environment variable is required. Please set it in your .env file."
        )

    logger.info(f"Using table name from DB_TABLE_NAME environment variable: {table_name}")
    return PGVectorStore.from_params(
        database=database,
        host=host,
        password=quote_plus(password),
        port=int(port),
        user=user,
        table_name=table_name,
        embed_dim=embed_dim,
    )


class RAGService:
    """Core service for multi-modal diet counselling RAG system."""
    
    def __init__(self):
        """Initialize the RAG service."""
        self.index: Optional[VectorStoreIndex] = None
        self.llm = None
        self.embed_model = None
        self.semantic_chunker = None
        self.query_engine = None
        self._initialized = False
        self._index_loaded = False
    
    def initialize(self):
        """Initialize LLM, embeddings, and processors."""
        if not self._initialized:
            logger.info("Initializing LLM and embedding models...")
            self.llm, self.embed_model = configure_llm_and_embeddings()
            
            # Initialize semantic chunker
            self.semantic_chunker = SemanticChunker(self.embed_model)
            
            self._initialized = True
            logger.info("RAG service initialized successfully")
            
            # Try to load existing index after initialization
            if not self._index_loaded:
                self._load_existing_index()
    
    def _load_existing_index(self):
        """Load existing index from PostgreSQL if it exists."""
        if self._index_loaded:
            return
        
        self._index_loaded = True
        
        try:
            logger.info("Attempting to load existing index from PostgreSQL...")
            
            if not self._initialized:
                self.initialize()
            
            vector_store = create_vector_store(embed_dim=1536)
            
            try:
                Settings.embed_model = self.embed_model
                index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
            except Exception as e1:
                logger.debug(f"First attempt to load index failed: {e1}, trying with explicit embed_model...")
                try:
                    index = VectorStoreIndex.from_vector_store(
                        vector_store=vector_store,
                        embed_model=self.embed_model
                    )
                except Exception as e2:
                    logger.debug(f"Second attempt to load index failed: {e2}")
                    raise e2
            
            self.index = index
            # Build query engine from loaded index
            self.query_engine = create_query_engine(
                index=self.index,
                llm=self.llm,
            )
            logger.info("Successfully loaded existing index from PostgreSQL")
        except Exception as e:
            logger.info(f"No existing index found in PostgreSQL (this is normal for first run): {type(e).__name__}: {e}")
            self.index = None
            self.query_engine = None
    
    def process_document(
        self,
        pdf_path: str,
        original_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a PDF document and add it to the multi-modal index.
        
        Processes text (with semantic chunking), tables, and images.
        
        Args:
            pdf_path: Path to the PDF file (may be temporary)
            original_filename: Original filename to use in metadata
            
        Returns:
            Dictionary with processing results including node statistics
        """
        logger.info("Processing document (boilerplate): %s", pdf_path)

        # TODO: Process the document and index it into the vector store, then return a result dict.
        # HINT: Ensure services are initialized (LLM, embedding model, semantic chunker, etc.)
        # HINT: Build metadata using `get_file_metadata(pdf_path)`
        # HINT: If `original_filename` is provided, override `source`/`file_path` and re-extract
        #       diet tags using `extract_diet_metadata_from_filename(original_filename)`
        # HINT: Parse the PDF into plain text/markdown (extract tables/images if present)
        # HINT: Turn the parsed content into nodes/chunks and attach metadata to each node
        # HINT: Create/load the vector store using `create_vector_store(...)`
        # HINT: Create or load a `VectorStoreIndex`, then insert nodes into it
        # HINT: Return a dict like:
        #   - message: str
        #   - documents_indexed: int
        #   - optional: total_nodes/text_nodes/table_nodes/image_nodes, file_path, etc.
        # Your code here:

        # Ensure services are initialized (LLM, embedding model, semantic chunker, etc.)
        if not self._initialized:
            self.initialize()

        # Build metadata using get_file_metadata(pdf_path)
        metadata = get_file_metadata(pdf_path)

        # If original_filename is provided, override source/file_path and re-extract
        # diet tags using extract_diet_metadata_from_filename(original_filename)
        if original_filename:
            metadata["source"] = original_filename
            metadata["file_path"] = original_filename
            diet_tags = extract_diet_metadata_from_filename(original_filename)
            metadata.update(diet_tags)

        source_name = metadata.get("source", os.path.basename(pdf_path))
        logger.info(f"Processing document: source={source_name}, metadata={metadata}")

        # Parse the PDF into plain text/markdown (LlamaParse)
        full_text = load_documents(pdf_path)

        # --- Text nodes via semantic chunking ---
        logger.info("Creating semantic text chunks...")
        text_nodes: List[TextNode] = self.semantic_chunker.process(full_text, metadata=metadata)
        logger.info(f"Created {len(text_nodes)} text node(s)")

        # --- Table nodes ---
        logger.info("Extracting markdown tables...")
        table_tuples = find_markdown_tables(full_text)
        table_markdowns = [t[2] for t in table_tuples]
        table_nodes: List[TextNode] = []
        if table_markdowns:
            table_nodes = build_nodes_from_tables(
                source_name=source_name,
                table_markdowns=table_markdowns,
                llm=self.llm,
                additional_metadata=metadata,
            )
        logger.info(f"Created {len(table_nodes)} table node(s)")

        # --- Image nodes ---
        logger.info("Extracting images from PDF...")
        image_nodes: List[TextNode] = []
        with tempfile.TemporaryDirectory() as image_output_dir:
            extracted_images = extract_images_from_pdf(pdf_path, image_output_dir)
            for img_record in extracted_images:
                try:
                    caption = generate_caption(img_record["path"])
                    img_metadata = dict(metadata)
                    img_metadata["content_type"] = "image_caption"
                    img_metadata["page"] = img_record["page"]
                    img_metadata["image_index"] = img_record["image_index"]
                    node = TextNode(text=caption, metadata=img_metadata)
                    image_nodes.append(node)
                except Exception as img_err:
                    logger.warning(f"Skipping image caption for {img_record['path']}: {img_err}")
        logger.info(f"Created {len(image_nodes)} image node(s)")

        # Combine all nodes
        all_nodes: List[TextNode] = text_nodes + table_nodes + image_nodes
        logger.info(f"Total nodes to index: {len(all_nodes)}")

        # Create/load the vector store using create_vector_store(...)
        vector_store = create_vector_store(embed_dim=1536)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # Create or load a VectorStoreIndex, then insert nodes into it
        if self.index is None:
            logger.info("Creating new VectorStoreIndex and inserting nodes...")
            self.index = VectorStoreIndex(
                nodes=all_nodes,
                storage_context=storage_context,
                embed_model=self.embed_model,
            )
        else:
            logger.info("Inserting nodes into existing VectorStoreIndex...")
            for node in all_nodes:
                self.index.insert(node)

        # Build/refresh query engine after indexing
        self.query_engine = create_query_engine(
            index=self.index,
            llm=self.llm,
        )

        logger.info(f"Successfully indexed document: {source_name}")

        # Return a dict like:
        #   - message: str
        #   - documents_indexed: int
        #   - optional: total_nodes/text_nodes/table_nodes/image_nodes, file_path, etc.
        return {
            "message": f"Successfully processed and indexed document: {source_name}",
            "documents_indexed": 1,
            "total_nodes": len(all_nodes),
            "text_nodes": len(text_nodes),
            "table_nodes": len(table_nodes),
            "image_nodes": len(image_nodes),
            "file_path": source_name,
        }
    
    def query(
        self,
        question: str,
        similarity_top_k: int = 2,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, List[Any]]:
        """
        Query the index with optional metadata filtering.
        
        Args:
            question: Query question
            similarity_top_k: Number of top similar results to retrieve
            filters: Optional metadata filters (e.g., {"meal_type": "breakfast", "dietary_restriction": "vegetarian"})
            
        Returns:
            Tuple of (answer string, list of retrieved nodes)
        """
        # If query_engine is already set (e.g. loaded from existing index or set externally),
        # delegate directly to it — this avoids requiring self.index to be set separately
        if self.query_engine is not None:
            logger.info(
                f"Processing query via self.query_engine: "
                f"question='{question[:100]}...', "
                f"similarity_top_k={similarity_top_k}, filters={filters}"
            )

            try:
                result = self.query_engine.query(
                    question,
                    similarity_top_k=similarity_top_k,
                    filters=filters
                )

            except TypeError:
                qe = create_query_engine(
                    index=self.index,
                    llm=self.llm,
                    similarity_top_k=similarity_top_k,
                    filters=filters,
                )

                result = qe.query(question)

            if isinstance(result, tuple):
                return result

            answer = (
                str(result.response)
                if hasattr(result, "response")
                else str(result)
            )

            nodes = (
                result.source_nodes
                if hasattr(result, "source_nodes")
                else []
            )

            logger.info(
                f"Query completed, answer generated "
                f"(length: {len(answer)} characters), "
                f"{len(nodes)} nodes retrieved"
            )

            return answer, nodes

        # Try to load existing index if not already loaded
        if not self.index and not self._index_loaded:
            self._load_existing_index()
        
        if not self.index:
            raise ValueError("Index not initialized. Please process a document first.")
        
        logger.info(f"Processing query: question='{question[:100]}...', similarity_top_k={similarity_top_k}, filters={filters}")

        qe = create_query_engine(
            index=self.index,
            llm=self.llm,
            similarity_top_k=similarity_top_k,
            filters=filters,
        )
        response = qe.query(question)

        answer = str(response.response) if hasattr(response, "response") else str(response)
        nodes = []
        if hasattr(response, "source_nodes") and response.source_nodes:
            nodes = response.source_nodes
        
        logger.info(f"Query completed, answer generated (length: {len(answer)} characters), {len(nodes)} nodes retrieved")
        
        return answer, nodes
    
    def is_initialized(self) -> bool:
        """Check if the service has been initialized with a document."""
        if not self.index and not self._index_loaded:
            try:
                self._load_existing_index()
            except Exception:
                pass
        return self.index is not None