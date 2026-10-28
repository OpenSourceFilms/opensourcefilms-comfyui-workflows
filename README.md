# opensourcefilms-comfyui-workflows

ComfyUI workflow graphs used in production by [Open Source Films](https://github.com/OpenSourceFilms),
released under MIT. These are the actual workflow graphs we use, not vendored
copies of other people's tools, plus one custom node package that's genuinely
ours.

> Unless otherwise stated, original code, workflow files and documentation
> authored by Open Source Films are licensed under the MIT License.
> Third-party software, models, weights and datasets remain subject to their
> respective licences. The MIT licence applied to an OSF workflow or
> integration does not grant additional rights to its dependencies.
> Commercial suitability depends on the complete dependency set selected by
> the user.

## Credit to the original developers

**These are OSF's integrations and parameterised workflow graphs, not OSF-developed AI models.** We use software and research created by the [ComfyUI](https://github.com/Comfy-Org/ComfyUI) community and independent upstream teams, including the authors of SCAIL-2, Meta SAM, Wan, VideoMaMa, GIMM-VFI and other node/model projects where referenced. The underlying model architectures, trained weights and external custom nodes remain those authors' work.

OSF's contribution here is assembling, testing and documenting workflow combinations, plus a separately identified optical-flow mask propagation node. A workflow's MIT licence covers only its original OSF-authored material, **not** downstream rights to the upstream models or software. See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md), [DEPENDENCIES.lock](DEPENDENCIES.lock) and each workflow's sidecar for project-specific credits and restrictions.

## What's in here vs. what isn't

- **In this repo**: the workflow graph JSON files (node connections,
  parameters, prompts), one OSF-authored custom node package
  (`custom_nodes/mask_propagate_optical_flow/`), a legacy dependency installer
  with a mixture of pinned and mutable upstream references, and dependency
  documentation.
- **Not in this repo**: ComfyUI itself, third-party custom node source code,
  or any model weights. The **legacy** `scripts/install-dependencies.sh`
  clones a broad set of third-party custom nodes from their upstream repositories.
  Some references are commit-pinned, but others use mutable `main` and the
  default group includes nodes used only by research workflows. It is not a
  reproducible or rights-cleared minimal install. Obtain model weights from
  upstream sources yourself: see the license/source notes in each workflow's `.md` sidecar,
  [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md), and
  [DEPENDENCIES.lock](DEPENDENCIES.lock) (machine-readable, canonical if it
  ever disagrees with the prose docs).

## Commercial use

Every workflow is labeled with a `commercial_status` in its `.md` sidecar
file, one of:

- **`commercial-compatible`**; the reviewed dependencies do not have an
  identified blanket non-commercial-use prohibition. This **does not** mean
  every dependency is MIT, Apache or GPL: several workflows use Meta SAM 3
  under the **custom SAM License**, with additional attribution,
  redistribution, prohibited-use and other contractual conditions. GPL-3.0
  also imposes obligations when covered software is distributed. This label
  is a conditional OSF assessment, **not** legal clearance for every use or
  deployment. Check current terms and the exact dependency versions first.
- **`research-only`**; at least one dependency is CC-BY-NC-4.0 or otherwise
  restricted to research/education use. Don't use these commercially without
  separately clearing that dependency with its owner.

Full detail, upstream URLs, and pinned commits/versions for every dependency:
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

This is our own assessment, based on reading the actual license text of each
dependency (not just trusting badges/labels); it is not legal advice.
Verify independently before any commercial distribution.

## Workflows

### `workflows/commercial-compatible/`

| Workflow | What it does |
|---|---|
| `sam3_custompkg_probe.json` | Minimal SAM 3 segmentation smoke test |
| `step4_5_sam3_mask.json` | SCAIL-2 pipeline: SAM 3 mask generation from a driving video |
| `step6_animation_mode.json` | SCAIL-2 pipeline: character animation / motion transfer |
| `step7_replacement_mode.json` | SCAIL-2 pipeline: character replacement |
| `gimm_sgm_vfi_video_interpolate.json` | Frame interpolation with GIMM-VFI + SGM-VFI |
| `mm_upscale_video_workflow.json` | Video upscale with Florence2 auto-captioning |
| `wan22_fmlf_first_middle_last_frame.json` | Wan 2.2 first/middle/last-frame to video |
| `video_wan2_2_14B_flf2v.json` | Wan 2.2 14B first-last-frame to video |
| `video_wan2_2_14B_fmlf2v.json` | Wan 2.2 14B first-middle-last-frame to video (simple variant) |
| `video_wan2_2_14B_i2v.json` | Wan 2.2 14B image to video |
| `video_wan_vace_14B_v2v.json` | Wan VACE 14B video-to-video with Canny conditioning |

### `workflows/research-only/`

| Workflow | What it does | Blocked by |
|---|---|---|
| `videomama_sam_points_text_matte_optflow.json` | SAM3 + VideoMaMa mask-guided matting | VideoMaMa (CC-BY-NC-4.0 / Stability AI Community License) |
| `videomama_split_sam_points_text_matte_optflow.json` | Same, segmented for longer videos | VideoMaMa |
| `sam_effecteraser_points_text_matte_optflow.json` | SAM3 + EffectErase object removal | EffectErase (CC-BY-NC-4.0) |
| `frame_interpolation_test.json` | 4-way interpolation comparison | BiM-VFI (research/education only) |
| `tween_interpolate_loop.json` | Looping interpolation via ComfyUI-Tween | BiM-VFI (research/education only) |

A separate [live node-class coverage audit](docs/clean-cpu-runtime-qualification.md#real-eleven-workflow-node-registration-coverage) compares the actual class IDs in **all eleven selected commercial-compatible UI/API graphs** with the `/object_info` registry of the isolated pinned clean ComfyUI CPU test. It reports registered IDs, missing fork-native and custom-node IDs, UI annotations and unresolved UUID-typed groups, without installing the full dependency set or claiming GPU/model inference compatibility.

For a no-GPU structural check of exported graphs, use the
[offline workflow validator](docs/validate-workflows.md). It does not check model
availability or runtime correctness.

For the **eleven selected commercial-compatible workflows**, the
[source-only node-class coverage preflight](docs/selected-11-node-coverage.md)
audits both ComfyUI UI and API exports, identifies native SCAIL-2/SAM3
class names in pinned public ComfyUI and unresolved embedded-group execution,
and distinguishes clean-CPU registrations from unverified model/runtime
operations. The [eleven-workflow admission HOLD report](docs/selected11-release-hold.md)
reconciles this inventory with embedded link and provider-provenance audits
and **fails closed** on report drift. A passing HOLD report is **not** an
assertion that the eleven graphs execute, are GPU-qualified or have cleared
model rights.

The disposable CPU acceptance also requires the exact-pinned Florence2
loader and runner to register with the expected live input/output sockets.
**This is not Florence2 model loading or inference.** The pinned model
loader downloads weights only if executed; the CPU test does not execute it.

For byte-level verification of delivered native `SaveImage` sequences, use the
[read-only PNG sequence audit](docs/audit-native-png-sequence.md). It verifies
frame counts, dimensions, bit depth, chunk CRCs and file hashes without
compositing or changing pixels.

## Custom nodes

`custom_nodes/mask_propagate_optical_flow/` is Open Source Films' own code:
two nodes (`MaskPropagateOpticalFlow`, `MaskPropagateFromFlow`) that
propagate a single mask across a video's frames using OpenCV Farneback
optical flow, so you draw or generate one mask instead of one per frame. No
external model weights, no third-party dependencies beyond OpenCV/NumPy/
PyTorch (which ComfyUI already requires). Used by the matting/object-removal
workflows in `workflows/research-only/`. Published here for the first time,
MIT-licensed; see its own [README](custom_nodes/mask_propagate_optical_flow/README.md).

## Install: broad legacy script versus strictly scoped bundle

The historical installer below clones a **broad custom-node set**. By default
it omits two explicitly research-restricted packages (BiM-VFI and VideoMaMa),
but its default list **still contains some nodes used only in research workflows**
and mutable `main` references. It is **not** a minimal, fully pinned,
commercially cleared installation, nor a clean-install compatibility guarantee.

```bash
./scripts/install-dependencies.sh /path/to/ComfyUI
```

The installer also copies OSF's `mask_propagate_optical_flow` node. It
does not download model weights. It **skips pre-existing node directories
without validating their Git origin or revision** and warns accordingly.
Review the individual upstream rights and exact installed commits before
use. [Fresh-directory simulated installer tests](docs/legacy-installer-fresh-root-smoke.md)
exercise clone and checkout failure handling but do not establish actual
upstream availability, ComfyUI node imports or GPU execution. To also clone the two explicitly
excluded restricted packages for research workflows:

```bash
INSTALL_RESTRICTED=1 ./scripts/install-dependencies.sh /path/to/ComfyUI
```

For a strictly enumerated **11-workflow, no-download staging profile**,
start instead with the [commercial-compatible preparation guide](runpod/commercial-compatible/README.md).
That profile only copies graph files and documentation; it **does not install
ComfyUI, custom nodes or model weights**. There is no verified clean
ComfyUI deployment or one-click RunPod template yet.

A separate [clean ComfyUI CPU smoke](docs/clean-cpu-runtime-qualification.md)
is available for **OSF's own two optical-flow nodes only**. It attempts
a fresh pinned upstream ComfyUI install, loopback node registration and
synthetic CPU propagation on a disposable CI runner, together with real
registration checks for six commit-pinned external node packages (VideoHelperSuite, rgthree-comfy,
DownsampleFPS, GGUF, UltimateSDUpscale and Florence2), plus CPU-only synthetic frame
dropping by the real DownsampleFPS node, and one minimal synthetic
ComfyUI API graph combining VideoHelperSuite frame selection, rgthree
routing and GIF/H.264/H.265/ProRes 4444 encoding. Distinct
red/green/blue/yellow frames are checked for exact red/blue pixels
in temporary PNG/GIF outputs and bounded channel errors in separately
decoded H.264/HEVC MP4s and a ProRes 4444 MOV. The latter checks
12-bit 4:4:4 storage, **not** 12-bit input fidelity; a separate
RGB-channel-sensitive opt-in VHS test checks 27 YUV fine-detail comparisons
across red, green and blue sources, retaining the earlier 36 greyscale
luminance checks. HQ profile's
observed format discrepancy is documented separately. An additional
**independent direct-FFmpeg test** generates genuine planar 12-bit YUV444
sample values, encodes/decodes ProRes 4444 and checks that subtle 12-bit
differences survive within a bounded error. This does **not** establish
12-bit input support through ComfyUI or VideoHelperSuite. A
[separate source-verified VHS precision audit](docs/vhs-prores-input-precision.md)
confirms the pinned ProRes preset defaults to 8-bit RGB input and
demonstrates loss of subtle 12-bit source distinctions before FFmpeg.
A separate [test of the explicit opt-in 16-bit VHS input path](docs/vhs-prores-16bit-qualification.md)
compares the same test-only ComfyUI tensor through default 8-bit and
locally configured 16-bit ProRes paths. The CI-only preset is not deployed,
and this precision comparison is not a production colour-fidelity claim. UltimateSDUpscale requires its exact nested GPLv3 Git submodule
and a fail-closed guard against a mutable download. It is not GPU/model
or 11-workflow acceptance.

Once separately installed and validated, open UI-format workflows via
**Workflow → Open**. The `sam3_custompkg_probe.json` file is an API-format
prompt and is not a normal UI-canvas graph.

## Run on RunPod

We develop and run these workflows on [RunPod](https://www.runpod.io/) GPU pods.
[RUNPOD.md](RUNPOD.md) contains historical setup guidance, indicative GPU/VRAM
classes and storage recommendations. **It has not been independently accepted
as a fresh-pod, end-to-end ComfyUI installation.** The convenience wrapper
below invokes the *broad legacy installer*, not the strict 11-workflow
staging profile:

```bash
git clone https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows.git
cd opensourcefilms-comfyui-workflows
./scripts/setup-runpod.sh /path/to/ComfyUI
```

## Restricted-scope RunPod workflow bundle

For a **strictly staged, no-download subset** of the 11 graphs labelled
`commercial-compatible`, use the
[RunPod staging profile](runpod/commercial-compatible/README.md). It
validates the canonical dependency manifest and explicitly selected graphs,
copies only those graphs/rights sidecars and generates SHA-256 inventory
metadata. Run `python3 runpod/commercial-compatible/prepare.py` for the
read-only preflight; supply `--stage /path/to/new/output` to produce a bundle.

**Do not confuse this with the broader installer above:** the historical
`install-dependencies.sh` default also includes some nodes only required
by research workflows, plus unpinned dependencies. The strict profile
**does not call that installer**, fetch models, launch ComfyUI, or claim
that a clean GPU deployment has been tested. Upstream rights, SAM 3's
custom model agreement and compatibility still require individual review.

## Requirements

A ComfyUI installation and an NVIDIA GPU. Requirements vary a lot by
workflow; the SAM 3 / interpolation workflows are comfortable on a single
mid-range GPU, while the Wan 2.2 14B and SCAIL-2 video workflows want 24GB+
of VRAM. We develop and run all of these on GPU pods from
[Runpod](https://www.runpod.io/), in collaboration with them on GPU compute:
their on-demand pricing makes it practical to spin up a large-VRAM card just
for a session rather than owning one outright, which is how we test the
heavier workflows here.

## License

Workflow graphs, `custom_nodes/mask_propagate_optical_flow/`, and
`scripts/install-dependencies.sh`: MIT, see [LICENSE](LICENSE).
Third-party custom nodes and models referenced (not bundled) by these
workflows keep their own original licenses; see
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) and
[DEPENDENCIES.lock](DEPENDENCIES.lock).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
