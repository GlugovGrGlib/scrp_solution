"""Flask API for local development and testing."""

import json
import logging
from typing import Any

from flask import Flask, Response, request

from core.db import (
    create_campaign,
    create_item,
    get_campaign,
    get_campaign_items,
    init_db,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


def json_response(data: dict[str, Any], status: int = 200) -> Response:
    return Response(json.dumps(data), status=status, mimetype="application/json")


def to_dict(obj: Any) -> dict[str, Any]:
    """Serializes object into dictionary."""
    from datetime import datetime

    result: dict[str, Any] = {}
    for c in obj.__table__.columns:
        value = getattr(obj, c.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        result[c.name] = value
    return result


@app.before_request
def ensure_db() -> None:
    if not getattr(app, "_db_initialized", False):
        init_db()
        app._db_initialized = True  # type: ignore[attr-defined]


@app.route("/campaigns", methods=["POST"])
def create_campaign_endpoint() -> Response:
    """
    Entry endpoint to create a new campaign for processing.
    As scrapping pipeline step is not implemented, the request should include
    audio_url to start the stt processing.
    """
    data = request.get_json()
    if not data or "name" not in data:
        return json_response({"error": "name is required"}, 400)

    campaign = create_campaign(data["name"])

    items = []
    items_with_audio = []
    for item_data in data.get("items", []):
        source_url = item_data.get("source_url", "")
        audio_url = item_data.get("audio_url")
        item_type = item_data.get("type", "video")
        item = create_item(campaign.id, source_url, item_type, audio_url)
        items.append(to_dict(item))
        if audio_url:
            items_with_audio.append(item)

    logger.info("Created campaign %s with %d items", campaign.id, len(items))

    # Invoke STT processing for items with audio URLs
    if items_with_audio:
        from core.invoker import invoke_stt

        for item in items_with_audio:
            logger.info("Invoking STT for item %s", item.id)
            invoke_stt(campaign.id, item.id)

    return json_response(
        {
            "campaign_id": campaign.id,
            "name": campaign.name,
            "status": campaign.status,
            "items": items,
        }
    )


@app.route("/campaigns/<campaign_id>", methods=["GET"])
def get_campaign_endpoint(campaign_id: str) -> Response:
    campaign = get_campaign(campaign_id)
    if not campaign:
        return json_response({"error": "Campaign not found"}, 404)

    from core.cache import create_cache

    cache = create_cache()
    items = get_campaign_items(campaign_id)

    items_with_results = []
    for item in items:
        item_dict = to_dict(item)
        if cache and item.status == "completed":
            result = cache.get(f"stt:result:{item.id}")
            if result:
                item_dict["result"] = result
        items_with_results.append(item_dict)

    return json_response(
        {
            **to_dict(campaign),
            "items": items_with_results,
        }
    )


@app.route("/health", methods=["GET"])
def health() -> Response:
    return json_response({"status": "ok"})


def run() -> None:
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    run()
