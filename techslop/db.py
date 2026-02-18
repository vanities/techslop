from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from techslop.config import settings
from techslop.models import Script, ScriptSection, Story, VideoJob


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stories (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            score REAL,
            published_at TIMESTAMP,
            raw_data JSON,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS video_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT REFERENCES stories(id),
            script JSON,
            audio_path TEXT,
            video_path TEXT,
            youtube_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            published_at TIMESTAMP
        );
        """
    )
    conn.close()


def upsert_story(story: Story) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO stories (id, title, url, source, score, published_at, raw_data, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET score=excluded.score, raw_data=excluded.raw_data
        """,
        (
            story.id,
            story.title,
            story.url,
            story.source,
            story.score,
            story.published_at.isoformat() if story.published_at else None,
            json.dumps(story.raw_data),
            story.status,
            story.created_at.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_top_new_stories(limit: int = 5) -> list[Story]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM stories WHERE status = 'new' ORDER BY score DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [_row_to_story(r) for r in rows]


def get_all_stories() -> list[Story]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM stories ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [_row_to_story(r) for r in rows]


def update_story_status(story_id: str, status: str) -> None:
    conn = get_connection()
    conn.execute("UPDATE stories SET status = ? WHERE id = ?", (status, story_id))
    conn.commit()
    conn.close()


def create_video_job(job: VideoJob) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO video_jobs (story_id, script, audio_path, video_path, youtube_id, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            job.story_id,
            json.dumps(_script_to_dict(job.script)) if job.script else None,
            str(job.audio_path) if job.audio_path else None,
            str(job.video_path) if job.video_path else None,
            job.youtube_id,
            job.status,
        ),
    )
    conn.commit()
    job_id = cursor.lastrowid
    conn.close()
    return job_id


def update_video_job(job_id: int, **kwargs) -> None:
    conn = get_connection()
    sets = []
    vals = []
    for k, v in kwargs.items():
        sets.append(f"{k} = ?")
        if k == "script" and v is not None:
            vals.append(json.dumps(_script_to_dict(v)))
        elif isinstance(v, Path):
            vals.append(str(v))
        elif isinstance(v, datetime):
            vals.append(v.isoformat())
        else:
            vals.append(v)
    vals.append(job_id)
    conn.execute(f"UPDATE video_jobs SET {', '.join(sets)} WHERE id = ?", vals)
    conn.commit()
    conn.close()


def get_video_job(job_id: int) -> VideoJob | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM video_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return _row_to_video_job(row) if row else None


def _row_to_story(row: sqlite3.Row) -> Story:
    return Story(
        id=row["id"],
        title=row["title"],
        url=row["url"],
        source=row["source"],
        score=row["score"] or 0.0,
        published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else datetime.now(timezone.utc),
        raw_data=json.loads(row["raw_data"]) if row["raw_data"] else {},
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(timezone.utc),
    )


def _row_to_video_job(row: sqlite3.Row) -> VideoJob:
    script_data = json.loads(row["script"]) if row["script"] else None
    script = _dict_to_script(script_data) if script_data else None
    return VideoJob(
        id=row["id"],
        story_id=row["story_id"],
        script=script,
        audio_path=Path(row["audio_path"]) if row["audio_path"] else None,
        video_path=Path(row["video_path"]) if row["video_path"] else None,
        youtube_id=row["youtube_id"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(timezone.utc),
        published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
    )


def _script_to_dict(script: Script) -> dict:
    return {
        "story_id": script.story_id,
        "hook": script.hook,
        "body": [{"text": s.text, "screen_text": s.screen_text, "duration_hint": s.duration_hint} for s in script.body],
        "cta": script.cta,
        "full_text": script.full_text,
    }


def _dict_to_script(d: dict) -> Script:
    return Script(
        story_id=d["story_id"],
        hook=d["hook"],
        body=[ScriptSection(**s) for s in d["body"]],
        cta=d["cta"],
        full_text=d["full_text"],
    )
