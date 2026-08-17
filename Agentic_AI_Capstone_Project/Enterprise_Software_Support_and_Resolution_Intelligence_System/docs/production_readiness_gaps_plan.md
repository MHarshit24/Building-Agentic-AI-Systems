# Production-readiness gap analysis — investigation & plan

**Status: implemented (2026-07-29).** B.3, B.4, and B.5 below were built
exactly as designed, with one disclosed deviation: the migration
requirements section calls for two separate Alembic revisions; Alembic's
autogenerate produced one combined revision
(`4314520ade09_add_is_active_to_users_and_create_.py`) since both schema
changes were authored together — functionally equivalent, just one
deploy step instead of two. Self-lockout guards (B.3) and the decided
revocation-timing tradeoff are implemented exactly as written below. Full
test suite run after implementation: all new/modified tests pass; the
only suite failures are pre-existing and caused by an invalid/expired
Azure API key in the local environment (real embedding/LLM calls used by
`test_hybrid_search.py`, `test_graph_parallel_fanout.py`, and
`test_tracing_eval.py`), unrelated to any change in this document.

Originally a planning-and-investigation document only, produced before
any implementation code was written — kept below as the design record
this implementation followed.

Scope note: this analysis is not tied to any specific Blueprint.md section.
It was triggered by comparing the actual running system against claims
README.md itself makes about being production-grade / enterprise-ready.
Two items were suspected gaps but unverified; three are confirmed gaps
with a real design proposed below.

---

## Part A — verification against real code

### A.1 — `customer_id` scoping: per-request parameter, not per-agent-restricted

**Claim under test:** is `customer_id` restricted to "the agent's own
customers," or is it a plain per-request parameter any authenticated
`support_agent` can set to any value?

**Verdict: plain per-request parameter. No agent-to-customer restriction
exists anywhere in the call path.** This matches the project's established
role-based-not-customer-scoped RBAC model, not a bug.

Evidence:

- `app/sql_tools/queries.py` — `get_customer(customer_id: int)`,
  `get_tickets(customer_id: int)`, `get_incidents(customer_id: int)` (plus
  the argument-less `get_active_incidents()`) all take a plain typed `int`,
  validated only by `_require_int()` (a type/range guard, not an ownership
  check). The module's own docstring states the design intent explicitly:
  *"The only argument is a typed int, sourced from state["customer_id"]
  (the authenticated request's own field), never from LLM output or raw
  query text."* That sentence is about injection-safety (no free-text SQL
  construction), not about ownership scoping — there is no second sentence
  anywhere restricting which `customer_id` values a given agent may supply.
- `app/orchestration/nodes/account_validation.py` —
  `account_validation_node` reads `customer_id = state.get("customer_id")`
  and passes it straight into the three whitelisted functions above. No
  lookup of "which customers does this `user_id` own," no join against
  `handled_by_user_id`, no filter of any kind.
- `tests/integration/test_rbac_violations.py`'s
  `test_get_tickets_never_returns_another_customers_rows` proves
  *isolation correctness* (querying customer A's ID never leaks customer
  B's rows) — it does not test, and does not imply, any "agent's own
  customers" restriction. It is the right test for the model this system
  actually implements.

**Conclusion: not a gap.** Any authenticated `support_agent` may
legitimately look up any `customer_id` — this is how the system is
designed to work, and the code is internally consistent about it. No
change proposed.

### A.2 — Layer B (topic-centroid check): soft signal only, and that is the right call

**Claim under test:** when Layer B (the cosine-similarity topic-centroid
check in `scope_guardrail.py`) flags a query as off-topic, does it do
anything beyond adding a soft note to the prompt?

**Verdict: no. Confirmed from `app/orchestration/nodes/doc_retrieval.py`:**

```python
scope_note = ""
try:
    query_embedding = await embed_text(query)
    centroid = await get_cached_centroid()
    if not is_in_scope(query_embedding, centroid):
        scope_note = (
            "NOTE: this query's topical similarity to the support corpus is unusually low. "
            "If the retrieved evidence below doesn't clearly relate to enterprise software "
            "support, treat it as out of scope and say so rather than answering from general "
            "knowledge."
        )
        log_event(logger, "WARNING", "scope_guardrail_layer_b_flagged", query=query)
except ValueError:
    log_event(logger, "WARNING", "scope_guardrail_layer_b_unavailable")
```

`scope_note` is prepended to `evidence` and passed into the same LLM
prompt. No early return, no routing change, no hard block. This sits
alongside Layer A (`classify_node`'s LLM-based `out_of_scope` enum,
routed by `router.py` to a fixed refusal) — Layer A is the actual hard
gate; Layer B only ever influences Layer-A-passed queries that already
reached retrieval.

**Assessment — arguing for one position, not just describing both:**
this is a deliberate, reasonable design choice, not a genuine gap.

`SCOPE_SIMILARITY_THRESHOLD = 0.15` is explicitly documented in the code
itself as *"a reasonable starting point... not a number derived from real
measurement yet."* A threshold with that provenance is not something you
wire to a hard block. Cosine similarity to a corpus-wide mean embedding is
a coarse, single-number signal with no context about the query's actual
content — a legitimate but unusually-phrased support question (terse,
jargon-heavy, or about a rarely-discussed corner of the product) can sit
just as far from the centroid as a genuinely off-topic one. Layer A
already does the semantically precise version of this job: an LLM
classifier that reads the actual query text and reasons about it, with
its own explicit `out_of_scope` category and its own hard routing
consequence. Stacking a second hard block behind a purely mathematical
proximity signal, calibrated on a placeholder threshold, would trade a
small reduction in one specific residual-risk case (Layer A false
negative + Layer B correct catch) for a real, ongoing false-positive tax
on legitimate queries that happen to phrase things atypically. The
current design — Layer A gates, Layer B nudges the LLM's own judgment on
borderline retrieval — puts the hard decision at the layer best equipped
to make it and uses the weaker signal only where it's actually reliable:
as a hint for a model that can weigh it against everything else it sees.

If this is revisited, the trigger should be *evidence*, not
precaution: once real query traffic exists, measure Layer A's false
negative rate on genuinely out-of-scope queries. If that rate turns out
to be materially non-zero, that's the point to reconsider promoting
Layer B — and even then, an escalating response (e.g. requiring
`explicit_human_request`-style secondary confirmation, or logging for
review) is a smaller, safer step than a silent hard block on a threshold
nobody has calibrated against real measurement yet. No code change
proposed here; this is a documented "leave as-is, revisit on evidence"
call.

---

## Part B — three real gaps: designs

Building B.3 and B.4 pushes the API surface past Blueprint.md's original
9 endpoints. **That expansion is named here explicitly, as a deliberate,
disclosed decision** — not something to quietly not mention. Both are
real operational gaps (no way to create a user account without hand-run
SQL; no way for a user to recover a forgotten password) that a system
calling itself production-grade cannot actually ship without.

### B.3 — User management (CRUD)

**New file:** `app/api/routes_users.py`, registered in `app/main.py`
exactly like every other router (`from app.api.routes_users import router
as users_router` / `app.include_router(users_router)`).

Every endpoint below is `require_admin`-gated — matches
`routes_ingest.py`'s exact pattern (`Depends(require_admin)` +
`@limiter.limit(...)`), no new RBAC mechanism invented.

| Method & path | Rate limit | Purpose |
| --- | --- | --- |
| `POST /users` | `10/minute` (user_id-keyed, admin already authenticated) | Create a user |
| `GET /users` | `60/minute` | List users, paginated |
| `GET /users/{user_id}` | `60/minute` | Get one user |
| `PATCH /users/{user_id}` | `10/minute` | Update role/email |
| `POST /users/{user_id}/deactivate` | `10/minute` | Soft-retire |
| `POST /users/{user_id}/reactivate` | `10/minute` | Undo a deactivation |

`10/minute` for the mutating endpoints matches the existing `/ingest`
row's own rate in §16.1's table (an admin-only, low-frequency,
higher-blast-radius action); `60/minute` for reads matches
`/conversations`/`/metrics`'s existing row exactly.

**Schemas** (`app/schemas/users.py`, plain `pydantic.BaseModel`, matching
`app/schemas/auth.py`'s convention exactly — plain `email: str`, not
`EmailStr`, since this project has no `pydantic[email]` dependency and
`LoginRequest` already sets that precedent):

```python
class UserCreateRequest(BaseModel):
    email: str
    password: str
    role: UserRole  # "support_agent" | "admin"

class UserUpdateRequest(BaseModel):
    email: str | None = None
    role: UserRole | None = None

class UserResponse(BaseModel):
    user_id: int
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
```

Never a `password_hash` field in any response — matches the User model's
own docstring convention (`email — ... never returned in responses` is
already the norm to extend to the hash).

**Endpoint bodies, in terms of existing primitives only:**

- `POST /users` — reject if email already exists (`uq_users_email` will
  raise on insert; catch and return 409). Call `hash_password(password)`
  from `app/auth/security.py` (the exact function already used by
  seeding/login) — no new hashing code. Insert `User(email=...,
  password_hash=..., role=..., is_active=True)`. Return `201` +
  `UserResponse`.
- `GET /users` — `limit: int = Query(default=50, le=100, ge=1)`,
  `offset: int = Query(default=0, ge=0)` — the exact pagination signature
  already used by `GET /conversations` (`routes_conversations.py`), not a
  new convention. Optional `role`/`is_active` query filters.
- `GET /users/{user_id}` — 404 if not found.
- `PATCH /users/{user_id}` — partial update of `email`/`role` only. No
  password field here — password change is a separate, explicit concern
  (either reuse the reset flow below, or add a dedicated
  admin-set-password endpoint later if actually needed; not designed here
  since it wasn't asked for and would just be a second way to do what B.4
  already does).
- `POST /users/{user_id}/deactivate` — sets `is_active = False`. Does
  **not** delete or invalidate existing rows referencing this user
  (`Conversation.handled_by_user_id`, `SupportEscalation.handled_by_user_id`)
  — matches the project's existing "audit trail persists" stance already
  documented on those FK columns.

  **Revocation timing — decided, not deferred.** Enforcement happens at
  `/auth/login`: `verify_password`'s existing success path gains one
  extra check (`if not user.is_active: raise 401` — same generic
  unauthorized shape login already uses, no new error surface) before
  issuing a token, so a deactivated user cannot obtain a new access
  token. It does **not** add an `is_active` check inside
  `get_current_user`. The tradeoff, named explicitly: a token issued
  *before* deactivation stays valid for the remainder of its own
  lifetime — bounded to at most `ACCESS_TOKEN_EXPIRE_MINUTES` (**30
  minutes**, `app/auth/jwt_handler.py`), never indefinite. This is an
  accepted, bounded window, not an open-ended gap, for two concrete
  reasons: (1) `get_current_user` (`app/middleware/jwt_auth.py`)
  currently makes zero Postgres calls on any authenticated request — its
  only per-request check is a Redis `is_token_blacklisted` lookup — and
  adding a DB round-trip to the single hottest dependency in the entire
  system, on every request, to close a ≤30-minute window is a
  disproportionate cost; (2) it matches this project's own existing
  risk-acceptance pattern elsewhere (Layer B's soft-fail in §A.2 above,
  `is_token_blacklisted`'s own "Redis unreachable → fail open" branch) —
  small, bounded, disclosed windows over hot-path cost, consistently.
  If a future requirement demands sub-30-minute revocation, the correct
  mechanism is a Redis-based per-user revocation marker (a
  `revoked_at` timestamp keyed by `user_id`, compared against the
  token's own `iat` claim in `get_current_user` — same Redis-lookup cost
  profile as today's blacklist check, no new DB call), not a DB check —
  not building this now since the 30-minute bound makes it unnecessary
  for this pass.
- `POST /users/{user_id}/reactivate` — sets `is_active = True`. Included
  for symmetry with the soft-retire philosophy (nothing here is
  permanent) even though not explicitly requested — it's the direct,
  minimal completion of "deactivate" having an inverse, not a scope add.

**Self-lockout guards — a real gap, closed explicitly.** Without these,
an admin could strip the system of every admin account, exactly the
failure mode user management exists to prevent:

- **Self-demotion / self-deactivation rejected outright.** `PATCH
  /users/{user_id}` (when changing `role`) and `POST
  /users/{user_id}/deactivate` both compare `user_id` (the path param)
  against the requesting admin's own `user["user_id"]` (from
  `require_admin`'s `Depends(get_current_user)` payload). If they match
  and the mutation would demote/deactivate, reject with `400` — *"Cannot
  demote or deactivate your own account"* — not silently ignored, not a
  403 (this is a validation failure, not an authorization failure — the
  admin *is* allowed to act on users in general, just not this specific
  self-destructive mutation).
- **Last-remaining-active-admin rejected.** Before applying a
  role-change-away-from-admin or a deactivation to *any* target user
  (self or otherwise), run `SELECT COUNT(*) FROM users WHERE role =
  'admin' AND is_active = True`. If the target is currently an active
  admin and this count is `1` (i.e. the target *is* that one remaining
  admin), reject with `400` — *"Cannot remove the last remaining active
  admin account"*. This subsumes the self-lockout case when there's only
  one admin total, but is checked independently since a non-self admin
  could just as easily be the last one.

**Migration** — new `is_active` column on `User`, template copied exactly
from `alembic/versions/30623f89349f_add_possibly_truncated_to_tables.py`
(the project's own precedent for this exact shape of change), matching
`IngestedAsset.is_active`'s own definition:

```python
def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Soft-retire flag (§21/§22 convention) — set False to deactivate an account, never hard-deleted",
        ),
    )

def downgrade() -> None:
    op.drop_column("users", "is_active")
```

`server_default=text("true")` means every existing seeded user becomes
active by default on migration — correct, no manual backfill needed.

### B.4 — Password reset flow

**New model** (`app/db/models.py`), a single-use, hashed, time-limited
token — same principle as `password_hash`, never storing the raw token:

```python
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    token_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # sha256 hex digest
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

`used_at` (nullable, set once) rather than deleting the row on use — same
soft-retire discipline as everything else in this codebase; a used/expired
token stays as an audit record rather than vanishing.

Token generation: `secrets.token_urlsafe(32)` for the raw token (sent to
the user, never stored); `hashlib.sha256(raw_token.encode()).hexdigest()`
stored as `token_hash`. This mirrors `password_hash`'s "never store the
raw secret" principle while using a fast hash (not bcrypt) since this is a
high-entropy random token, not a low-entropy human password — bcrypt's
slow-by-design cost has no security benefit here and would just add
latency; a plain SHA-256 digest is the correct, standard choice for
random-token-at-rest, distinct from password hashing on purpose.

**Endpoints** (`app/api/routes_auth.py`, alongside the existing
`login`/`logout` — same file, same router, not a new one, since this is
squarely an auth-flow endpoint):

| Method & path | Rate limit | Auth |
| --- | --- | --- |
| `POST /auth/password-reset/request` | `5/15minute`, keyed by **IP** | None (pre-auth, same reasoning as `/auth/login`) |
| `POST /auth/password-reset/confirm` | `5/15minute`, keyed by IP | None (token *is* the auth) |

Both reuse `/auth/login`'s exact rate-limit shape and IP-keying rationale
(no JWT exists yet at this point in the flow) — not a new pattern.

**Anti-enumeration design, matching `/auth/login`'s own established
"never reveal which check failed" discipline:**

- `POST /auth/password-reset/request` body: `{"email": str}`. Regardless
  of whether the email exists, looks up the user, and — only if found —
  generates a token, stores its hash, and calls
  `mcp_servers/notification_mcp/mailtrap_client.py`'s `send_email(to=email,
  subject=..., body=f"...{raw_token}...")` (the exact, already-built,
  already-proven mechanism — `send_email` never raises, always returns
  `bool`, so a Mailtrap outage degrades gracefully rather than 500ing).
  **Response is always identical** — `202 Accepted`, `{"message": "If an
  account exists for that email, a reset link has been sent."}` —
  whether or not the email was found, and whether or not the send
  actually succeeded. This is the direct analog of login's "generic 401
  regardless of which check failed."
- `POST /auth/password-reset/confirm` body: `{"token": str, "new_password":
  str}`. Hash the incoming token, look up `PasswordResetToken` by
  `token_hash`; reject (generic `400`, no distinction between
  "not found," "expired," "already used") if missing, `used_at is not
  None`, or `expires_at < now()`. On success: `hash_password(new_password)`
  into the `User` row, set `used_at = now()` on the token, return `200`.
- Token expiry: 30 minutes — short enough to bound the exposure window
  from an intercepted email, long enough to be usable; a `Settings` field
  (`password_reset_token_expiry_minutes: int = 30`) rather than a hardcoded
  constant, matching the project's existing "tunable values live in
  `Settings`" convention (e.g. the confidence thresholds).

**Migration** — new `password_reset_tokens` table, same
`op.create_table(...)` Alembic shape already used for every other table
in this schema (no new template needed beyond what Alembic
autogenerates from the model above).

### B.5 — Version-extraction parsing

**Real investigated basis (per the explicit requirement — checked the
actual DB, not assumed):**

```text
chunks.product_version distribution:      None: 53   'v3.5': 52
tables.product_version distribution:      'v3.5': 25  None: 19
document_versions.product_version dist.:  'v3.5': 4   None: 3
```

Sample real chunk text containing a version mention:

```text
"API Error Codes & Troubleshooting Handbook\nEnterprise Resolution
Intelligence System API v3.5\n..."
"API Integration & Authentication Guide\nEnterprise Resolution
Intelligence System API v3.5\nBase URL:\nhttps://api.example.com/v3\n..."
"Product Installation & Setup Guide\nEnterprise Resolution Intelligence
System v3.5\nDocument\nVersion:\n3.5.1\nRelease Date:\nMarch 2026\n..."
```

**Finding: the original deferral's worry — "fragile general regex" against
an unpredictable range of version strings — does not describe this
corpus.** Every non-null value across all three tables is the single
literal string `'v3.5'`. The document text itself is consistent too: the
product name is always followed by `vX.Y` (`v3.5`), with one place also
spelling out a longer `X.Y.Z` form (`3.5.1`) as a labeled "Document
Version" field rather than inline prose. There is exactly one product
version in this corpus today — this is a narrow, single-value real-world
case, not the broad multi-version catalog the original deferral was
guarding against.

**Proposed extraction mechanism, sized to match that reality — not
over-built for versions that don't exist yet:**

A single, deliberately narrow regex against the user's query text,
looking for the same `vX.Y` shape actually observed in the corpus:

```python
import re

_VERSION_PATTERN = re.compile(r"\bv(\d+(?:\.\d+){0,2})\b", re.IGNORECASE)

def extract_product_version(query: str) -> str | None:
    match = _VERSION_PATTERN.search(query)
    if not match:
        return None
    return f"v{match.group(1)}"
```

This matches `"v3.5"`, `"V3"`, `"v3.5.1"` from query text like *"How do I
configure OAuth for API v3.5?"* — directly the phrasing pattern already
seen in the real chunk text above, so a query written the way a support
agent would naturally phrase it (echoing the doc's own `vX.Y` convention)
will match. It intentionally does **not** try to parse bare `"3.5"`
without a leading `v` (the original deferral's "fragile" concern was
precisely about guessing whether a bare number is a version, a dollar
amount, a ticket number, etc. — that ambiguity is real and this design
sidesteps it by requiring the unambiguous `v`-prefixed form actually used
in the corpus, rather than trying to be clever about bare numbers). If a
future corpus expansion introduces version references that don't carry a
leading `v`, that's the point to revisit — not to guess a broader pattern
now against data that doesn't exist yet.

**Wiring point** — `app/orchestration/nodes/doc_retrieval.py`'s
`_run_one_attempt()` currently builds:

```python
filters = {"category": category} if category else None
```

This becomes:

```python
extracted_version = extract_product_version(query)
filters = {}
if category:
    filters["category"] = category
if extracted_version:
    filters["product_version"] = extracted_version
filters = filters or None
```

No changes needed in `app/retrieval/vector_search.py` or
`app/retrieval/keyword_search.py` — both already implement
`product_version` filtering (`if product_version and hasattr(model,
"product_version"): stmt = stmt.where(model.product_version ==
extracted_version)`), confirmed present today. `hybrid_search(query,
filters)` already passes an arbitrary `filters` dict straight through.
**The only genuinely missing piece was extraction + wiring — the filter
plumbing itself was already fully built**, which meaningfully narrows
this item's real implementation cost versus what the original deferral's
framing ("fragile general regex" as a blocking concern) suggested.

**A behavior worth deciding explicitly at implementation time:** should
an extracted-but-wrong version (e.g. a query mentions `v9.0`, which
doesn't exist in the corpus) filter results down to zero, or should the
filter be dropped/fall back to unfiltered search on an empty result set?
Given `is_in_scope`'s own "fail open" philosophy for the analogous
ValueError case, falling back to unfiltered search on zero filtered
results is the more consistent choice — proposed here, not yet built.

---

## Migration requirements (summary)

Two new Alembic revisions, in this order (the second has no FK
dependency on the first, so order is for clarity, not correctness):

1. `add_is_active_to_users` — `op.add_column("users", ...)` per B.3.
2. `create_password_reset_tokens` — `op.create_table("password_reset_tokens",
   ...)` per B.4.

No migration needed for B.5 (uses existing `product_version` columns,
already present per §27).

---

## Test design (L1–L5 discipline)

**B.3 (user CRUD):**
- L1: `hash_password`/schema validation already covered; new pure-logic
  coverage limited to any request-shape validation added to
  `UserCreateRequest`/`UserUpdateRequest`.
- L2 (mocked component / integration against a test DB): `POST /users`
  creates a row with a hashed (never plaintext) password; duplicate email
  returns 409; non-admin JWT gets 403 on every endpoint in this router
  (extends `test_rbac_violations.py`'s existing non-admin-`/ingest`-403
  pattern to the new surface); `deactivate` sets `is_active=False` and a
  subsequent `reactivate` restores it; deactivated users still resolve
  correctly as `handled_by_user_id` on old conversations (no orphaned FK
  behavior).
- **Self-lockout guards (both required, per the confirmed gap):** an
  admin calling `POST /users/{their_own_user_id}/deactivate` gets `400`,
  not a silent no-op or a 500; an admin calling `PATCH
  /users/{their_own_user_id}` with `role: "support_agent"` gets `400`
  for the same reason. Separately: seed exactly one active admin, assert
  `deactivate` on that admin's `user_id` (called by a *different*
  authenticated admin — requires seeding two, then dropping to one via
  the first deactivation attempt failing) returns `400`; assert a
  role-change away from `admin` on the last remaining active admin via
  `PATCH` is rejected the same way. A positive-path test confirms
  deactivating a non-last admin (≥2 active admins present) succeeds
  normally — the guard must not block ordinary admin turnover, only the
  zero-remaining-admins case.
- A test confirming a deactivated user's existing, not-yet-expired token
  still authenticates successfully (proving the decided ≤30-minute
  window is real and intentional, not an oversight), and a separate test
  confirming `/auth/login` rejects a deactivated user's credentials with
  the same generic `401` login already uses for bad credentials (not a
  distinguishable error — same anti-enumeration discipline as B.4).
- No L3/L4/L5 needed — no LLM or judge involvement in this feature at all.

**B.4 (password reset):**
- L1: token generation produces a high-entropy raw token and a distinct
  stored hash (raw never persisted); expiry-comparison logic.
- L2: `request` endpoint returns the identical response shape for both an
  existing and a non-existing email (the concrete, checkable form of the
  anti-enumeration requirement) — assert byte-identical response bodies
  across both cases, not just "both succeed"; `confirm` endpoint rejects
  expired tokens, already-used tokens, and unknown tokens with the same
  generic error (mirrors the enumeration check — assert the three
  rejection cases are indistinguishable from the response alone); a valid
  token successfully changes the password and a second use of the same
  token then fails; rate-limit test confirms the 6th request within
  15 minutes from one IP is rejected (matches the existing
  `/auth/login`-rate-limit test's shape, if one already exists, or
  establishes the same pattern if not). Mailtrap's `send_email` is
  mocked here via the existing queued-fake-client pattern (§7's own
  precedent) — never a real send in this layer.
- L3: one VCR-style or mocked-transport test is unnecessary here since
  `send_email` already has unit coverage from Stage 7 and this feature
  only calls it, doesn't change its contract — no new cassette needed.

**B.5 (version extraction):**
- L1: `extract_product_version()` pure-function tests — `"v3.5"` →
  `"v3.5"`, `"V3"` → `"v3"`, `"v3.5.1"` → `"v3.5.1"`, no version present
  → `None`, and a couple of the "don't false-positive on bare numbers"
  cases (`"I have 3.5 million records"` → `None`, since there's no
  leading `v`).
- L2: `doc_retrieval_node`/`_run_one_attempt()` test confirming a query
  containing `"v3.5"` produces a `filters` dict with `product_version:
  "v3.5"` passed into a mocked `hybrid_search`; a query with no version
  mention produces a `filters` dict with no `product_version` key at all
  (not `None` masking a bug — an explicit absence).
- L4 (golden-eval): if `golden_50.json` doesn't already contain a
  version-scoped query (e.g. "How do I set up OAuth in v3.5?"), this is
  the natural place to confirm one exists or add one, so the calibration
  suite actually exercises this path — flagged here for the
  implementation pass to check, not assumed.

**Part A (regression guards, not new behavior):** `A.1`'s "no
per-agent-restriction" and `A.2`'s "Layer B never hard-blocks" are both
already implicitly covered by existing passing tests
(`test_get_tickets_never_returns_another_customers_rows` for A.1; any
existing `doc_retrieval_node` test exercising a low-similarity query
without asserting a refusal, for A.2) — no new tests proposed for Part A
since both are "confirm current behavior is correct and intentional,"
not "build something new." If desired, a single explicit regression test
asserting `doc_retrieval_node` still returns a normal (non-refusal)
response for a Layer-B-flagged-but-Layer-A-passed query would make the
"soft note only" contract permanent and catch any future accidental
hardening — worth adding if this design is implemented, not required by
this investigation itself.

---

## Endpoint count disclosure

Blueprint.md's original line specifies 9 endpoints. This plan's B.3 + B.4
additions bring the total to **9 + 6 (users) + 2 (password reset) = 17**.
This is named here explicitly, as instructed: a deliberate, disclosed
expansion driven by two confirmed operational gaps a production system
cannot ship without (account provisioning, password recovery) — not scope
creep introduced quietly.

---

## Stop point (original) / implementation record (current)

This document was originally the complete planning deliverable: Part A's
findings (both items, with an argued position on A.2), exact
endpoint/model designs for B.3–B.4, the real investigated basis and
design for B.5, migration requirements, and test design across the
L1–L5 discipline. It has since been implemented in full — see the status
note at the top of this document for the one disclosed deviation
(a single combined Alembic migration instead of two) and the test-run
summary.
