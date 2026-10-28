# Experimental VHS ProRes 16-bit input path, disposable CPU only

This narrowly qualifies whether **pinned VideoHelperSuite** preserves
sub-8-bit distinctions when its ProRes encoder receives a ComfyUI
`IMAGE` tensor and a reviewed format preset with
`input_color_depth=16bit`.

## Provenance and scope

The separately accepted [source code audit](vhs-prores-input-precision.md)
found that upstream
`ComfyUI-VideoHelperSuite@2984ec4c4b93292421888f38db74a5e8802a8ff8`
uses `tensor_to_bytes` (8-bit `rgb24`) by default, but
`tensor_to_shorts` (16-bit `rgb48`) when
`input_color_depth=16bit` is specified. Upstream
`video_formats/ProRes.json` does **not** select the 16-bit path.

This acceptance test makes exactly **one local override**: after verifying
the pinned upstream source, it creates a new untracked preset
`video_formats/osf_ci_prores16bit.json` in the throwaway runner checkout.
This preset duplicates the upstream ProRes JSON, adding only
`"input_color_depth": "16bit"`. The original pinned file remains
byte-for-byte unchanged, and the additional preset is never committed to
the public repository or deployed to RunPod.

A separate OSF-authored, **test-only** ComfyUI custom node, copied into
the disposable runner from
`tests/fixtures/comfy_12bit_source/__init__.py`, generates a two-frame
64×64 float32 `IMAGE` tensor. Each frame contains four grayscale
32×32 tiles whose intensities encode distinct 12-bit levels, including
two left/right pairs per frame that map to **the same 8-bit RGB value**.

The test submits a real ComfyUI `/prompt` graph with identical source
frames routed to two pinned `VHS_VideoCombine` nodes:

1. **Control:** the original `video/ProRes` preset, `profile=4444`
   (upstream default 8-bit input conversion).
2. **Opt-in:** `video/osf_ci_prores16bit`, `profile=4444`
   (the same preset plus the explicit 16-bit input override).

Both return temporary MOVs with `save_output=false`. The harness
accepts only safe loopback `/view` filenames, caps media at 2 MB,
and uses the pinned CPU FFmpeg executable to verify actual ProRes 4444
storage (`yuv444p12le`) and decode exactly two 64×64 frames of 12-bit
YUV444 samples per output. It requires four tested luminance tile pairs
to **collapse** in the default 8-bit control, but remain **distinct and
correctly ordered** in the opt-in path. Each preserved difference must
be between 1 and 20 out of 4095 12-bit code levels.

The acceptance report contains only numeric differences, hashes of
the temporary MOVs and an explicit failure of bit-exact fidelity
qualification. The videos and source tensors remain in the disposable
runner and are not uploaded.

## Important limitations

Passing this narrow comparison is **evidence of retaining controlled
sub-8-bit distinctions through the tested float32 ComfyUI tensor →
16-bit RGB48 VHS input → ProRes 4444 encode → 12-bit YUV decode**.
It is **not** a calibrated 12-bit RGB or YUV roundtrip, nor evidence of
bit-exact component reproduction, transfer-function correctness,
colour-managed HDR acquisition, timebase accuracy, larger image sizes,
full sensor precision, codec/container suitability for production,
or any model/11-workflow inference.

No production formats, ComfyUI installations or user footage are
changed. This uses a temporary test node, a temporary ProRes preset and
a zero-weight CPU-only ComfyUI runner. Upstream software licences remain
unchanged. The general 11-workflow GPU/model acceptance is tracked under
[issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
