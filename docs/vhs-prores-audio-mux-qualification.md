# Synthetic ProRes 4444 video and PCM audio mux acceptance

This is an **isolated, disposable CPU** test of the actual pinned
`VHS_VideoCombine` audio-mux branch. It is separate from ComfyUI
model inference, feature-film media ingest, the real eleven-workflow
GPU deployment, and the independent FFmpeg 12-bit source checks.

The fixed model-free three-node graph creates two black 64×64
`EmptyImage` frames (2 fps) and one 48 kHz mono 440 Hz sine tone of
0.2 amplitude from the **test-only**
[`OSFTestSineAudio`](../tests/fixtures/comfy_synthetic_audio/__init__.py)
custom node. It sends both to pinned VideoHelperSuite's
`VHS_VideoCombine`, with `video/ProRes`, `profile=4444` and
`save_output=false`. The upstream format declares PCM `s16le`
audio for a QuickTime MOV.

The [runtime gate](../scripts/qualify_vhs_audio_mux.py) executes the
real ComfyUI `/prompt` graph, awaits completed `/history` records,
and requires exactly one temporary `-audio.mov` entry. The file is
retrieved from `127.0.0.1` via strict name, type and subfolder
validation with a 2 MB limit. Only the disposable runner handles the
encoded media.

The pinned FFmpeg decoder independently requires a ProRes 4444 video
stream with exactly two black 64×64 frames and an **uncompressed
mono PCM s16le audio stream at 48 kHz**. It decodes audio to float32,
checks sample count close to one second, peak amplitude around 0.2,
and deterministic waveform checkpoints against the expected 440 Hz
sine. Incorrect or missing audio, silent tracks, wrong tone/frequency,
wrong output format, excessive sample deviations, and missing video
frames fail closed.

The uploaded evidence is **JSON only**: codec, signal validation,
counts, maximum sample error and hashes. Neither encoded MOV nor
decoded waveform is uploaded.

## Non-acceptance

This short synthetic check does **not** establish sample-accurate
audio/video sync for production clips, dialogue intelligibility,
surround sound, 24-bit PCM, 96 kHz, Atmos, timecode, channel-layout
metadata, long-duration drift, delivery-loudness compliance, arbitrary
audio sample rates, or GPU/workflow inference. It does not change a
production VHS preset or install any custom node in a live RunPod
instance. A successful result is one narrow PCM mux smoke test, not
full audio post-production acceptance.

Source coverage and model/rights holds remain tracked under
[issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
