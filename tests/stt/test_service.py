"""Tests for STT service."""

from unittest.mock import MagicMock, patch

import pytest

from stt.service import TranscriptionError, TranscriptionService


@pytest.fixture
def mock_deps():
    with (
        patch("stt.service.settings") as mock_settings,
        patch("stt.service.create_cache") as mock_create_cache,
        patch("stt.service.cache_key") as mock_cache_key,
        patch("stt.service.aai") as mock_aai,
    ):
        mock_settings.assemblyai_api_key = "test-key"
        mock_settings.language_code = "en"
        mock_settings.speaker_labels = False
        mock_settings.punctuate = True
        mock_settings.format_text = True
        mock_settings.rate_limit_requests = 5

        cache = MagicMock()
        cache.get.return_value = None
        mock_cache_key.return_value = "test:key"
        mock_create_cache.return_value = cache

        transcript = MagicMock()
        transcript.text = "Hello world."
        transcript.words = [MagicMock(text="Hello", start=0, end=500, confidence=0.95)]
        transcript.sentences = [MagicMock(text="Hello world.", start=0, end=1000)]
        transcript.language_code = "en"
        transcript.confidence = 0.93
        transcript.audio_duration = 1.0
        transcript.error = None
        mock_aai.TranscriptStatus.error = "error"
        mock_aai.Transcriber.return_value.transcribe.return_value = transcript

        yield {
            "settings": mock_settings,
            "cache": cache,
            "cache_key": mock_cache_key,
            "aai": mock_aai,
            "transcript": transcript,
        }


class TestTranscriptionService:
    def test_transcribe_success(self, mock_deps):
        service = TranscriptionService()
        result = service.transcribe("https://example.com/audio.mp3")

        assert result.text == "Hello world."
        assert result.confidence == 0.93
        mock_deps["cache"].set.assert_called_once()

    def test_transcribe_cache_hit(self, mock_deps, sample_transcription_dict):
        mock_deps["cache"].get.return_value = sample_transcription_dict

        service = TranscriptionService()
        result = service.transcribe("https://example.com/audio.mp3")

        assert result.text == "Hello world."
        mock_deps["aai"].Transcriber.assert_not_called()

    def test_transcribe_no_speech(self, mock_deps):
        mock_deps["transcript"].text = ""

        service = TranscriptionService()

        with pytest.raises(TranscriptionError) as exc:
            service.transcribe("https://example.com/audio.mp3")

        assert exc.value.error_code == "NO_SPEECH_DETECTED"

    def test_transcribe_api_error(self, mock_deps):
        mock_deps["transcript"].status = mock_deps["aai"].TranscriptStatus.error
        mock_deps["transcript"].error = "API error"

        service = TranscriptionService()

        with pytest.raises(TranscriptionError) as exc:
            service.transcribe("https://example.com/audio.mp3")

        assert exc.value.error_code == "STT_FAILED"

    @patch("stt.service.time.sleep")
    def test_max_retries_exceeded(self, _, mock_deps):
        error_transcript = MagicMock()
        error_transcript.status = mock_deps["aai"].TranscriptStatus.error
        error_transcript.error = "rate limit exceeded"
        mock_deps["aai"].Transcriber.return_value.transcribe.return_value = error_transcript

        service = TranscriptionService()

        with pytest.raises(TranscriptionError) as exc:
            service.transcribe("https://example.com/audio.mp3")

        assert exc.value.error_code == "RATE_LIMITED"
