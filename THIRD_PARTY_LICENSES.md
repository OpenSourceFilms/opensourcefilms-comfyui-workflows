# Third-Party Licenses

The workflow graph JSON files in this repository are authored by Open Source
Films and released under this repo's [LICENSE](LICENSE) (MIT). They do not
contain any third-party source code or model weights — they only *reference*
ComfyUI core and the custom node packages / models listed below by name.
Whether referencing a package by name in a workflow graph constitutes a
"derivative work" under that package's license was researched separately
(legal research summary retained internally); the working conclusion is that
it does not, provided the JSON itself embeds no copied code, so this
repository can be MIT while still requiring users to separately obtain and
agree to the licenses below to actually *run* a workflow.

**Nothing in this repo vendors any of the packages, models, or weights
below.** `install.sh` fetches them from their own upstream sources at install
time. Model weights are never redistributed from this repository.

Verified: 2026-07-22.

## ComfyUI core

All workflows require a ComfyUI installation. ComfyUI itself
(`comfyanonymous/ComfyUI`) is licensed **GPL-3.0**. GPL-3.0 is commercially
usable — it imposes copyleft/source-availability obligations on distribution
of the combined work, it is not a non-commercial license. Running ComfyUI
does not require you to open-source your own workflow files or outputs.

## Custom node packages

| Package | Upstream | License | Pinned commit / version (verified 2026-07-22) |
|---|---|---|---|
| ComfyUI-VideoHelperSuite | https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite | GPL-3.0 | `2984ec4c4b93292421888f38db74a5e8802a8ff8` |
| rgthree-comfy | https://github.com/rgthree/rgthree-comfy | MIT | v1.0.2512112053 |
| ComfyUI-KJNodes | https://github.com/kijai/ComfyUI-KJNodes | GPL-3.0 | v1.3.6 |
| ComfyUI-SAM3 | https://github.com/PozzettiAndrea/ComfyUI-SAM3 | GPL-3.0 | v0.1.6 |
| comfyui_sam3 | https://github.com/wouterverweirder/comfyui_sam3 | MIT | v0.2.1 |
| ComfyUI-Easy-Sam3 | https://github.com/yolain/ComfyUI-Easy-Sam3 | Apache-2.0 | `88fe578a1a5e03d95281197303d5d3a73fd5a089` |
| ComfyUI-Easy-Use | https://github.com/yolain/ComfyUI-Easy-Use | GPL-3.0 | unpinned — verify commit before install |
| ComfyUI-Video-Reverse | https://github.com/Sean-Bradley/ComfyUI-Video-Reverse | Apache-2.0 | unpinned — verify commit before install |
| ComfyUI-Florence2 | https://github.com/kijai/ComfyUI-Florence2 | MIT | v1.0.9 |
| ComfyUI_essentials | https://github.com/cubiq/ComfyUI_essentials | MIT | `9d9f4bedfc9f0321c19faf71855e228c93bd0dc9` |
| ComfyUI-GGUF | https://github.com/city96/ComfyUI-GGUF | Apache-2.0 | v1.1.10 |
| ComfyUI_UltimateSDUpscale | https://github.com/ssitu/ComfyUI_UltimateSDUpscale | GPL-3.0 | v1.7.2 |
| ComfyUI-GIMM-VFI | https://github.com/kijai/ComfyUI-GIMM-VFI | ISC | `4c9a3123762af85e7c796e41737da0b70c75d72d` |
| ComfyUI-Tween | https://github.com/Ethanfel/ComfyUI-Tween | Apache-2.0 | `91947c0b8c795cf504d3848274d4217f0432a324` |
| ComfyUI-DownsampleFPS | https://github.com/Austat/ComfyUI-DownsampleFPS | Apache-2.0 | `4d741ef8e33b0c5111ad21033f9408acffc63651` |
| ComfyUI-WanVideoWrapper | https://github.com/kijai/ComfyUI-WanVideoWrapper | Apache-2.0 | v1.4.7 |
| comfyui_controlnet_aux | https://github.com/Fannovel16/comfyui_controlnet_aux | Apache-2.0 | unpinned — verify commit before install |
| comfyui-rmbg (ComfyUI-RMBG) | https://github.com/1038lab/ComfyUI-RMBG | GPL-3.0 | unpinned — verify commit before install |
| EMA-VFI (ComfyUI wrapper) | (bundled within ComfyUI-Tween; upstream research code Apache-2.0) | Apache-2.0 | see ComfyUI-Tween |
| ComfyUI-SCAIL2-Easy | https://github.com/jieg9341-lab/ComfyUI-SCAIL2-Easy | Apache-2.0 | v1.1.2 — **not required by any workflow in this repo**; documented here only because it was found alongside the SCAIL-2 ComfyUI fork during the audit. Not an OSF package. |

`mask_propagate_optical_flow` (the node package providing
`Unimatch_OptFlowPreprocessor`'s consumer, `MaskPropagateFromFlow`) is
**Open Source Films' own code** — plain OpenCV Farneback optical flow, no
external model weights or vendored source — and is covered by this repo's
own MIT license, not this table. Its source is not yet published separately;
until it is, treat it as a required companion install alongside the packages
above (see `install.sh`).

`EffectEraseBridge` (WANVACE install) has no LICENSE file of its own — it is
a thin ComfyUI node wrapper. The model it wraps, **EffectErase**, is
**CC-BY-NC-4.0** — see Models below. Treat the wrapper as inheriting that
restriction for any workflow that uses it.

## Models

| Model | Upstream | License | Commercial use |
|---|---|---|---|
| SAM 3 (`sam3.1_multiplex_fp16.safetensors`) | Meta ("SAM License", vendored copy dated 2025-11-19) | Custom "SAM License" (not OSI-approved, source-available) | **Permitted** — no revenue/MAU cap found in the license text. Requires: redistribute the license text with any redistribution of the model or derivatives, acknowledge use in any publication, comply with Meta's Trade Controls / weapons-use prohibition. |
| SCAIL-2 (`wan2.1_14B_SCAIL_2_fp16.safetensors`) | https://github.com/zai-org/SCAIL-2 (Zhipu AI / Z.ai) | Apache-2.0 | Permitted. Confirmed via the upstream repo's own README ("This project is licensed under the Apache License 2.0") covering code and released weights. |
| VideoMaMa (checkpoint + `dino_projection_mlp.pth`) | https://github.com/cvlab-kaist/VideoMaMa ; checkpoint `SammyLim/VideoMaMa` on Hugging Face | Code: **CC-BY-NC-4.0**. Checkpoint additionally under the **Stability AI Community License** (built on Stable Video Diffusion). | **Not permitted for commercial use.** All workflows depending on VideoMaMa are marked `research-only` in this repo. |
| BiM-VFI | https://github.com/KAIST-VICLab/BiM-VFI | Research/education only per repo README | **Not permitted for commercial use** without written permission from the principal investigator (Prof. Munchurl Kim, KAIST). Workflows using it are marked `research-only`. |
| EffectErase | (see prior OSF licensing audit) | CC-BY-NC-4.0 | **Not permitted for commercial use.** Workflows using it are marked `research-only`. |
| Wan 2.1 / Wan 2.2 base models, CLIP/VAE/UMT5 components | Alibaba Wan team | Apache-2.0 | Permitted. |
| GIMM-VFI, EMA-VFI, SGM-VFI model weights | see respective wrapper repos above | Apache-2.0 / ISC per wrapper repos | Permitted — not independently re-verified beyond the wrapper package's own license statement; re-check before high-stakes commercial use. |

## How `commercial_status` is assigned per workflow

- **commercial-compatible**: every node package and model the workflow
  depends on is permissively licensed or GPL-3.0 (GPL is fine commercially,
  see above) — no CC-BY-NC, no "research only", no revenue-capped community
  license in the dependency chain.
- **research-only**: the workflow depends on at least one CC-BY-NC,
  "research/education only", or otherwise commercially-restricted component
  (VideoMaMa, BiM-VFI, or EffectErase in this repo's current set).

This is a repo-authored assessment, not legal advice. Verify licenses
yourself before commercial distribution, especially for any component marked
"unpinned" above.
