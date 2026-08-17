"""
tests/unit/test_customers.py

L2 coverage (§19) for GET /customers — frontend integration pass. Closes
a real gap: ChatRequest.customer_id is a required int, but nothing in the
API surface ever let a client discover which customer_id values exist.
support_agent|admin (not admin-only — agents need this routinely).
"""

from __future__ import annotations

import pytest


async def _login(client, user, password) -> str:
    resp = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_support_agent_can_list_customers(client, support_agent_user, make_customer):
    user, password = support_agent_user
    token = await _login(client, user, password)
    await make_customer(company_name="Acme Corp")
    await make_customer(company_name="Beta LLC")

    resp = await client.get("/customers", headers=_auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    names = {c["company_name"] for c in body["customers"]}
    assert {"Acme Corp", "Beta LLC"} <= names
    assert body["total"] >= 2


@pytest.mark.asyncio
async def test_customer_search_filters_by_company_name(client, support_agent_user, make_customer):
    user, password = support_agent_user
    token = await _login(client, user, password)
    await make_customer(company_name="Zephyr Industries")
    await make_customer(company_name="Totally Different Co")

    resp = await client.get("/customers", params={"search": "zephyr"}, headers=_auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    assert all("zephyr" in c["company_name"].lower() for c in body["customers"])
    assert any(c["company_name"] == "Zephyr Industries" for c in body["customers"])


@pytest.mark.asyncio
async def test_customers_requires_authentication(client):
    resp = await client.get("/customers")
    assert resp.status_code in (401, 403)
