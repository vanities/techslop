from __future__ import annotations

import asyncio
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from techslop.config import settings
from techslop.db import (
    create_video_job,
    get_all_stories,
    get_top_new_stories,
    init_db,
    update_story_status,
    update_video_job,
    upsert_story,
)
from techslop.models import VideoJob


@click.group()
def cli():
    """techslop - Automated Tech News YouTube Shorts Pipeline"""
    init_db()
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)


@cli.command()
def ingest():
    """Fetch and score stories from all sources."""
    from techslop.ingest.sources import ingest_all

    stories = asyncio.run(ingest_all())
    for story in stories:
        upsert_story(story)
    click.echo(f"Ingested {len(stories)} stories.")


@cli.command()
def list():
    """Show stories and their statuses."""
    stories = get_all_stories()
    if not stories:
        click.echo("No stories found. Run 'ingest' first.")
        return
    for s in stories:
        click.echo(f"[{s.status:>10}] {s.score:.2f}  {s.source:<12} {s.title[:70]}")


@cli.command()
@click.option("--count", default=1, help="Number of stories to process.")
def preview(count):
    """Generate video(s) but don't upload. Opens the result."""
    _run_pipeline(count=count, upload=False)


@cli.command()
@click.option("--count", default=1, help="Number of stories to process.")
def run(count):
    """Full pipeline: ingest → script → voice → video → upload."""
    _run_pipeline(count=count, upload=True)


def _run_pipeline(count: int = 1, upload: bool = False):
    from techslop.ingest.sources import ingest_all
    from techslop.scriptgen.generator import generate_script
    from techslop.video.assembler import assemble_video, get_audio_duration
    from techslop.video.assets import generate_background, generate_title_card
    from techslop.video.captions import generate_captions
    from techslop.voice.base import TTSProvider
    from techslop.voice.timestamps import extract_timestamps

    # Step 1: Ingest
    click.echo("Ingesting stories...")
    stories = asyncio.run(ingest_all())
    for story in stories:
        upsert_story(story)
    click.echo(f"  Found {len(stories)} stories total.")

    # Step 2: Pick top stories
    top_stories = get_top_new_stories(limit=count)
    if not top_stories:
        click.echo("No new stories to process.")
        return

    tts = TTSProvider.from_config(settings)
    output_dir = Path(settings.output_dir)

    for story in top_stories:
        click.echo(f"\nProcessing: {story.title[:60]}...")

        job = VideoJob(story_id=story.id)
        job_id = create_video_job(job)
        story_dir = output_dir / story.id[:12]
        story_dir.mkdir(parents=True, exist_ok=True)

        # Step 3: Generate script
        click.echo("  Generating script...")
        script = asyncio.run(generate_script(story))
        update_video_job(job_id, script=script, status="scripted")
        update_story_status(story.id, "scripted")
        click.echo(f"  Script: {len(script.full_text)} chars")

        # Step 4: Synthesize voice
        click.echo("  Synthesizing voice...")
        audio_path = story_dir / "narration.mp3"
        asyncio.run(tts.synthesize(script.full_text, audio_path))
        update_video_job(job_id, audio_path=audio_path, status="voiced")
        click.echo(f"  Audio: {audio_path}")

        # Step 5: Extract timestamps
        click.echo("  Extracting word timestamps...")
        timestamps_path = story_dir / "timestamps.json"
        extract_timestamps(audio_path, timestamps_path)
        click.echo(f"  Timestamps: {timestamps_path}")

        # Step 6: Generate captions
        click.echo("  Generating captions...")
        captions_path = story_dir / "captions.ass"
        generate_captions(timestamps_path, captions_path)

        # Step 7: Generate background
        click.echo("  Generating background...")
        bg_path = story_dir / "background.png"
        generate_background(bg_path)

        # Step 8: Assemble video
        click.echo("  Assembling video...")
        video_path = story_dir / "output.mp4"
        duration = get_audio_duration(audio_path)
        assemble_video(
            audio_path=audio_path,
            captions_path=captions_path,
            background_path=bg_path,
            output_path=video_path,
            title=story.title,
            duration=duration,
        )
        update_video_job(job_id, video_path=video_path, status="rendered")
        update_story_status(story.id, "rendered")
        click.echo(f"  Video: {video_path}")

        # Step 9: Upload (or preview)
        if upload:
            click.echo("  Uploading to YouTube...")
            from techslop.publish.youtube import upload_to_youtube

            description = (
                f"{script.hook}\n\n"
                f"Source: {story.url}\n\n"
                f"#tech #news #shorts"
            )
            youtube_id = upload_to_youtube(
                video_path=video_path,
                title=f"{story.title[:90]} #Shorts",
                description=description,
                tags=["tech", "news", "shorts", story.source],
            )
            update_video_job(
                job_id,
                youtube_id=youtube_id,
                status="published",
                published_at=datetime.now(timezone.utc),
            )
            update_story_status(story.id, "published")
            click.echo(f"  Published: https://youtube.com/shorts/{youtube_id}")
        else:
            click.echo(f"  Preview ready: {video_path}")
            if sys.platform == "darwin":
                subprocess.run(["open", str(video_path)])
            elif sys.platform == "linux":
                subprocess.run(["xdg-open", str(video_path)])

    click.echo("\nDone!")


if __name__ == "__main__":
    cli()
