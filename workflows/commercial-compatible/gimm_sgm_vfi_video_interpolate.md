---
title: "GIMM-VFI + SGM-VFI Video Interpolation"
osf_license: MIT
commercial_status: commercial-compatible
source: workflows/commercial-compatible/gimm_sgm_vfi_video_interpolate.json
---

# GIMM-VFI + SGM-VFI Video Interpolation

Frame-interpolates a source video using GIMM-VFI and SGM-VFI (segment-wise), with FPS downsampling for source prep.

**Commercial status: `commercial-compatible`**
All dependencies are permissively licensed or GPL-3.0 (GPL imposes distribution obligations, not a commercial-use ban) — safe for commercial use as far as this audit could determine.

## Dependencies

- ComfyUI-DownsampleFPS (Apache-2.0)
- rgthree-comfy (MIT)
- ComfyUI-GIMM-VFI (ISC)
- ComfyUI-Tween — provides SGM-VFI (Apache-2.0)
- ComfyUI-VideoHelperSuite (GPL-3.0)

Install with `../../install.sh` (see repo root) or manually via ComfyUI-Manager.
Full license detail for every dependency: [THIRD_PARTY_LICENSES.md](../../THIRD_PARTY_LICENSES.md).
