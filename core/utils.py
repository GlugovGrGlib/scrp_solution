"""Shared utilities."""

import json
from datetime import datetime
from typing import Any

from flask import Response


def json_response(data: dict[str, Any], status: int = 200) -> Response:
    """Create a Flask JSON response."""
    return Response(json.dumps(data), status=status, mimetype="application/json")


def lambda_response(data: dict[str, Any], status: int = 200) -> dict[str, Any]:
    """Create an AWS Lambda response."""
    return {"statusCode": status, "body": json.dumps(data)}


def to_dict(obj: Any) -> dict[str, Any]:
    """Serialize SQLAlchemy model to dictionary."""
    result: dict[str, Any] = {}
    for c in obj.__table__.columns:
        value = getattr(obj, c.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        result[c.name] = value
    return result
