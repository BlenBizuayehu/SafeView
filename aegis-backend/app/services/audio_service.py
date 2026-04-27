"""
Audio transcription service using OpenAI Whisper (FREQ-04).
"""

from __future__ import annotations

import re
import tempfile
from typing import Any, Optional

import whisper


class AudioService:
    """
    Loads Whisper model once and provides async transcription of short audio chunks.
    """

    def __init__(self) -> None:
        # Load tiny model at startup for lower latency and memory usage.
        self.model = whisper.load_model("tiny")
        self.bad_words = {
            "fuck",
            "fucking",
            "shit",
            "porn",
            "porno",
            "bitch",
            "asshole",
            "sex",
        }

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

    async def analyze_audio(self, audio_bytes: bytes) -> dict[str, Any]:
        """
        Transcribe audio bytes and decide whether to MUTE/ALLOW.
        """
        transcript = await self.transcribe_audio(audio_bytes)
        normalized_tokens = re.findall(r"[a-zA-Z']+", transcript.lower())
        matched = sorted({word for word in normalized_tokens if word in self.bad_words})
        action = "MUTE" if matched else "ALLOW"
        return {
            "action": action,
            "transcript": transcript,
            "matched_words": matched,
        }

