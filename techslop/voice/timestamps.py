import json
from pathlib import Path

import whisper


def extract_timestamps(audio_path: Path, output_path: Path) -> Path:
    model = whisper.load_model("base")
    result = model.transcribe(str(audio_path), word_timestamps=True)

    words = []
    for segment in result["segments"]:
        for word_info in segment.get("words", []):
            words.append(
                {
                    "word": word_info["word"],
                    "start": word_info["start"],
                    "end": word_info["end"],
                }
            )

    output_path.write_text(json.dumps(words, indent=2))
    return output_path
