"""
app/ingestion/extract_images.py

Image extraction + captioning, per §8.2's `images` row: "PyMuPDF extraction
-> vision-model (Azure GPT-5-mini) caption" — "caption is what's embedded,
not pixels".

Two separate functions, deliberately not one combined pass (§8.3): image
captioning is a real, costed vision-API call, unlike text/table extraction
which are free/local. asset_hash MUST come from the raw image bytes, not
the caption, and MUST be computed before any captioning happens — if it
were computed from the caption text instead, an unchanged image could
still hash differently on every re-ingestion run just because the vision
model's output isn't perfectly deterministic, silently defeating §8.3's
whole dedup point (never re-caption an asset that hasn't changed) and
re-triggering a costly recaption every run, forever.

  extract_image_assets(pdf_path)  — pure PyMuPDF extraction, local, free.
  caption_image(image_bytes, ...) — the costed vision call, called later
                                    by pipeline.py, only for assets
                                    dedup_engine.diff_assets() has already
                                    flagged as new/changed.
"""

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from app.ingestion.extract_text import split_into_sections
from app.ingestion.extract_tables import _section_header_for_page
from app.ingestion.hashing import hash_bytes
from app.llm.azure_client import get_llm_client

# ASSUMPTION (not specified in the blueprint — flagging explicitly, per the
# task): images are persisted to disk, not just carried as in-memory bytes,
# at backend/data/ingested_images/{asset_hash}.{ext}. Content-addressed by
# the image's own asset_hash (not a counter or the source PDF's name) so
# an identical image reused across documents/versions naturally collapses
# onto the same file on disk too, mirroring the DB-level dedup rather than
# fighting it. blob_ref is stored as a path *relative to backend/* (e.g.
# "data/ingested_images/<hash>.png"), not absolute, so it stays valid
# across a dev machine, Docker container, or CI runner.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_IMAGE_DIR = _BACKEND_DIR / "data" / "ingested_images"


@dataclass
class ExtractedImage:
    blob_ref: str  # path to the saved image file, relative to backend/
    caption: str | None  # None until caption_image() is called — never set here
    page_number: int
    section_header: str | None
    asset_hash: str  # hash_bytes(raw image bytes) — computed before any captioning


def extract_image_assets(pdf_path: str) -> list[ExtractedImage]:
    """
    Pure extraction: walks every page's embedded raster images via
    PyMuPDF's page.get_images(), saves each to disk, and returns one
    ExtractedImage per distinct image. No vision/LLM call in this
    function at all — caption is always None here; that's
    caption_image()'s job, invoked separately and selectively.

    section_header reuses the exact page-range attribution approach
    extract_tables.py already established
    (extract_tables._section_header_for_page against
    extract_text.split_into_sections()'s output) rather than
    reimplementing a third copy of the same lookup — same reasoning
    extract_tables.py itself gave for reusing split_into_sections()
    instead of extract_text.py's per-line header predicates directly.

    Dedup note: the same embedded image object (e.g. a repeated
    logo/banner) can legitimately appear via get_images() on more than
    one page — full=True returns every image *reference* on a page, and
    a reused image keeps the same xref everywhere it's placed. Extracted
    once per xref (first page it appears on wins), not once per
    occurrence — every extra occurrence would otherwise become a second
    ExtractedImage with an identical asset_hash, and since captioning is
    costed, that's a wasted (future) API call for an asset that's
    already covered, not just redundant bookkeeping.
    """
    doc = fitz.open(pdf_path)
    try:
        sections = split_into_sections(doc)
        _IMAGE_DIR.mkdir(parents=True, exist_ok=True)

        seen_xrefs: set[int] = set()
        results: list[ExtractedImage] = []

        for page_index, page in enumerate(doc, start=1):
            for image_info in page.get_images(full=True):
                xref = image_info[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                extracted = doc.extract_image(xref)
                image_bytes = extracted["image"]
                ext = extracted["ext"]
                asset_hash = hash_bytes(image_bytes)

                blob_path = _IMAGE_DIR / f"{asset_hash}.{ext}"
                if not blob_path.exists():
                    blob_path.write_bytes(image_bytes)

                results.append(
                    ExtractedImage(
                        blob_ref=str(blob_path.relative_to(_BACKEND_DIR)).replace("\\", "/"),
                        caption=None,
                        page_number=page_index,
                        section_header=_section_header_for_page(sections, page_index),
                        asset_hash=asset_hash,
                    )
                )

        return results
    finally:
        doc.close()


_DEFAULT_CAPTION_PROMPT = (
    "Describe this image from a software support/technical document in "
    "1-3 concise sentences, focused on what a support agent would need to "
    "know (e.g. what UI element, error message, diagram, or screenshot "
    "content it shows). This caption is what gets embedded and searched "
    "later, not the pixels — describe content, not visual styling."
)


async def caption_image(image_bytes: bytes, prompt: str | None = None) -> str:
    """
    The costed step, kept separate from extract_image_assets() on purpose
    (§8.3): calls the configured vision-capable LLM client
    (get_llm_client() — real Azure client, or MockLLMClient under
    LLM_PROVIDER=mock, no network call) to caption one image. pipeline.py
    should call this only for assets dedup_engine.diff_assets() has
    determined are new_hashes or otherwise changed — never for every
    image on every re-ingestion run, since an unchanged image's
    asset_hash (computed in extract_image_assets(), from the raw bytes)
    already tells the caller nothing needs to be redone here.
    """
    client = get_llm_client()
    return await client.generate_vision(image_bytes, prompt or _DEFAULT_CAPTION_PROMPT)
