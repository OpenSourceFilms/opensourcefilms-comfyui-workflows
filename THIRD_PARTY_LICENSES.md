# Third-Party Licenses

> Unless otherwise stated, original code, workflow files and documentation
> authored by Open Source Films are licensed under the MIT License.
> Third-party software, models, weights and datasets remain subject to their
> respective licences. The MIT licence applied to an OSF workflow or
> integration does not grant additional rights to its dependencies.
> Commercial suitability depends on the complete dependency set selected by
> the user.

The workflow graph JSON files in this repository are authored by Open Source
Films and released under this repo's [LICENSE](LICENSE) (MIT). They do not
contain any third-party source code or model weights; they only *reference*
ComfyUI core and the custom node packages / models listed below by name.

Whether referencing a package by name in a workflow graph constitutes a
"derivative work" under that package's license was researched separately
(external legal research, retained internally). The working conclusion,
briefly: an independently-authored workflow JSON containing node class
names, IDs, connections, parameter values, and model filenames, but no
copied source code, is very unlikely to be a derivative work of ComfyUI or
the custom nodes it references. GPLv3 itself says output is only covered
where it constitutes a covered work, and separate independent works placed
in an aggregate don't inherit GPL; the FSF's own interpreter analysis treats
data consumed by a GPL interpreter as ordinarily separate; and (persuasive
authority) courts have repeatedly held that functional identifiers
(function/command names) aren't themselves protected expression. That
reasoning holds for `KSampler`, `VHS_VideoCombine`, `SAM3Segmentation` and
similarly for every node name referenced by the JSON files here. It would
**not** hold if a workflow embedded copied source code, scripts, substantial
documentation, or binary assets from a third party; none of the workflows
in this repo do.

**Per-workflow declaration** (also included in each workflow's `.md`
sidecar): *This workflow file and its original documentation are licensed
under MIT. It requires third-party software and models that remain subject
to their own licences. The MIT licence on this workflow does not grant
rights to those dependencies.*

**Nothing in this repo vendors any third-party package, model, or weight
file.** `scripts/install-dependencies.sh` fetches custom node packages from
their own upstream sources at pinned commits. Model weights are never
redistributed from this repository; you obtain them yourself from the
sources listed below. The one exception is `custom_nodes/
mask_propagate_optical_flow/`, which **is** vendored here because it is
Open Source Films' own code (MIT), not a third party's.

The machine-readable version of everything below, mapped per workflow file,
is [DEPENDENCIES.lock](DEPENDENCIES.lock); if the two ever disagree, the
lock file is canonical.

Verified: 2026-07-22. Custom-node pins re-checked against live upstream 2026-08-20;
see [DEPENDENCIES.lock](DEPENDENCIES.lock) for what changed (five tags had gone
stale upstream and were repinned to commits).

---

## ComfyUI core

- **Canonical upstream**: https://github.com/comfyanonymous/ComfyUI
- **Code license**: GPL-3.0
- **Integration type**: external: every workflow requires a ComfyUI
  installation; nothing from ComfyUI core is vendored in this repo.
- **Commercial use**: Permitted. GPL-3.0 imposes copyleft/source-availability
  obligations on distribution of the combined work; it is not a
  non-commercial license. Running ComfyUI does not require you to
  open-source your own workflow files or generated outputs.
- **Redistribution permitted**: yes, under GPL-3.0 terms, if you were to
  redistribute ComfyUI itself; not applicable to this repo, which doesn't.
- **Modifications by OSF**: the `step4_5_sam3_mask.json` /
  `step6_animation_mode.json` / `step7_replacement_mode.json` workflows were
  developed against a ComfyUI build with SAM 3 and SCAIL-2 support patched
  into `comfy_extras/` (native core nodes `SAM3_Detect`, `SAM3_VideoTrack`,
  `SCAIL2ColoredMask`, `WanSCAILToVideo`) rather than as separate
  custom_nodes packages. That patch set is not OSF's own; it ships with the
  SCAIL-2-enabled ComfyUI fork these workflows were built on. If your
  ComfyUI install doesn't have these natively, you'll need a build that
  does; we haven't isolated the patch as a standalone diff.
  **Updated public-core evidence (2026-10-28):** The exact reviewed public
  `Comfy-Org/ComfyUI@08cf0284ff45723aa67841c80cabb0e3cb50c9d7`
  now contains `comfy_extras/nodes_sam3.py` and `nodes_scail.py`,
  exposing all five relevant native IDs (`SAM3_Detect`,
  `SAM3_VideoTrack`, `SAM3_TrackPreview`, `SCAIL2ColoredMask`,
  `WanSCAILToVideo`). These five IDs also registered through a
  fresh isolated live `/object_info` CPU test in [PR #26](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/pull/26).
  Thus a *specialized fork is not established as mandatory merely for
  these class names*. This new evidence does **not** establish that
  the original fork's node schema and execution behaviour are identical,
  nor that SCAIL-2/SAM3 weights can load or run on this upstream build.
- **Required notices**: preserve GPL notices if you redistribute a modified
  ComfyUI build.
- **Date verified**: 2026-07-22.

## Custom node packages

Each entry: name, upstream URL, code license, pinned commit/version,
integration type (all "external"; none are vendored here except
`mask_propagate_optical_flow`), redistribution note, date verified.

| Package | Upstream | License | Pinned | Integration |
|---|---|---|---|---|
| ComfyUI-VideoHelperSuite | github.com/Kosinkadink/ComfyUI-VideoHelperSuite | GPL-3.0 | `2984ec4c4b93292421888f38db74a5e8802a8ff8` | external |
| rgthree-comfy | github.com/rgthree/rgthree-comfy | MIT | `d92cad68a6e92a1c5d4032d3ac53f79ea44b08e4` | external |
| ComfyUI-KJNodes | github.com/kijai/ComfyUI-KJNodes | GPL-3.0 | `3f20054214fec9f9234fd3841ae6f1e4287948f6` | external |
| ComfyUI-SAM3 | github.com/PozzettiAndrea/ComfyUI-SAM3 | GPL-3.0 | `de0ff5d2c2ea435d29f800abfa568cffdfb94773` | external |
| comfyui_sam3 | github.com/wouterverweirder/comfyui_sam3 | MIT | v0.2.1 | external (unused by current workflows; documented for completeness) |
| ComfyUI-Easy-Sam3 | github.com/yolain/ComfyUI-Easy-Sam3 | Apache-2.0 | `88fe578a1a5e03d95281197303d5d3a73fd5a089` | external |
| ComfyUI-Easy-Use | github.com/yolain/ComfyUI-Easy-Use | GPL-3.0 | unpinned; verify commit before install | external |
| ComfyUI-Video-Reverse | github.com/Sean-Bradley/ComfyUI-Video-Reverse | Apache-2.0 | unpinned; verify commit before install | external |
| ComfyUI-Florence2 | github.com/kijai/ComfyUI-Florence2 | MIT | `9ece3de914214c5f581d725167bc9d0eeb0d1120` | external |
| ComfyUI_essentials | github.com/cubiq/ComfyUI_essentials | MIT | `9d9f4bedfc9f0321c19faf71855e228c93bd0dc9` | external |
| ComfyUI-GGUF | github.com/city96/ComfyUI-GGUF | Apache-2.0 | `6ea2651e7df66d7585f6ffee804b20e92fb38b8a` | external |
| ComfyUI_UltimateSDUpscale | github.com/ssitu/ComfyUI_UltimateSDUpscale | GPL-3.0 | `a5547db9e1d07d3318bb21e9e9c474f4c1e9c8df` | external |
| ComfyUI-GIMM-VFI | github.com/kijai/ComfyUI-GIMM-VFI | ISC | `4c9a3123762af85e7c796e41737da0b70c75d72d` | external |
| ComfyUI-Tween | github.com/Ethanfel/ComfyUI-Tween | Apache-2.0 | `91947c0b8c795cf504d3848274d4217f0432a324` | external |
| ComfyUI-DownsampleFPS | github.com/Austat/ComfyUI-DownsampleFPS | Apache-2.0 | `4d741ef8e33b0c5111ad21033f9408acffc63651` | external |
| ComfyUI-WanVideoWrapper | github.com/kijai/ComfyUI-WanVideoWrapper | Apache-2.0 | `088128b224242e110d3906c6750e9a3a348a659b` | external |
| comfyui_controlnet_aux | github.com/Fannovel16/comfyui_controlnet_aux | Apache-2.0 | unpinned; verify commit before install | external |
| ComfyUI-RMBG | github.com/1038lab/ComfyUI-RMBG | GPL-3.0 | unpinned; verify commit before install | external |
| EMA-VFI (wrapper) | bundled within ComfyUI-Tween; upstream research code Apache-2.0 | Apache-2.0 | see ComfyUI-Tween | external |
| **mask_propagate_optical_flow** | **this repo**; `custom_nodes/mask_propagate_optical_flow/` | **MIT (OSF's own)** | this repo, current commit | **vendored** |

Redistribution: none of the "external" rows above are redistributed by this
repo: `scripts/install-dependencies.sh` clones them from their own
upstream at install time, so no separate redistribution permission is
needed. `mask_propagate_optical_flow` is OSF's own code with no third-party
content, so vendoring it needs no permission beyond OSF's own copyright.

`ComfyUI-SCAIL2-Easy` (github.com/jieg9341-lab/ComfyUI-SCAIL2-Easy,
Apache-2.0, v1.1.2) is **not required by any workflow in this repo**; it's
a third-party convenience-node package found alongside the SCAIL-2 ComfyUI
fork during the audit, not an OSF package, and not something these workflows
depend on. Documented here only so nobody mistakes it for ours if they go
looking at the same install.

`EffectEraseBridge` (in the upstream WANVACE install this repo's workflows
were extracted from) has no LICENSE file of its own: it's a thin ComfyUI
node wrapper. The model it wraps, **EffectErase**, is CC-BY-NC-4.0; see
Models below. Treat the wrapper as inheriting that restriction for any
workflow that uses it (`sam_effecteraser_points_text_matte_optflow.json`).

## Models

None of these weights are included in this repository. You download them
yourself from the sources below; commercial-use verdicts are OSF's own
reading of each license's actual text, not legal advice.

| Model | Upstream | Code/weights license | Commercial use | Redistribution |
|---|---|---|---|---|
| SAM 3 (`sam3.1_multiplex_fp16.safetensors`) | Meta | Custom "SAM License" (source-available, dated 2025-11-19), [official terms](https://github.com/facebookresearch/sam3/blob/main/LICENSE); **not** MIT/Apache/GPL | **Permitted**: no revenue/MAU cap found. Requires redistributing the license text with any redistribution of the model/derivatives, acknowledging use in publications, and complying with Meta's Trade Controls / weapons-use prohibition. | Permitted per the SAM License terms; not redistributed by this repo regardless. |
| SCAIL-2 (`wan2.1_14B_SCAIL_2_fp16.safetensors`) | github.com/zai-org/SCAIL-2 (Zhipu AI / Z.ai) | Apache-2.0 | **Permitted.** Confirmed via `gh api repos/zai-org/SCAIL-2/contents/README.md`; "This project is licensed under the Apache License 2.0"; covering code and released weights. | Permitted per Apache-2.0; not redistributed by this repo. |
| VideoMaMa (checkpoint + `dino_projection_mlp.pth`) | github.com/cvlab-kaist/VideoMaMa; checkpoint `SammyLim/VideoMaMa` on Hugging Face | Code: **CC-BY-NC-4.0** (confirmed via `gh api repos/cvlab-kaist/VideoMaMa`). Checkpoint additionally under the **Stability AI Community License** (built on Stable Video Diffusion). | **Not permitted for commercial use.** Both workflows depending on VideoMaMa are marked `research-only`. | Not permitted commercially; not redistributed by this repo. |
| BiM-VFI | github.com/KAIST-VICLab/BiM-VFI | "Research and education only... commercial use requires formal permission from the principal investigator (Prof. Munchurl Kim, mkimee@kaist.ac.kr)"; quoted from the repo's own README | **Not permitted for commercial use** without written permission from KAIST. Both workflows using it are marked `research-only`. | Not permitted commercially. |
| EffectErase | see prior OSF third-party licensing audit | CC-BY-NC-4.0 | **Not permitted for commercial use.** The workflow using it is marked `research-only`. | Not permitted commercially. |
| Wan 2.1 / Wan 2.2 base models, CLIP/VAE/UMT5 components | Alibaba Wan team | Apache-2.0 | Permitted. | Permitted per Apache-2.0; not redistributed by this repo. |
| GIMM-VFI, EMA-VFI, SGM-VFI model weights | see respective wrapper repos above | Apache-2.0 / ISC per wrapper repos | Permitted; not independently re-verified beyond the wrapper package's own license statement; re-check before high-stakes commercial use. | Not redistributed by this repo. |

## How `commercial_status` is assigned per workflow

- **commercial-compatible**: no identified blanket prohibition on
  commercial use in the reviewed dependency chain, including the custom
  **Meta SAM License** where SAM 3 is used. **This is not the same as saying
  all components have OSI-approved/permissive or GPL licences.** SAM 3 is
  source-available under a separate agreement; its conditions include
  redistribution of the agreement with redistributed SAM Materials,
  acknowledgment in published research, trade-control and prohibited-use
  restrictions, and further terms. Other dependencies may impose copyleft
  or separate model-weight restrictions. The status does **not** guarantee
  clearance for a specific deployment, distribution or downstream use.
- **research-only**: the workflow depends on at least one CC-BY-NC,
  "research/education only", or otherwise commercially-restricted component
  (VideoMaMa, BiM-VFI, or EffectErase in this repo's current set).

This is a repo-authored assessment, not legal advice. Verify licenses
yourself before commercial distribution, especially for any component marked
"unpinned" above; a package name alone isn't proof of terms; forks and
similarly-named packages can carry different licenses, which is why every
row above records an exact commit/tag where we had one available.
