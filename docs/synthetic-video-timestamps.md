# Synthetic H.264, HEVC and ProRes presentation timing acceptance

This is an additional **model-free CPU acceptance check** for the existing
pinned VideoHelperSuite/rgthree synthetic ComfyUI API graph.

## What the test measures

The 14-node ComfyUI graph produces exactly two selected 64×64 RGB frames
at a requested **2 frames per second**. Existing checks verify actual
H.264, HEVC and ProRes 4444 codec identities and full decoded-frame
colour content. This timing gate opens each temporary encoded output
with the pinned `imageio-ffmpeg==0.6.0` binary, uses the `showinfo`
decoder filter and requires:

- Exactly two decoded frame records, in sequence `n=0,1`.
- Nominal frame rate `2/1` reported by the decoder.
- Presentation timestamps **0.0 seconds and 0.5 seconds**.
- Each frame's reported duration **0.5 seconds**.
- Positive monotonic timestamp ticks and duration ticks.

The parsed values are retained in the JSON-only CPU evidence under
`h264_mp4.video_timing`, `h265_mp4.video_timing` and
`prores_mov.video_timing`. A nonzero exit, malformed diagnostic,
incorrect frame count, wrong cadence or missing duration fails the
qualification. Contract tests also inject duplicate/reordered indices,
a wrong nominal FPS, timing drift and incomplete metadata.

Each file is generated entirely from fixed synthetic images and read
only from a disposable runner's temporary directory. No source footage,
binary MP4/MOV files, generated imagery or external model weights are
uploaded. No RunPod GPU or live ComfyUI service is used.

## What this does not qualify

Two-frame timing is not a substitute for long-duration timing stability,
variable-frame-rate handling, frame drops under load, audiovisual
synchronisation, timecode, colour fidelity, production resolution, output
container interoperability or 11-workflow model inference. This is a
strict narrow **two-frame, 2 fps** temporal smoke check, not a production
delivery acceptance. See
[clean CPU qualification scope](clean-cpu-runtime-qualification.md).
