# techslop

Automated Tech News YouTube Shorts Pipeline. Ingests tech news from multiple sources, generates short-form video scripts with AI, synthesizes voice, assembles vertical video with animated captions, and publishes to YouTube Shorts.

## Setup

```bash
# Clone
git clone https://github.com/vanities/techslop.git
cd techslop

# Install dependencies
uv sync

# Configure
cp .env.example .env
# Edit .env with your API keys
```

### Required API Keys

- **OPENAI_API_KEY** - For script generation (required)
- **YouTube OAuth** - For publishing (optional, needed for `run` command)

### System Requirements

- Python 3.12+
- ffmpeg (for video assembly)
- uv (Python package manager)

## Usage

```bash
# Fetch and score stories from all sources
uv run python pipeline.py ingest

# Show stories and their statuses
uv run python pipeline.py list

# Generate a video preview (no upload)
uv run python pipeline.py preview

# Full pipeline: ingest → script → voice → video → upload
uv run python pipeline.py run

# Process multiple stories
uv run python pipeline.py preview --count 3
```

## Sources

- **Hacker News** - Top stories via Firebase API
- **Reddit** - r/technology, r/programming RSS feeds
- **TechCrunch** - RSS feed

## TTS Providers

Set `TTS_PROVIDER` in `.env`:

| Provider | Key | Cost |
|----------|-----|------|
| `edge` | None needed | Free (default) |
| `openai` | `OPENAI_API_KEY` | Paid |
| `elevenlabs` | `ELEVENLABS_API_KEY` | Paid (stub) |

## Docker

```bash
# Build and run
docker compose build
docker compose run techslop ingest
docker compose run techslop preview

# Run with cron (every 6 hours)
docker compose up cron -d
```

## Pipeline Steps

1. **Ingest** - Fetch stories from HN, Reddit, TechCrunch
2. **Score** - Normalize scores, apply source weights, recency boost, dedup
3. **Script** - Generate 30-45s YouTube Shorts script via OpenAI
4. **Voice** - Synthesize narration with edge-tts (or OpenAI/ElevenLabs)
5. **Timestamps** - Extract word-level timestamps with Whisper
6. **Captions** - Generate ASS subtitles with karaoke-style word highlighting
7. **Video** - Assemble with ffmpeg (background + audio + captions + branding)
8. **Publish** - Upload to YouTube Shorts

## Project Structure

```
techslop/
├── pipeline.py              # CLI entry point
├── techslop/
│   ├── models.py            # Dataclasses: Story, Script, VideoJob
│   ├── config.py            # Settings from .env
│   ├── db.py                # SQLite schema + CRUD
│   ├── ingest/              # News source fetchers + scoring
│   ├── scriptgen/           # OpenAI script generation
│   ├── voice/               # TTS providers + Whisper timestamps
│   ├── video/               # ffmpeg assembly + ASS captions
│   └── publish/             # YouTube upload + stubs
├── Dockerfile
├── docker-compose.yml
└── output/                  # Generated videos (gitignored)
```
