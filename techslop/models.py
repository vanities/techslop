from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ScriptSection:
    text: str
    screen_text: str
    duration_hint: float


@dataclass
class Script:
    story_id: str
    hook: str
    body: list[ScriptSection]
    cta: str
    full_text: str


@dataclass
class Story:
    id: str
    title: str
    url: str
    source: str
    score: float
    published_at: datetime
    raw_data: dict = field(default_factory=dict)
    status: str = "new"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class VideoJob:
    story_id: str
    audio_path: Path | None = None
    timestamps_path: Path | None = None
    video_path: Path | None = None
    youtube_id: str | None = None
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: datetime | None = None
    script: Script | None = None
    id: int | None = None
