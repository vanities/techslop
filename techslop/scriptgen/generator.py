"""Script generation using OpenAI — feeds all gathered context for richer scripts."""

from __future__ import annotations

import json
import logging

import openai

from techslop.config import settings
from techslop.models import Script, ScriptSection, Story

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a scriptwriter for a viral tech news YouTube Shorts channel called "TechSlop".
Your job is to turn a tech news story and its surrounding discussion into a punchy, \
engaging 30-45 second script.

Rules:
- The hook MUST grab attention in the first 3 seconds. Start with something shocking, \
funny, or curiosity-driven. Never start with "Hey guys" or "So today".
- Body sections should each be 5-10 seconds of narration. Keep sentences short and punchy.
- Use casual, opinionated tech commentary. Be snarky but informative.
- If community comments/reactions are provided, weave in the best takes — what people \
are actually saying about this. Quote or paraphrase the spiciest reactions.
- screen_text should be a short, bold caption (1-6 words) that reinforces the narration.
- duration_hint is the estimated seconds for that section.
- The CTA should be quick and natural, like "Follow for more tech chaos" or \
"Drop a comment if you saw this coming".
- Total script should be 60-100 words for a 30-45 second short.
- Produce 3-5 body sections.
- Be NOVEL. Don't sound like every other AI news channel. Have a take. Be weird. Be real.

Respond with JSON in this exact format:
{
  "hook": "string — the attention-grabbing opening line (3 seconds)",
  "body": [
    {
      "text": "string — narration for this section",
      "screen_text": "string — short bold on-screen caption",
      "duration_hint": 7.0
    }
  ],
  "cta": "string — the closing call-to-action line"
}
"""


def _build_context(story: Story) -> str:
    """Build a rich context string from a story and all its gathered data."""
    parts = [
        f"Title: {story.title}",
        f"Source: {story.source}",
        f"URL: {story.url}",
    ]

    if story.raw_data.get("summary"):
        parts.append(f"Summary: {story.raw_data['summary']}")

    # HN / 4chan comments
    comments = story.raw_data.get("comments", [])
    if comments:
        parts.append("\nCommunity reactions:")
        for c in comments[:8]:
            if isinstance(c, dict):
                author = c.get("author", "anon")
                text = c.get("text", "")
                parts.append(f"  - {author}: {text[:200]}")
            else:
                parts.append(f"  - {str(c)[:200]}")

    # X/Twitter tweet text
    if story.raw_data.get("tweet_text"):
        parts.append(f"\nTweet: {story.raw_data['tweet_text'][:300]}")

    return "\n".join(parts)


async def generate_script(story: Story) -> Script:
    """Generate a YouTube Shorts script from a tech news story with full context.

    Feeds all gathered context (comments, discussions, tweet text) to OpenAI
    for richer, more novel scripts.
    """
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    context = _build_context(story)
    user_prompt = (
        f"Write a YouTube Shorts script about this tech news story.\n"
        f"Use the community reactions to make it feel authentic and plugged-in.\n\n"
        f"{context}"
    )

    logger.info("Generating script for story %s: %s", story.id[:12], story.title)

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.9,
        max_tokens=512,
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)

    hook = data["hook"]
    cta = data["cta"]

    body = [
        ScriptSection(
            text=section["text"],
            screen_text=section["screen_text"],
            duration_hint=float(section["duration_hint"]),
        )
        for section in data["body"]
    ]

    body_texts = " ".join(section.text for section in body)
    full_text = f"{hook} {body_texts} {cta}"

    script = Script(
        story_id=story.id,
        hook=hook,
        body=body,
        cta=cta,
        full_text=full_text,
    )

    logger.info(
        "Script generated: %d sections, %d chars",
        len(body),
        len(full_text),
    )

    return script
