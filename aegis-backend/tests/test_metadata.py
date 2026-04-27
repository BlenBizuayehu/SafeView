"""
Deterministic tests for /analyze-metadata using mocked httpx responses.
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
async def test_metadata_allow_when_no_match(client: AsyncClient, mocker):
    # Mock env var for TMDb key
    mocker.patch("app.services.metadata_service.os.getenv", return_value="fake-key")

    # Mock httpx client.get for both search and details/keywords
    async def mock_get(url, params=None):
        class R:
            def raise_for_status(self): ...
            def json(self_inner):
                if "search/multi" in url:
                    return {"results": [{"id": 1, "media_type": "movie"}]}
                if "/movie/1" in url and "keywords" not in url:
                    return {"genres": [{"id": 18, "name": "Drama"}]}
                if "/movie/1/keywords" in url:
                    return {"keywords": [{"id": 100, "name": "friendship"}]}
                return {}
        return R()

    mocker.patch("httpx.AsyncClient.get", side_effect=mock_get)

    payload = {"title": "Some Title", "blocked_themes": ["Horror", "Violence"]}
    resp = await client.post("/analyze-metadata", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ALLOW"


@pytest.mark.anyio
async def test_metadata_block_on_keyword_match(client: AsyncClient, mocker):
    mocker.patch("app.services.metadata_service.os.getenv", return_value="fake-key")

    async def mock_get(url, params=None):
        class R:
            def raise_for_status(self): ...
            def json(self_inner):
                if "search/multi" in url:
                    return {"results": [{"id": 2, "media_type": "movie"}]}
                if "/movie/2" in url and "keywords" not in url:
                    return {"genres": [{"id": 27, "name": "Horror"}]}
                if "/movie/2/keywords" in url:
                    return {"keywords": [{"id": 101, "name": "gore"}]}
                return {}
        return R()

    mocker.patch("httpx.AsyncClient.get", side_effect=mock_get)

    payload = {"title": "Scary Title", "blocked_themes": ["horror", "violence"]}
    resp = await client.post("/analyze-metadata", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "BLOCK"
    assert "genre:" in data["reason"] or "keyword:" in data["reason"]

