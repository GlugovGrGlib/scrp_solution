"""Speech-to-Text module using AssemblyAI."""

from stt.models import Sentence, TranscriptionResult, Word
from stt.service import TranscriptionError, TranscriptionService

__all__ = [
    "Sentence",
    "TranscriptionError",
    "TranscriptionResult",
    "TranscriptionService",
    "Word",
]
