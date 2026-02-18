from pathlib import Path

from openai import AsyncOpenAI

from techslop.voice.base import TTSProvider


class OpenAITTS(TTSProvider):
    MODEL = "tts-1"
    VOICE = "onyx"

    def __init__(self, config):
        self.config = config
        self.client = AsyncOpenAI(api_key=config.openai_api_key)

    async def synthesize(self, text: str, output_path: Path) -> Path:
        response = await self.client.audio.speech.create(
            model=self.MODEL,
            voice=self.VOICE,
            input=text,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await response.astream_to_file(str(output_path))
        return output_path
