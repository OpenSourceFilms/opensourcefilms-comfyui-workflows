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
ComfyUI installation. It additionally fetches **exactly five public,
commit-pinned third-party packages** to the same disposable checkout,
without invoking the broad legacy installer:

| Package | Exact source revision | Required registered class |
|---|---|---|
| ComfyUI-VideoHelperSuite | `2984ec4c4b93292421888f38db74a5e8802a8ff8` | `VHS_VideoCombine` |
| rgthree-comfy | `d92cad68a6e92a1c5d4032d3ac53f79ea44b08e4` | `Any Switch (rgthree)` |
| ComfyUI-DownsampleFPS | `4d741ef8e33b0c5111ad21033f9408acffc63651` | `DownsampleFPSNode` |
| ComfyUI-GGUF | `6ea2651e7df66d7585f6ffee804b20e92fb38b8a` | `UnetLoaderGGUF` |
| ComfyUI_UltimateSDUpscale | `a5547db9e1d07d3318bb21e9e9c474f4c1e9c8df` | `UltimateSDUpscale` |

The job requires actual Git HEAD to match each pinned SHA, installs
`imageio-ffmpeg==0.6.0` and `gguf==0.13.0` with CPU/headless
OpenCV provided by the core test, and disables persistence of the checkout
credential. These packages are independent upstream software with their
own GPL/MIT/Apache terms; they are neither vendored nor relicensed by OSF.
The runner then starts ComfyUI with
`--cpu --offline --listen 127.0.0.1`, checks the real
`/object_info` API for both registered OSF nodes **and the five selected
external package classes**, executes both OSF functions on
generated 48×48 tensors: zero-flow propagation and static
Farneback optical flow. It also executes the actual DownsampleFPS frame-drop
method on eight synthetic CPU frames (8 fps to 4 fps), checking expected
frame selection and recording the resulting tensor hash. GGUF is **import
and registration only**, not a quantized model-load test. It checks shape, finite values, initial-mask
preservation and zero-motion consistency, and records output hashes.
A further **real ComfyUI HTTP `/prompt` execution** checks selected
frame contents and image encoding, not merely the number of outputs.
Four native `EmptyImage` nodes generate distinct solid-red, solid-green,
solid-blue and solid-yellow 64×64 images. Three native `ImageBatch` nodes
form the ordered sequence. The pinned `VHS_SelectEveryNthImage` selects
indices zero and two, which must be **red, then blue**. Pinned
`Any Switch (rgthree)` forwards that batch to two outputs: native
`PreviewImage` and pinned `VHS_VideoCombine` using Pillow's
`image/gif` encoder at 2 fps, with `save_output=false`.

The harness requires successful `/history/{prompt_id}` completion,
exactly two temporary PNG previews and one temporary GIF.
It downloads these three *temporary local files* solely through the
loopback `/view` API, with strict filename/subfolder checks and a
2 MB maximum per file. Pillow decodes every pixel, requiring the exact
red/blue RGB sequence in both PNG previews and the animated GIF, exactly
two 64×64 GIF frames and 500 ms per frame. Pixel-content SHA-256 values,
not binary image files or filenames, are written to the JSON evidence
report. Binary previews and GIF remain on the disposable runner and
are **never uploaded**.

This qualifies a narrow live VideoHelperSuite selection and GIF encoding
operation plus rgthree routing. It does not qualify video codecs such as
H.264/H.265, full media workflows or any pretrained model.

The loopback process is terminated in all normal and exceptional paths.

The only uploaded artifact is a small JSON report with source SHA, tool
versions, registration, synthetic output hashes and explicit exclusions.
No generated images, model weights, third-party source or logs containing
personal paths are uploaded.

## Pinned UltimateSDUpscale submodule, no mutable fallback

The pinned `ssitu/ComfyUI_UltimateSDUpscale` source at
`a5547db9e1d07d3318bb21e9e9c474f4c1e9c8df` contains the Git
submodule `repositories/ultimate_sd_upscale`. Its gitlink resolves to
`Coyote-A/ultimate-upscale-for-automatic1111` at the exact commit
`2322caa480535b1011a1f9c18126d85ea444f146`. Both repositories
include GPLv3 licence text. The workflow explicitly fetches that
*exact* gitlink commit, checks `git ls-tree` against the parent's tracked
gitlink and verifies the nested source revision and required nonempty
`scripts/ultimate-upscale.py` and `LICENSE` before startup.

**Known unsafe default:** If the submodule directory is empty, the pinned
wrapper's `__init__.py` invokes `urllib.request.urlretrieve` against a
mutable `master.zip` URL. In addition to requiring the populated gitlink,
the disposable ComfyUI Python process preloads
[the targeted no-download guard](../scripts/usdu_offline_guard/sitecustomize.py),
which *rejects every `urllib.request.urlretrieve` call* at runtime. The
qualification script verifies that the interpreter actually loaded that
guard before executing the external node import. This is specific to the
observed pinned code path; it is **not** general network isolation or a
claim that any other network API is blocked.

The test checks `UltimateSDUpscale` appears in the live ComfyUI class
registry, **not** that upscaling or diffusion works. No model weights or
Automatic1111 installation are used. This code and nested source remain
upstream GPLv3, not OSF-owned or relicensed by OSF.

The pinned GIMM-VFI source also declares `cupy-cuda12x`; this CPU test
cannot certify its CUDA/kernel compatibility.

## Crucial non-acceptance

This is **not a clean installation of all 11 selected workflows**.
It verifies five *representative* external node imports in addition to
OSF's own two node functions and executes the DownsampleFPS CPU frame-drop
method. It executes only the small synthetic VHS selection/GIF-encoding and rgthree routing operations described above.
It does **not** execute GGUF or UltimateSDUpscale nodes, nor VideoHelperSuite
external model loading or any full 11-workflow graph.
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
