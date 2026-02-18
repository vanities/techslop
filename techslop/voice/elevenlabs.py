from pathlib import Path

from techslop.voice.base import TTSProvider


class ElevenLabsTTS(TTSProvider):
    def __init__(self, config):
        self.config = config

    async def synthesize(self, text: str, output_path: Path) -> Path:
        raise NotImplementedError("ElevenLabs TTS not yet implemented")
