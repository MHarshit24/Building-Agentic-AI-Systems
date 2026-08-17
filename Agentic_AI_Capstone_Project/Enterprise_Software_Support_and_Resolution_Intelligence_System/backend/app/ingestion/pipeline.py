"""
app/ingestion/pipeline.py

§8.3's idempotent re-ingestion algorithm, end to end. Dispatched as a
FastAPI BackgroundTask by routes_ingest.py's POST /ingest handler — the
request returns 202 immediately (§7's notify_human() dispatch pattern,
applied here), and this module does the actual work afterward, updating
the ingestion_jobs row as it goes so GET /ingest/{job_id} can report
progress.

Five steps below, numbered to match §8.3's own numbering, each in its own
function/block with a comment naming which step it implements. One
ordering note up front, not silently reordered: §8.3 lists "insert new
document_versions row" as step 4, after step 3's diff/insert — but step
3's new/unchanged asset rows need to stamp first_seen_version/
last_seen_version against the NEW version's primary key, which only
exists once that row is inserted. So the insert (and a flush to obtain
version_id) happens first, ahead of step 3, with a comment marking it as
"step 4, part 1" at the point it actually runs.

Import style note: extract_text/_tables/_images/_diagrams are imported as
MODULES (`from app.ingestion import extract_text`, etc.), not by pulling
individual names out of them. app.db.models.Chunk and
extract_text.Chunk are two different classes with the same name (a DB row
vs. an extraction-layer dataclass) — importing extract_text as a module
and always writing `extract_text.something` avoids that collision at the
source, the same way app.db.models.DiagramGraphRow was named to avoid
colliding with extract_diagrams.DiagramGraph.
"""

from __future__ import annotations

import logging
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.models import (
    Chunk,
    DiagramGraphRow,
    DocumentStatus,
    DocumentVersion,
    Image,
    IngestedAsset,
    IngestionJob,
    IngestionJobStatus,
    TableAsset,
)
from app.db.session import async_session_maker
from app.ingestion import extract_diagrams, extract_images, extract_tables, extract_text
from app.ingestion.dedup_engine import diff_assets, is_document_unchanged
from app.ingestion.embedding_client import embed_batch
from app.ingestion.extract_diagrams import parse_diagram
from app.ingestion.extract_images import caption_image
from app.ingestion.hashing import hash_bytes, hash_text
from app.llm.azure_client import get_llm_client
from app.logging.structured_logger import log_event
from app.observability import tracing

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[2]

_SLUG_RE = re.compile(r"[^a-z0-9]+")

_EMPTY_STATS = {
    "assets_new": 0,
    "assets_unchanged_skipped": 0,
    "assets_updated": 0,
    "assets_retired": 0,
}


def slugify_document_id(filename: str) -> str:
    """Derives a stable document_id from the uploaded filename's stem —
    see schemas/ingest.py for the full design rationale (system-derived,
    not caller-supplied). Lowercased, extension stripped, any run of
    non-alphanumeric characters collapsed to a single underscore,
    leading/trailing underscores trimmed."""
    stem = Path(filename).stem
    slug = _SLUG_RE.sub("_", stem.lower()).strip("_")
    return slug or "untitled_document"


@dataclass
class _CandidateAsset:
    """One flattened entry from any of the four extractors, keyed
    elsewhere by its own asset_hash — Step 2's "one flat set"."""

    asset_type: str  # "chunk" | "table" | "image" | "diagram"
    page_number: int
    section_header: str | None
    payload: object  # the original extract_text.Chunk / ExtractedTable / ExtractedImage / ExtractedDiagram


def _extract_all(file_bytes: bytes) -> tuple[list, list, list, list]:
    """Step 2 (§8.3): run all four extractors — free/local, no LLM calls
    yet. The extractors take a filesystem path, not bytes, so the upload
    is written to a temp file for the duration of extraction only."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        cm, span = tracing.traced_child_span("extract_text")
        chunks = extract_text.extract_and_chunk(tmp_path)
        tracing.end_child_span(cm, span, output={"chunk_count": len(chunks)})

        cm, span = tracing.traced_child_span("extract_tables")
        tables = extract_tables.extract_tables(tmp_path)
        tracing.end_child_span(cm, span, output={"table_count": len(tables)})

        cm, span = tracing.traced_child_span("extract_images")
        images = extract_images.extract_image_assets(tmp_path)
        tracing.end_child_span(cm, span, output={"image_count": len(images)})

        cm, span = tracing.traced_child_span("extract_diagrams")
        diagrams = extract_diagrams.extract_diagram_assets(tmp_path)
        tracing.end_child_span(cm, span, output={"diagram_count": len(diagrams)})

        return chunks, tables, images, diagrams
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _build_candidates(chunks: list, tables: list, images: list, diagrams: list) -> dict[str, _CandidateAsset]:
    """Step 2 (§8.3): "collect every resulting asset's asset_hash into
    one flat set". Three of the four extractors already compute their
    own asset_hash (ExtractedTable/ExtractedImage/ExtractedDiagram);
    extract_text.Chunk does not, so it's computed here with the same
    hash_text() used everywhere else in the ingestion layer, keeping the
    identity rule consistent (content-hash equality is the identity,
    per dedup_engine.py's own stated design)."""
    candidates: dict[str, _CandidateAsset] = {}
    for c in chunks:
        candidates[hash_text(c.text)] = _CandidateAsset("chunk", c.page_number, c.section_header, c)
    for t in tables:
        candidates[t.asset_hash] = _CandidateAsset("table", t.page_number, t.section_header, t)
    for img in images:
        candidates[img.asset_hash] = _CandidateAsset("image", img.page_number, img.section_header, img)
    for d in diagrams:
        candidates[d.asset_hash] = _CandidateAsset("diagram", d.page_number, d.section_header, d)
    return candidates


async def _get_active_version(db, document_id: str) -> DocumentVersion | None:
    result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.status == DocumentStatus.active,
        )
    )
    return result.scalar_one_or_none()


async def _get_active_assets(db, document_id: str) -> list[IngestedAsset]:
    """Step 3 (§8.3): "the previous version's ingested_assets". Filtering
    by is_active (rather than matching a specific old version_id) is what
    correctly represents "current state" across more than one version
    hop: an asset retired in an earlier transition already has
    is_active=False and is correctly excluded from this baseline without
    needing to track exactly which version retired it."""
    result = await db.execute(
        select(IngestedAsset).where(
            IngestedAsset.document_id == document_id,
            IngestedAsset.is_active.is_(True),
        )
    )
    return list(result.scalars().all())


def _process_unchanged(previous_assets: list[IngestedAsset], unchanged_hashes: frozenset[str], new_version_id: int) -> None:
    """Step 3 (§8.3), unchanged bucket: no re-embed/recaption/reparse —
    just bump last_seen_version so this asset is recognized as still
    present in the new version. Objects are already session-attached
    (loaded via _get_active_assets), so mutating them is enough; no
    explicit db.add()/flush needed here — db.commit() picks up the change."""
    by_hash = {a.asset_hash: a for a in previous_assets}
    for h in unchanged_hashes:
        by_hash[h].last_seen_version = new_version_id


def _process_retired(previous_assets: list[IngestedAsset], retired_hashes: frozenset[str]) -> None:
    """Step 3 (§8.3), retired bucket: soft-retire only — never a hard delete."""
    by_hash = {a.asset_hash: a for a in previous_assets}
    for h in retired_hashes:
        by_hash[h].is_active = False


async def _insert_ingested_asset(
    db, document_id: str, asset_type: str, asset_hash: str, candidate: _CandidateAsset, version_id: int
) -> IngestedAsset:
    """(a) from the task spec: the IngestedAsset row is inserted first,
    to get its asset_id before the type-specific row can reference it."""
    asset = IngestedAsset(
        document_id=document_id,
        asset_type=asset_type,
        asset_hash=asset_hash,
        first_seen_version=version_id,
        last_seen_version=version_id,
        is_active=True,
        page_number=candidate.page_number,
        section_header=candidate.section_header,
    )
    db.add(asset)
    await db.flush()  # need asset.asset_id below
    return asset


async def _insert_new_chunks(
    db, document_id: str, version_id: int, items: list[tuple[str, _CandidateAsset]],
    embeddings: list[list[float]], source_document: str | None, product_version: str | None, category: str | None,
    embedding_namespace: str | None,
) -> None:
    for (asset_hash, candidate), embedding in zip(items, embeddings):
        chunk = candidate.payload
        asset = await _insert_ingested_asset(db, document_id, "chunk", asset_hash, candidate, version_id)
        row = Chunk(
            asset_id=asset.asset_id,
            text=chunk.text,  # tsv is DB-generated STORED — never set explicitly (models.py's own note)
            embedding=embedding,
            embedding_namespace=embedding_namespace,
            source_document=source_document,
            section_header=candidate.section_header,
            page_number=candidate.page_number,
            product_version=product_version,
            category=category,
        )
        db.add(row)
        await db.flush()  # (b) insert the type-specific row
        asset.embedding_id = str(row.chunk_id)  # (c) write the PK back


async def _insert_new_tables(
    db, document_id: str, version_id: int, items: list[tuple[str, _CandidateAsset]],
    embeddings: list[list[float]], source_document: str | None, product_version: str | None, category: str | None,
    embedding_namespace: str | None,
) -> None:
    for (asset_hash, candidate), embedding in zip(items, embeddings):
        table = candidate.payload
        asset = await _insert_ingested_asset(db, document_id, "table", asset_hash, candidate, version_id)
        row = TableAsset(
            asset_id=asset.asset_id,
            raw_json=table.raw_json,
            text_serialization=table.text_serialization,
            embedding=embedding,
            embedding_namespace=embedding_namespace,
            source_document=source_document,
            section_header=candidate.section_header,
            page_number=candidate.page_number,
            product_version=product_version,
            category=category,
            possibly_truncated=table.possibly_truncated,
            has_unresolved_symbols=table.has_unresolved_symbols,
        )
        db.add(row)
        await db.flush()
        asset.embedding_id = str(row.table_id)


def _read_image_bytes(blob_ref: str) -> bytes:
    """ExtractedImage carries blob_ref (a saved file path), not bytes —
    unlike diagrams, images are persisted to disk by extract_images.py.
    Read back from there for captioning."""
    return (_BACKEND_DIR / blob_ref).read_bytes()


async def _insert_new_images(
    db, document_id: str, version_id: int, items: list[tuple[str, _CandidateAsset]],
    captions: list[str], embeddings: list[list[float]], source_document: str | None, category: str | None,
    embedding_namespace: str | None,
) -> None:
    for (asset_hash, candidate), caption, embedding in zip(items, captions, embeddings):
        image = candidate.payload
        asset = await _insert_ingested_asset(db, document_id, "image", asset_hash, candidate, version_id)
        row = Image(
            asset_id=asset.asset_id,
            blob_ref=image.blob_ref,
            caption=caption,
            embedding=embedding,
            embedding_namespace=embedding_namespace,
            source_document=source_document,
            page_number=candidate.page_number,
            category=category,
        )
        db.add(row)
        await db.flush()
        asset.embedding_id = str(row.image_id)


async def _insert_new_diagrams(
    db, document_id: str, version_id: int, items: list[tuple[str, _CandidateAsset]],
    parsed_results: list, embeddings: list[list[float]], source_document: str | None, category: str | None,
    embedding_namespace: str | None,
) -> None:
    for (asset_hash, candidate), parsed, embedding in zip(items, parsed_results, embeddings):
        asset = await _insert_ingested_asset(db, document_id, "diagram", asset_hash, candidate, version_id)
        row = DiagramGraphRow(
            asset_id=asset.asset_id,
            graph_json=parsed.graph_json,
            caption=parsed.caption,
            embedding=embedding,
            embedding_namespace=embedding_namespace,
            source_document=source_document,
            page_number=candidate.page_number,
            category=category,
            diagram_type=parsed.diagram_type,
        )
        db.add(row)
        await db.flush()
        asset.embedding_id = str(row.diagram_id)


async def _process_new(
    db,
    document_id: str,
    version_id: int,
    candidates: dict[str, _CandidateAsset],
    new_hashes: frozenset[str],
    source_document: str | None,
    product_version: str | None,
    category: str | None,
) -> None:
    """Step 3 (§8.3), new bucket — the ONLY place costed LLM/embedding
    calls happen, and only for these hashes, never for unchanged assets.
    All costed calls are made up front, batched by type where the LLM
    abstraction supports batching (embeddings — §8.4's own stated
    optimization), before any DB write, so the insert loop is pure
    bookkeeping and the exact call count is easy to reason about."""
    new_chunks = [(h, candidates[h]) for h in new_hashes if candidates[h].asset_type == "chunk"]
    new_tables = [(h, candidates[h]) for h in new_hashes if candidates[h].asset_type == "table"]
    new_images = [(h, candidates[h]) for h in new_hashes if candidates[h].asset_type == "image"]
    new_diagrams = [(h, candidates[h]) for h in new_hashes if candidates[h].asset_type == "diagram"]

    # Resolved ONCE for this whole run (not per asset type) so every row this
    # run inserts is stamped with the SAME namespace as the embed_batch()
    # calls below actually used — see Chunk.embedding_namespace's own
    # comment for the real bug this closes.
    embedding_namespace = get_llm_client().embedding_namespace

    chunk_embeddings = []
    if new_chunks:
        cm, span = tracing.traced_child_span("embed_batch", input={"asset_type": "chunk", "count": len(new_chunks)})
        chunk_embeddings = await embed_batch([c.payload.text for _, c in new_chunks])
        tracing.end_child_span(cm, span, output={"embedded_count": len(chunk_embeddings)})

    table_embeddings = []
    if new_tables:
        cm, span = tracing.traced_child_span("embed_batch", input={"asset_type": "table", "count": len(new_tables)})
        table_embeddings = await embed_batch([t.payload.text_serialization for _, t in new_tables])
        tracing.end_child_span(cm, span, output={"embedded_count": len(table_embeddings)})

    # No batch API for vision captioning (generate_vision is one image
    # per call) — sequential, one real vision call per new image, each
    # its own caption_image span (beyond §15's literal 6 ingestion span
    # names — the real costed vision call, traced per the "trace
    # everything" coverage principle, see tracing.py's module docstring).
    image_captions = []
    for _, img in new_images:
        cm, span = tracing.traced_child_span("caption_image", input={"blob_ref": img.payload.blob_ref})
        caption = await caption_image(_read_image_bytes(img.payload.blob_ref))
        tracing.end_child_span(cm, span, output={"caption": caption})
        image_captions.append(caption)

    image_embeddings = []
    if image_captions:
        cm, span = tracing.traced_child_span("embed_batch", input={"asset_type": "image", "count": len(image_captions)})
        image_embeddings = await embed_batch(image_captions)
        tracing.end_child_span(cm, span, output={"embedded_count": len(image_embeddings)})

    # Same shape for diagrams: one structured vision call per new diagram,
    # each its own parse_diagram span (same "beyond §15's literal list" reasoning).
    diagram_results = []
    for _, d in new_diagrams:
        cm, span = tracing.traced_child_span(
            "parse_diagram", input={"page_number": d.payload.page_number, "section_header": d.payload.section_header}
        )
        parsed = await parse_diagram(d.payload.image_bytes)
        tracing.end_child_span(
            cm, span,
            output={
                "diagram_type": parsed.diagram_type,
                "caption": parsed.caption,
                "node_count": len(parsed.nodes),
                "edge_count": len(parsed.edges),
            },
        )
        diagram_results.append(parsed)

    diagram_embeddings = []
    if diagram_results:
        cm, span = tracing.traced_child_span(
            "embed_batch", input={"asset_type": "diagram", "count": len(diagram_results)}
        )
        diagram_embeddings = await embed_batch([r.caption for r in diagram_results])
        tracing.end_child_span(cm, span, output={"embedded_count": len(diagram_embeddings)})

    await _insert_new_chunks(db, document_id, version_id, new_chunks, chunk_embeddings, source_document, product_version, category, embedding_namespace)
    await _insert_new_tables(db, document_id, version_id, new_tables, table_embeddings, source_document, product_version, category, embedding_namespace)
    await _insert_new_images(db, document_id, version_id, new_images, image_captions, image_embeddings, source_document, category, embedding_namespace)
    await _insert_new_diagrams(db, document_id, version_id, new_diagrams, diagram_results, diagram_embeddings, source_document, category, embedding_namespace)


async def _process_document(
    document_id: str,
    file_bytes: bytes,
    doc_title: str | None,
    product_version: str | None,
    category: str | None,
    trace_id: str,
) -> dict:
    source_document = doc_title  # propagated onto every asset row this run touches
    # Captured here (not just built at each return point) so the finally
    # block below can attach real output= to the root span regardless of
    # which return path was taken — previously this span never set any
    # output at all (confirmed live: Langfuse's UI showed "Output:
    # undefined" for every ingestion_job trace), even though this exact
    # stats dict was already sitting in scope one line before the span
    # closed.
    stats: dict = dict(_EMPTY_STATS)

    async with async_session_maker() as db:
        # Root span for this ingestion trace (§15's "ingestion_job" trace
        # name) — every span below (extract_*, dedup_check, embed_batch,
        # caption_image, parse_diagram) nests under this one via OTel
        # context propagation, the same role classify_node's span plays
        # for a chat_request trace.
        cm, span = tracing.traced_root_span(
            "ingestion_job",
            trace_id,
            input={"document_id": document_id, "doc_title": doc_title},
            metadata={"document_id": document_id},
        )
        try:
            # ---- Step 1 (§8.3): hash + no-op early exit ----
            # The single most important cost-saving path in the whole
            # pipeline — get this right before anything else runs.
            content_hash = hash_bytes(file_bytes)
            active_version = await _get_active_version(db, document_id)
            if is_document_unchanged(content_hash, active_version.content_hash if active_version else None):
                return dict(_EMPTY_STATS)

            # ---- Step 2 (§8.3): extract everything — free/local, no LLM calls yet ----
            chunks, tables, images, diagrams = _extract_all(file_bytes)
            candidates = _build_candidates(chunks, tables, images, diagrams)

            # ---- Step 4, part 1 (§8.3) — see module docstring for why this
            # runs ahead of step 3 rather than after it ----
            new_version = DocumentVersion(
                document_id=document_id,
                content_hash=content_hash,
                status=DocumentStatus.active,
                doc_title=doc_title,
                product_version=product_version,
                category=category,
            )
            db.add(new_version)
            await db.flush()  # need new_version.version_id below

            if active_version is not None:
                active_version.status = DocumentStatus.superseded

            # ---- Step 3 (§8.3): diff against the previous version's ingested_assets ----
            previous_assets = await _get_active_assets(db, document_id)
            previous_hashes = {a.asset_hash for a in previous_assets}
            dedup_cm, dedup_span = tracing.traced_child_span(
                "dedup_check",
                input={"previous_count": len(previous_hashes), "candidate_count": len(candidates)},
            )
            diff = diff_assets(previous_hashes, set(candidates.keys()))
            dedup_output = {
                "new": len(diff.new_hashes),
                "unchanged": len(diff.unchanged_hashes),
                "retired": len(diff.retired_hashes),
            }
            tracing.end_child_span(dedup_cm, dedup_span, output=dedup_output)

            _process_unchanged(previous_assets, diff.unchanged_hashes, new_version.version_id)
            _process_retired(previous_assets, diff.retired_hashes)
            await _process_new(
                db, document_id, new_version.version_id, candidates, diff.new_hashes,
                source_document, product_version, category,
            )

            await db.commit()

            # ---- Step 5 (§8.3): stats ----
            # assets_updated is always 0 — a deliberate decision, not an
            # oversight. diff_assets() is purely hash-based (dedup_engine.py's
            # own stated design: "content-hash equality IS the identity for
            # dedup purposes"), so it has no way to know a retired hash and a
            # new hash are "the same conceptual asset, changed" versus two
            # unrelated assets. Every content change is fully and correctly
            # represented as one retirement + one new insertion already;
            # inventing a fourth "updated" bucket would need a same-slot
            # heuristic (e.g. matching by page_number/section_header) that's
            # fragile exactly when it matters most — inserting or deleting a
            # paragraph shifts every later chunk's page/section pairing
            # without any of them actually being "updates".
            stats = {
                "assets_new": len(diff.new_hashes),
                "assets_unchanged_skipped": len(diff.unchanged_hashes),
                "assets_updated": 0,
                "assets_retired": len(diff.retired_hashes),
            }
            return stats
        finally:
            tracing.end_child_span(cm, span, output=stats)


async def _update_job(job_id: str, **fields) -> None:
    """Own short-lived session, separate from _process_document's — job
    bookkeeping must persist independently of whether the main
    ingestion transaction commits or rolls back."""
    async with async_session_maker() as db:
        result = await db.execute(select(IngestionJob).where(IngestionJob.job_id == job_id))
        job = result.scalar_one()
        for key, value in fields.items():
            setattr(job, key, value)
        await db.commit()


async def run_ingestion(
    job_id: str,
    document_id: str,
    file_bytes: bytes,
    doc_title: str | None,
    product_version: str | None,
    category: str | None,
) -> None:
    """
    Top-level entry point, dispatched via FastAPI BackgroundTasks by
    routes_ingest.py — the HTTP response has already been sent by the
    time this runs (§7's notify_human() dispatch pattern, applied here).

    Wrapped in a top-level try/except so the job always ends at
    completed or failed, never stuck at pending/processing forever on an
    unhandled error.
    """
    trace_id = tracing.safe_create_trace_id()
    await _update_job(job_id, status=IngestionJobStatus.processing)
    try:
        stats = await _process_document(document_id, file_bytes, doc_title, product_version, category, trace_id)
    except Exception as exc:
        log_event(
            logger, "ERROR", "ingestion_job_failed",
            job_id=job_id, document_id=document_id, error_type=type(exc).__name__,
        )
        await _update_job(job_id, status=IngestionJobStatus.failed, completed_at=datetime.now(timezone.utc))
        raise
    else:
        log_event(logger, "INFO", "ingestion_job_completed", job_id=job_id, document_id=document_id, **stats)
        await _update_job(
            job_id,
            status=IngestionJobStatus.completed,
            stats_json=stats,
            completed_at=datetime.now(timezone.utc),
        )
    finally:
        tracing.safe_flush()  # §15: "Flush | langfuse.flush() at request teardown" — ingestion's equivalent
