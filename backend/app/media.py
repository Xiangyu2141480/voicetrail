from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path


class MediaError(ValueError):
    """An understandable media operation failure; never includes a private path."""


@dataclass(frozen=True)
class MediaInfo:
    duration_ms: int
    has_audio: bool
    sample_rate: int | None
    channels: int | None


def run_media(args: list[str], timeout: int = 600):
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise MediaError("FFmpeg/FFprobe is missing; install FFmpeg and restart.") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaError("Media processing timed out.") from exc
    if result.returncode:
        # Raw stderr may contain source paths, so do not return it to the API/log.
        raise MediaError("Media could not be decoded; check that it is readable and not damaged.")
    return result.stdout


def inspect_media(path: Path) -> MediaInfo:
    payload = run_media(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                         "-of", "json", str(path)], timeout=30)
    try:
        data = json.loads(payload)
        audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
        duration = data.get("format", {}).get("duration")
        if duration is None and audio:
            duration = audio.get("duration")
        if duration is None:
            raise MediaError("Media duration could not be determined.")
        return MediaInfo(round(float(duration) * 1000), audio is not None,
                         int(audio["sample_rate"]) if audio else None,
                         int(audio["channels"]) if audio else None)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, MediaError):
            raise
        raise MediaError("Unsupported media metadata.") from exc


def extract_audio(path: Path, output: Path, start_ms: int = 0,
                  end_ms: int | None = None) -> MediaInfo:
    if start_ms < 0 or (end_ms is not None and end_ms <= start_ms):
        raise MediaError("Invalid audio time range.")
    info = inspect_media(path)
    if not info.has_audio:
        raise MediaError("This file has no audio track.")
    end_ms = info.duration_ms if end_ms is None else end_ms
    if end_ms > info.duration_ms + 100 or start_ms >= info.duration_ms:
        raise MediaError("Audio range exceeds the source duration.")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_name(f".{uuid.uuid4().hex}.wav")
    try:
        # Seek after input: decode the original timeline, including compressed inputs.
        run_media(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(path),
                   "-ss", str(start_ms / 1000), "-t", str((end_ms - start_ms) / 1000),
                   "-map", "0:a:0", "-vn", "-ar", "16000", "-ac", "1",
                   "-c:a", "pcm_s16le", str(staging)])
        result = inspect_media(staging)
        if (not result.has_audio or abs(result.duration_ms - (end_ms - start_ms)) > 100
                or staging.stat().st_size < 100):
            raise MediaError("Decoded audio duration did not match the selected range.")
        os.replace(staging, output)
        return result
    finally:
        staging.unlink(missing_ok=True)


def fingerprint(path: Path) -> dict:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    identity = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
    if identity(before) != identity(after):
        raise MediaError("Source changed while being read; retry indexing.")
    return {"device": after.st_dev, "inode": after.st_ino, "size": after.st_size,
            "mtime_ns": after.st_mtime_ns, "sha256": digest.hexdigest()}
