---
title: "SAM 3 Custom Package Probe"
osf_license: MIT
commercial_status: commercial-compatible
source: workflows/commercial-compatible/sam3_custompkg_probe.json
---

# SAM 3 Custom Package Probe

Minimal SAM 3 segmentation test: point/box prompts in, combined mask out. Useful as a smoke test after installing ComfyUI-SAM3.

**Commercial status: `commercial-compatible`**
This workflow requires Meta SAM 3 under the **custom SAM License**, as well
as separately licensed ComfyUI nodes. The reviewed SAM terms grant use without
a blanket non-commercial-use prohibition, but impose redistribution,
attribution, prohibited-use and other conditions. Here,
`commercial-compatible` is a **conditional dependency assessment**, not a
statement that every dependency is MIT/Apache/GPL or an unconditional legal
clearance. Check the current [Meta SAM License](https://github.com/facebookresearch/sam3/blob/main/LICENSE)
and all exact dependencies before commercial use.

> This workflow file and its original documentation are licensed under MIT. It requires third-party software and models that remain subject to their own licences. The MIT licence on this workflow does not grant rights to those dependencies.

## Dependencies

- ComfyUI core (GPL-3.0)
- ComfyUI-SAM3 (GPL-3.0)
- Model: SAM 3 (Meta SAM License)

Install with `../../scripts/install-dependencies.sh` (see repo root) or manually via ComfyUI-Manager.
Full license detail for every dependency: [THIRD_PARTY_LICENSES.md](../../THIRD_PARTY_LICENSES.md).
