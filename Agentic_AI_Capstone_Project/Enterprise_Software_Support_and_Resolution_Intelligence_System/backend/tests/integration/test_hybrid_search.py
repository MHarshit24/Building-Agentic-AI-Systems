"""
tests/integration/test_hybrid_search.py

Integration test (§19 L3-ish, explicitly requested against real data, not
this suite's usual disposable/mocked fixtures) for app/retrieval/
hybrid_search.py and its four building blocks (vector_search, keyword_search,
fusion, rerank).

---------------------------------------------------------------------------
Two deliberate deviations from every other test in this suite — both
necessary for this file to test what it's actually supposed to test, both
undone again after this module's tests finish.
---------------------------------------------------------------------------
1. Real dev database, not the disposable per-session test DB. tests/
   conftest.py redirects every test to a freshly-migrated, EMPTY
   `{DB_NAME}_test` database (see that file's own module docstring) — correct
   for every other test, but there is no ingested corpus there. This file
   is explicitly testing retrieval QUALITY against the real 7-document
   corpus already ingested into the dev database; re-ingesting all 7 real
   PDFs (with real LLM calls) into a throwaway DB just to run this file
   would be enormously slower and more expensive than querying data that
   already exists. `_use_real_dev_database` below points
   app.retrieval.vector_search's and keyword_search's already-imported
   `async_session_maker` name at a second engine connected to the real dev
   database, for the duration of this module only.

2. Real Azure LLM calls, not LLM_PROVIDER=mock. conftest.py defaults
   LLM_PROVIDER to "mock" for the whole suite. Under mock, embed_text()
   returns a deterministic-but-fake vector seeded from a hash of the query
   text (app/llm/mock_client.py) — completely unrelated to the REAL
   embedding space the actual corpus was embedded into during ingestion.
   Running vector_search under mock here wouldn't test retrieval quality at
   all, it would test nothing (cosine similarity against unrelated random
   vectors). `_use_real_llm_provider` below temporarily forces
   LLM_PROVIDER=azure so query embeddings land in the same space as the
   real corpus, and so rerank.py's LLM call actually reasons about
   relevance instead of short-circuiting on its mock path.

   Running this file therefore makes real, costed Azure OpenAI calls
   (embeddings per query, plus one chat completion per hybrid_search() call
   for reranking) — unlike every other test in this suite. That's the
   explicit point of it (§19's "show real output" requirement for this
   stage), not an oversight.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote_plus

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.retrieval.keyword_search as keyword_search_module
import app.retrieval.vector_search as vector_search_module
from app.config import get_settings
from app.retrieval.fusion import fuse
from app.retrieval.hybrid_search import hybrid_search
from app.retrieval.keyword_search import keyword_search
from app.retrieval.vector_search import vector_search

_GOLDEN_PATH = Path(__file__).resolve().parents[2] / "golden_queries" / "golden_50.json"

# Every test in this file makes real Azure API calls and connects to the
# real dev database (see module docstring above) — backend-ci.yml's L3 job
# runs `pytest tests/integration/ -m "not eval"` precisely to exclude tests
# like this one, since CI has neither a dev database nor Azure credentials.
# Module-level `pytestmark` applies this marker to every test below at
# once, so no individual test here can be added later and accidentally
# left unmarked.
pytestmark = pytest.mark.eval


@pytest_asyncio.fixture(autouse=True)
async def _use_real_dev_database():
    """See module docstring, deviation 1. Builds a second engine pointed at
    the real dev database (the disposable test DB's name with its "_test"
    suffix stripped back off) and monkeypatches it into the two retrieval
    modules that each did `from app.db.session import async_session_maker`
    — patching app.db.session's own attribute wouldn't reach them, since
    that import already copied the reference into their own module
    namespaces at import time.

    Function-scoped (a fresh engine per test, disposed at the end of each),
    not module-scoped — matches tests/conftest.py's own
    `_fresh_engine_pool_per_test` fixture and for the exact same reason:
    pytest-asyncio gives each test its own event loop by default,
    asyncpg's pooled connections are bound to the loop they were opened
    under, and a connection opened in test N is already dead by the time
    test N+1 (a different loop) tries to reuse it from a module-scoped
    pool — confirmed the hard way (first pass at this fixture was
    module-scoped and every other test failed with "Event loop is
    closed"). A fresh engine per test costs one extra asyncpg connection
    per test, negligible next to the real LLM call each test already makes."""
    settings = get_settings()
    dev_db_name = settings.db_name.removesuffix("_test")
    password = quote_plus(settings.db_password)
    dev_url = f"postgresql+asyncpg://{settings.db_user}:{password}@{settings.db_host}:{settings.db_port}/{dev_db_name}"

    dev_engine = create_async_engine(dev_url, echo=False, future=True, pool_pre_ping=True)
    dev_session_maker = async_sessionmaker(bind=dev_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    original_vs = vector_search_module.async_session_maker
    original_ks = keyword_search_module.async_session_maker
    vector_search_module.async_session_maker = dev_session_maker
    keyword_search_module.async_session_maker = dev_session_maker

    yield

    vector_search_module.async_session_maker = original_vs
    keyword_search_module.async_session_maker = original_ks
    await dev_engine.dispose()


@pytest.fixture(scope="module", autouse=True)
def _use_real_llm_provider():
    """See module docstring, deviation 2."""
    original_env = os.environ.get("LLM_PROVIDER")
    os.environ["LLM_PROVIDER"] = "azure"
    get_settings.cache_clear()

    yield

    if original_env is None:
        os.environ.pop("LLM_PROVIDER", None)
    else:
        os.environ["LLM_PROVIDER"] = original_env
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def golden_queries() -> list[dict]:
    with open(_GOLDEN_PATH, encoding="utf-8") as f:
        return json.load(f)["queries"]


def _golden(golden_queries: list[dict], query_id: str) -> dict:
    match = next(q for q in golden_queries if q["id"] == query_id)
    return match


def _document_names_in(expected_sources: list[str]) -> list[str]:
    """expected_sources entries are either a document reference
    ("SLA & Support Operation Policy § 2. ...") or a SQL-table reference
    ("support_tickets (ticket_id = 1)") — golden_50.json mixes both since a
    Hybrid query's ground truth spans both retrieval tools. This test only
    exercises hybrid_search (the RAG/document leg), so SQL-table entries
    are filtered out; a document entry is recognized by NOT looking like a
    lowercase snake_case SQL table reference.
    """
    return [s for s in expected_sources if not s.split(" ")[0].islower()]


def _print_results(label: str, results) -> None:
    print(f"\n--- {label} ({len(results)} results) ---")
    for i, r in enumerate(results):
        snippet = r.text.replace("\n", " ")[:160]
        print(f"  [{i}] score={r.score:.4f} type={r.asset_type} doc={r.source_document!r} section={r.section_header!r}")
        print(f"      {snippet}")


# ---------------------------------------------------------------------------
# Documentation-category golden queries — confirm hybrid_search surfaces
# the expected source document.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("query_id", ["gq_002", "gq_006", "gq_008", "gq_010", "gq_013"])
async def test_documentation_query_retrieves_expected_source(golden_queries, query_id):
    entry = _golden(golden_queries, query_id)
    expected_docs = _document_names_in(entry["expected_sources"])
    assert expected_docs, f"{query_id} has no document-type expected_sources to check"

    results = await hybrid_search(entry["query"])
    _print_results(f"{query_id}: {entry['query']!r}", results)

    assert results, f"hybrid_search returned nothing for {query_id}"
    found = any(
        result.source_document and result.source_document in expected
        for expected in expected_docs
        for result in results
    )
    assert found, (
        f"{query_id}: none of {[r.source_document for r in results]} matched expected {expected_docs}"
    )


# ---------------------------------------------------------------------------
# Hybrid-category golden queries — same check, on queries whose ground
# truth spans both a document and a SQL fact (only the document half is
# checked here; SQL retrieval is a separate tool, not part of this stage).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("query_id", ["gq_026", "gq_033"])
async def test_hybrid_query_retrieves_expected_source_document(golden_queries, query_id):
    entry = _golden(golden_queries, query_id)
    expected_docs = _document_names_in(entry["expected_sources"])
    assert expected_docs, f"{query_id} has no document-type expected_sources to check"

    results = await hybrid_search(entry["query"])
    _print_results(f"{query_id}: {entry['query']!r}", results)

    assert results, f"hybrid_search returned nothing for {query_id}"
    found = any(
        result.source_document and result.source_document in expected
        for expected in expected_docs
        for result in results
    )
    assert found, (
        f"{query_id}: none of {[r.source_document for r in results]} matched expected {expected_docs}"
    )


# ---------------------------------------------------------------------------
# §27 metadata filtering — category filter genuinely excludes non-matching
# content, applied as a pre-filter (not post-hoc).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_category_filter_excludes_non_matching_content():
    query = "What steps should I follow to resolve a problem?"

    unfiltered = await vector_search(query, top_k=20)
    filtered = await vector_search(query, filters={"category": "security"}, top_k=20)

    _print_results("unfiltered", unfiltered)
    _print_results("filtered category=security", filtered)

    assert unfiltered, "expected at least some unfiltered results"
    assert any(r.category != "security" for r in unfiltered), (
        "test is meaningless if every unfiltered result already happens to be category=security"
    )
    assert filtered, "expected at least some security-category results"
    assert all(r.category == "security" for r in filtered), (
        f"filter leaked non-security results: {[(r.source_document, r.category) for r in filtered if r.category != 'security']}"
    )


# ---------------------------------------------------------------------------
# Regression coverage for the category-filter-exclusion bug (real, confirmed
# via a full-golden-set investigation): doc_retrieval_node used to build
# filters={"category": <classify_node's category>} and pass it into
# hybrid_search — the query's own topic classification, not the correct
# answer document's own category tag. For gq_004/gq_007/gq_010 those two
# values are DIFFERENT real category tags, so the hard filter excluded the
# correct document from the candidate pool entirely, every time. The fix
# (doc_retrieval.py's _run_one_attempt()) now never constructs a category
# filter at all — these tests call hybrid_search() the same way
# _run_one_attempt() actually does post-fix (no category filter) and assert
# the correct document now wins TOP-1, not just "appears somewhere."
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query_id,query,expected_top1_doc",
    [
        ("gq_004", "What is the difference between MTTR and MTTA in incident metrics?", "ITIL Incident Management Summary"),
        ("gq_007", "What is the API rate limit for the Free tier?", "API Integration & Authentication Guide"),
        ("gq_010", "How do I troubleshoot a 401 authentication error from the API?", "API Error Codes & Troubleshooting Handbook"),
    ],
)
async def test_no_category_filter_retrieves_correct_top1_document(query_id, query, expected_top1_doc):
    results = await hybrid_search(query)  # no filters — matches _run_one_attempt()'s real post-fix call shape
    _print_results(f"{query_id}: {query!r}", results)

    assert results, f"hybrid_search returned nothing for {query_id}"
    assert results[0].source_document == expected_top1_doc, (
        f"{query_id}: expected top-1 document {expected_top1_doc!r}, got {results[0].source_document!r} "
        f"— category-filter-exclusion regression?"
    )


# ---------------------------------------------------------------------------
# Keyword leg — exact tokens embeddings under-rank (§9's own examples).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_keyword_leg_surfaces_exact_error_code_429():
    kw_results = await keyword_search("429", top_k=20)
    vec_results = await vector_search("429", top_k=20)

    _print_results("keyword_search('429')", kw_results)
    _print_results("vector_search('429')", vec_results)

    kw_hit_index = next(
        (i for i, r in enumerate(kw_results) if "429" in r.text and r.source_document == "API Error Codes & Troubleshooting Handbook"),
        None,
    )
    assert kw_hit_index is not None, "keyword leg did not surface the '429' rate-limiting table/chunk at all"
    assert kw_hit_index == 0, f"expected the exact-token match ranked first by keyword leg, got rank {kw_hit_index}"


@pytest.mark.asyncio
async def test_keyword_leg_surfaces_exact_config_name_db_password():
    kw_results = await keyword_search("DB_PASSWORD", top_k=20)
    vec_results = await vector_search("DB_PASSWORD", top_k=20)

    _print_results("keyword_search('DB_PASSWORD')", kw_results)
    _print_results("vector_search('DB_PASSWORD')", vec_results)

    kw_hit_index = next(
        (i for i, r in enumerate(kw_results) if "DB_PASSWORD" in r.text and r.source_document == "Product Installation & Setup Guide"),
        None,
    )
    assert kw_hit_index is not None, "keyword leg did not surface the DB_PASSWORD config parameter at all"
    assert kw_hit_index == 0, f"expected the exact-token match ranked first by keyword leg, got rank {kw_hit_index}"


# ---------------------------------------------------------------------------
# End-to-end sanity: fusion + rerank actually narrow and reorder results,
# not just pass the vector leg through untouched.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hybrid_search_returns_at_most_five_reranked_results():
    results = await hybrid_search("How do I troubleshoot a rate limit error?")
    _print_results("hybrid_search full pipeline", results)

    assert 0 < len(results) <= 5
    fused_preview = await fuse("How do I troubleshoot a rate limit error?", top_k=20)
    assert len(fused_preview) >= len(results), "fusion should produce at least as many candidates as the final reranked set"
