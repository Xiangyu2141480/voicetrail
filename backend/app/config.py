import os
from dataclasses import dataclass
from pathlib import Path

MODEL_ID = "speechbrain/spkrec-ecapa-voxceleb"
MODEL_REVISION = "0f99f2d0ebe89ac095bcc5903c4dd8f72b367286"
PREPROCESSING_VERSION = "pcm16k-vad2-window10-hop5-v1"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    port: int = 8765
    dev_ui: bool = False

    @classmethod
    def from_env(cls):
        default = Path.home() / "Library/Application Support/VoiceTrail"
        if os.name != "posix" or not Path("/System/Library").exists():
            default = Path.home() / ".local/share/voicetrail"
        return cls(Path(os.getenv("VOICETRAIL_DATA", str(default))).expanduser().resolve(),
                   int(os.getenv("VOICETRAIL_PORT", "8765")),
                   os.getenv("VOICETRAIL_DEV_UI") == "1")

    def prepare(self):
        for folder in ("tmp", "references", "exports", "previews", "models"):
            (self.data_dir / folder).mkdir(parents=True, exist_ok=True)
