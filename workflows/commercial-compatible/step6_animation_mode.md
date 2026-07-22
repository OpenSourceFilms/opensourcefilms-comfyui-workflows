---
title: "SCAIL-2 Pipeline Step 6; Animation Mode"
osf_license: MIT
commercial_status: commercial-compatible
source: workflows/commercial-compatible/step6_animation_mode.json
---

# SCAIL-2 Pipeline Step 6; Animation Mode

Drives a reference character with a SAM3-masked source video using SCAIL-2, in animation (motion-transfer) mode.

**Commercial status: `commercial-compatible`**
All dependencies are permissively licensed or GPL-3.0 (GPL imposes distribution obligations, not a commercial-use ban), safe for commercial use as far as this audit could determine.

> This workflow file and its original documentation are licensed under MIT. It requires third-party software and models that remain subject to their own licences. The MIT licence on this workflow does not grant rights to those dependencies.

## Dependencies

- ComfyUI core fork with native SCAIL-2 + SAM 3 support (GPL-3.0)
- ComfyUI-VideoHelperSuite (GPL-3.0)
- Model: SAM 3 (Meta SAM License)
- Model: SCAIL-2 / Wan2.1-14B (Apache-2.0, zai-org)
- Wan CLIP/VAE components (Apache-2.0)

Install with `../../scripts/install-dependencies.sh` (see repo root) or manually via ComfyUI-Manager.
Full license detail for every dependency: [THIRD_PARTY_LICENSES.md](../../THIRD_PARTY_LICENSES.md).
