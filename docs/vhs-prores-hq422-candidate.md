# Disposable ProRes HQ 4:2:2 preset candidate

**Status: candidate test only.** This does not modify VideoHelperSuite's exact-pinned upstream `video_formats/ProRes.json`, alter an existing ComfyUI installation, or authorize production deployment.

The previous synthetic ProRes test using the pinned VideoHelperSuite `profile=hq` reported **ProRes HQ (`apch`) with decoded `yuv444p10le`**, rather than the expected 10-bit 4:2:2 storage. An explicit `profile=4444` test correctly returned ProRes 4444 with `yuv444p12le`, but that is a different codec profile. Neither result establishes an HQ 4:2:2 output path.

The [candidate probe](../scripts/qualify_vhs_prores_hq422.py) performs a real two-output API execution on the disposable GitHub Actions CPU runner. It checks the original exact-pinned ProRes preset structure, preserves its bytes unchanged, then writes one untracked temporary preset `osf_ci_proreshq422.json` into the runner's cloned VideoHelperSuite `video_formats` directory. The candidate duplicates every upstream configuration field and makes a **single explicit change to the FFmpeg main pass**: appending `-pix_fmt yuv422p10le`.

Two native ComfyUI `EmptyImage` nodes create 64×64 red and blue frames. `ImageBatch` combines them. Both pinned `VHS_VideoCombine` instances consume **the exact same source**, both request `profile=hq`, run at 2 fps and set `save_output=false`:

| Output | Preset | Acceptance requirement |
|---|---|---|
| Stock control | `video/ProRes` | Actual ProRes HQ (`apch`), with observed default `yuv444p10le` |
| Explicit 422 candidate | `video/osf_ci_proreshq422` | Actual ProRes HQ (`apch`), with **`yuv422p10le`** |

The probe requires successful ComfyUI `/prompt` and `/history` results and exactly two distinct temporary MOVs. It retrieves each through loopback `/view` only, applies strict file metadata and a 2 MB size limit, verifies QuickTime/MP4 `ftyp`, and decodes with the pinned `imageio-ffmpeg==0.6.0` CPU binary. Both decoded RGB24 outputs must contain precisely two 64×64 frames ordered red then blue, with every RGB component within an absolute 24/255 tolerance for YUV roundtrips.

Only the **metadata-only JSON result** is retained, including original source hash, codec/profile, pixel format, per-frame maximum colour error and encoded-file hashes. No MOV or preview file is uploaded. The preset exists solely in the disposable runner and is not committed or reused in RunPod.

**Limits:** The inputs are 8-bit synthetic RGB constants. ProRes HQ's 10-bit 4:2:2 *storage* does not demonstrate 10-bit source fidelity, calibrated colour transforms, professional camera ingest, real footage, audio, HDR metadata, frame-rate stability under load or the selected eleven workflows. If this test passes, it is a **candidate-only format fix**, not an approved production preset. The older HQ default discrepancy remains a separate factual finding. Full selected-workflow runtime, model weights, GPU and licence acceptance remain on [issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
