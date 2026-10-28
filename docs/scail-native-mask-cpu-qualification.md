# Native SCAIL-2 coloured-mask CPU execution, synthetic only

This isolated acceptance exercises the **actual pinned public ComfyUI**
`SCAIL2ColoredMask` implementation, rather than merely checking that the
node is registered or its published input fields match a workflow.

## Provenance and execution

The disposable GitHub Actions CPU runner installs public
`Comfy-Org/ComfyUI@08cf0284ff45723aa67841c80cabb0e3cb50c9d7`.
Its native source is `comfy_extras/nodes_scail.py`. The same pinned
ComfyUI runtime already registers five SAM3/SCAIL classes.

A small **test-only** custom-node fixture,
[`comfy_scail_cpu_source`](../tests/fixtures/comfy_scail_cpu_source/__init__.py),
creates two frames of two synthetic identities in SAM3's bit-packed
`SAM3_TRACK_DATA` shape, plus a plain `MASK` reference subject. The
track's right-hand object deliberately precedes the left-hand object
in its original index order. No SAM3 detection, tracking model, camera
footage, external files or model downloads are used.

The [CPU test driver](../scripts/qualify_scail_native_mask_cpu.py)
submits an **actual ComfyUI `/prompt` graph** with two calls to native
`SCAIL2ColoredMask`, both with `sort_by=left_to_right`: one
`replacement_mode=false` (animation), the other
`replacement_mode=true` (replacement). Both outputs of each call are
sent to native `PreviewImage` nodes.

The harness requires successful completion in `/history` and checks
all pixels in **six** temporary 64×64 PNG previews:

- Both driving frames show the **left identity blue** and **right
  identity red**, regardless of the reverse object index order.
- Animation-mode driving background is **black** and its reference-mask
  background is **white**.
- Replacement-mode driving background is **white** and its reference-mask
  background is **black**.
- The single reference subject remains **blue** in both modes.

The RGB comparison is exact, covering every pixel, not merely a preview
count or a single pixel. Source and output geometry are fixed and small.
Only JSON status and frame pixel SHA-256 hashes are saved to the evidence
artifact. The preview PNGs remain in the disposable runner. The
existing temporary-asset safeguards (safe filename, temp-only and a
2 MB limit) are reused.

## Non-acceptance

This verifies **native SCAIL-2 mask-colour rendering and background
semantics**, not SAM3 segmentation/tracking inference, SCAIL-2 or Wan
diffusion, driving-video realism, arbitrary multi-identity occlusion,
reference matching on real media, GPU execution or model rights.
It does not substitute conventional VFX or compositing for SCAIL; it
tests part of SCAIL's own preparation logic in isolation.

It neither changes source models nor creates a production fixture,
preset or ComfyUI installation. No RunPod workload, private media,
weights or GPU resources are used. The selected eleven-workflow
qualification remains **OPEN** under
[issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
