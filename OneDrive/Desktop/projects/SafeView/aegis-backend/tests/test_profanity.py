"""
Deterministic tests for /analyze-text profanity endpoint.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_analyze_text_allow_when_clean(client: AsyncClient):
    payload = {"text": "This is a perfectly normal sentence."}
    resp = await client.post("/analyze-text", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["contains_profanity"] is False
    assert data["action"] == "ALLOW"
    assert data["duration"] == 0.0


@pytest.mark.anyio
async def test_analyze_text_mute_on_profanity(client: AsyncClient):
    payload = {"text": "What the hell is this?"}
    resp = await client.post("/analyze-text", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["contains_profanity"] is True
    assert data["action"] == "MUTE"
    assert abs(float(data["duration"]) - 1.5) < 1e-6
    assert "hell" in data["matched"]

