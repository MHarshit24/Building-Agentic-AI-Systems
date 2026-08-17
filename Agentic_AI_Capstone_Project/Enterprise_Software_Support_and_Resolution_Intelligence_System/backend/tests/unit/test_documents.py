"""
tests/unit/test_documents.py

L2 coverage (§19) for GET /documents — frontend integration pass (A5).
Admin-only listing of every currently-active ingested document, joined
against a live count of its still-active IngestedAsset rows.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.db.models import DocumentStatus, DocumentVersion, IngestedAsset
from app.db.session import async_session_maker


async def _login(client, user, password) -> str:
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def seeded_documents():
    """doc_a: one superseded version + one active version + 2 active assets.
    doc_b: one active version, no assets at all (exercises the outer-join
    zero-count path). Superseded version proves it's excluded from the
    listing, not just that active ones are included."""
    version_ids: list[int] = []
    asset_ids: list[int] = []

    async with async_session_maker() as session:
        old_a = DocumentVersion(
            document_id="doc_a",
            content_hash="hash_a_old",
            ingested_at=datetime.now(timezone.utc) - timedelta(days=1),
            status=DocumentStatus.superseded,
            doc_title="Doc A (old)",
        )
        new_a = DocumentVersion(
            document_id="doc_a",
            content_hash="hash_a_new",
            status=DocumentStatus.active,
            doc_title="Doc A",
            product_version="v2",
            category="usage",
        )
        b = DocumentVersion(
            document_id="doc_b",
            content_hash="hash_b",
            status=DocumentStatus.active,
            doc_title="Doc B",
        )
        session.add_all([old_a, new_a, b])
        await session.commit()
        for v in (old_a, new_a, b):
            await session.refresh(v)
            version_ids.append(v.version_id)

        assets = [
            IngestedAsset(document_id="doc_a", asset_type="chunk", asset_hash=f"a_hash_{i}", is_active=True)
            for i in range(2)
        ]
        # An inactive asset for doc_a must NOT count toward active_asset_count.
        assets.append(
            IngestedAsset(document_id="doc_a", asset_type="chunk", asset_hash="a_hash_retired", is_active=False)
        )
        session.add_all(assets)
        await session.commit()
        for a in assets:
            await session.refresh(a)
            asset_ids.append(a.asset_id)

    yield

    async with async_session_maker() as session:
        await session.execute(delete(IngestedAsset).where(IngestedAsset.asset_id.in_(asset_ids)))
        await session.execute(delete(DocumentVersion).where(DocumentVersion.version_id.in_(version_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_admin_lists_only_active_versions_with_correct_asset_counts(
    client, admin_user, seeded_documents
):
    admin, admin_password = admin_user
    token = await _login(client, admin, admin_password)

    resp = await client.get("/documents", headers=_auth_header(token))
    assert resp.status_code == 200
    docs = {d["document_id"]: d for d in resp.json()["documents"]}

    assert set(docs.keys()) == {"doc_a", "doc_b"}  # superseded version of doc_a excluded

    assert docs["doc_a"]["content_hash"] == "hash_a_new"
    assert docs["doc_a"]["doc_title"] == "Doc A"
    assert docs["doc_a"]["product_version"] == "v2"
    assert docs["doc_a"]["active_asset_count"] == 2  # the retired one doesn't count

    assert docs["doc_b"]["active_asset_count"] == 0  # no assets at all — outer join, not inner


@pytest.mark.asyncio
async def test_non_admin_cannot_list_documents(client, support_agent_user, seeded_documents):
    user, password = support_agent_user
    token = await _login(client, user, password)

    resp = await client.get("/documents", headers=_auth_header(token))
    assert resp.status_code == 403
