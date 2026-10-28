# Isolated clean ComfyUI CPU runtime qualification

**Purpose:** Establish one narrow but **real** clean-install checkpoint for
OSF's own `mask_propagate_optical_flow` custom-node package, independently
of production RunPod, model weights and third-party research nodes.

## Exact test scope

The [separate GitHub Actions job](../.github/workflows/verify-clean-cpu-runtime.yml)
uses a disposable Ubuntu 24.04 GitHub-hosted runner, Python 3.12,
CPU-only PyTorch 2.8.0 / torchvision 0.23.0, and a fresh Git checkout
of upstream `Comfy-Org/ComfyUI` at commit
`08cf0284ff45723aa67841c80cabb0e3cb50c9d7`. It installs that
checkout's requirements into the isolated runner Python environment plus
`opencv-python-headless==4.10.0.84`. The checkout's exact SHA is validated,
and `pip check` must pass.

The job copies OSF's own optical-flow node into that scratch
ComfyUI installation. It additionally fetches **exactly four public,
commit-pinned third-party packages** to the same disposable checkout,
without invoking the broad legacy installer:

| Package | Exact source revision | Required registered class |
|---|---|---|
| ComfyUI-VideoHelperSuite | `2984ec4c4b93292421888f38db74a5e8802a8ff8` | `VHS_VideoCombine` |
| rgthree-comfy | `d92cad68a6e92a1c5d4032d3ac53f79ea44b08e4` | `Any Switch (rgthree)` |
| ComfyUI-DownsampleFPS | `4d741ef8e33b0c5111ad21033f9408acffc63651` | `DownsampleFPSNode` |
| ComfyUI-GGUF | `6ea2651e7df66d7585f6ffee804b20e92fb38b8a` | `UnetLoaderGGUF` |

The job requires actual Git HEAD to match each pinned SHA, installs
`imageio-ffmpeg==0.6.0` and `gguf==0.13.0` with CPU/headless
OpenCV provided by the core test, and disables persistence of the checkout
credential. These packages are independent upstream software with their
own GPL/MIT/Apache terms; they are neither vendored nor relicensed by OSF.
The runner then starts ComfyUI with
`--cpu --offline --listen 127.0.0.1`, checks the real
`/object_info` API for both registered OSF nodes **and the four selected
external package classes**, executes both OSF functions on
generated 48×48 tensors: zero-flow propagation and static
Farneback optical flow. It also executes the actual DownsampleFPS frame-drop
method on eight synthetic CPU frames (8 fps to 4 fps), checking expected
frame selection and recording the resulting tensor hash. GGUF is **import
and registration only**, not a quantized model-load test. It checks shape, finite values, initial-mask
preservation and zero-motion consistency, and records output hashes.
The loopback process is terminated in all normal and exceptional paths.

The only uploaded artifact is a small JSON report with source SHA, tool
versions, registration, synthetic output hashes and explicit exclusions.
No generated images, model weights, third-party source or logs containing
personal paths are uploaded.

## Next dependency gate: unpinned initialization fetch

The pinned `ComfyUI_UltimateSDUpscale@a5547db9e1d07d3318bb21e9e9c474f4c1e9c8df`
source contains a Git submodule at `repositories/ultimate_sd_upscale`.
Its `__init__.py` attempts to download
`Coyote-A/ultimate-upscale-for-automatic1111/archive/master.zip` when that
submodule directory is empty. A Git checkout without its submodule may
therefore execute **unreviewed mutable upstream bytes at import time**.
Do not import this package in clean acceptance until the exact submodule
commit and license are verified, checked out explicitly, and the fallback
network download is disabled or otherwise made fail-closed. This is an
installation provenance boundary, not a claim of malicious behaviour.

The pinned GIMM-VFI source also declares `cupy-cuda12x`; this CPU test
cannot certify its CUDA/kernel compatibility.

## Crucial non-acceptance

This is **not a clean installation of all 11 selected workflows**.
It verifies four *representative* external node imports in addition to
OSF's own two node functions and executes the DownsampleFPS CPU frame-drop
method. It does **not** execute VideoHelperSuite, rgthree or GGUF nodes,
or the rest of the dependency set. It does not verify SCAIL-2, SAM3,
Wan2.2, GIMM-VFI, model licences, model weights, GPU/CUDA/VRAM,
workflow loading or inference. Optical-flow nodes
are referenced by research-only graphs, so their import acceptance does not
confer rights to research-restricted VideoMaMa or EffectErase components.
The 11-workflow staged bundle is still not an installed runtime.

A successful CPU smoke is a first independent clean *ComfyUI core*
and OSF-node registration/runtime check. The broader live-model
acceptance remains in [issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
The legacy broad installer clean-install issue is
[issue #2](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/2).

**Resource and security boundary:** This one-shot CI job installs
external packages and clones a pinned public ComfyUI commit on the
disposable GitHub runner only. It never accesses a connected RunPod
pod, live ComfyUI ports, project footage, credentials or GPUs. Do not
present these CPU results as model execution acceptance.
