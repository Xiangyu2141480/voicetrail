import subprocess
from pathlib import Path

import pytest

from backend.app.media import MediaError, extract_audio, inspect_media


def generate(path: Path, *args: str):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, str(path)], check=True)


def test_extract_normalizes_to_16k_mono(tmp_path):
    source, output = tmp_path / "source.wav", tmp_path / "out.wav"
    generate(source, "-f", "lavfi", "-i", "sine=frequency=500:duration=4", "-ar", "48000", "-ac", "2")
    info = extract_audio(source, output, 700, 2700)
    assert info.sample_rate == 16000 and info.channels == 1
    assert abs(info.duration_ms - 2000) <= 100
    assert output.stat().st_size > 1000


def test_unicode_path_and_no_audio(tmp_path):
    source = tmp_path / "中文 空格.wav"
    generate(source, "-f", "lavfi", "-i", "sine=duration=1")
    assert inspect_media(source).has_audio
    silent_video = tmp_path / "无音轨.mp4"
    generate(silent_video, "-f", "lavfi", "-i", "color=size=32x32:duration=1", "-an")
    assert not inspect_media(silent_video).has_audio
    output = tmp_path / "bad.wav"
    with pytest.raises(MediaError, match="audio"):
        extract_audio(silent_video, output)
    assert not output.exists()


def test_corrupt_media(tmp_path):
    source, output = tmp_path / "corrupt.mp4", tmp_path / "out.wav"
    source.write_bytes(b"not media")
    with pytest.raises(MediaError):
        extract_audio(source, output)
    assert not output.exists()


def test_invalid_bounds_do_not_remove_existing_output(tmp_path):
    output = tmp_path / "existing.wav"
    output.write_bytes(b"preserve")
    with pytest.raises(MediaError):
        extract_audio(tmp_path / "missing.wav", output, -1, 10)
    assert output.read_bytes() == b"preserve"
