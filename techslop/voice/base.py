from abc import ABC, abstractmethod
from pathlib import Path


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, output_path: Path) -> Path: ...

    @classmethod
    def from_config(cls, config) -> "TTSProvider":
        from techslop.voice.edge import EdgeTTS
        from techslop.voice.openai import OpenAITTS
        from techslop.voice.elevenlabs import ElevenLabsTTS

        providers = {"edge": EdgeTTS, "openai": OpenAITTS, "elevenlabs": ElevenLabsTTS}
        return providers[config.tts_provider](config)
