"""techslop CLI — human-in-the-loop tech news YouTube Shorts pipeline."""

from __future__ import annotations

import asyncio
import json
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
    """techslop — multi-platform AI motion video pipeline.

    Channel selection: set TECHSLOP_ENV=<name> to load .env.<name> instead of .env.

    Human-in-the-loop workflow:

        \b
        pipeline.py ingest          # 1. Fetch & score stories
        pipeline.py list            # 2. Review stories
        pipeline.py script <ID>     # 3. Generate script
        pipeline.py voice <ID>      # 4. Synthesize voice
        pipeline.py shots <ID>      # 5. gpt-image-2 grid → split → Kling i2v
        pipeline.py video <ID>      # 6. Assemble final motion video
        pipeline.py publish <ID>    # 7. Upload to YT/TikTok/IG/LinkedIn
        \b
        pipeline.py preview         # Auto: ingest → … → video, open locally (no upload)
        pipeline.py run             # Auto: ingest → … → publish to all enabled platforms
    """
    init_db()
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Step 1: Ingest
# ---------------------------------------------------------------------------


@cli.command()
def ingest():
    """Fetch and score stories from all sources."""
    from techslop.ingest.sources import ingest_all

    stories = asyncio.run(ingest_all())
    for story in stories:
        upsert_story(story)
    click.echo(f"Ingested {len(stories)} stories.")
    click.echo("\nTop 5:")
    for s in stories[:5]:
        click.echo(f"  {s.score:.2f}  [{s.source:<12}] {s.title[:65]}")
    click.echo(f"\nRun 'pipeline.py list' to see all, or 'pipeline.py script <ID>' to generate a script.")


# ---------------------------------------------------------------------------
# Step 2: List / Review
# ---------------------------------------------------------------------------


@cli.command("list")
@click.option("--status", default=None, help="Filter by status (new, scripted, rendered, published).")
@click.option("--source", default=None, help="Filter by source.")
@click.option("--limit", default=20, help="Max stories to show.")
def list_stories(status, source, limit):
    """Show stories and their statuses."""
    stories = get_all_stories()
    if not stories:
        click.echo("No stories found. Run 'ingest' first.")
        return

    if status:
        stories = [s for s in stories if s.status == status]
    if source:
        stories = [s for s in stories if s.source == source]

    for s in stories[:limit]:
        comments = len(s.raw_data.get("comments", []))
        ctx = f"+{comments}c" if comments else ""
        click.echo(f"  [{s.status:>10}] {s.score:.2f}  {s.source:<12} {s.title[:55]} {ctx}")
        click.echo(f"             ID: {s.id[:12]}  URL: {s.url[:60]}")

    total = len(stories)
    if total > limit:
        click.echo(f"\n  ... and {total - limit} more. Use --limit to show more.")


@cli.command()
@click.argument("story_id")
def show(story_id):
    """Show full details for a story (by ID prefix)."""
    story = _find_story(story_id)
    if not story:
        return

    click.echo(f"Title:     {story.title}")
    click.echo(f"Source:    {story.source}")
    click.echo(f"URL:       {story.url}")
    click.echo(f"Score:     {story.score:.3f}")
    click.echo(f"Status:    {story.status}")
    click.echo(f"Published: {story.published_at}")

    comments = story.raw_data.get("comments", [])
    if comments:
        click.echo(f"\nComments ({len(comments)}):")
        for c in comments:
            if isinstance(c, dict):
                click.echo(f"  [{c.get('author', 'anon')}]: {c.get('text', '')[:150]}")
            else:
                click.echo(f"  {str(c)[:150]}")

    if story.raw_data.get("tweet_text"):
        click.echo(f"\nTweet: {story.raw_data['tweet_text'][:300]}")


# ---------------------------------------------------------------------------
# Step 3: Script generation
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--limit", default=30, help="Max stories to include.")
@click.option("--source", default=None, help="Filter by source.")
@click.option("--status", default=None, help="Filter by status.")
def context(limit, source, status):
    """Dump ALL ingested stories and context for collaborative script crafting.

    Gathers everything from all sources into one big context dump so you can
    pick the best stuff and craft a script in Claude Code.
    """
    stories = get_all_stories()
    if not stories:
        click.echo("No stories found. Run 'ingest' first.")
        return

    if source:
        stories = [s for s in stories if s.source == source]
    if status:
        stories = [s for s in stories if s.status == status]

    stories = stories[:limit]

    click.echo(f"\n{'='*70}")
    click.echo(f"ALL STORIES CONTEXT ({len(stories)} stories)")
    click.echo(f"{'='*70}")

    for i, story in enumerate(stories, 1):
        click.echo(f"\n{'─'*70}")
        click.echo(f"[{i}] {story.title}")
        click.echo(f"    Source: {story.source}  |  Score: {story.score:.2f}  |  ID: {story.id[:12]}")
        click.echo(f"    URL: {story.url}")

        comments = story.raw_data.get("comments", [])
        if comments:
            click.echo(f"    Comments ({len(comments)}):")
            for c in comments[:5]:
                if isinstance(c, dict):
                    text = c.get("text", "")[:200]
                    author = c.get("author", "anon")
                    click.echo(f"      [{author}]: {text}")
                else:
                    click.echo(f"      {str(c)[:200]}")

        if story.raw_data.get("tweet_text"):
            click.echo(f"    Tweet: {story.raw_data['tweet_text'][:300]}")

        if story.raw_data.get("summary"):
            click.echo(f"    Summary: {story.raw_data['summary'][:300]}")

    click.echo(f"\n{'='*70}")
    click.echo(f"Pick stories to combine into a script. Save to output/<id>/script.json")
    click.echo(f"Format:")
    click.echo("""{
  "story_id": "<id>",
  "hook": "Attention-grabbing opener (3 seconds)",
  "body": [
    {"text": "Narration", "screen_text": "ON-SCREEN TEXT", "duration_hint": 7.0}
  ],
  "cta": "Call to action",
  "full_text": "All narration concatenated for TTS"
}""")


@cli.command()
@click.argument("story_id")
@click.option("--interactive", "-i", is_flag=True, help="Dump raw context only — skip AI generation, craft the script yourself.")
def script(story_id, interactive):
    """Generate a script for a story, or dump context for manual crafting.

    Default: generates a script via OpenAI as a starting point.
    With --interactive: prints all raw context (story, comments, tweets)
    so you can collaborate on the script in Claude Code, then save it
    by editing output/<id>/script.json directly.
    """
    story = _find_story(story_id)
    if not story:
        return

    story_dir = _story_dir(story.id)
    script_path = story_dir / "script.json"

    if interactive:
        _dump_story_context(story)
        click.echo(f"\nScript file: {script_path}")
        click.echo("Craft the script here, then I'll save it to script.json.")
        click.echo("When done, run: pipeline.py voice " + story.id[:12])
        return

    from techslop.scriptgen.generator import generate_script

    click.echo(f"Generating script for: {story.title[:60]}...")
    script_obj = asyncio.run(generate_script(story))

    _save_script_json(script_obj, script_path)

    job = VideoJob(story_id=story.id, script=script_obj)
    job_id = create_video_job(job)
    update_story_status(story.id, "scripted")

    _print_script(script_obj)
    click.echo(f"\nScript saved to: {script_path}")
    click.echo(f"Job ID: {job_id}")
    click.echo(f"\nEdit the script, or continue: pipeline.py voice {story.id[:12]}")


# ---------------------------------------------------------------------------
# Step 4: Voice synthesis
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("story_id")
def voice(story_id):
    """Synthesize voice for a scripted story."""
    from techslop.voice.base import TTSProvider
    from techslop.voice.timestamps import extract_timestamps

    story = _find_story(story_id)
    if not story:
        return

    story_dir = _story_dir(story.id)
    script_path = story_dir / "script.json"
    if not script_path.exists():
        click.echo(f"No script found. Run 'script {story_id}' first.")
        return

    script_obj = _load_script_json(script_path, story.id)

    tts = TTSProvider.from_config(settings)
    audio_path = story_dir / "narration.mp3"

    click.echo(f"Synthesizing voice ({settings.tts_provider})...")
    asyncio.run(tts.synthesize(script_obj.full_text, audio_path))
    click.echo(f"Audio: {audio_path}")

    click.echo("Extracting word timestamps...")
    timestamps_path = story_dir / "timestamps.json"
    extract_timestamps(audio_path, timestamps_path)
    click.echo(f"Timestamps: {timestamps_path}")

    click.echo(f"\nNext: pipeline.py video {story.id[:12]}")


# ---------------------------------------------------------------------------
# Step 5: Shots (gpt-image-2 grid → split → Kling motion clips)
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("story_id")
def shots(story_id):
    """Generate motion clips for a scripted story.

    Calls gpt-image-2 once to produce a character-consistent grid, splits the
    grid into per-section keyframes, then animates each via Kling 2.1 Pro i2v.
    """
    from techslop.image_gen.grid import generate_grid, grid_shape
    from techslop.image_gen.split import split_grid
    from techslop.motion.kling import animate_shots

    story = _find_story(story_id)
    if not story:
        return

    story_dir = _story_dir(story.id)
    script_path = story_dir / "script.json"
    if not script_path.exists():
        click.echo(f"No script found. Run 'script {story_id}' first.")
        return

    script_obj = _load_script_json(script_path, story.id)
    shots_dir = story_dir / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Generating grid via gpt-image-2 ({len(script_obj.body)} panels)...")
    grid_path = generate_grid(
        script=script_obj,
        output_path=shots_dir / "grid.png",
        character_brief=settings.character_brief,
        size=settings.image_size,
    )
    click.echo(f"  Grid: {grid_path}")

    rows, cols = grid_shape(len(script_obj.body))
    click.echo(f"Splitting into {rows}x{cols} keyframes...")
    keyframes = split_grid(grid_path, rows=rows, cols=cols, output_dir=shots_dir)

    # Use screen_text (or first words of text) as a short motion prompt per shot.
    motion_prompts = [
        (s.screen_text or s.text[:60]) + ", subtle cinematic camera motion"
        for s in script_obj.body[: len(keyframes)]
    ]

    click.echo(f"Animating {len(keyframes)} shots via Kling i2v (parallel)...")
    clip_paths = asyncio.run(
        animate_shots(
            image_paths=keyframes,
            motion_prompts=motion_prompts,
            output_dir=shots_dir,
            duration=settings.motion_duration,
        )
    )
    click.echo(f"  Clips: {len(clip_paths)} written to {shots_dir}")
    click.echo(f"\nNext: pipeline.py video {story.id[:12]}")


# ---------------------------------------------------------------------------
# Step 6: Video assembly
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("story_id")
@click.option("--open", "open_video", is_flag=True, default=True, help="Open video after assembly.")
def video(story_id, open_video):
    """Assemble the final video. Uses motion clips if present, else falls back to a static background."""
    from techslop.video.assembler import (
        assemble_video_motion,
        assemble_video_static,
        get_audio_duration,
    )
    from techslop.video.assets import generate_background
    from techslop.video.captions import generate_captions

    story = _find_story(story_id)
    if not story:
        return

    story_dir = _story_dir(story.id)
    audio_path = story_dir / "narration.mp3"
    timestamps_path = story_dir / "timestamps.json"

    if not audio_path.exists():
        click.echo(f"No audio found. Run 'voice {story_id}' first.")
        return

    click.echo("Generating captions...")
    captions_path = story_dir / "captions.ass"
    generate_captions(timestamps_path, captions_path)

    video_path = story_dir / "output.mp4"
    shots_dir = story_dir / "shots"
    motion_clips = sorted(shots_dir.glob("clip_*.mp4")) if shots_dir.exists() else []

    if motion_clips:
        click.echo(f"Assembling motion video from {len(motion_clips)} clips...")
        assemble_video_motion(
            clip_paths=motion_clips,
            audio_path=audio_path,
            captions_path=captions_path,
            output_path=video_path,
            title=story.title,
        )
    else:
        click.echo("No motion clips found — falling back to static background.")
        bg_path = story_dir / "background.png"
        generate_background(bg_path)
        duration = get_audio_duration(audio_path)
        assemble_video_static(
            audio_path=audio_path,
            captions_path=captions_path,
            background_path=bg_path,
            output_path=video_path,
            title=story.title,
            duration=duration,
        )

    update_story_status(story.id, "rendered")
    click.echo(f"Video: {video_path}")

    if open_video:
        _open_file(video_path)

    click.echo(f"\nNext: pipeline.py publish {story.id[:12]}")


# ---------------------------------------------------------------------------
# Step 6: Publish
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("story_id")
@click.option("--all", "all_platforms", is_flag=True, default=False, help="Upload to every platform with creds in env.")
@click.option("--youtube/--no-youtube", default=True, help="Upload to YouTube.")
@click.option("--tiktok/--no-tiktok", default=False, help="Upload to TikTok.")
@click.option("--instagram/--no-instagram", default=False, help="Upload to Instagram.")
@click.option("--linkedin/--no-linkedin", default=False, help="Upload to LinkedIn.")
def publish(story_id, all_platforms, youtube, tiktok, instagram, linkedin):
    """Upload a rendered video to platforms."""
    story = _find_story(story_id)
    if not story:
        return

    story_dir = _story_dir(story.id)
    video_path = story_dir / "output.mp4"
    script_path = story_dir / "script.json"

    if not video_path.exists():
        click.echo(f"No video found. Run 'video {story_id}' first.")
        return

    script_obj = _load_script_json(script_path, story.id) if script_path.exists() else None
    description = (
        f"{script_obj.hook}\n\n" if script_obj else ""
    ) + f"Source: {story.url}\n\n#tech #news #shorts"

    title = f"{story.title[:90]} #Shorts"

    if all_platforms:
        youtube = bool(settings.youtube_refresh_token)
        tiktok = bool(settings.tiktok_refresh_token)
        instagram = bool(settings.instagram_access_token)
        linkedin = bool(settings.linkedin_access_token)

    if youtube:
        click.echo("Uploading to YouTube...")
        from techslop.publish.youtube import upload_to_youtube

        yt_id = upload_to_youtube(
            video_path=video_path,
            title=title,
            description=description,
            tags=["tech", "news", "shorts", story.source],
        )
        click.echo(f"  YouTube: https://youtube.com/shorts/{yt_id}")

    if tiktok:
        click.echo("Uploading to TikTok...")
        from techslop.publish.tiktok import upload_to_tiktok

        publish_id = upload_to_tiktok(video_path, title)
        click.echo(f"  TikTok publish_id: {publish_id} (check mobile drafts inbox)")

    if instagram:
        click.echo("Uploading to Instagram...")
        from techslop.publish.instagram import upload_to_instagram

        media_id = upload_to_instagram(video_path, title)
        click.echo(f"  Instagram media_id: {media_id}")

    if linkedin:
        click.echo("Uploading to LinkedIn...")
        from techslop.publish.linkedin import upload_to_linkedin

        post_id = upload_to_linkedin(video_path, title, description)
        click.echo(f"  LinkedIn post: {post_id}")

    update_story_status(story.id, "published")
    click.echo("Done!")


# ---------------------------------------------------------------------------
# Convenience commands (auto pipeline)
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--count", default=1, help="Number of stories to process.")
def preview(count):
    """Auto-pick top story, generate full video, open it. No upload."""
    _run_pipeline(count=count, upload=False)


@cli.command()
@click.option("--count", default=1, help="Number of stories to process.")
def run(count):
    """Full auto pipeline: ingest → script → voice → video → upload."""
    _run_pipeline(count=count, upload=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_story(story_id_prefix: str):
    """Find a story by ID prefix."""
    stories = get_all_stories()
    matches = [s for s in stories if s.id.startswith(story_id_prefix)]
    if not matches:
        click.echo(f"No story found matching '{story_id_prefix}'. Run 'list' to see IDs.")
        return None
    if len(matches) > 1:
        click.echo(f"Multiple matches for '{story_id_prefix}'. Be more specific:")
        for s in matches:
            click.echo(f"  {s.id[:12]}  {s.title[:50]}")
        return None
    return matches[0]


def _story_dir(story_id: str) -> Path:
    d = Path(settings.output_dir) / story_id[:12]
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_script_json(script_obj, path: Path):
    data = {
        "story_id": script_obj.story_id,
        "hook": script_obj.hook,
        "body": [
            {"text": s.text, "screen_text": s.screen_text, "duration_hint": s.duration_hint}
            for s in script_obj.body
        ],
        "cta": script_obj.cta,
        "full_text": script_obj.full_text,
    }
    path.write_text(json.dumps(data, indent=2))


def _load_script_json(path: Path, story_id: str):
    from techslop.models import Script, ScriptSection

    data = json.loads(path.read_text())
    return Script(
        story_id=data.get("story_id", story_id),
        hook=data["hook"],
        body=[ScriptSection(**s) for s in data["body"]],
        cta=data["cta"],
        full_text=data["full_text"],
    )


def _dump_story_context(story):
    """Print all raw context for a story — used in interactive script crafting."""
    click.echo(f"\n{'='*70}")
    click.echo(f"STORY CONTEXT")
    click.echo(f"{'='*70}")
    click.echo(f"Title:     {story.title}")
    click.echo(f"Source:    {story.source}")
    click.echo(f"URL:       {story.url}")
    click.echo(f"Score:     {story.score:.3f}")
    click.echo(f"Published: {story.published_at}")

    comments = story.raw_data.get("comments", [])
    if comments:
        click.echo(f"\n--- Community Reactions ({len(comments)}) ---")
        for c in comments:
            if isinstance(c, dict):
                author = c.get("author", "anon")
                text = c.get("text", "")
                click.echo(f"\n  [{author}]:")
                click.echo(f"  {text[:500]}")
            else:
                click.echo(f"\n  {str(c)[:500]}")

    if story.raw_data.get("tweet_text"):
        click.echo(f"\n--- Tweet ---")
        click.echo(f"  {story.raw_data['tweet_text'][:500]}")

    # Show any other useful raw_data
    summary = story.raw_data.get("summary")
    if summary:
        click.echo(f"\n--- Summary ---")
        click.echo(f"  {summary[:500]}")

    click.echo(f"\n{'='*70}")
    click.echo(f"SCRIPT FORMAT (save to script.json):")
    click.echo(f"{'='*70}")
    click.echo("""{
  "story_id": "<id>",
  "hook": "Attention-grabbing opener (3 seconds)",
  "body": [
    {"text": "Narration", "screen_text": "ON-SCREEN TEXT", "duration_hint": 7.0}
  ],
  "cta": "Call to action",
  "full_text": "All narration concatenated for TTS"
}""")


def _print_script(script_obj):
    """Pretty-print a generated script."""
    click.echo(f"\n--- Generated Script ---")
    click.echo(f"\nHook: {script_obj.hook}")
    click.echo(f"\nBody:")
    for i, section in enumerate(script_obj.body, 1):
        click.echo(f"  {i}. [{section.screen_text}] {section.text} ({section.duration_hint}s)")
    click.echo(f"\nCTA: {script_obj.cta}")
    click.echo(f"\nFull narration ({len(script_obj.full_text)} chars):")
    click.echo(f"  {script_obj.full_text}")


def _open_file(path: Path):
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)])
    elif sys.platform == "linux":
        subprocess.run(["xdg-open", str(path)])


def _run_pipeline(count: int = 1, upload: bool = False):
    from techslop.image_gen.grid import generate_grid, grid_shape
    from techslop.image_gen.split import split_grid
    from techslop.ingest.sources import ingest_all
    from techslop.motion.kling import animate_shots
    from techslop.scriptgen.generator import generate_script
    from techslop.video.assembler import (
        assemble_video_motion,
        assemble_video_static,
        get_audio_duration,
    )
    from techslop.video.assets import generate_background
    from techslop.video.captions import generate_captions
    from techslop.voice.base import TTSProvider
    from techslop.voice.timestamps import extract_timestamps

    motion_enabled = bool(settings.fal_key)

    click.echo("Ingesting stories...")
    stories = asyncio.run(ingest_all())
    for story in stories:
        upsert_story(story)
    click.echo(f"  Found {len(stories)} stories.")

    top_stories = get_top_new_stories(limit=count)
    if not top_stories:
        click.echo("No new stories to process.")
        return

    tts = TTSProvider.from_config(settings)

    for story in top_stories:
        click.echo(f"\nProcessing: {story.title[:60]}...")

        job = VideoJob(story_id=story.id)
        job_id = create_video_job(job)
        story_dir = _story_dir(story.id)

        click.echo("  Generating script...")
        script_obj = asyncio.run(generate_script(story))
        _save_script_json(script_obj, story_dir / "script.json")
        update_video_job(job_id, script=script_obj, status="scripted")
        update_story_status(story.id, "scripted")

        click.echo("  Synthesizing voice...")
        audio_path = story_dir / "narration.mp3"
        asyncio.run(tts.synthesize(script_obj.full_text, audio_path))
        update_video_job(job_id, audio_path=audio_path, status="voiced")

        click.echo("  Extracting timestamps...")
        timestamps_path = story_dir / "timestamps.json"
        extract_timestamps(audio_path, timestamps_path)

        click.echo("  Generating captions...")
        captions_path = story_dir / "captions.ass"
        generate_captions(timestamps_path, captions_path)

        motion_clips: list[Path] = []
        if motion_enabled:
            click.echo("  Generating gpt-image-2 grid...")
            shots_dir = story_dir / "shots"
            shots_dir.mkdir(parents=True, exist_ok=True)
            grid_path = generate_grid(
                script=script_obj,
                output_path=shots_dir / "grid.png",
                character_brief=settings.character_brief,
                size=settings.image_size,
            )
            rows, cols = grid_shape(len(script_obj.body))
            keyframes = split_grid(grid_path, rows=rows, cols=cols, output_dir=shots_dir)

            click.echo(f"  Animating {len(keyframes)} shots via Kling i2v...")
            motion_prompts = [
                (s.screen_text or s.text[:60]) + ", subtle cinematic camera motion"
                for s in script_obj.body[: len(keyframes)]
            ]
            motion_clips = asyncio.run(
                animate_shots(
                    image_paths=keyframes,
                    motion_prompts=motion_prompts,
                    output_dir=shots_dir,
                    duration=settings.motion_duration,
                )
            )

        click.echo("  Assembling video...")
        video_path = story_dir / "output.mp4"
        if motion_clips:
            assemble_video_motion(
                clip_paths=motion_clips,
                audio_path=audio_path,
                captions_path=captions_path,
                output_path=video_path,
                title=story.title,
            )
        else:
            bg_path = story_dir / "background.png"
            generate_background(bg_path)
            duration = get_audio_duration(audio_path)
            assemble_video_static(
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

        if upload:
            description = f"{script_obj.hook}\n\nSource: {story.url}\n\n#tech #news #shorts"
            title = f"{story.title[:90]} #Shorts"
            tags = ["tech", "news", "shorts", story.source]

            yt_id = None
            if settings.youtube_refresh_token:
                click.echo("  Uploading to YouTube...")
                from techslop.publish.youtube import upload_to_youtube

                yt_id = upload_to_youtube(
                    video_path=video_path, title=title, description=description, tags=tags,
                )
                click.echo(f"    YouTube: https://youtube.com/shorts/{yt_id}")

            if settings.tiktok_refresh_token:
                click.echo("  Uploading to TikTok...")
                from techslop.publish.tiktok import upload_to_tiktok

                pid = upload_to_tiktok(video_path, title)
                click.echo(f"    TikTok publish_id: {pid}")

            if settings.instagram_access_token:
                click.echo("  Uploading to Instagram...")
                from techslop.publish.instagram import upload_to_instagram

                mid = upload_to_instagram(video_path, title)
                click.echo(f"    Instagram media_id: {mid}")

            if settings.linkedin_access_token:
                click.echo("  Uploading to LinkedIn...")
                from techslop.publish.linkedin import upload_to_linkedin

                pid = upload_to_linkedin(video_path, title, description)
                click.echo(f"    LinkedIn post: {pid}")

            update_video_job(
                job_id, youtube_id=yt_id, status="published",
                published_at=datetime.now(timezone.utc),
            )
            update_story_status(story.id, "published")
        else:
            click.echo(f"  Preview: {video_path}")
            _open_file(video_path)

    click.echo("\nDone!")


if __name__ == "__main__":
    cli()
