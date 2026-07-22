---
title: "Video Upscale with Florence2 Captioning"
osf_license: MIT
commercial_status: commercial-compatible
source: workflows/commercial-compatible/mm_upscale_video_workflow.json
---

# Video Upscale with Florence2 Captioning

Upscales a video/image sequence with UltimateSDUpscale, using Florence2 for auto-captioning and GGUF-quantized UNet loading.

**Commercial status: `commercial-compatible`**
All dependencies are permissively licensed or GPL-3.0 (GPL imposes distribution obligations, not a commercial-use ban) — safe for commercial use as far as this audit could determine.

> This workflow file and its original documentation are licensed under MIT. It requires third-party software and models that remain subject to their own licences. The MIT licence on this workflow does not grant rights to those dependencies.

## Dependencies

- comfyui-florence2 (MIT)
- ComfyUI-GGUF (Apache-2.0)
- ComfyUI_UltimateSDUpscale (GPL-3.0)
- rgthree-comfy (MIT)
- ComfyUI-Custom-Scripts / pysssss (MIT)
- ComfyUI-VideoHelperSuite (GPL-3.0)

Install with `../../scripts/install-dependencies.sh` (see repo root) or manually via ComfyUI-Manager.
Full license detail for every dependency: [THIRD_PARTY_LICENSES.md](../../THIRD_PARTY_LICENSES.md).
