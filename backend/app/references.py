import numpy as np

from .db import new_id
from .embedding import prepare_voice
from .media import MediaError, extract_audio, fingerprint


def create_reference(db, settings, model, source, name, start_ms=0, end_ms=None):
    identifier = new_id()
    output = settings.data_dir / "references" / f"{identifier}.wav"
    before = fingerprint(source)
    try:
        info = extract_audio(source, output, start_ms, end_ms)
        audio, _ = prepare_voice(output, reference=True)
        vector = model.embed_samples(audio)
        if fingerprint(source) != before:
            raise MediaError("Reference source changed during processing; retry.")
        version = model.info
        db.execute("INSERT INTO reference VALUES(?,?,?,?,?,?,?)",
                   (identifier, name, info.duration_ms, version.id, version.revision,
                    version.preprocessing_version, np.asarray(vector, dtype="<f4").tobytes()))
        return {"id": identifier, "name": name, "duration_ms": info.duration_ms}
    except BaseException:
        output.unlink(missing_ok=True)
        raise
