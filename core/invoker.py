"""Utility for invoking services via HTTP, direct function call, or Step Functions."""

import json
import logging
import uuid
from enum import StrEnum
from typing import Any

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


class InvokeMode(StrEnum):
    """Mode for invoking services."""

    HTTP = "http"
    DIRECT = "direct"
    STEP = "step"


def get_invoke_mode() -> InvokeMode:
    """Get the configured invoke mode."""
    mode = getattr(settings, "invoke_mode", "direct")
    return InvokeMode(mode)


def invoke_stt(campaign_id: str, item_id: str) -> dict[str, Any]:
    """
    Invoke STT processing for an item.

    Args:
        campaign_id: The campaign ID
        item_id: The item ID

    Returns:
        Response from the STT handler
    """
    mode = get_invoke_mode()
    event = {"campaign_id": campaign_id, "item_id": item_id}

    if mode == InvokeMode.HTTP:
        return _invoke_http(event)
    elif mode == InvokeMode.STEP:
        return _invoke_step_functions(event)
    else:
        return _invoke_direct(event)


def _invoke_http(event: dict[str, Any]) -> dict[str, Any]:
    """Invoke STT via HTTP request to the stt container."""
    stt_url = getattr(settings, "stt_service_url", "http://stt:5001")
    url = f"{stt_url}/invoke"

    logger.info("Invoking STT via HTTP: %s", url)

    try:
        response = httpx.post(url, json=event, timeout=300.0)
        return {
            "statusCode": response.status_code,
            "body": response.text,
        }
    except httpx.RequestError as e:
        logger.error("HTTP request to STT failed: %s", e)
        return {
            "statusCode": 503,
            "body": json.dumps({"error": "SERVICE_UNAVAILABLE", "message": str(e)}),
        }


def _invoke_direct(event: dict[str, Any]) -> dict[str, Any]:
    """Invoke STT handler directly (same process)."""
    from stt.handler import handler

    logger.info("Invoking STT directly")
    return handler(event, None)


def _invoke_step_functions(event: dict[str, Any]) -> dict[str, Any]:
    """Invoke STT via AWS Step Functions."""
    import boto3

    state_machine_arn = getattr(settings, "stt_state_machine_arn", "")
    if not state_machine_arn:
        logger.error("stt_state_machine_arn not configured")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "CONFIGURATION_ERROR",
                    "message": "stt_state_machine_arn not configured",
                }
            ),
        }

    logger.info("Invoking STT via Step Functions: %s", state_machine_arn)

    try:
        client = boto3.client("stepfunctions")
        execution_name = f"stt-{event['item_id']}-{uuid.uuid4().hex[:8]}"

        response = client.start_execution(
            stateMachineArn=state_machine_arn,
            name=execution_name,
            input=json.dumps(event),
        )

        return {
            "statusCode": 202,
            "body": json.dumps(
                {
                    "status": "started",
                    "execution_arn": response["executionArn"],
                    "item_id": event["item_id"],
                    "campaign_id": event["campaign_id"],
                }
            ),
        }
    except Exception as e:
        logger.error("Step Functions invocation failed: %s", e)
        return {
            "statusCode": 503,
            "body": json.dumps({"error": "STEP_FUNCTIONS_ERROR", "message": str(e)}),
        }
