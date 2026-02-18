"""Tests for video caption generation."""

import json
from pathlib import Path

from techslop.video.captions import generate_captions


def test_generate_captions(tmp_path):
    """Should produce a valid ASS file from timestamps."""
    timestamps = [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 0.5, "end": 1.0},
        {"word": "this", "start": 1.0, "end": 1.3},
        {"word": "is", "start": 1.3, "end": 1.5},
        {"word": "a", "start": 1.5, "end": 1.6},
        {"word": "test", "start": 1.6, "end": 2.0},
    ]

    ts_path = tmp_path / "timestamps.json"
    ts_path.write_text(json.dumps(timestamps))

    out_path = tmp_path / "captions.ass"
    result = generate_captions(ts_path, out_path)

    assert result == out_path
    assert out_path.exists()

    content = out_path.read_text()
    assert "[Script Info]" in content
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert "[Events]" in content
    # Should have dialogue lines
    assert "Dialogue:" in content
