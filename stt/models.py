"""Data models for transcription results."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Word:
    """Single transcribed word with timing."""

    text: str
    start_ms: int
    end_ms: int
    confidence: float


@dataclass(frozen=True, slots=True)
class Sentence:
    """Sentence with timing information."""

    text: str
    start_ms: int
    end_ms: int


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """Complete transcription result."""

    text: str
    words: tuple[Word, ...]
    sentences: tuple[Sentence, ...]
    language_code: str
    confidence: float
    duration_ms: int
    audio_url: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "text": self.text,
            "words": [
                {
                    "text": w.text,
                    "start_ms": w.start_ms,
                    "end_ms": w.end_ms,
                    "confidence": w.confidence,
                }
                for w in self.words
            ],
            "sentences": [
                {"text": s.text, "start_ms": s.start_ms, "end_ms": s.end_ms} for s in self.sentences
            ],
            "language_code": self.language_code,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
            "audio_url": self.audio_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranscriptionResult":
        """Deserialize from dictionary."""
        return cls(
            text=data["text"],
            words=tuple(
                Word(
                    text=w["text"],
                    start_ms=w["start_ms"],
                    end_ms=w["end_ms"],
                    confidence=w["confidence"],
                )
                for w in data["words"]
            ),
            sentences=tuple(
                Sentence(text=s["text"], start_ms=s["start_ms"], end_ms=s["end_ms"])
                for s in data["sentences"]
            ),
            language_code=data["language_code"],
            confidence=data["confidence"],
            duration_ms=data["duration_ms"],
            audio_url=data["audio_url"],
        )
