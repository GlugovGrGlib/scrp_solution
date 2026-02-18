# Media Scraper Solution

[![Lint](https://github.com/GlugovGrGlib/scrp_solution/actions/workflows/ci.yml/badge.svg?branch=main&event=push&job=lint)](https://github.com/GlugovGrGlib/scrp_solution/actions/workflows/ci.yml)
[![Type Check](https://github.com/GlugovGrGlib/scrp_solution/actions/workflows/ci.yml/badge.svg?branch=main&event=push&job=typecheck)](https://github.com/GlugovGrGlib/scrp_solution/actions/workflows/ci.yml)
[![Tests](https://github.com/GlugovGrGlib/scrp_solution/actions/workflows/ci.yml/badge.svg?branch=main&event=push&job=test)](https://github.com/GlugovGrGlib/scrp_solution/actions/workflows/ci.yml)

Social media content analysis system.

## Architecture

![System Architecture](docs/solution-diagram-export-white.png)

This module is part of a larger social media content analysis pipeline. See [Solution Design](docs/0001_Social_Media_Scraper_Solution_Design.md) for full documentation, or view the [interactive diagram on Eraser](https://app.eraser.io/workspace/N6NkfzhR77JTLJ53atft?origin=share).

## Project

Audio transcription service using [AssemblyAI](https://www.assemblyai.com/) for the STT step of the AI Pipeline.

## Configuration

Uses [dynaconf](https://github.com/dynaconf/dynaconf) for settings management.

Create `.secrets.toml` with your API keys (git-ignored):

```toml
[default]
stt_assemblyai_api_key = "your_key"

[development]
stt_assemblyai_api_key = "your_key"
```

Default settings in `settings.toml`:

```toml
[default]
database_url = "postgresql://scraper:scraper@localhost:5432/scraper"
redis_url = "redis://localhost:6379/0"
cache_ttl_seconds = 3600
stt_rate_limit_requests = 5

# Service invocation mode: "direct", "http", or "step"
invoke_mode = "direct"
stt_service_url = "http://localhost:5001"
stt_state_machine_arn = ""

[development]
invoke_mode = "http"
stt_service_url = "http://stt:5001"

[production]
invoke_mode = "step"
stt_state_machine_arn = "arn:aws:states:REGION:ACCOUNT:stateMachine:stt-pipeline"
```

### Invoke Modes

| Mode | Description |
|------|-------------|
| `direct` | Calls STT handler function directly (same process) |
| `http` | Calls STT container via HTTP (local development) |
| `step` | Starts AWS Step Functions execution (production) |

## Local Development

```bash
docker compose up
```

This starts PostgreSQL, Redis, the Flask API (port 5000), and the STT service (port 5001).

## API Endpoints

### Create Campaign

```bash
curl -X POST http://localhost:5000/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-campaign",
    "items": [
      {
        "source_url": "https://example.com/video",
        "audio_url": "https://example.com/audio.wav",
        "type": "video"
      }
    ]
  }'
```

When items include an `audio_url`, STT processing is automatically triggered.

### Get Campaign

```bash
curl http://localhost:5000/campaigns/<campaign_id>
```

Returns campaign with items and transcription results:

```json
{
  "id": "uuid",
  "name": "my-campaign",
  "status": "pending",
  "items": [
    {
      "id": "uuid",
      "status": "completed",
      "audio_url": "...",
      "result": {
        "text": "Transcribed text...",
        "words": [...],
        "sentences": [...],
        "confidence": 0.97,
        "duration_ms": 103200
      }
    }
  ]
}
```

### Health Check

```bash
curl http://localhost:5000/health
```

## Testing

```bash
uv sync --all-extras
uv run pytest
```

Run with coverage:

```bash
uv run pytest --cov=stt --cov-report=term-missing
```

Run CI checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy core stt
uv run pytest
```

## Deploy

Uses AWS SAM with container images:

```bash
sam build
sam deploy --guided
```

## Project Structure

```
core/
├── config.py     # dynaconf settings
├── cache.py      # Redis caching + rate limiting
├── db.py         # SQLAlchemy database client
├── models.py     # Campaign, ContentItem, Failure
├── api.py        # Flask API for local dev
└── invoker.py    # STT invocation utility (http/direct/step)

stt/
├── models.py     # TranscriptionResult, Word, Sentence
├── service.py    # AssemblyAI client with retry logic
├── handler.py    # Lambda entry point
└── server.py     # HTTP server for local development

tests/
└── stt/
    ├── test_service.py
    └── test_handler.py
```

## License

MIT
