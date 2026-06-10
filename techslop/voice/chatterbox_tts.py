from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

import torch
import torchaudio

from techslop.voice.base import TTSProvider

logger = logging.getLogger(__name__)


class ChatterboxTTSProvider(TTSProvider):
    SAMPLE_RATE = 24000
    EXAGGERATION = 0.7
    CFG_WEIGHT = 0.3

    def __init__(self, config):
        self.config = config
        self._model = None
        self._audio_prompt = getattr(config, "chatterbox_voice_ref", None) or None

    def _get_model(self):
        if self._model is None:
            from chatterbox.tts import ChatterboxTTS

            device = "mps" if torch.backends.mps.is_available() else "cpu"
            logger.info("Loading Chatterbox model on %s...", device)
            self._model = ChatterboxTTS.from_pretrained(device)
            logger.info("Chatterbox model loaded (sr=%d)", self._model.sr)
        return self._model

    async def synthesize_chunk(self, text: str, output_path: Path) -> Path:
        model = self._get_model()
        wav = model.generate(
            text,
            exaggeration=self.EXAGGERATION,
            cfg_weight=self.CFG_WEIGHT,
            audio_prompt_path=self._audio_prompt,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix == ".mp3":
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_wav = Path(tmp.name)
            torchaudio.save(str(tmp_wav), wav, self.SAMPLE_RATE)
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(tmp_wav), "-c:a", "libmp3lame", "-q:a", "2", str(output_path)],
                capture_output=True,
                check=True,
            )
            tmp_wav.unlink()
        else:
            torchaudio.save(str(output_path), wav, self.SAMPLE_RATE)

        return output_path
