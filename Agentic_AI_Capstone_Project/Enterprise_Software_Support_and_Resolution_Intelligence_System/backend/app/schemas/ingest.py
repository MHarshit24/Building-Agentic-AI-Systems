"""
app/schemas/ingest.py

Request/response models for POST /ingest and GET /ingest/{job_id} — §8.1,
§17. File upload (multipart) only — §8.1 also mentions URL-reference
ingestion, but that's explicitly out of scope for this task.

---------------------------------------------------------------------------
Design decision: where document_id comes from
---------------------------------------------------------------------------
§8.3's whole idempotent re-ingestion algorithm depends on document_id
staying stable across re-uploads of an updated version of the same
document — that's the identity the diff is keyed on — but nothing in
§21's schema says who assigns it. Two options, both defensible:

  (a) the caller supplies it explicitly as a request field, or
  (b) the system derives a canonical one from the uploaded filename.

Decided: **(b) — the system derives it, it is NOT a request field.**

Why: §17's own GET /ingest/{job_id} example response —
{"document_id": "api_error_handbook", "version_id": 4, ...} — already
shows a value that's obviously derived from a filename
(API_Error_Codes_Troubleshooting_Handbook.pdf), not an opaque ID a caller
invented. Beyond just following that precedent: POST /ingest is a
human-driven, admin-only multipart upload (§16), not a machine-to-machine
API integration — the natural workflow is "re-upload the updated PDF,"
not "remember and resupply the exact document_id string from months ago
that nothing displays back to you in the UI." Deriving it from the
filename (slugify_document_id() in pipeline.py — lowercased, extension
stripped, non-alphanumeric runs collapsed to underscores) makes that
natural workflow correct *by construction*: re-uploading a file with the
same name — the overwhelmingly common case, a doc gets updated in place,
not renamed — automatically lands on the same document_id and triggers
§8.3's diff path, with zero discipline required from the admin doing the
upload.

The real cost, accepted as reasonable for this admin-controlled,
human-in-the-loop flow: renaming a file starts a new document lineage
instead of versioning the old one, and two differently-named files that
happen to slugify identically would collide. A machine-to-machine API
surface would need a stable opaque ID to protect against exactly this;
this endpoint doesn't have that requirement.

doc_title/product_version/category are accepted as optional form fields
alongside the file, since none of those are derivable from the file
content or name reliably — they're genuine metadata only a human admin
would know. They land on document_versions and are then propagated onto
every chunk/table/image/diagram row produced from that version, for
§27's fast metadata pre-filtering.
"""

from pydantic import BaseModel


class IngestResponse(BaseModel):
    job_id: str
    status: str


class IngestStats(BaseModel):
    """§8's step 5 / IngestionJob.stats_json's shape exactly."""

    assets_new: int
    assets_unchanged_skipped: int
    assets_updated: int
    assets_retired: int


class IngestStatusResponse(BaseModel):
    job_id: str
    document_id: str
    status: str
    stats: IngestStats | None = None  # null until status == "completed"


class IngestDeleteResponse(BaseModel):
    document_id: str
    assets_retired: int
