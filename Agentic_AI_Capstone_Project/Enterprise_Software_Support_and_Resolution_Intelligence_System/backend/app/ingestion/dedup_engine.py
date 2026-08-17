"""
app/ingestion/dedup_engine.py

Pure diff logic for §8.3's idempotent re-ingestion algorithm. Takes
already-computed hashes (from hashing.py) and previously-stored hashes
(read from ingested_assets by the caller) and decides what to do —
never touches the DB or the filesystem itself, so it's testable with
plain sets and no fixtures (§25, "unit-tested first").

§8.3 is explicitly a HASH-based diff, not an ID-based one: "unchanged
hash", "new hash, unseen", "present before, missing now" are all framed
in terms of the hash values themselves, not a stable identity key
matched across versions. That's deliberate — content-hash equality *is*
the identity for dedup purposes. This is what makes "editing one
paragraph re-embeds that one chunk, not the whole corpus" true: every
*other* chunk's hash is unchanged and lands in the intersection; only
the edited chunk's old hash disappears (retired) and its new hash
appears (new).
"""

from dataclasses import dataclass
from typing import Iterable


def is_document_unchanged(new_content_hash: str, active_version_content_hash: str | None) -> bool:
    """
    §8.3 step 1 — whole-file hash comparison against the current active
    version. No active version at all (first-ever ingest of this
    document_id) is never "unchanged" — there's nothing to be unchanged
    from.
    """
    if active_version_content_hash is None:
        return False
    return new_content_hash == active_version_content_hash


@dataclass(frozen=True)
class AssetDiffResult:
    """
    §8.3 step 3's three buckets, as hash sets. The caller (pipeline.py)
    is responsible for mapping new_hashes back to the actual freshly-
    extracted content that produced them (this module never sees that
    content, only hashes) and mapping retired_hashes to existing DB rows
    to soft-retire.
    """
    new_hashes: frozenset[str]
    unchanged_hashes: frozenset[str]
    retired_hashes: frozenset[str]


def diff_assets(
    previous_asset_hashes: Iterable[str],
    new_asset_hashes: Iterable[str],
) -> AssetDiffResult:
    """
    §8.3 step 3.
      - new_hashes:       in new, not in previous  -> extract, embed, insert
      - unchanged_hashes: in both                   -> keep row+embedding as-is, no re-embed call
      - retired_hashes:   in previous, not in new    -> soft-retire (is_active=false), never hard-deleted
    """
    previous = frozenset(previous_asset_hashes)
    new = frozenset(new_asset_hashes)
    return AssetDiffResult(
        new_hashes=new - previous,
        unchanged_hashes=new & previous,
        retired_hashes=previous - new,
    )