# Native SAM3 track-preview CPU acceptance

This is a **model-free** live execution check of the pinned public
`SAM3_TrackPreview` node from
`Comfy-Org/ComfyUI@08cf0284ff45723aa67841c80cabb0e3cb50c9d7`.
It does **not** call SAM3 detection, segmentation or video tracking.

The disposable CPU runner uses the existing
`OSF_CI_SCAILTrack` fixture, which generates two frames of bit-packed
64×64 binary masks for two identities, with the right-hand identity
deliberately stored as object index 0 in frame zero. In frame one,
the identities exchange left/right positions **without changing their
SAM3 indices**, so preview colours must follow the track rather than
the current screen position. A two-node ComfyUI API graph
connects that synthetic `SAM3_TRACK_DATA` to the **real native**
`SAM3_TrackPreview` node with opacity 1.0 and 2 fps.

The output is created by the pinned native node itself through its PyAV
H.264 video writer, not by VideoHelperSuite or a compositing fallback.
The harness requires real loopback `/prompt` and `/history` completion,
one animated temporary `sam3_track_preview_<8 hex>.mp4`, and validates
its filename, subfolder and temp-only status. The existing 2 MB bound
applies to retrieving the MP4 from `/view`. Using the installed
imageio-FFmpeg binary, it identifies a genuine H.264 stream and decodes
exactly two 64×64 RGB24 frames. Five interior/background probes
in each frame require **orange left and blue right** on frame zero,
then **blue left and orange right** on frame one. This confirms
palette stability under a synthetic crossing with fixed identity
indices, not per-frame re-sorting. Every probe must be within
32 RGB code levels after H.264/YUV420 conversion. Per-frame hashes,
observed maximum channel errors and MP4 SHA-256 are metadata-only.

The probes exclude label glyph centres and hard mask edges: they
measure stable interior colours and background. The test does not
claim full-image/label raster equality, 10-bit media fidelity, genuine
SAM3 tracking accuracy, real-world crossing/occlusion performance or
long-duration encoding.

**No models, checkpoints, GPU, private footage or production services
are used.** This is native mask-preview rendering from already provided
synthetic tracks, not real SAM3 inference. The broader selected-eleven
GPU/model/rights acceptance remains on HOLD in
[issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
