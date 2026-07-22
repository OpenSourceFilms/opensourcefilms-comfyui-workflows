---
title: "VideoMaMa Matting — SAM3 Points + Text + Optical Flow"
osf_license: MIT
commercial_status: research-only
source: workflows/research-only/videomama_sam_points_text_matte_optflow.json
---

# VideoMaMa Matting — SAM3 Points + Text + Optical Flow

Video matting pipeline: SAM 3 point/text-prompted segmentation feeds VideoMaMa for mask-guided matting, with optical-flow mask propagation.

**Commercial status: `research-only`**
At least one dependency below is CC-BY-NC-4.0 or otherwise restricted to research/education use. Do not use this workflow's output commercially without separately clearing that dependency.

## Dependencies

- **ComfyUI-VideoMaMa — CC-BY-NC-4.0 code, checkpoint under Stability AI Community License (blocks commercial use)**
- ComfyUI-SAM3 (GPL-3.0)
- ComfyUI-VideoHelperSuite (GPL-3.0)
- mask_propagate_optical_flow — OSF's own code (MIT)
- ComfyUI-RMBG (GPL-3.0)
- rgthree-comfy (MIT)

Install with `../../install.sh` (see repo root) or manually via ComfyUI-Manager.
Full license detail for every dependency: [THIRD_PARTY_LICENSES.md](../../THIRD_PARTY_LICENSES.md).
