from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)

# Silence gap between sentences (seconds)
SENTENCE_GAP = 0.35


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize_chunk(self, text: str, output_path: Path) -> Path:
        """Synthesize a single text chunk to an audio file."""
        ...

    async def synthesize(self, text: str, output_path: Path) -> Path:
        """Synthesize text with sentence-level chunking and silence gaps.

        Splits on sentence boundaries, synthesizes each chunk separately,
        then concatenates with short silence gaps for natural pacing.
        """
        chunks = _split_sentences(text)

        if len(chunks) <= 1:
            return await self.synthesize_chunk(text, output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            chunk_paths: list[Path] = []

            for i, chunk in enumerate(chunks):
                chunk = chunk.strip()
                if not chunk:
                    continue
                chunk_path = tmp_dir / f"chunk_{i:03d}.mp3"
                await self.synthesize_chunk(chunk, chunk_path)
                chunk_paths.append(chunk_path)
                logger.info("Chunk %d: %s", i, chunk[:50])

            if not chunk_paths:
                return await self.synthesize_chunk(text, output_path)

            _concatenate_with_gaps(chunk_paths, output_path, gap=SENTENCE_GAP)

        return output_path

    @classmethod
    def from_config(cls, config) -> TTSProvider:
        from techslop.voice.chatterbox_tts import ChatterboxTTSProvider
        from techslop.voice.edge import EdgeTTS
        from techslop.voice.elevenlabs import ElevenLabsTTS
        from techslop.voice.openai import OpenAITTS

        providers = {
            "edge": EdgeTTS,
            "openai": OpenAITTS,
            "elevenlabs": ElevenLabsTTS,
            "chatterbox": ChatterboxTTSProvider,
        }
        return providers[config.tts_provider](config)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on . ? ! while keeping the punctuation."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _concatenate_with_gaps(chunk_paths: list[Path], output_path: Path, gap: float = 0.35) -> None:
    """Concatenate audio chunks with silence gaps using ffmpeg."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # Generate a silence file
        silence_path = tmp_dir / "silence.mp3"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"anullsrc=r=24000:cl=mono",
                "-t", str(gap),
                "-c:a", "libmp3lame", "-q:a", "9",
                str(silence_path),
            ],
            capture_output=True,
            check=True,
        )

        # Build concat list: chunk, silence, chunk, silence, ..., chunk
        concat_list = tmp_dir / "concat.txt"
        lines = []
        for i, cp in enumerate(chunk_paths):
            lines.append(f"file '{cp}'")
            if i < len(chunk_paths) - 1:
                lines.append(f"file '{silence_path}'")
        concat_list.write_text("\n".join(lines))

        # Concatenate
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c:a", "libmp3lame", "-q:a", "2",
                str(output_path),
            ],
            capture_output=True,
            check=True,
        )

    logger.info("Concatenated %d chunks → %s", len(chunk_paths), output_path)
