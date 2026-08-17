# Document & conversation deletion — investigation & plan

**Status: implemented (2026-07-31).** Both items built exactly as
designed below, including the two reviewer-requested revisions: the
`is_active` join/filter fix in `vector_search.py`/`keyword_search.py`
applies to all four asset types (verified structurally — both files
share one `_search_one_table()` looped over the same `ASSET_TABLES`
registry covering chunk/table/image/diagram, so one fix in each file
covers all four, not just the two illustrative examples originally
named). Regression-verified against the real corpus: all 11 of the
existing real, golden-query-based Stage 4/6 retrieval tests
(`test_hybrid_search.py`) pass unchanged. Full non-eval suite: 235
passed, 14 deselected, 0 failed (12 new tests added). Migration applied
to the dev DB.

Originally a planning-and-investigation document only — kept below as
the design record this implementation followed.

---

## Item 1 — Document deletion

### Investigation: is there a real deletion mechanism today?

**Confirmed: no.** `app/api/routes_ingest.py` has exactly two endpoints —
`POST /ingest` (upload) and `GET /ingest/{job_id}` (job status) — no
`DELETE` of any kind. The only existing soft-retire mechanism is
`app/ingestion/dedup_engine.py`'s `diff_assets()`, which sets
`IngestedAsset.is_active = False` on hashes that a **re-ingestion** no
longer produces — a side effect of uploading a new version of the same
`document_id`, not a direct, intentional "remove this document" action.
Uploading an empty/dummy file to trigger this indirectly is the only
thing resembling deletion today, exactly as suspected: real, but
accidental and fragile — it depends on the dedup diff correctly treating
"everything" as removed, which isn't what that code path was designed to
prove.

### A second, more serious finding: soft-retiring `IngestedAsset` does not currently remove anything from search

Checked directly, not assumed: **`app/retrieval/vector_search.py` and
`app/retrieval/keyword_search.py` never reference `ingested_assets` or
`is_active` at all.** `Chunk`, `TableAsset`, `Image`, and
`DiagramGraphRow` each carry their own `asset_id` FK back to
`IngestedAsset`, but none of them have their own `is_active` column, and
retrieval queries `Chunk`/`TableAsset` directly with no join back to
`IngestedAsset` to check the flag. **`IngestedAsset.is_active` is
therefore a bookkeeping-only value today, consulted solely by
`dedup_engine.py`'s own diffing logic during re-ingestion — it has zero
effect on what a live query actually retrieves.**

This means a `DELETE /ingest/{document_id}` endpoint that only sets
`is_active = False` on `IngestedAsset` rows (as originally proposed)
would be a **silent no-op** with respect to its actual purpose — the
document would still surface in every search result, exactly as before,
while the endpoint reports success. This has to be named and fixed as
part of this item, not discovered later as a confusing bug report.

### Design

**Fix required alongside the endpoint (not optional, not deferred):**
`vector_search.py` and `keyword_search.py`'s per-model query builders
must join to `IngestedAsset` and filter `is_active = true`. Concretely,
in both files' shared query-construction path (wherever `stmt =
select(...)` is built for `Chunk`/`TableAsset`):

```python
stmt = stmt.join(IngestedAsset, model.asset_id == IngestedAsset.asset_id).where(
    IngestedAsset.is_active.is_(True)
)
```

This closes the gap for **both** the existing re-ingestion-triggered
soft-retire path (which today silently does nothing either) and the new
explicit-deletion endpoint below — one fix, two beneficiaries. No schema
change needed for this half; `asset_id` FKs already exist on every
asset-type table.

**New endpoint** — `DELETE /ingest/{document_id}`, in
`app/api/routes_ingest.py` alongside `POST`/`GET`:

```python
@router.delete("/{document_id}", response_model=IngestDeleteResponse)
@limiter.limit("5/minute")
async def delete_document(
    request: Request,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
) -> IngestDeleteResponse:
    result = await db.execute(
        update(IngestedAsset)
        .where(IngestedAsset.document_id == document_id, IngestedAsset.is_active.is_(True))
        .values(is_active=False)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Document not found or already inactive")
    await db.commit()
    return IngestDeleteResponse(document_id=document_id, assets_retired=result.rowcount)
```

- **`require_admin`** — matches `POST /ingest`'s own gating exactly; not
  argued as a new decision, since ingestion management is already
  established as admin-only in this project (§16), and deletion is the
  same category of action as creation.
- **`5/minute`** rate limit — matches `POST /ingest`'s own existing rate
  exactly (§16.1's table), the same reasoning (admin-only, low-frequency,
  high-blast-radius).
- **404 if zero rows affected** — either the `document_id` never existed,
  or every asset for it is already inactive (idempotent delete already
  applied) — both read as "nothing to delete," matching the general
  precedent of not leaking internal state distinctions through the
  response shape.
- **Does not touch `document_versions`** — `DocumentVersion` rows are a
  version-history ledger (§8.3), not a live index; leaving them as-is
  preserves the record that this document existed and was ingested,
  consistent with "never hard-delete, never rewrite history."
- **Schema** (`app/schemas/ingest.py`, alongside `IngestResponse`):
  ```python
  class IngestDeleteResponse(BaseModel):
      document_id: str
      assets_retired: int
  ```

**Migration**: none. `IngestedAsset.is_active` already exists; the
`vector_search.py`/`keyword_search.py` join fix is a code change, not a
schema change.

### Test design

- L1: none needed — no new pure logic beyond a SQL `UPDATE` statement.
- L2: `DELETE /ingest/{document_id}` — seed two documents' worth of
  `IngestedAsset`/`Chunk` rows (distinct `document_id`s), delete one,
  assert its rows are `is_active=False` and the other's remain `True`;
  assert 404 on an unknown `document_id` and on a second delete of the
  same one (idempotency check); non-admin gets 403 (extends
  `test_rbac_violations.py`'s existing pattern).
- **The retrieval-side fix needs its own direct test**, independent of
  the endpoint: seed one active and one inactive (`is_active=False`)
  `Chunk` with otherwise-identical embeddings/text, call `vector_search`/
  `keyword_search` directly, assert the inactive one never appears in
  results — this is the test that would have caught today's silent gap,
  and must exist regardless of whether the endpoint above is built,
  since it's fixing a real, independently-wrong behavior.

---

## Item 2 — Conversation deletion

### Investigation: does anything exist today?

**Confirmed: no.** `app/api/routes_conversations.py` has exactly two
endpoints — `GET /conversations` (list) and `GET /conversations/{id}`
(detail) — no mutation of any kind, let alone deletion.
`ConversationStatus` (`app/db/models.py`) has five values (`open`,
`in_progress`, `resolved`, `escalated`, `closed`) — no `deleted`/
`archived` value exists.

### Is this a real gap worth closing?

**Yes, but narrower than document deletion, and named as a data-hygiene
feature, not a security gap.** Nothing about the current system is
unsafe without it — conversations are already properly access-scoped
(`handled_by_user_id`/admin, confirmed in `get_conversation`). The real
argument for building it is retention/cleanup hygiene: a support agent
or admin currently has no way to mark a stale, test, or mistakenly-
created conversation as no longer relevant, and every conversation the
system has ever seen accumulates in `GET /conversations` forever. That's
a real operational annoyance for a system meant to run in production
long enough to accumulate meaningful volume, not a hypothetical.

**Confirmed the audit-trail concern named in the request is real**:
`EscalationLog.trace_id` is a plain string column (no FK — same
non-enforceable-reference pattern already used for `document_id`
elsewhere in this schema) that matches values written onto `Message`
rows. Hard-deleting a `Message` row would silently orphan any
`EscalationLog` whose `trace_id` pointed at it — the escalation record
would remain, but the message that triggered it would be unrecoverable.
This directly confirms hard deletion is the wrong mechanism here,
independent of this project's general soft-retire philosophy.

### Design

**A status transition, not a hard DELETE** — consistent with
`ConversationStatus`'s existing enum design and the audit-trail finding
above. New enum value: `archived`.

```python
class ConversationStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    escalated = "escalated"
    closed = "closed"
    archived = "archived"
```

**New endpoint** — `POST /conversations/{conversation_id}/archive`, in
`app/api/routes_conversations.py`:

```python
@router.post("/{conversation_id}/archive", response_model=ConversationSummary)
@limiter.limit("10/minute")
async def archive_conversation(
    request: Request,
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_support_or_admin),
) -> ConversationSummary:
    result = await db.execute(select(Conversation).where(Conversation.conversation_id == conversation_id))
    conversation = result.scalar_one_or_none()

    if conversation is None or (
        user.get("role") != "admin" and conversation.handled_by_user_id != user["user_id"]
    ):
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.status = ConversationStatus.archived
    await db.commit()
    await db.refresh(conversation)
    return ConversationSummary(...)
```

**RBAC — argued explicitly, not silently picked:** the assigned agent OR
an admin, reusing `get_conversation`'s exact existing access rule
(`require_support_or_admin` + the same `role != admin and
handled_by_user_id != user_id` → 404 check), not admin-only. Reasoning:
this is the same access boundary the agent already has for *reading*
their own conversation (§17/§29's own "assigned agent or admin" rule) —
archiving is a lighter-weight action than deletion in any real sense
(fully reversible, nothing destroyed), so requiring a stricter boundary
than read access would be inconsistent with the rest of this endpoint
family for no real security benefit. Document deletion, by contrast, is
rightly admin-only because it affects a shared corpus every agent
retrieves from — a conversation only affects the agent's own record.

**Rate limit**: `10/minute`, matching this project's established
mutating-endpoint tier (same as user-management writes and `/ingest`
POST) — a lower-frequency, real-state-changing action, not a read.

**404, not 403, on "not yours"** — matches `get_conversation`'s own
established "not yours reads as not-found" precedent exactly.

**List/detail behavior**: `GET /conversations` should exclude
`archived` conversations by default (matching "cleanup" as the actual
intent) with an explicit `include_archived: bool = False` query param to
see them again — never permanently hidden, just off by default. `GET
/conversations/{id}` continues to work normally on an archived
conversation (the record isn't gone, just decluttered from the default
list) — this is what makes it reversible in spirit even without a
literal "unarchive" endpoint (proposed below).

**Symmetry, matching this plan's own B.3 precedent** (reactivate
mirroring deactivate): `POST /conversations/{conversation_id}/unarchive`,
identical shape, sets status back — but only if the conversation's
status was `archived` in the first place (reject with 400 otherwise, to
avoid accidentally reviving a conversation that was `closed` for a
different, real reason).

### The hard-delete question — named explicitly, not assumed

**Should a real hard-delete ever exist, for GDPR-style right-to-erasure
compliance?** This is a genuine, unresolved tension, surfaced rather than
silently resolved in one direction:

- **Argument for eventually building one**: a real "right to erasure"
  request (from a customer whose data appears in a conversation) is a
  legal obligation in relevant jurisdictions, not just a nice-to-have,
  and no amount of "soft-retire" satisfies it — the underlying `Message`
  content (which may contain PII per `guardrails/pii.py`'s own existence)
  must actually be gone from the database, not just hidden from the
  default list view.
- **Argument against building it now**: no such request has ever been
  received today, `EscalationLog.trace_id`'s dangling-reference problem
  named above would need a real decision (null out orphaned trace_ids?
  cascade-delete the EscalationLog too, destroying a different audit
  record?), and building compliance machinery speculatively, before a
  real legal requirement or real customer request forces the specific
  shape it needs to take, risks building the wrong shape.
- **Recommendation, not a silent default**: do not build hard-delete now.
  If/when a real erasure obligation arises, it should be its own
  narrowly-scoped, admin-only, heavily-audited endpoint (with its own
  explicit decision on what happens to `EscalationLog`/`NotificationLog`
  rows referencing the erased data) — not an extension of the `archive`
  endpoint above, which is explicitly NOT that. Naming this now so the
  distinction between "archive" (reversible, default-hidden) and
  "erase" (irreversible, compliance-driven, unbuilt) is never conflated
  later.

### Migration requirements

One Alembic revision, adding `archived` to the `conversation_status`
Postgres enum. Alembic has no native "add enum value" operation — this
project's existing migrations only ever `CREATE TYPE` fresh, so this is
a new pattern here, done via raw SQL:

```python
def upgrade() -> None:
    op.execute("ALTER TYPE conversation_status ADD VALUE 'archived'")

def downgrade() -> None:
    # Postgres cannot drop a single enum value without recreating the
    # type; documented as a known, accepted one-way migration (same
    # asymmetry already accepted elsewhere for irreversible DDL), not
    # silently pretended to be reversible.
    raise NotImplementedError("Removing an enum value requires recreating conversation_status; not supported.")
```

### Test design

- L1: none beyond the new enum value itself (covered by schema
  validation).
- L2: assigned agent archives their own conversation → 200, status
  becomes `archived`; a different agent attempts to archive it → 404
  (extends the existing cross-agent-access pattern in
  `test_rbac_violations.py`); admin can archive any conversation → 200;
  `GET /conversations` excludes an archived conversation by default,
  includes it with `include_archived=true`; unarchive restores `open`
  (or whatever status preceded archiving — decide which at
  implementation time, flagged here since the current design above
  doesn't specify it); unarchiving a conversation that was never
  archived (e.g. `closed`) → 400.

---

## Summary of decisions made explicit, not assumed

1. Document deletion is a real, admin-only gap — and fixing it correctly
   requires also fixing retrieval's currently-nonexistent `is_active`
   filtering, a separate, more serious bug found during this
   investigation.
2. Conversation deletion is a real but lower-stakes gap — reversible
   archive, not deletion; assigned-agent-or-admin, not admin-only,
   argued on the precedent of matching read-access scope.
3. Hard-delete/right-to-erasure is named as a genuine open question,
   deliberately not built now, with the reasoning for waiting stated
   explicitly rather than the omission being silent.

No implementation started. Awaiting review before proceeding.
