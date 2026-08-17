from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence
from urllib.parse import quote_plus

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.postgres import PGVectorStore

import time


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionResult:
    source_files: List[str]
    total_documents: int
    total_chunks: int
    table_name: str


class IngestionPipeline:
    """Ingests investment advisory documents into Postgres/pgvector."""

    def __init__(
        self,
        *,
        table_name: str | None = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        embed_dim: int = 1536,
    ) -> None:
        self.table_name = table_name or os.getenv("DB_TABLE_NAME", "investment_advisor_docs")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embed_dim = embed_dim

    def ingest_paths(self, paths: Sequence[str]) -> IngestionResult:
        logger.info("pipeline.start paths=%s table=%s", list(paths), self.table_name)
        files = self._expand_files(paths)
        documents = self._load_files(files)
        nodes = self._chunk(documents)
        t0 = time.perf_counter()
        self._persist_nodes(nodes)
        logger.info("pipeline.persist_nodes done ms=%.1f table=%s chunks=%d", (time.perf_counter() - t0) * 1000, self.table_name, len(nodes))

        logger.info(
            "pipeline.complete table=%s files=%d documents=%d chunks=%d",
            self.table_name,
            len(files),
            len(documents),
            len(nodes),
        )
        return IngestionResult(
            source_files=[str(p) for p in files],
            total_documents=len(documents),
            total_chunks=len(nodes),
            table_name=self.table_name,
        )

    def _expand_files(self, paths: Sequence[str]) -> List[Path]:
        out: List[Path] = []
        for raw in paths:
            p = Path(raw)
            if p.is_dir():
                for child in sorted(p.rglob("*")):
                    if child.is_file() and child.suffix.lower() in {".txt", ".pdf"}:
                        out.append(child)
            else:
                out.append(p)

        # de-dupe while preserving order
        seen = set()
        uniq: List[Path] = []
        for p in out:
            rp = str(p.resolve())
            if rp not in seen:
                seen.add(rp)
                uniq.append(p)
        return uniq

    def _load_files(self, files: Sequence[Path]) -> List[Document]:
        docs: List[Document] = []
        for path in files:
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            suffix = path.suffix.lower()
            if suffix == ".txt":
                text = path.read_text(encoding="utf-8")
            elif suffix == ".pdf":
                # Keep dependency light: use pypdf directly
                from pypdf import PdfReader

                reader = PdfReader(str(path))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            else:
                raise ValueError(f"Unsupported file type: {path}")

            logger.info("pipeline.loaded file=%s type=%s chars=%d", path.name, suffix, len(text or ""))
            docs.append(
                Document(
                    text=text,
                    metadata={
                        "source_path": str(path),
                        "filename": path.name,
                    },
                )
            )
        return docs

    def _chunk(self, documents: Sequence[Document]):
        splitter = SentenceSplitter(chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
        t0 = time.perf_counter()
        nodes = splitter.get_nodes_from_documents(list(documents))
        logger.info(
            "pipeline.chunk done ms=%.1f documents=%d chunk_size=%d chunk_overlap=%d",
            (time.perf_counter() - t0) * 1000,
            len(documents),
            self.chunk_size,
            self.chunk_overlap,
        )
        logger.info("pipeline.chunked nodes=%d", len(nodes))
        return nodes

    def _persist_nodes(self, nodes) -> None:
        vector_store = PGVectorStore.from_params(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "rag_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=quote_plus(os.getenv("DB_PASSWORD")),
            table_name=self.table_name,
            embed_dim=self.embed_dim,
        )

        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # This will embed and persist
        VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            show_progress=True,
        )