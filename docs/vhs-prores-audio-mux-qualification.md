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
requires exactly 48,000 samples for the fixed one-second source
(no accepted padding), a peak amplitude around 0.2, and compares
**every one of the 48,000 decoded samples** against the analytic 440 Hz
sine at matching sample indices. The maximum absolute error must be
at most 0.001 per float32 sample, allowing a margin for 16-bit PCM
quantisation. Unlike the earlier 16-checkpoint gate, this rejects
corruption at any position, including a 3,000-sample silent tail or
an isolated off-grid sample error. Incorrect or missing audio, padding,
truncation, wrong tone/frequency, wrong output format and missing
video frames fail closed.

The uploaded evidence is **JSON only**: codec, signal validation,
counts, maximum and mean full-waveform sample errors and hashes. Neither encoded MOV nor
decoded waveform is uploaded.

## Independent two-channel PCM16 channel identity test

An additional model-free ComfyUI graph uses a **second, test-only**
`OSFTestStereoAudio` source class in the same disposable fixture.
It generates 48 kHz stereo audio with independently identifiable channels:
**440 Hz at amplitude 0.20 on the left** and **660 Hz at amplitude 0.14
on the right**. The `AUDIO` waveform has exactly one batch, two
channels, and 48,000 source sample frames. It combines this with two
synthetic black images using the actual pinned `VHS_VideoCombine`
`video/ProRes` / `profile=4444` node and `save_output=false`.

The separate [stereo qualification gate](../scripts/qualify_vhs_stereo_pcm_mux.py)
uses the real ComfyUI `/prompt` and `/history` paths, validates the
temporary `-audio.mov` filename, and retrieves the MOV only via
loopback `/view` with the existing 2 MB limit. FFmpeg must identify
ProRes 4444 video containing exactly two black 64×64 frames and a
**48 kHz stereo PCM s16le track**. Decoded interleaved float32 audio
is verified *channel by channel* against both independently generated
sine waves for **46,976 consecutive sample frames**, not a sparse
selection of checkpoints. Maximum permitted absolute waveform error
is **0.003 per channel**; the two source-channel amplitudes must also
fall within their distinct peak ranges.

The negative contracts reject missing/unsafe output, mono duplicates,
swapped left and right, wrong amplitude or frequency, odd frame
alignment, NaNs, sample-count discrepancies, and even a single
out-of-tolerance interior sample. This demonstrates **channel
identity and separation** through this particular short synthetic
VHS/ProRes PCM16 mux path, not multi-hour drift or cross-device sync.
Only numeric errors, codec metadata and hashes are included in
JSON-only evidence; no MOVs or decoded audio are retained or uploaded.

## Non-acceptance

These short synthetic checks do **not** establish sample-accurate
audio/video sync for production clips, dialogue intelligibility,
surround sound, 24-bit PCM, 96 kHz, Atmos, timecode, channel-layout
metadata, long-duration drift, delivery-loudness compliance, arbitrary
audio sample rates, or GPU/workflow inference. It does not change a
production VHS preset or install any custom node in a live RunPod
instance. A successful result is one narrow PCM mux smoke test, not
full audio post-production acceptance.

Source coverage and model/rights holds remain tracked under
[issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
