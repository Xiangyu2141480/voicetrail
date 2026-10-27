# VoiceTrail v0.1.0-alpha.1 — local technical preview

Search an explicitly selected local media library using a real, pinned SpeechBrain ECAPA model on CPU. Listen to similar-voice candidates at their original timestamps, review them and export original audio as WAV clips with a provenance manifest in a ZIP.

The preview includes persistent/incremental indexing, per-file errors, cancellation, explicit retry after interruption, reference/review/export persistence, same-origin local UI, registered-media access and read-only source handling. No synthetic voice generation or cloud inference is used.

See [README](https://github.com/Xiangyu2141480/voicetrail/blob/main/README.md) or [中文启动说明](https://github.com/Xiangyu2141480/voicetrail/blob/main/README.zh-CN.md) for Python 3.11, Node 24, uv and external FFmpeg setup.

Validation scope: 24 offline engineering regressions, frontend type/build and contract checks; frozen five-utterance/three-speaker English retrieval ordering; network-blocked real inference and API indexing/export/restart; real Chromium original/exported WAV playback, forced crash/retry and persistent reviews. GitHub CI runs the engineering checks; the local real gates remain separate mandatory evidence.

Cosine scores are rankings, not identity probabilities. Different audiobook chapters do not demonstrate independent environments or cross-age reliability. Chinese/noisy family recordings, overlapping voices, large libraries and human adoption remain unverified. macOS ARM64 is the real-model/browser test platform; Linux has engineering CI coverage, and Windows is unsupported.

Original VoiceTrail code is MIT; dependencies, weights and data retain their licenses. This release contains source/documentation only. Model weights and evaluation audio must be prepared locally; no recordings, vectors, database or dependency binaries are attached.
