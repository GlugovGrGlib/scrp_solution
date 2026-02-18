"""AWS Lambda handler for STT service."""

import json
import logging
from typing import Any

from core.cache import create_cache
from core.db import create_failure, get_item, update_item_status
from stt.service import TranscriptionError, TranscriptionService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_service: TranscriptionService | None = None


def get_service() -> TranscriptionService:
    """Get or create service instance (singleton for Lambda warmth)."""
    global _service
    if _service is None:
        _service = TranscriptionService()
    return _service


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """
    Lambda handler for audio transcription.

    Expected event format (from Step Functions):
    {
        "campaign_id": "uuid",
        "item_id": "uuid"
    }

    Returns:
        Lambda response with statusCode and body
    """
    campaign_id = event.get("campaign_id")
    item_id = event.get("item_id")

    if not campaign_id or not item_id:
        return _error_response(400, "INVALID_INPUT", "campaign_id and item_id required")

    item = get_item(item_id)
    if not item:
        return _error_response(404, "ITEM_NOT_FOUND", f"Item {item_id} not found")

    if item.campaign_id != campaign_id:
        return _error_response(400, "INVALID_INPUT", "Item does not belong to campaign")

    if not item.audio_url:
        _log_failure(item_id, campaign_id, "NO_AUDIO_URL", "Item has no audio_url set")
        update_item_status(item_id, "failed")
        return _error_response(422, "NO_AUDIO_URL", "Item has no audio_url set")

    update_item_status(item_id, "processing")

    try:
        service = get_service()
        result = service.transcribe(item.audio_url)

        cache = create_cache()
        if cache:
            cache.set(f"stt:result:{item_id}", result.to_dict())

        update_item_status(item_id, "completed")
        logger.info("Transcription completed for item %s", item_id)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "item_id": item_id,
                    "campaign_id": campaign_id,
                    "status": "completed",
                    "duration_ms": result.duration_ms,
                    "confidence": result.confidence,
                }
            ),
        }

    except TranscriptionError as e:
        logger.error("Transcription failed for item %s: %s", item_id, e)
        _log_failure(item_id, campaign_id, e.error_code, str(e))
        update_item_status(item_id, "failed")
        return _error_response(422, e.error_code, str(e), item_id, campaign_id)

    except Exception as e:
        logger.exception("Unexpected error for item %s", item_id)
        _log_failure(item_id, campaign_id, "INTERNAL_ERROR", str(e))
        update_item_status(item_id, "failed")
        return _error_response(500, "INTERNAL_ERROR", str(e), item_id)


def _error_response(
    status: int,
    error: str,
    message: str,
    item_id: str | None = None,
    campaign_id: str | None = None,
) -> dict[str, Any]:
    """Build error response."""
    body: dict[str, Any] = {"error": error, "message": message}
    if item_id:
        body["item_id"] = item_id
    if campaign_id:
        body["campaign_id"] = campaign_id
    return {"statusCode": status, "body": json.dumps(body)}


def _log_failure(item_id: str, campaign_id: str, error: str, message: str) -> None:
    try:
        create_failure(item_id, campaign_id, "stt", error, message)
    except Exception:
        logger.exception("Failed to log failure record")
