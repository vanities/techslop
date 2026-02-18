"""Tests for techslop.db — uses a temp database."""

import os
from datetime import datetime, timezone

import pytest

from techslop.models import Script, ScriptSection, Story, VideoJob


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    """Point the database at a temp file for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("techslop.config.settings.database_path", db_path)
    from techslop.db import init_db
    init_db()


def _make_story(id_suffix="1", title="Test Story", score=10.0) -> Story:
    return Story(
        id=f"story_{id_suffix}",
        title=title,
        url=f"https://example.com/{id_suffix}",
        source="hackernews",
        score=score,
        published_at=datetime.now(timezone.utc),
    )


def test_upsert_and_get_stories():
    from techslop.db import get_all_stories, upsert_story

    s1 = _make_story("1", score=10.0)
    s2 = _make_story("2", score=20.0)
    upsert_story(s1)
    upsert_story(s2)

    stories = get_all_stories()
    assert len(stories) == 2


def test_upsert_updates_score():
    from techslop.db import get_all_stories, upsert_story

    s = _make_story("1", score=10.0)
    upsert_story(s)

    s.score = 99.0
    upsert_story(s)

    stories = get_all_stories()
    assert len(stories) == 1
    assert stories[0].score == 99.0


def test_get_top_new_stories():
    from techslop.db import get_top_new_stories, upsert_story

    for i in range(10):
        upsert_story(_make_story(str(i), score=float(i)))

    top = get_top_new_stories(limit=3)
    assert len(top) == 3
    assert top[0].score >= top[1].score >= top[2].score


def test_update_story_status():
    from techslop.db import get_all_stories, update_story_status, upsert_story

    s = _make_story("1")
    upsert_story(s)
    update_story_status(s.id, "scripted")

    stories = get_all_stories()
    assert stories[0].status == "scripted"


def test_create_and_get_video_job():
    from techslop.db import create_video_job, get_video_job, upsert_story

    s = _make_story("1")
    upsert_story(s)

    script = Script(
        story_id=s.id,
        hook="Hook!",
        body=[ScriptSection(text="body", screen_text="BODY", duration_hint=5.0)],
        cta="Follow!",
        full_text="Hook! body Follow!",
    )
    job = VideoJob(story_id=s.id, script=script)
    job_id = create_video_job(job)

    loaded = get_video_job(job_id)
    assert loaded is not None
    assert loaded.story_id == s.id
    assert loaded.script.hook == "Hook!"
    assert len(loaded.script.body) == 1


def test_update_video_job():
    from techslop.db import create_video_job, get_video_job, update_video_job, upsert_story

    s = _make_story("1")
    upsert_story(s)

    job = VideoJob(story_id=s.id)
    job_id = create_video_job(job)

    update_video_job(job_id, status="rendered", youtube_id="yt_abc123")

    loaded = get_video_job(job_id)
    assert loaded.status == "rendered"
    assert loaded.youtube_id == "yt_abc123"
