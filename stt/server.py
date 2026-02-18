"""HTTP server for STT service (local development)."""

import json
import logging

from flask import Flask, Response, request

from core.db import init_db
from core.utils import json_response
from stt.handler import handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.before_request
def ensure_db() -> None:
    if not getattr(app, "_db_initialized", False):
        init_db()
        app._db_initialized = True  # type: ignore[attr-defined]


@app.route("/invoke", methods=["POST"])
def invoke() -> Response:
    """Invoke STT handler via HTTP."""
    data = request.get_json()
    if not data:
        return json_response({"error": "Request body required"}, 400)

    result = handler(data, None)
    return json_response(json.loads(result["body"]), result["statusCode"])


def run() -> None:
    app.run(host="0.0.0.0", port=5001, debug=True)


if __name__ == "__main__":
    run()
