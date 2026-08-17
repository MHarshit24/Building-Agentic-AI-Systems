"""
tests/unit/test_document_deletion.py

L2 coverage (§19) for DELETE /ingest/{document_id} — production-readiness
gap analysis, deletion item 1. Soft-retires IngestedAsset rows, never a
hard delete; the accompanying retrieval-side is_active fix has its own
direct regression test in test_retrieval_is_active_filter.py.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models import IngestedAsset
from app.db.session import async_session_maker


async def _login(client, user, password) -> str:
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def seeded_two_documents():
    created_ids: list[int] = []

    async with async_session_maker() as session:
        doc_a_assets = [
            IngestedAsset(document_id="doc_a", asset_type="chunk", asset_hash=f"hash_a_{i}", is_active=True)
            for i in range(2)
        ]
        doc_b_assets = [
            IngestedAsset(document_id="doc_b", asset_type="chunk", asset_hash=f"hash_b_{i}", is_active=True)
            for i in range(3)
        ]
        session.add_all(doc_a_assets + doc_b_assets)
        await session.commit()
        for asset in doc_a_assets + doc_b_assets:
            await session.refresh(asset)
            created_ids.append(asset.asset_id)

    yield {"doc_a_count": len(doc_a_assets), "doc_b_count": len(doc_b_assets)}

    async with async_session_maker() as session:
        from sqlalchemy import delete

        await session.execute(delete(IngestedAsset).where(IngestedAsset.asset_id.in_(created_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_admin_can_delete_document_soft_retires_only_its_own_assets(
    client, admin_user, seeded_two_documents
):
    admin, admin_password = admin_user
    token = await _login(client, admin, admin_password)
    counts = seeded_two_documents

    resp = await client.delete("/ingest/doc_a", headers=_auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_id"] == "doc_a"
    assert body["assets_retired"] == counts["doc_a_count"]

    async with async_session_maker() as session:
        doc_a_rows = (
            await session.execute(select(IngestedAsset).where(IngestedAsset.document_id == "doc_a"))
        ).scalars().all()
        doc_b_rows = (
            await session.execute(select(IngestedAsset).where(IngestedAsset.document_id == "doc_b"))
        ).scalars().all()

    assert all(not row.is_active for row in doc_a_rows)
    assert all(row.is_active for row in doc_b_rows)


@pytest.mark.asyncio
async def test_delete_unknown_document_returns_404(client, admin_user):
    admin, admin_password = admin_user
    token = await _login(client, admin, admin_password)

    resp = await client.delete("/ingest/nonexistent_document", headers=_auth_header(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_same_document_twice_is_idempotent_second_call_404s(
    client, admin_user, seeded_two_documents
):
    admin, admin_password = admin_user
    token = await _login(client, admin, admin_password)

    first = await client.delete("/ingest/doc_a", headers=_auth_header(token))
    assert first.status_code == 200

    second = await client.delete("/ingest/doc_a", headers=_auth_header(token))
    assert second.status_code == 404


@pytest.mark.asyncio
async def test_non_admin_cannot_delete_document(client, support_agent_user, seeded_two_documents):
    user, password = support_agent_user
    token = await _login(client, user, password)

    resp = await client.delete("/ingest/doc_a", headers=_auth_header(token))
    assert resp.status_code == 403
