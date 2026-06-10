#!/usr/bin/env bash
# Record a voice reference clip for Chatterbox voice cloning.
# Requires: ffmpeg (with avfoundation on macOS)
#
# Usage:
#   ./record_voice.sh                    # Records to assets/voice_ref.wav
#   ./record_voice.sh my_voice.wav       # Records to custom path
#
# Tips:
#   - Speak naturally for 10-15 seconds
#   - Read something similar to what the TTS will say
#   - Quiet room, no background noise
#   - Press Ctrl+C to stop recording
#
# After recording, set in .env:
#   CHATTERBOX_VOICE_REF=assets/voice_ref.wav

set -euo pipefail

OUTPUT="${1:-assets/voice_ref.wav}"
mkdir -p "$(dirname "$OUTPUT")"

echo "=== Chatterbox Voice Reference Recorder ==="
echo ""
echo "Output: $OUTPUT"
echo ""

# List available audio inputs on macOS
if [[ "$(uname)" == "Darwin" ]]; then
    echo "Available audio input devices:"
    ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | grep -A 50 "audio devices" | grep "^\[" | head -10 || true
    echo ""
    echo "Using default input device (index 0)."
    echo ""
    AUDIO_INPUT=":0"
    AUDIO_FMT="avfoundation"
elif [[ "$(uname)" == "Linux" ]]; then
    AUDIO_INPUT="default"
    AUDIO_FMT="pulse"
else
    echo "Unsupported platform. Record a .wav file manually."
    exit 1
fi

echo "Suggested text to read (or say anything for 10-15 seconds):"
echo ""
echo "  \"The latest developments in artificial intelligence continue"
echo "   to push the boundaries of what we thought was possible."
echo "   From new language models to breakthrough research papers,"
echo "   the tech world moves fast and we're here to keep up.\""
echo ""
echo "Press ENTER to start recording, then Ctrl+C to stop."
read -r

echo "Recording... (Ctrl+C to stop)"
ffmpeg -y -f "$AUDIO_FMT" -i "$AUDIO_INPUT" \
    -ar 24000 -ac 1 -c:a pcm_s16le \
    "$OUTPUT" 2>/dev/null || true

if [[ -f "$OUTPUT" ]]; then
    DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$OUTPUT" 2>/dev/null || echo "unknown")
    SIZE=$(ls -lh "$OUTPUT" | awk '{print $5}')
    echo ""
    echo "Saved: $OUTPUT ($SIZE, ${DURATION}s)"
    echo ""
    echo "To use this voice, add to your .env:"
    echo "  CHATTERBOX_VOICE_REF=$OUTPUT"
    echo ""
    echo "Or test it directly:"
    echo "  CHATTERBOX_VOICE_REF=$OUTPUT TTS_PROVIDER=chatterbox uv run python pipeline.py voice <ID>"
else
    echo "Recording failed. Make sure your mic is connected."
    exit 1
fi
