"""Prepare licensed real audio plus explicit error fixtures outside the repository."""
import hashlib
import json
import shutil
from pathlib import Path

from backend.app.config import Settings
from backend.app.media import extract_audio, run_media


def main():
    settings = Settings.from_env()
    evaluation = settings.data_dir / "evaluation"
    manifest = json.loads(Path("docs/evaluation_manifest.json").read_text())
    target = evaluation / "ui-library"
    target.mkdir(exist_ok=True)
    for sample in manifest["samples"]:
        source = evaluation / sample["path"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == sample["sha256"], sample["id"]
        if sample["role"] == "target":
            shutil.copyfile(source, target / f"{sample['id']} 中文 空格.flac")
    run_media(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i",
               "color=c=black:s=64x64:d=2", "-an", str(target / "无音轨 video.mp4")])
    (target / "损坏 broken.wav").write_bytes(b"This is deliberately broken test media.")
    reference = evaluation / "references/2277-149896-0032.flac"
    extract_audio(reference, evaluation / "short-reference.wav", 0, 2000)
    run_media(["ffmpeg", "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i",
               "anullsrc=r=16000:cl=mono", "-t", "5", str(evaluation / "silence-reference.wav")])
    print(json.dumps({"library": str(target), "evaluation": str(evaluation)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
