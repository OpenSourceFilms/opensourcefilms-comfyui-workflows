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

## What's in here vs. what isn't

- **In this repo**: the workflow graph JSON files (node connections,
  parameters, prompts), one OSF-authored custom node package
  (`custom_nodes/mask_propagate_optical_flow/`), a pinned installer script,
  and full dependency documentation.
- **Not in this repo**: ComfyUI itself, third-party custom node source code,
  or any model weights. `scripts/install-dependencies.sh` fetches the
  third-party custom nodes you need from their own upstream repos, pinned to
  commits we've verified. Model weights are your own responsibility to
  download: see the license/source notes in each workflow's `.md` sidecar,
  [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md), and
  [DEPENDENCIES.lock](DEPENDENCIES.lock) (machine-readable, canonical if it
  ever disagrees with the prose docs).

## Commercial use

Every workflow is labeled with a `commercial_status` in its `.md` sidecar
file, one of:

- **`commercial-compatible`**; every dependency (ComfyUI core, custom
  nodes, models) is either permissively licensed or GPL-3.0. GPL-3.0 is
  commercially usable (it imposes distribution/copyleft obligations, it is
  not a non-commercial license); we don't treat GPL as a blocker.
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

## Custom nodes

`custom_nodes/mask_propagate_optical_flow/` is Open Source Films' own code:
two nodes (`MaskPropagateOpticalFlow`, `MaskPropagateFromFlow`) that
propagate a single mask across a video's frames using OpenCV Farneback
optical flow, so you draw or generate one mask instead of one per frame. No
external model weights, no third-party dependencies beyond OpenCV/NumPy/
PyTorch (which ComfyUI already requires). Used by the matting/object-removal
workflows in `workflows/research-only/`. Published here for the first time,
MIT-licensed; see its own [README](custom_nodes/mask_propagate_optical_flow/README.md).

## Install

```bash
./scripts/install-dependencies.sh /path/to/ComfyUI
```

This installs the commercial-compatible custom node dependencies, plus
`mask_propagate_optical_flow`, by default. To also install the research-only
dependencies (needed for `workflows/research-only/*`):

```bash
INSTALL_RESTRICTED=1 ./scripts/install-dependencies.sh /path/to/ComfyUI
```

Then in ComfyUI: **Workflow → Open** and pick a `.json` from `workflows/`.

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
