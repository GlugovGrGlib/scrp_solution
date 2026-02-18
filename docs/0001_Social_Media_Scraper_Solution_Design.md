# Social Media Scraper Solution

## Date
02/16/2026

## Status
Proposed

## Context
This document outlines the system design for a data processing system that ingests data from TikTok, Instagram, and other social media websites. It processes it through a defined AI pipeline, aggregates data, and provides an API with structured JSON and a human-readable summary. The system is built using Python and leverages AWS services, including Lambda and S3.

---

# 1. System Design


## 1.1 Requirements Analysis
Complete requirements can be found in [﻿docs.google.com/document/d/17o0P6b3XbjW2ZP_VN_YSp67NBE8zqA1tgRMsk9Y5qak/edit?tab=t.0](https://docs.google.com/document/d/17o0P6b3XbjW2ZP_VN_YSp67NBE8zqA1tgRMsk9Y5qak/edit?tab=t.0) 

### Assumptions
1. The goal of the system is to analyze the content of the selected creators on TikTok.
2. AI pipelines and platform scraping algorithms will rely on 3rd party services.
3. Content processing and analysis is optimized for the English language.
4. The processing will be performed in batches per campaign.
5. There won't be a major loading on the system during the first phase. The main concern is the availability of 3rd-party APIs.
6. Partial results for the visual analysis are acceptable.
7. Content analysis criteria thresholds are hardcoded for the initial implementation and can't be adjusted from the admin UI.


### Out-of-scope items
- Support for Instagram or other social media platforms is out of scope but is expected in the future via 3rd party or custom-built tools.
- Concurrent processing of multiple campaigns, scaling of the AI pipeline.
- Historical data and archive storage.


## 1.2 Architecture Characteristics
Based on the requirements and architecture assumptions, the following quality attributes should be prioritized:



- Accuracy - constant false alarms may cause reviewers to spend too much time reviewing content that should have been in a different category. Also, frequent false alarms cause reviewers to ignore warnings.
- Cost Efficiency - The dependency on 3rd-party API calls across multiple services without controls could consume the whole budget per one campaign.
- Extensibility - solution should be developed with the ease of extensibility in mind. Both for the enhancements of the initial analysis pipeline and for 3rd-party services and APIs integrations. As requirements will be changing along with the product adoption.
- Maintainability - When 3rd-party provides changes to their API or raises prices, updating or swapping providers shouldn't require refactoring half the system.
- Auditability - Flagged content may be disputed. The system must preserve evidence (scores, timestamps, source artifacts) to justify why a decision was made.
- Fault-tolerance - 3rd-party API failures are possible. The system must return partial results and clearly indicate what failed rather than blocking entire campaign analysis.


## 1.3 Technical Decisions Rationale
### High-level description of the system architecture
The system follows a serverless orchestration pattern built on AWS.

The architecture separates concerns between API handling (API Gateway, Flask), AI pipeline workflow orchestration (Step Functions), and AI pipeline task execution (Lambda).

This approach provides the minimum time to market for the initial setup and deployment, cost efficiency for batch workloads, and flexibility for future scaling.

### Key components and their responsibilities
| Category | Technology | Purpose |
| ----- | ----- | ----- |
| Hosting | AWS | Apps deployment, services and infrastructure management |
| API Management | AWS API Gateway | Rate limiting, auth, request validation |
| Storage | AWS S3 | Blob storage for raw media and text files |
| Database | PostgreSQL | Campaign metadata, analysis results, audit trail |
| Cache / NoSQL Storage | Redis | 3P API rate limiting, response cache, progress tracking |
| Orchestration | AWS Step Functions | Pipeline coordination, retries, parallel processing |
| Compute | AWS Lambda | Stateless workers for each pipeline stage |
| Backend | Python / Flask | Core app API layer and request handling |
| Frontend | AWS Amplify / AstroJS | Simple static web app with usable UI |
| AI Pipeline (scraping) | Apify (3P) | Content fetching from the social media platforms |
| AI Pipeline (video proc) | FFmpeg (Lambda layer) | Segmentation, FPS reduction, A/V split |
| AI Pipeline (transcription) | AssemblyAI (3P) | Audio-to-text transformation with timestamps |
| AI Pipeline (visual) | Sightengine (3P) | Safety scoring of the visual content |
| AI Pipeline (NLP) | Claude AI (3P) | Result summarization and NLP |

**Flask API Backend**

 The core application is built with Flask and serves as the central API layer. Flask was chosen over a pure FaaS or BaaS solution for several reasons:

- It provides a unified codebase that can run locally for development and testing
- Unlimited and low-effort customization possibilities for the future user-facing web application
- Acts as the integration point between frontend requests and Step Functions execution
- Simplifies future migration path when Lambda-based pipeline stages need to be replaced with containerized microservices. The Flask app remains the stable API interface

**AWS API Gateway**

 API Gateway is an important element of any modern solution. It's placed in front of the Flask backend to provide:

- Rate limiting to prevent abuse and control costs
- API key management for partner access
- Request/response logging for debugging
- SSL termination and DDoS protection

**AWS Step Functions**

 Step Functions orchestrate the AI pipeline execution. Each campaign analysis triggers a state machine that:

- Coordinates the sequence of Lambda invocations
- Handles parallel processing of multiple content items
- Manages retries and error states without custom code
- Provides visual debugging and execution history

**AWS Lambda Functions**

 Individual pipeline stages run as Lambda functions:

- scraper - fetches content from social platforms via Apify
- video_processor - splits video, reduces frame rate, extracts audio
- stt - sends audio to AssemblyAI for transcription
- visual_analysis - sends frames to Sightengine for safety scoring
- ai_summary - generates human-readable report via Anthropic API

**Data Storage Solutions**

- **Amazon RDS (PostgreSQL)** - stores campaign metadata, analysis results, and audit records
- **Amazon MemoryDB for Redis** - handles rate limiting for 3rd-party APIs, caches API responses, tracks real-time processing progress
- **Amazon S3** - stores raw media files, extracted frames, audio segments, and serves as backup storage for other databases.


## 1.4 REST API Structure
The following minimal API structure is suggested for the initial solution.

### POST /campaigns
Initiates a new campaign analysis. Name and Source URLs list is mandatory. Source URLs can be for profiles as well as for posts or videos. In case any of the source URLs is a profile URL, it's possible to specify additional optional fields to define what parts of the content should be processed, with default sorting from the latest to the oldest. 

The API validates the request, creates a campaign record in the database, and triggers the Step Functions state machine. Processing happens asynchronously, and the endpoint returns results immediately with an identifier to track the progress.

**Request:**

```
{
  "name": "string",
  "source_urls": ["string"],
  "options": {
    "date_from": "string (ISO 8601, optional)",
    "date_to": "string (ISO 8601, optional)",
    "max_items": "integer (optional)"
  }
}
```
**Response:** 200 OK

```
{
  "campaign_id": "string",
  "execution_id": "string",
  "status": "string (pending | processing | completed | failed)",
  "created_at": "string (ISO 8601)"
}
```
**Errors:**400 Bad Request

---

### GET /campaigns/{campaign_id}/status
Returns current processing progress. The frontend polls this endpoint to display real-time status updates. Progress data is read from Redis for fast response times. Percent indicates overall completion (0-100) calculated from the initial item count returned by the scraper.

**Response:** 200 OK

```
{
  "campaign_id": "string",
  "status": "string (pending | processing | completed | failed)",
  "progress": {
    "stage": "string",
    "percent": "integer"
  },
  "updated_at": "string (ISO 8601)"
}
```
**Errors:**404 Not Found

---

### GET /campaigns/{campaign_id}/results
Returns complete analysis results. This endpoint reads from PostgreSQL and returns the full analysis payload, including aggregated scores, per-item breakdowns, AI-generated summary, and any failures.

**Response:** 200 OK

```
{
  "campaign_id": "string",
  "status": "string",
  "summary": {
    "overall_status": "string (safe | warning | unsafe)",
    "overall_visual_score": "integer",
    "overall_text_score": "integer",
    "ai_summary": "string"
  },
  "visual_analysis": [
    {
      "category": "string",
      "score": "integer",
      "status": "string (safe | warning| unsafe)"
    }
  ],
  "text_analysis": [
    {
      "category": "string",
      "score": "integer",
      "status": "string (safe | warning | unsafe)",
      "recommendation": "string (optional)"
    }
  ],
  "content_items": [
    {
      "item_id": "string",
      "source_url": "string",
      "type": "string (video | image | text)",
      "visual_score": "integer",
      "text_score": "integer",
      "status": "string (safe | warning| unsafe)",
      "flags_count": "integer"
    }
  ],
  "failures": [
    {
      "item_id": "string",
      "source_url": "string",
      "error": "string",
      "message": "string",
      "stage": "string"
    }
  ]
}
```
**Errors:**404 Not Found, 409 Conflict (if processing in progress)



### GET /campaigns/{campaign_id}/items/{item_id}
Returns detailed analysis for a single content item. Use this endpoint to get information about specific items that have warnings. Includes full flag details with timestamps and evidence links for audit purposes.

**Response:** 200 OK

```
{
  "item_id": "string",
  "campaign_id": "string",
  "source_url": "string",
  "type": "string (video | image | text)",
  "duration_sec": "integer (optional, for video)",
  "visual_score": "integer (0-100)",
  "text_score": "integer (0-100)",
  "status": "string (safe | warning)",
  "transcript": "string (optional)",
  "flags": [
    {
      "category": "string",
      "score": "integer (0-100)",
      "status": "string (safe | warning)",
      "timestamp_ms": "integer (optional)",
      "evidence": "string"
    }
  ],
  "analyzed_at": "string (ISO 8601)"
}
```
**Errors:**404 Not Found

---

## 1.5 Data Flow
As you can see on the architecture diagram, the numbered flow represents the following data flow [﻿View on canvas](https://app.eraser.io/workspace/N6NkfzhR77JTLJ53atft?elements=3bpr9vnP2NLooOsxUxLwWg).

1. User provides campaign parameters through the Frontend (AWS Amplify) and later accesses results through the same interface.
2. The Frontend sends REST API requests to the Flask backend for campaign submission and results retrieval.
3. Flask validates the request, stores initial campaign data in PostgreSQL, and triggers the Step Functions state machine.
4. The state machine coordinates the execution of Lambda functions in sequence of the AI Pipeline. Detailed decomposition of the flow can be seen in section 2. Data Pipeline Definition.
5. During processing, Lambda workers use MemoryDB (Redis) for rate limiting 3rd-party API calls and storing real-time progress updates. Analysis scores, transcripts, and metadata are persisted to Redis after each pipeline stage for the final aggregation.
6. Raw content, images, extracted frames, and audio files are stored in S3 for processing and verification purposes.
7. Final aggregated analysis scores, transcripts, summaries, and metadata are persisted to PostgreSQL after the AI pipeline is finished.
8. When the frontend polls for status, Flask reads the current progress from Redis for real-time updates. As status is updated to completed, the frontend issues a request to get the final result, and the Flask app collects data from PostgreSQL and Redis to build an API response.
## 1.6 AI Tools Usage
The AI pipeline relies on four 3rd-party services, each handling a specific processing stage.

### Apify (Content Scraping)
Apify is a web scraping and automation platform that provides an API for the many social media platforms and other websites.

Our Scraper Lambda Function uses Apify to fetch videos, images, and metadata from TikTok creator profiles. The Lambda triggers an Apify actor (such as clockworks/tiktok-scraper) with the profile URL and date filters, then polls asynchronously until completion. Once complete, the Lambda downloads media files to S3 and stores metadata (captions, hashtags, publish dates, engagement metrics) in Redis and PostgreSQL.

Key limitations include geo-restricted content and whether a profile is private or not found. If some posts are blocked, the pipeline continues with available content and logs skipped items.

### AssemblyAI (Speech-to-Text)
The STT Lambda sends extracted audio files to AssemblyAI for transcription with word-level timestamps. After the video processor extracts and uploads audio to S3, the Lambda submits the S3 presigned URL to AssemblyAI's transcript endpoint. The API returns a transcript ID immediately, and the Lambda polls until processing completes.

The final output includes full transcript text, per-word timestamps (start_ms, end_ms), confidence scores, and detected language. We can map these timestamps directly to the original video timeline for linking flagged speech to specific parts of the video.

The system is optimized for English mainly, and other languages may have lower accuracy. If no speech is detected or audio is too short, the item is marked, and the pipeline continues. Important note: background music and overlapping speakers may reduce accuracy.

### Sightengine (Visual Analysis)
Sightengine is a content moderation API that uses AI and machine learning to automatically detect inappropriate, unsafe, or unwanted content in images, videos, and text.

The Visual Analysis Lambda sends extracted frames to Sightengine for safety scoring across five categories:

- adult content
- violence/weapons
- hate content
- medical/gore
- spoof/fake
Raw scores (0.0-1.0) are transformed to safety percentages, and raw responses are persisted in S3 for audit purposes.

Error handling follows a partial-success pattern: rate limits trigger backoff and retry. Model failures are skipped and logged.

### Anthropic Claude API (Summarization)
The AI Summary Lambda calls Claude to generate a human-readable summary with actionable recommendations. The Lambda aggregates all results from PostgreSQL, like campaign metadata, overall scores, flagged categories with counts, and sample evidence. Then it incorporates it into a structured prompt for the Claude API. The API returns an executive summary, key findings, a risk level assessment, and recommended actions. The prompt explicitly instructs Claude to be transparent and avoid making assumptions. If the context exceeds limits, evidence samples are truncated.

If Claude is unavailable after retries, the system returns results without the AI summary with the status failed.

## 1.7 Error Handling and Retries
AWS Step Functions provides built-in error handling through state
 machine configuration. Lambda functions use Redis to cache intermediate
 results and track progress, enabling the pipeline to resume from the
 last successful stage after a failure.

AWS Step Functions can handle out of the box:

- Automatic retries - Each Lambda invocation can be configured with retry policies including maximum attempts, backoff intervals, and exponential backoff rates. Transient failures (timeouts, throttling) are retried automatically.
- Error catching - States can define catch blocks that route specific error types to fallback states. This allows the pipeline to continue with partial results when non-critical steps fail.
- Parallel fault isolation - When processing multiple content items in parallel (using Map state), individual item failures don't block other items. Failed items are recorded and the pipeline continues.
- Execution history - Step Functions maintains detailed execution logs for each state transition, making it straightforward to identify where failures occurred and why.
- Dead-letter handling - Permanently failed items are logged with full error context and excluded from aggregation. The final results clearly indicate which items failed and at which stage.
# 2. Data Pipeline Definition
This section expands farther into the architecture of the AI pipeline, as well as the data structures used.

## 2.1 Pipeline Input Format
The pipeline accepts campaign requests through the Flask API.

**Campaign Creation Request:**

```json
{
  "name": "string",
  "source_urls": ["string"],
  "options": {
    "date_from": "string (ISO 8601, optional)",
    "date_to": "string (ISO 8601, optional)",
    "max_items": "integer (optional, default: 100)"
  }
}
```
Source URLs can be profile URLs (e.g., `https://tiktok.com/@username`) or direct content URLs. The API validates URLs and creates a pipeline execution record with generated `campaign_id` and `execution_id`.

Upon receiving a valid request, the Flask API generates a `campaign_id` , creates a campaign record in PostgreSQL, starts a Step Functions state machine execution, and records an `execution_id` in the DB. Afterward, returns both identifiers to the client.

Step Functions orchestrate the pipeline sequence but do not manage data flow. Each Lambda receives only `campaign_id` and `item_id` references, reads input from PostgreSQL, Redis, or S3, and writes output back. This decouples orchestration from data transfer and avoids payload limits.

Types of progress data stored in Redis during AI pipeline execution:

- Current pipeline stage and percent complete
- Per-item processing status
- Individual frame scores before aggregation
- Transcript text and word timestamps
- Rate limit counters for 3rd-party APIs
The pipeline continues processing when individual items or stages fail. Failed items are excluded from score aggregation.

When items have stage-level failures, the response includes a `partial_analysis` object indicating which stage failed and why.

Failure log record example:

```json
{
  "item_id": "string",
  "campaign_id": "string",
  "source_url": "string",
  "error": "string (error code)",
  "message": "string",
  "stage": "string (scraper | video_processor | stt | visual_analysis | ai_summary)",
  "details": "object (optional)",
  "failed_at": "string (ISO 8601)",
  "retries_attempted": "integer"
}
```
Example error codes: SCRAPER_FAILED, DOWNLOAD_FAILED, VIDEO_PROCESSING_FAILED, AUDIO_EXTRACTION_FAILED, STT_FAILED, NO_SPEECH_DETECTED, VISUAL_ANALYSIS_FAILED, RATE_LIMITED, TIMEOUT, SUMMARY_FAILED.

## 2.2 Transcript Structure
The STT Lambda submits audio to AssemblyAI, polls for completion, and stores the result. According to the [﻿API Reference](https://www.assemblyai.com/docs/api-reference/transcripts/submit), we need to submit an audio using a POST request to the endpoint[﻿api.assemblyai.com/v2/transcript ](https://api.assemblyai.com/v2/transcript).

The body can include the following fields:

```json
{
  "audio_url": "string (required)",
  "language_code": "string (en_us)",
  "language_detection": "boolean (optional)",
  "punctuate": "boolean (optional)",
  "speaker_labels": "boolean (optional)",
  "webhook_url": "string (optional)"
}
```
We are considering that audio was extracted from the video content using the Video Processor Lambda function, and the link to the media file in S3 is provided in the request.

According to the API Reference, the API returns an instant response with a transcript `id` and `status: queued`. The Lambda stores the response in Redis cache and polls `GET /v2/transcript/{id}` until status changes to `completed` or `error`.

Minimal response from the GET Transcript endpoint ([﻿API Reference](https://www.assemblyai.com/docs/api-reference/transcripts/get)):

```json
{
  "id": "string",
  "status": "string",
  "audio_url": "string",
  "audio_duration": "integer",
  "audio_start_from": "integer (optional)",
  "audio_end_at": "integer (optional)",
  "text": "string",
  "confidence": "number",
  "language_code": "string",
  "language_confidence": "number",
  "words": [
    {
      "text": "string",
      "start": "integer",
      "end": "integer",
      "confidence": "number",
      "speaker": "string (optional)"
    }
  ],
  "utterances": [
    {
      "speaker": "string",
      "text": "string",
      "start": "integer",
      "end": "integer",
      "confidence": "number",
      "words": ["array"]
    }
  ],
  "error": "string"
}
```
Optional feature results (when enabled in request):

- `entities`  - detected named entities with timestamps
- `content_safety_labels`  - content moderation results with severity scores
- `auto_highlights_result`  - key phrases with rankings
- `chapters`  - auto-generated chapter summaries
- `summary`  - text summary (when `summarization: true` )
- `sentiment_analysis_results`  - per-sentence sentiment
Word-level timestamps (`start`, `end`) enable linking flagged speech to specific video positions.

## 2.3 Moderation Results Structure
The Visual Analysis Lambda analyzes images, video frames, and text for restricted or sensitive content using [﻿Sightengine](https://sightengine.com/).

Sightengine provides a REST API for multiple use cases. Each request must specify the content type (image, text, or video) and the models for analysis.

The response will include scores and params for each model. Different models provide scores in their specific format. 

For the initial phase, we will focus on the following categories: adult content, violence/weapons, hate content, medical/gore, spoof/fake. Currently, Sightengine provides the following models for this category: nudity-2.1,weapon,violence,offensive-2.0,gore-2.0,medical,genai.

**Image Moderation** ([﻿docs](https://sightengine.com/docs/getstarted)):

```
POST https://api.sightengine.com/1.0/check.json
media={image_file} | url={image_url}
models=nudity-2.1,weapon,medical...
api_user={api_user}
api_secret={api_secret}
```
```json
{
  "status": "string",
  "request": { "id": "string", "timestamp": "number", "operations": "integer" },
  "media": { "id": "string", "uri": "string" },
  "nudity": { "prob": "score", ... },
  "weapon": { ... },
  "medical": { ... },
  ...
}
```
**Video Moderation** ([﻿docs](https://sightengine.com/docs/moderate-stored-video)):

Synchronous moderation works for videos under 60 seconds. Therefore, we should split longer videos into chunks on the previous stage.

```
POST https://api.sightengine.com/1.0/video/check-sync.json
media={video_file} | stream_url={video_url}
models=nudity-2.1,weapon,medical...
api_user={api_user}
api_secret={api_secret}
```
```json
{
  "status": "string",
  "request": { "id": "string", "timestamp": "number" },
  "media": { "id": "string", "uri": "string" },
  "data": {
    "frames": [
      {
        "info": { "id": "integer", "position": "number (seconds)" },
        "nudity": { "...": "model scores" },
        "weapon": { "...": "..." },
        ...
      }
    ]
  }
}
```
**Text Moderation** ([﻿docs](https://sightengine.com/docs/text-moderation-ml-models)):

```
POST https://api.sightengine.com/1.0/text/check.json
text={utf8_text}
mode=ml
models=sexual,discriminatory...
lang=en
api_user={api_user}
api_secret={api_secret}
```
```json
{
  "status": "string",
  "request": { "id": "string", "timestamp": "number" },
  "moderation_classes": {
    "available": ["array of active classes"],
    "sexual": "number (0.0-1.0)",
    "discriminatory": "number (0.0-1.0)",
    "insulting": "number (0.0-1.0)",
    "violent": "number (0.0-1.0)",
    "toxic": "number (0.0-1.0)",
    "self-harm": "number (0.0-1.0)"
  }
}
```
## 2.4 Final API response
Returned by `GET /campaigns/{campaign_id}/results`. 

```json
{
  "campaign_id": "string",
  "status": "string",
  "summary": {
    "overall_status": "string (safe | warning | unsafe)",
    "overall_visual_score": "integer",
    "overall_text_score": "integer",
    "ai_summary": "string"
  },
  "visual_analysis": [
    {
      "category": "string",
      "score": "integer",
      "status": "string (safe | warning| unsafe)"
    }
  ],
  "text_analysis": [
    {
      "category": "string",
      "score": "integer",
      "status": "string (safe | warning | unsafe)",
      "recommendation": "string (optional)"
    }
  ],
  "content_items": [
    {
      "item_id": "string",
      "source_url": "string",
      "type": "string (video | image | text)",
      "visual_score": "integer",
      "text_score": "integer",
      "status": "string (safe | warning| unsafe)",
      "flags_count": "integer"
    }
  ],
  "failures": [
    {
      "item_id": "string",
      "source_url": "string",
      "error": "string",
      "message": "string",
      "stage": "string"
    }
  ]
}
```
Overall scores are weighted averages with higher weight for adult_content, violence/hate_speech, and misinformation categories.

For even more detailed information on content items, each item's flags can be fetched using `GET /campaigns/{campaign_id}/items/{item_id}` .

```
{
  "item_id": "string",
  "campaign_id": "string",
  "source_url": "string",
  "type": "string (video | image | text)",
  "duration_sec": "integer (optional)",
  "visual_score": "integer (0-100)",
  "text_score": "integer (0-100)",
  "status": "string (safe | warning| unsafe)",
  "transcript": "string (optional)",
  "flags": [
    {
      "category": "string",
      "score": "integer (0-100)",
      "status": "string (safe | warning| unsafe)",
      "timestamp_ms": "integer (optional)",
      "evidence": "string"
    }
  ],
  "analyzed_at": "string"
}
```

# 3. Implementation Reference

https://github.com/GlugovGrGlib/scrp_solution

# 4. Optimization Notes
## **4.1 How to reduce latency**
The primary latency optimization opportunity is parallel execution of independent pipeline stages.

STT and visual analysis can run concurrently since neither depends on the other's output.

In addition, the major opportunity is to reduce the number of Sightengine API calls without sacrificing detection quality by reducing frame sampling and FPS. This way the same video can be processed much faster.

For the future high-traffic scenario, we can provision Lambda concurrently to eliminate cold start delays.

## 4.2 How to control AI-related costs
Cost control mainly depends on reducing the number of API calls.

Implement early termination logic that will skip remaining analysis if initial frames already exceed unsafe thresholds.

One of the advanced ideas is to use perceptual hashing for frame deduplication. Eventually, skipping near-identical frames can greatly save costs on visual analysis.

For summarization, it is possible to experiment with the models, context, and prompts to find the best balance between results quality and total price per campaign, which is determined by the number of tokens used.

## 4.3 What to improve next
Support for other social media platforms like Instagram via Apify's actors.

Allow admins to configure currently hardcoded thresholds from the admin UI.

Better UI for reviewers with detailed information on flags, including timestamps, evidence links, and context for each flagged item.

Webhooks for 3rd-party integration instead of polling. Most services, like AssemblyAI and Sightengine support delayed updates via callbacks. This can reduce unnecessary API calls.

As the project grows, we can migrate services one by one from Lambda to microservices. It would provide more control over scaling, deployment and optimization.

Monitoring and observability with dashboards for pipeline health, API usage, error rates, and cost tracking per campaign. Alerting on failures and budget thresholds.



