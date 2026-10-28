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

The job copies **only OSF's own** optical-flow node into that scratch
ComfyUI installation. It does not invoke the broad legacy installer or
add any third-party custom nodes. The runner then starts ComfyUI with
`--cpu --offline --listen 127.0.0.1`, checks the real
`/object_info` API for both registered OSF nodes, and executes their
functions on generated 48×48 tensors: zero-flow propagation and static
Farneback optical flow. It checks shape, finite values, initial-mask
preservation and zero-motion consistency, and records output hashes.
The loopback process is terminated in all normal and exceptional paths.

The only uploaded artifact is a small JSON report with source SHA, tool
versions, registration, synthetic output hashes and explicit exclusions.
No generated images, model weights, third-party source or logs containing
personal paths are uploaded.

## Crucial non-acceptance

This is **not a clean installation of all 11 selected workflows**. It
does not verify SCAIL-2, SAM3, Wan2.2, GIMM-VFI, model licences, model
weights, GPU/CUDA/VRAM, workflow loading or inference. Optical-flow nodes
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
