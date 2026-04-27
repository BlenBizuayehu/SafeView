"""
Deterministic tests for /analyze-audio with mocked STT transcription.
"""

import io
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


def fake_audio(min_size: int = 32) -> io.BytesIO:
    # Produce dummy bytes larger than minimum validation threshold
    return io.BytesIO(b"\x00" * min_size)


@pytest.mark.anyio
async def test_analyze_audio_clean_text(client: AsyncClient, mocker):
    # Mock the audio_service.transcribe_audio to avoid loading Whisper
    mocked_transcribe = mocker.patch(
        "app.main.audio_service.transcribe_audio",
        return_value="hello world this is fine",
    )

    response = await client.post(
        "/analyze-audio",
        files={"audio": ("chunk.wav", fake_audio(), "audio/wav")},
    )

    mocked_transcribe.assert_called_once()
    assert response.status_code == 200
    data = response.json()
    assert data["transcribed_text"] == "hello world this is fine"
    assert data["profanity_analysis"]["contains_profanity"] is False
    assert data["profanity_analysis"]["action"] == "ALLOW"


@pytest.mark.anyio
async def test_analyze_audio_profane_text(client: AsyncClient, mocker):
    mocked_transcribe = mocker.patch(
        "app.main.audio_service.transcribe_audio",
        return_value="what the hell is that",
    )

    response = await client.post(
        "/analyze-audio",
        files={"audio": ("chunk.wav", fake_audio(), "audio/wav")},
    )

    mocked_transcribe.assert_called_once()
    assert response.status_code == 200
    data = response.json()
    assert data["transcribed_text"] == "what the hell is that"
    assert data["profanity_analysis"]["contains_profanity"] is True
    assert data["profanity_analysis"]["action"] == "MUTE"
    assert abs(float(data["profanity_analysis"]["duration"]) - 1.5) < 1e-6

