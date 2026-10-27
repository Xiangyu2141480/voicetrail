import numpy as np
import pytest
import soundfile as sf

from backend.app.embedding import prepare_voice
from backend.app.media import MediaError


def test_silence_and_short_reference_rejected(tmp_path):
    silent = tmp_path / "silent.wav"
    sf.write(silent, np.zeros(16000 * 12), 16000, subtype="PCM_16")
    with pytest.raises(MediaError, match="speech"):
        prepare_voice(silent, reference=True)
    short = tmp_path / "short.wav"
    sf.write(short, np.zeros(16000), 16000, subtype="PCM_16")
    with pytest.raises(MediaError, match="3"):
        prepare_voice(short, reference=True)
