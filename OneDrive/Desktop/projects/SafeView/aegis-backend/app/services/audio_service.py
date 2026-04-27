"""
Audio transcription service using OpenAI Whisper (FREQ-04).
"""

from __future__ import annotations

from typing import Optional
import tempfile

import whisper


class AudioService:
    """
    Loads Whisper model once and provides async transcription of short audio chunks.
    """

    def __init__(self, model_name: str = "base") -> None:
        # Choose tiny/base/small per latency constraints.
        self.model = whisper.load_model(model_name)

    async def transcribe_audio(self, audio_bytes: bytes) -> str:
        """
        Transcribe audio bytes into text using Whisper.

        For compatibility, writes to a temporary file before transcription.
        """
        if not audio_bytes or len(audio_bytes) < 16:
            raise ValueError("Audio payload is empty or too small to decode.")

        # Write the audio bytes to a temporary file for whisper.
        # Whisper expects a file path or numpy audio array with proper format;
        # we use a temp file to keep implementation simple and robust.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            # Run transcription (blocking call). For short chunks this is acceptable.
            result = self.model.transcribe(tmp.name, fp16=False)  # CPU-safe default

        text: Optional[str] = (result or {}).get("text")
        return text.strip() if text else ""

