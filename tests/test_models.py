"""Tests for techslop.models."""

from datetime import datetime, timezone

from techslop.models import Script, ScriptSection, Story, VideoJob


def test_story_defaults():
    s = Story(
        id="abc123",
        title="Test",
        url="https://example.com",
        source="hackernews",
        score=42.0,
        published_at=datetime.now(timezone.utc),
    )
    assert s.status == "new"
    assert s.raw_data == {}
    assert s.created_at.tzinfo is not None


def test_script_full_text():
    script = Script(
        story_id="abc",
        hook="Breaking news!",
        body=[
            ScriptSection(text="First point.", screen_text="POINT 1", duration_hint=5.0),
            ScriptSection(text="Second point.", screen_text="POINT 2", duration_hint=5.0),
        ],
        cta="Follow for more.",
        full_text="Breaking news! First point. Second point. Follow for more.",
    )
    assert len(script.body) == 2
    assert "First point" in script.full_text
    assert "Follow for more" in script.full_text


def test_video_job_defaults():
    job = VideoJob(story_id="abc")
    assert job.status == "pending"
    assert job.audio_path is None
    assert job.video_path is None
    assert job.youtube_id is None
    assert job.id is None
