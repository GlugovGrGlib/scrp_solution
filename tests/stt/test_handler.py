"""Tests for STT Lambda handler."""

from unittest.mock import MagicMock, patch

import pytest

from stt.handler import handler


@pytest.fixture
def mock_item():
    item = MagicMock()
    item.id = "item-123"
    item.campaign_id = "campaign-456"
    item.audio_url = "https://example.com/audio.mp3"
    return item


class TestHandler:
    def test_missing_ids(self):
        result = handler({"item_id": "123"}, None)
        assert result["statusCode"] == 400

        result = handler({"campaign_id": "456"}, None)
        assert result["statusCode"] == 400

    @patch("stt.handler.get_item")
    def test_item_not_found(self, mock_get_item):
        mock_get_item.return_value = None

        result = handler({"campaign_id": "456", "item_id": "123"}, None)

        assert result["statusCode"] == 404

    @patch("stt.handler.update_item_status")
    @patch("stt.handler.create_failure")
    @patch("stt.handler.get_item")
    def test_no_audio_url(self, mock_get_item, mock_create_failure, _, mock_item):
        mock_item.audio_url = None
        mock_get_item.return_value = mock_item

        result = handler({"campaign_id": "campaign-456", "item_id": "item-123"}, None)

        assert result["statusCode"] == 422
        assert "NO_AUDIO_URL" in result["body"]

    @patch("stt.handler.create_cache")
    @patch("stt.handler.get_service")
    @patch("stt.handler.update_item_status")
    @patch("stt.handler.get_item")
    def test_success(self, mock_get_item, _, mock_get_service, mock_cache, mock_item):
        mock_get_item.return_value = mock_item
        mock_result = MagicMock()
        mock_result.duration_ms = 1000
        mock_result.confidence = 0.95
        mock_result.to_dict.return_value = {"text": "Hello"}
        mock_get_service.return_value.transcribe.return_value = mock_result
        mock_cache.return_value = MagicMock()

        result = handler({"campaign_id": "campaign-456", "item_id": "item-123"}, None)

        assert result["statusCode"] == 200
        assert "completed" in result["body"]
