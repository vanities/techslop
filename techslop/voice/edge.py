from pathlib import Path

import edge_tts

from techslop.voice.base import TTSProvider


class EdgeTTS(TTSProvider):
    VOICE = "en-US-GuyNeural"

    def __init__(self, config):
        self.config = config

    async def synthesize(self, text: str, output_path: Path) -> Path:
        communicate = edge_tts.Communicate(text, self.VOICE)
        await communicate.save(str(output_path))
        return output_path
