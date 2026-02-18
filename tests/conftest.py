"""Shared test fixtures."""

import pytest


@pytest.fixture
def sample_transcription_dict() -> dict:
    return {
        "text": "Hello world.",
        "words": [{"text": "hello", "start_ms": 0, "end_ms": 500, "confidence": 0.95}],
        "sentences": [{"text": "Hello world.", "start_ms": 0, "end_ms": 1000}],
        "language_code": "en",
        "confidence": 0.95,
        "duration_ms": 1000,
        "audio_url": "https://example.com/audio.mp3",
    }
