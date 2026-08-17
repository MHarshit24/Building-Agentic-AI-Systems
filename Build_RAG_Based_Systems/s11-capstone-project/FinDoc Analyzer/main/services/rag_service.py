"""
FinDoc Analyzer — Core RAG Service
Dual .env loader: root .env (secrets) + project .env (config).
rag_service.py lives at main/services/rag_service.py
  parents[5] = Building_Agentic_AI_Systems  -> root .env
  parents[2] = FinDoc Analyzer              -> project .env
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from urllib.parse import quote_plus
from dotenv import load_dotenv

from llama_index.core import (
    Settings,
    VectorStoreIndex,
    StorageContext,
    Document,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.ingestion import IngestionPipeline
from llama_index.vector_stores.postgres import PGVectorStore

logger = logging.getLogger(__name__)

# Global singletons
_llm                                = None
_embed_model                        = None
_index: Optional[VectorStoreIndex]  = None
_query_engine_cache: Dict[int, Any] = {}
_llm_provider: Optional[str]        = None


def _load_env():
    """
    Dual .env loader.
    rag_service.py: main/services/rag_service.py
      parents[5] = Building_Agentic_AI_Systems  -> root .env (secrets)
      parents[2] = FinDoc Analyzer              -> project .env (config)
    """
    if "pytest" in sys.modules:
        return

    base_dir = Path(__file__).resolve().parents[5]
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

    proj_dir = Path(__file__).resolve().parents[2]
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


def _build_llm(provider: str):
    """Build LLM instance for the selected provider."""
    if provider == "anthropic":
        try:
            from llama_index.llms.anthropic import Anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
            logger.info(f"Using Anthropic Claude: {model}")
            return Anthropic(model=model, api_key=api_key)
        except ImportError:
            raise ImportError("Run: pip install llama-index-llms-anthropic")

    elif provider == "openai":
        try:
            from llama_index.llms.openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            logger.info(f"Using OpenAI: {model}")
            return OpenAI(model=model, api_key=api_key)
        except ImportError:
            raise ImportError("Run: pip install llama-index-llms-openai")

    else:  # azure (default)
        from llama_index.llms.azure_openai import AzureOpenAI
        llm_deployment = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")
        if not llm_deployment:
            raise ValueError("AZURE_OPENAI_LLM_DEPLOYMENT not set")
        logger.info(f"Using Azure OpenAI LLM: {llm_deployment}")
        return AzureOpenAI(
            model=os.getenv("AZURE_OPENAI_LLM_MODEL", "gpt-4o-mini"),
            deployment_name=llm_deployment,
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        )


def _build_embed_model(provider: str):
    """
    Build embedding model.
    Anthropic has no embedding API — falls back to Azure or OpenAI embeddings.
    """
    embed_provider = os.getenv(
        "EMBEDDING_PROVIDER",
        provider if provider != "anthropic" else "openai"
    )

    if embed_provider == "openai":
        try:
            from llama_index.embeddings.openai import OpenAIEmbedding
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY required for OpenAI embeddings")
            model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            logger.info(f"Using OpenAI Embedding: {model}")
            return OpenAIEmbedding(model=model, api_key=api_key)
        except ImportError:
            raise ImportError("Run: pip install llama-index-embeddings-openai")

    else:  # azure
        from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
        emb_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        if not emb_deployment:
            raise ValueError("AZURE_OPENAI_EMBEDDING_DEPLOYMENT not set")
        logger.info(f"Using Azure OpenAI Embedding: {emb_deployment}")
        return AzureOpenAIEmbedding(
            model=os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            deployment_name=emb_deployment,
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        )


def _get_vector_store() -> PGVectorStore:
    """Create PGVectorStore — quote_plus on password."""
    password     = os.getenv("DB_PASSWORD", "")
    password_enc = quote_plus(password)
    return PGVectorStore.from_params(
        database=os.getenv("DB_NAME",       "findoc_db"),
        host=os.getenv("DB_HOST",           "localhost"),
        password=password_enc,
        port=int(os.getenv("DB_PORT",       "5432")),
        user=os.getenv("DB_USER",           "postgres"),
        table_name=os.getenv("DB_TABLE_NAME", "findoc_embeddings"),
        embed_dim=1536,
    )


def _load_or_create_index() -> VectorStoreIndex:
    """Load existing index from PostgreSQL or create a new empty one."""
    logger.info("Loading or creating vector index from PostgreSQL...")
    vector_store    = _get_vector_store()
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    try:
        index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            embed_model=_embed_model,
        )
        logger.info("Loaded existing index from PostgreSQL")
        return index
    except Exception as e:
        logger.info(f"No existing index ({e}). Creating new empty index...")
        index = VectorStoreIndex(
            nodes=[],
            storage_context=storage_context,
            embed_model=_embed_model,
        )
        logger.info("Created new empty index")
        return index


def initialize_services():
    """
    Initialize LLM, embedding model, and vector index.
    Called once at app startup from app.py lifespan.
    """
    global _llm, _embed_model, _index, _query_engine_cache, _llm_provider

    if _index is not None:
        logger.info("Services already initialized — reusing existing instances")
        return

    _load_env()

    _llm_provider = os.getenv("LLM_PROVIDER", "azure").lower()
    logger.info(f"Initializing FinDoc services | LLM provider: {_llm_provider}")

    _llm         = _build_llm(_llm_provider)
    _embed_model = _build_embed_model(_llm_provider)

    Settings.llm         = _llm
    Settings.embed_model = _embed_model

    _index              = _load_or_create_index()
    _query_engine_cache = {}

    logger.info(f"RAG services initialized | provider={_llm_provider}")


# ── Public accessors ──────────────────────────────────────────────

def get_llm():
    if _llm is None:
        initialize_services()
    return _llm


def get_embed_model():
    if _embed_model is None:
        initialize_services()
    return _embed_model


def get_index() -> VectorStoreIndex:
    if _index is None:
        initialize_services()
    return _index


def get_llm_provider() -> str:
    if _llm_provider is None:
        return os.getenv("LLM_PROVIDER", "azure").lower()
    return _llm_provider


def get_query_engine(similarity_top_k: int = 4):
    """Get or create a cached query engine."""
    if _index is None:
        initialize_services()
    if similarity_top_k in _query_engine_cache:
        return _query_engine_cache[similarity_top_k]
    engine = _index.as_query_engine(llm=_llm, similarity_top_k=similarity_top_k)
    _query_engine_cache[similarity_top_k] = engine
    logger.debug(f"Cached query engine for top_k={similarity_top_k}")
    return engine


def ingest_documents(
    documents: List[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> Dict:
    """
    Process documents through ingestion pipeline and store in PGVector.
    Returns counts of documents indexed and chunks created.
    """
    global _index, _query_engine_cache

    if _index is None:
        initialize_services()

    # ── Deduplication check ───────────────────────────────────────
    # Dedup key is (source_file, content_type) so that chart_analysis documents
    # from the multimodal pipeline can coexist in the vector store alongside the
    # text chunks from the same PDF without being incorrectly skipped.
    # content_type defaults to "text" for regular documents (no content_type metadata).
    import psycopg2
    from urllib.parse import quote_plus as qp
    already_indexed = set()
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "findoc_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT
                    metadata_->>'source_file',
                    COALESCE(metadata_->>'content_type', 'text')
                FROM data_findoc_embeddings
                WHERE metadata_->>'source_file' IS NOT NULL
            """)
            already_indexed = {(row[0], row[1]) for row in cur.fetchall()}
        conn.close()
    except Exception as e:
        logger.warning(f"Dedup check failed (proceeding with ingest): {e}")

    new_documents = []
    skipped = []
    for doc in documents:
        source_file  = doc.metadata.get("source_file", "")
        content_type = doc.metadata.get("content_type", "text")
        if source_file and (source_file, content_type) in already_indexed:
            skipped.append(source_file)
        else:
            new_documents.append(doc)

    if skipped:
        logger.info(f"Skipping {len(skipped)} already-indexed document(s): {set(skipped)}")

    if not new_documents:
        logger.info("All documents already indexed — nothing to do")
        return {"documents_indexed": 0, "chunks_created": 0}

    logger.info(f"Running ingestion pipeline on {len(new_documents)} new document(s)...")
    text_splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    pipeline      = IngestionPipeline(transformations=[text_splitter])
    nodes         = pipeline.run(documents=new_documents)
    logger.info(f"Split into {len(nodes)} chunks")

    for i, doc in enumerate(new_documents, 1):
        try:
            _index.insert(doc)
            logger.info(f"  Indexed document {i}/{len(new_documents)}")
        except Exception as e:
            logger.error(f"Error indexing document {i}: {e}")
            raise

    _query_engine_cache.clear()
    logger.info("Documents indexed. Query engine cache cleared.")
    return {"documents_indexed": len(new_documents), "chunks_created": len(nodes)}