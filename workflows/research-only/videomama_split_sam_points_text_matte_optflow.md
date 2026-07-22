---
title: "VideoMaMa Matting; Split Variant"
osf_license: MIT
commercial_status: research-only
source: workflows/research-only/videomama_split_sam_points_text_matte_optflow.json
---

# VideoMaMa Matting; Split Variant

Split-processing variant of the VideoMaMa matting pipeline, for longer source videos processed in segments.

**Commercial status: `research-only`**
At least one dependency below is CC-BY-NC-4.0 or otherwise restricted to research/education use. Do not use this workflow's output commercially without separately clearing that dependency.

> This workflow file and its original documentation are licensed under MIT. It requires third-party software and models that remain subject to their own licences. The MIT licence on this workflow does not grant rights to those dependencies.

## Dependencies

- **ComfyUI-VideoMaMa, CC-BY-NC-4.0 code, checkpoint under Stability AI Community License (blocks commercial use)**
- ComfyUI-SAM3 (GPL-3.0)
- ComfyUI-Easy-Sam3 (Apache-2.0)
- ComfyUI-VideoHelperSuite (GPL-3.0)
- mask_propagate_optical_flow; OSF's own code (MIT)
- ComfyUI-RMBG (GPL-3.0)
- rgthree-comfy (MIT)

Install with `../../scripts/install-dependencies.sh` (see repo root) or manually via ComfyUI-Manager.
Full license detail for every dependency: [THIRD_PARTY_LICENSES.md](../../THIRD_PARTY_LICENSES.md).
