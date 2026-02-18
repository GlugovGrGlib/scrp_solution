"""AssemblyAI transcription service."""

import logging
import time

import assemblyai as aai

from core.cache import RedisCache, cache_key, create_cache
from core.config import settings
from stt.models import Sentence, TranscriptionResult, Word

logger = logging.getLogger(__name__)

CACHE_PREFIX = "stt:transcript"
RATE_LIMIT_KEY = "stt:ratelimit:assemblyai"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2.0
RETRY_BACKOFF_MULTIPLIER = 2.0


class TranscriptionError(Exception):
    """Transcription error with error code for categorization."""

    def __init__(self, message: str, error_code: str = "STT_FAILED") -> None:
        super().__init__(message)
        self.error_code = error_code


class TranscriptionService:
    """Audio transcription using AssemblyAI with Redis caching."""

    def __init__(self) -> None:
        self._cache: RedisCache | None = create_cache()
        aai.settings.api_key = settings.stt_assemblyai_api_key

    def transcribe(self, audio_url: str) -> TranscriptionResult:
        """Transcribe audio from URL with caching and retry logic."""
        key = cache_key(CACHE_PREFIX, audio_url)
        if self._cache:
            cached = self._cache.get(key)
            if cached:
                logger.info("Cache hit for %s", audio_url[:50])
                return TranscriptionResult.from_dict(cached)
            self._cache.wait_for_rate_limit(RATE_LIMIT_KEY, settings.stt_rate_limit_requests)

        last_error: TranscriptionError | None = None
        delay = RETRY_DELAY_SECONDS

        for attempt in range(MAX_RETRIES):
            try:
                result = self._do_transcribe(audio_url)
                if self._cache:
                    self._cache.set(key, result.to_dict())
                return result

            except TranscriptionError as e:
                if e.error_code in ("RATE_LIMITED", "TIMEOUT"):
                    logger.warning("%s, attempt %d/%d", e.error_code, attempt + 1, MAX_RETRIES)
                    last_error = e
                    time.sleep(delay)
                    delay *= RETRY_BACKOFF_MULTIPLIER
                else:
                    raise

        raise last_error or TranscriptionError("Max retries exceeded")

    def _do_transcribe(self, audio_url: str) -> TranscriptionResult:
        """Execute single transcription attempt."""
        config = aai.TranscriptionConfig(
            speech_models=["universal-2"],
            language_code=settings.stt_language_code,
            speaker_labels=settings.stt_speaker_labels,
            punctuate=settings.stt_punctuate,
            format_text=settings.stt_format_text,
        )

        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(audio_url)

        if transcript.status == aai.TranscriptStatus.error:
            error_msg = transcript.error or "Unknown error"
            error_lower = error_msg.lower()
            if "rate limit" in error_lower:
                raise TranscriptionError(error_msg, "RATE_LIMITED")
            if "timeout" in error_lower:
                raise TranscriptionError(error_msg, "TIMEOUT")
            raise TranscriptionError(error_msg)

        if not transcript.text or not transcript.text.strip():
            raise TranscriptionError("No speech detected in audio", "NO_SPEECH_DETECTED")

        return self._build_result(transcript, audio_url)

    @staticmethod
    def _build_result(transcript: aai.Transcript, audio_url: str) -> TranscriptionResult:
        """Convert AssemblyAI transcript to internal model."""
        words = tuple(
            Word(
                text=w.text,
                start_ms=w.start,
                end_ms=w.end,
                confidence=w.confidence,
            )
            for w in (transcript.words or [])
        )

        if hasattr(transcript, "get_sentences"):
            transcript_sentences = transcript.get_sentences()
        else:
            transcript_sentences = []
        sentences = tuple(
            Sentence(
                text=s.text,
                start_ms=s.start,
                end_ms=s.end,
            )
            for s in (transcript_sentences or [])
        )

        return TranscriptionResult(
            text=transcript.text or "",
            words=words,
            sentences=sentences,
            language_code=transcript.language_code or "en",
            confidence=transcript.confidence or 0.0,
            duration_ms=int(transcript.audio_duration * 1000) if transcript.audio_duration else 0,
            audio_url=audio_url,
        )
