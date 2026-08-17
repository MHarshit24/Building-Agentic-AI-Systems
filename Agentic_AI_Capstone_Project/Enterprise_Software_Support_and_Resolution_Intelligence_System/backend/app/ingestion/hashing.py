"""
app/ingestion/hashing.py

Pure hashing utilities for §8.3's idempotent re-ingestion algorithm.
No DB, no I/O beyond what's passed in — deliberately dependency-free so
it's trivially unit-testable (§25, "hashing.py/dedup_engine.py
unit-tested first").
"""

import hashlib


def hash_bytes(data: bytes) -> str:
    """
    SHA256 hex digest of raw bytes. Used for both:
      - document_versions.content_hash (whole raw file, §8.3 step 1)
      - ingested_assets.asset_hash (extracted content of one asset —
        one chunk's text, one table's serialization, one image's bytes,
        one diagram's graph_json — encoded to bytes by the caller)
    """
    return hashlib.sha256(data).hexdigest()


def hash_text(text: str) -> str:
    """Convenience wrapper — encodes to UTF-8 then hashes. Most asset
    content (chunk text, table serialization, diagram JSON) is str, not
    raw bytes, so this is the one most callers will actually reach for."""
    return hash_bytes(text.encode("utf-8"))