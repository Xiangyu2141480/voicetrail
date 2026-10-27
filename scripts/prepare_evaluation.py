"""Fetch only the frozen CC BY 4.0 samples; synthetic files test errors only."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import urllib.request
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import soundfile as sf

from backend.app.config import Settings

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_URL = "https://www.openslr.org/resources/12/dev-clean.tar.gz"


def valid(path, sample):
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sample["sha256"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Use a local complete dev-clean.tar.gz")
    parser.add_argument("--offline", action="store_true", help="Fail if frozen samples are missing")
    args = parser.parse_args()
    settings = Settings.from_env()
    dataset = settings.data_dir / "evaluation"
    manifest = json.loads((ROOT / "docs/evaluation_manifest.json").read_text())
    missing = {s["id"] + ".flac": s for s in manifest["samples"]
               if not valid(dataset / s["path"], s)}
    if missing and args.offline:
        raise SystemExit("Frozen licensed samples missing or checksum differs; prepare online first.")
    if missing:
        print(f"Source: {ARCHIVE_URL}; license CC BY 4.0; retaining five frozen samples only.")
        with ExitStack() as stack:
            stream = stack.enter_context(args.archive.open("rb") if args.archive else
                                         urllib.request.urlopen(ARCHIVE_URL, timeout=60))
            archive = stack.enter_context(tarfile.open(fileobj=stream, mode="r|gz"))
            for member in archive:
                sample = missing.get(Path(member.name).name)
                if not sample or not member.isfile():
                    continue
                if member.size > 5_000_000:
                    raise SystemExit("Unexpected sample size.")
                content = archive.extractfile(member).read()
                if hashlib.sha256(content).hexdigest() != sample["sha256"]:
                    raise SystemExit(f"Frozen sample checksum differs: {sample['id']}")
                destination = dataset / sample["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
                del missing[Path(member.name).name]
                print(f"Verified {sample['id']}: {len(content)} bytes", flush=True)
                if not missing:
                    break
        if missing:
            raise SystemExit("Archive did not contain all frozen samples.")
    library = dataset / "ui-library"
    library.mkdir(parents=True, exist_ok=True)
    for sample in manifest["samples"]:
        assert valid(dataset / sample["path"], sample), sample["id"]
        if sample["role"] == "target":
            shutil.copyfile(dataset / sample["path"], library / f"{sample['id']} 原声.flac")
    # These signals never participate in real speaker-quality evaluation.
    sf.write(dataset / "short-reference.wav", np.zeros(32000), 16000, subtype="PCM_16")
    sf.write(dataset / "silence-reference.wav", np.zeros(80000), 16000, subtype="PCM_16")
    (library / "损坏 broken.mp4").write_bytes(b"not a media container")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "color=c=black:s=64x64:r=10", "-t", "1", "-an", "-c:v", "mpeg4",
                    str(library / "无音轨 video.mp4")], check=True)
    print("Frozen real samples and separate UI error fixtures ready.")


if __name__ == "__main__":
    main()
