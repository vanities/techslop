"""Settings loader with multi-channel support.

Pick which env file to load via the TECHSLOP_ENV var:

    TECHSLOP_ENV=swiftbible uv run python pipeline.py run   # loads .env.swiftbible
    TECHSLOP_ENV=techslop   uv run python pipeline.py run   # loads .env.techslop
    uv run python pipeline.py run                            # loads .env (default)

This lets the same pipeline drive multiple channels (techslop, swiftbible
devotionals, etc.) with separate API keys and posting accounts.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


def _resolve_env_file() -> str:
    name = os.environ.get("TECHSLOP_ENV", "").strip()
    if name:
        return f".env.{name}"
    return ".env"


_ENV_FILE = _resolve_env_file()
if Path(_ENV_FILE).exists():
    # override=True so switching channels mid-shell works as expected
    load_dotenv(_ENV_FILE, override=True)


class Settings(BaseSettings):
    # ── Script generation ────────────────────────────────────────────────
    openai_api_key: str = ""

    # ── TTS ──────────────────────────────────────────────────────────────
    tts_provider: str = "edge"  # edge | openai | elevenlabs | chatterbox
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""  # Cloned voice ID, when using elevenlabs

    # Chatterbox local TTS — point at a 30–60s wav of the target voice.
    # Empty = default Chatterbox voice.
    chatterbox_voice_ref: str = ""

    # ── Image generation (gpt-image-2 grid) ──────────────────────────────
    image_size: str = "2048x2048"  # gpt-image-2 size
    character_brief: str = ""  # one-line recurring character description

    # ── Motion (Kling i2v via fal.ai) ─────────────────────────────────────
    fal_key: str = ""
    motion_duration: str = "5"  # "5" or "10" seconds per Kling clip

    # ── YouTube ───────────────────────────────────────────────────────────
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_refresh_token: str = ""

    # ── TikTok Content Posting API ────────────────────────────────────────
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_refresh_token: str = ""

    # ── Instagram Graph API ──────────────────────────────────────────────
    instagram_access_token: str = ""
    instagram_page_id: str = ""  # IG Business Account ID, NOT the FB page
    # Template for the public HTTPS URL the IG Graph API can fetch the MP4 from.
    # Use a single {filename} placeholder. Example:
    #   https://my-bucket.s3.amazonaws.com/techslop/{filename}
    instagram_public_video_url_template: str = ""

    # ── LinkedIn UGC API ──────────────────────────────────────────────────
    linkedin_access_token: str = ""
    # urn:li:person:... or urn:li:organization:...
    linkedin_owner_urn: str = ""

    # ── Storage ───────────────────────────────────────────────────────────
    database_path: str = "techslop.db"
    output_dir: str = "output"

    # ── Source filters ────────────────────────────────────────────────────
    reddit_subreddits: str = (
        "technology,programming,machinelearning,artificial,LocalLLaMA,"
        "OpenAI,ClaudeAI,ChatGPT,singularity,ArtificialInteligence"
    )
    fourchan_keywords: str = (
        "AI,LLM,GPU,linux,rust,python,open source,self-hosted,homelab,programming"
    )
    x_keywords: str = (
        "AI breakthrough,new programming language,open source release,tech layoffs,GPU,LLM"
    )

    model_config = {"env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
