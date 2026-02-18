"""Project-wide configuration using dynaconf."""

import os
from pathlib import Path

from dynaconf import Dynaconf

_root = Path(os.environ.get("LAMBDA_TASK_ROOT", "."))

settings = Dynaconf(
    envvar_prefix="APP",
    root_path=_root,
    settings_files=["settings.toml", ".secrets.toml"],
    environments=True,
    load_dotenv=True,
    default_env="development",
    # Database
    database_url="postgresql://scraper:scraper@localhost:5432/scraper",
    # Redis
    redis_url="redis://localhost:6379/0",
    cache_ttl_seconds=3600,
    rate_limit_window_seconds=1,
    # STT
    stt_rate_limit_requests=5,
    stt_language_code="en_us",
    stt_speaker_labels=False,
    stt_punctuate=True,
    stt_format_text=True,
)
