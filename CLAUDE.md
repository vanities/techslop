# CLAUDE.md

## Project

techslop — Automated Tech News YouTube Shorts pipeline. Ingests stories from HN, Reddit, TechCrunch, 4chan /g/, and X, generates scripts via OpenAI, synthesizes voice, assembles vertical video with animated captions, and publishes to YouTube/TikTok/Instagram/LinkedIn.

## Commands

```bash
# Run unit tests (fast, mocked)
uv run pytest tests/ --ignore=tests/integration -v

# Run integration tests (hits real APIs, ~40s)
uv run pytest tests/integration/ -v -s

# Run all tests
uv run pytest tests/ -v

# Pipeline CLI
uv run python pipeline.py ingest
uv run python pipeline.py list
uv run python pipeline.py show <ID_PREFIX>
uv run python pipeline.py script <ID_PREFIX>
uv run python pipeline.py voice <ID_PREFIX>
uv run python pipeline.py video <ID_PREFIX>
uv run python pipeline.py publish <ID_PREFIX>
```

## Architecture

```
pipeline.py              # Click CLI entry point, orchestrates all steps
techslop/
  config.py              # pydantic-settings, reads .env
  models.py              # Dataclasses: Story, Script, ScriptSection, VideoJob
  db.py                  # SQLite CRUD (stories + video_jobs tables)
  ingest/                # Source fetchers (all async, return list[Story])
    hackernews.py        # HN API + top 5 comments per story
    reddit.py            # Configurable subreddits via REDDIT_SUBREDDITS env
    techcrunch.py        # TechCrunch RSS
    fourchan.py          # 4chan /g/ catalog, keyword-filtered
    xtwitter.py          # Nitter RSS search (graceful fallback)
    scorer.py            # Normalize, weight by source, recency boost, dedup
    sources.py           # Registry, runs all sources via asyncio.gather
  scriptgen/
    generator.py         # OpenAI gpt-4o-mini → structured Script JSON
  voice/
    base.py              # TTSProvider ABC + factory
    edge.py              # edge-tts (free, default)
    openai.py            # OpenAI TTS
    elevenlabs.py        # Stub
    timestamps.py        # Whisper word-level timestamps
  video/
    assembler.py         # ffmpeg: background + audio + ASS captions → mp4
    captions.py          # ASS subtitle generation with karaoke \kf tags
    assets.py            # Pillow background gradient + title card
  publish/
    youtube.py           # YouTube Data API v3 resumable upload
    tiktok.py            # Stub
    instagram.py         # Stub
    linkedin.py          # Stub
```

## Key Patterns

- Story IDs are SHA-256 of the URL. CLI commands accept ID prefixes (first 12 chars).
- All ingest sources are async functions returning `list[Story]`. Add new sources to `sources.py` SOURCES list.
- Community context (comments, tweets) goes in `story.raw_data["comments"]` or `story.raw_data["tweet_text"]` — the script generator reads all of it.
- TTS provider is selected by `TTS_PROVIDER` env var. Add new providers by subclassing `TTSProvider`.
- Video assembly is a single ffmpeg command: looped background image + audio + burned-in ASS subtitles.
- Each story's artifacts live in `output/<id_prefix>/` (script.json, narration.mp3, timestamps.json, captions.ass, output.mp4).

## Config (.env)

- `OPENAI_API_KEY` — required for script generation
- `TTS_PROVIDER` — "edge" (default/free), "openai", "elevenlabs"
- `REDDIT_SUBREDDITS` — comma-separated subreddit names
- `FOURCHAN_KEYWORDS` — comma-separated keyword filters for /g/
- `X_KEYWORDS` — comma-separated X/Twitter search terms
- `DATABASE_PATH` — SQLite file path (default: techslop.db)
- `OUTPUT_DIR` — output directory (default: output)

## Style

- Python 3.12+, type hints, `from __future__ import annotations`
- Use `uv` for all package management, never pip
- Use `datetime.now(timezone.utc)` not `datetime.utcnow()`
- Async sources, sync video/db operations
- Tests use pytest + pytest-asyncio, mock external APIs in unit tests
