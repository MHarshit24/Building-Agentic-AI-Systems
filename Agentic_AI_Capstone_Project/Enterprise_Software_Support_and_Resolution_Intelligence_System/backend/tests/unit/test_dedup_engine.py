"""
tests/unit/test_dedup_engine.py

L1 pure-logic tests (§19) — no LLM, no DB, no I/O. Covers §8.3's
idempotent re-ingestion algorithm: hashing.py + dedup_engine.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.ingestion.hashing import hash_bytes, hash_text
from app.ingestion.dedup_engine import is_document_unchanged, diff_assets


# ── hashing.py ────────────────────────────────────────────────────

def test_hash_bytes_is_deterministic():
    assert hash_bytes(b"hello world") == hash_bytes(b"hello world")

def test_hash_bytes_differs_on_different_input():
    assert hash_bytes(b"hello world") != hash_bytes(b"hello world!")

def test_hash_bytes_is_sha256_hex():
    # SHA256 hex digest is always exactly 64 hex characters
    digest = hash_bytes(b"anything")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)

def test_hash_text_matches_manual_utf8_encoding():
    assert hash_text("café") == hash_bytes("café".encode("utf-8"))


# ── is_document_unchanged (§8.3 step 1) ──────────────────────────

def test_document_unchanged_when_hash_matches_active_version():
    assert is_document_unchanged("abc123", "abc123") is True

def test_document_changed_when_hash_differs_from_active_version():
    assert is_document_unchanged("abc123", "def456") is False

def test_document_never_unchanged_on_first_ingest():
    # No active version exists yet -> nothing to be "unchanged" from
    assert is_document_unchanged("abc123", None) is False


# ── diff_assets (§8.3 step 3) ─────────────────────────────────────

def test_diff_assets_all_new_on_first_ingest():
    result = diff_assets(previous_asset_hashes=[], new_asset_hashes=["h1", "h2", "h3"])
    assert result.new_hashes == frozenset({"h1", "h2", "h3"})
    assert result.unchanged_hashes == frozenset()
    assert result.retired_hashes == frozenset()

def test_diff_assets_all_unchanged_on_identical_reingest():
    hashes = ["h1", "h2", "h3"]
    result = diff_assets(previous_asset_hashes=hashes, new_asset_hashes=hashes)
    assert result.new_hashes == frozenset()
    assert result.unchanged_hashes == frozenset({"h1", "h2", "h3"})
    assert result.retired_hashes == frozenset()

def test_diff_assets_editing_one_chunk_only_touches_that_chunk():
    """
    Direct test of §8.3's own stated example: "editing one paragraph
    re-embeds that one chunk, not the whole corpus." h2 changes to h2b;
    h1 and h3 are untouched and must land in unchanged, not new.
    """
    previous = ["h1", "h2", "h3"]
    new = ["h1", "h2b", "h3"]  # only the middle chunk changed
    result = diff_assets(previous_asset_hashes=previous, new_asset_hashes=new)
    assert result.new_hashes == frozenset({"h2b"})
    assert result.unchanged_hashes == frozenset({"h1", "h3"})
    assert result.retired_hashes == frozenset({"h2"})

def test_diff_assets_removed_content_is_retired_not_lost():
    result = diff_assets(previous_asset_hashes=["h1", "h2"], new_asset_hashes=["h1"])
    assert result.retired_hashes == frozenset({"h2"})
    assert result.new_hashes == frozenset()
    assert result.unchanged_hashes == frozenset({"h1"})

def test_diff_assets_handles_duplicate_hashes_in_input():
    # Two chunks that happen to hash identically should not break set logic
    result = diff_assets(previous_asset_hashes=["h1", "h1"], new_asset_hashes=["h1"])
    assert result.unchanged_hashes == frozenset({"h1"})
    assert result.new_hashes == frozenset()
    assert result.retired_hashes == frozenset()