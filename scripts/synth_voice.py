#!/usr/bin/env python
"""Standalone Chatterbox TTS synthesis with pause markers.

Usage:
    uv run python scripts/synth_voice.py <text> <output_path> [voice_ref_path]

Pause markers in `<text>` insert silence between synthesized sections:
    [pause]       — 0.8s of silence (default)
    [pause:1.5]   — 1.5s of silence
    [pause:0.4]   — 0.4s of silence

Example:
    "Today's reading: James chapter 2, verse 12. [pause:1.0]
     So speak ye, and so do. [pause] Speak honestly. Act faithfully."

If voice_ref_path is omitted, falls back to the model's default voice.
Output is 24kHz mono WAV (`.wav` suffix) or MP3 (`.mp3` suffix).
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import torch
import torchaudio
from chatterbox.tts import ChatterboxTTS

PAUSE_RE = re.compile(r"\[pause(?::([\d.]+))?\]", re.IGNORECASE)
DEFAULT_PAUSE_S = 0.8
SAMPLE_RATE = 24000

# Chatterbox's prosody barely honors punctuation, so we insert explicit pauses.
# Tuned to feel natural without being choppy. Order matters: longer matches first
# so `\n\n` is handled before `\n`, and ` — ` before bare `—`.
PUNCT_PAUSES: list[tuple[str, float]] = [
    ("\n\n", 0.8),
    ("\n",   0.5),
    (". ",   0.35),
    ("? ",   0.35),
    ("! ",   0.35),
    ("; ",   0.3),
    (" — ",  0.3),
    (" – ",  0.3),
    (", ",   0.2),
]


def add_punctuation_pauses(text: str) -> str:
    """Insert [pause:N] markers based on punctuation. Existing markers preserved.

    Bible refs like 'John 3:16' would produce false pauses on the colon, so we
    deliberately do NOT auto-pause on `: ` — callers should normalize verse refs
    to 'chapter 3 verse 16' before passing.
    """
    placeholder_fmt = "\x00P{}\x00"
    saved: list[str] = []

    def protect(m: re.Match) -> str:
        saved.append(m.group(0))
        return placeholder_fmt.format(len(saved) - 1)

    # 1. Protect any explicit [pause]/[pause:N] tokens so we don't double-process.
    work = PAUSE_RE.sub(protect, text)

    # 2. Insert pauses after punctuation (longest tokens first).
    for token, secs in PUNCT_PAUSES:
        replacement = f"{token}[pause:{secs}]"
        work = work.replace(token, replacement)

    # 3. Restore protected markers.
    for i, marker in enumerate(saved):
        work = work.replace(placeholder_fmt.format(i), marker)

    return work


def split_sections(text: str) -> list[tuple[str, float]]:
    """Split text on pause markers. Returns [(section_text, pause_after_seconds), ...].

    Trailing section gets pause_after = 0.
    """
    parts = PAUSE_RE.split(text)
    # `parts` shape: [text0, dur1_or_None, text1, dur2_or_None, ..., textN]
    sections: list[tuple[str, float]] = []
    for i in range(0, len(parts), 2):
        section = parts[i].strip()
        if not section:
            continue
        if i + 1 < len(parts):
            dur_str = parts[i + 1]
            pause_after = float(dur_str) if dur_str else DEFAULT_PAUSE_S
        else:
            pause_after = 0.0
        sections.append((section, pause_after))
    return sections


def synth(text: str, out_path: Path, voice_ref: Path | None) -> Path:
    text = add_punctuation_pauses(text)
    sections = split_sections(text)
    if not sections:
        raise ValueError("no text to synthesize")

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"[synth] device={device}, {len(sections)} section(s), loading model...", file=sys.stderr)
    model = ChatterboxTTS.from_pretrained(device)

    chunks: list[torch.Tensor] = []
    for idx, (section, pause_after) in enumerate(sections):
        print(f"[synth] section {idx + 1}/{len(sections)} ({len(section)} chars, pause_after={pause_after}s)", file=sys.stderr)
        wav = model.generate(
            section,
            exaggeration=0.7,
            cfg_weight=0.5,
            audio_prompt_path=str(voice_ref) if voice_ref else None,
        )
        chunks.append(wav)
        if pause_after > 0:
            silence_samples = int(pause_after * SAMPLE_RATE)
            chunks.append(torch.zeros(1, silence_samples))

    full = torch.cat(chunks, dim=-1)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix == ".mp3":
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_wav = Path(tmp.name)
        torchaudio.save(str(tmp_wav), full, SAMPLE_RATE)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(tmp_wav), "-c:a", "libmp3lame", "-q:a", "2", str(out_path)],
            capture_output=True,
            check=True,
        )
        tmp_wav.unlink()
    else:
        torchaudio.save(str(out_path), full, SAMPLE_RATE)

    print(f"[synth] saved {out_path}", file=sys.stderr)
    return out_path


def main():
    if len(sys.argv) < 3:
        print("usage: synth_voice.py <text> <output> [voice_ref]", file=sys.stderr)
        sys.exit(1)
    text = sys.argv[1]
    out = Path(sys.argv[2])
    ref = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    if ref and not ref.exists():
        print(f"voice_ref not found: {ref}", file=sys.stderr)
        sys.exit(1)
    synth(text, out, ref)


if __name__ == "__main__":
    main()
