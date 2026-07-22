---
title: "SCAIL-2 Pipeline Step 4.5 — SAM 3 Mask Generation"
osf_license: MIT
commercial_status: commercial-compatible
source: workflows/commercial-compatible/step4_5_sam3_mask.json
---

# SCAIL-2 Pipeline Step 4.5 — SAM 3 Mask Generation

Generates a colored SCAIL-2 conditioning mask from a driving video using SAM 3 detection/tracking. Feeds into the animation/replacement steps below.

**Commercial status: `commercial-compatible`**
All dependencies are permissively licensed or GPL-3.0 (GPL imposes distribution obligations, not a commercial-use ban) — safe for commercial use as far as this audit could determine.

> This workflow file and its original documentation are licensed under MIT. It requires third-party software and models that remain subject to their own licences. The MIT licence on this workflow does not grant rights to those dependencies.

## Dependencies

- ComfyUI core fork with native SCAIL-2 + SAM 3 support (GPL-3.0)
- ComfyUI-VideoHelperSuite (GPL-3.0)
- Model: SAM 3 (Meta SAM License)

Install with `../../scripts/install-dependencies.sh` (see repo root) or manually via ComfyUI-Manager.
Full license detail for every dependency: [THIRD_PARTY_LICENSES.md](../../THIRD_PARTY_LICENSES.md).
