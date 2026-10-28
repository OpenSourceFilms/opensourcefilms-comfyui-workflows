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

A second `VHS_VideoCombine` endpoint consumes the same selected images
with the pinned upstream `video/h264-mp4` format, `pix_fmt=yuv420p`,
`crf=0`, 2 fps and `save_output=false`. The harness retrieves this
temporary MP4 from the loopback server, verifies its container signature,
and uses the installed `imageio-ffmpeg` binary to decode it to raw RGB.
FFmpeg must identify the elementary video stream as **H.264** and return
exactly two 64×64 frames. Every pixel must match the expected **red,
then blue** sequence within an absolute tolerance of 24 per 8-bit RGB
channel. That tolerance permits the round trip through the format's
YUV420 colour conversion, unlike the exact PNG/GIF RGB checks. The
report includes maximum per-frame deviation, decoded frame hashes and
the MP4 SHA-256, but no uploaded media. Each fetched temporary file
is capped at 2 MB, and the MP4 is decoded only in a disposable
temporary directory.

A third `VHS_VideoCombine` encodes the same red/blue sequence with
the pinned upstream `video/h265-mp4` format, `pix_fmt=yuv420p`,
`crf=0`, 2 fps, and `save_output=false`. On the disposable CPU runner,
the harness fetches this temporary MP4 by the loopback `/view` API,
requires an MP4 `ftyp` signature and FFmpeg detection of an actual
**HEVC** video stream, and decodes to raw RGB24. Exactly two 64×64
frames must match the ordered red/blue source colours within 24/255
maximum absolute error at every pixel. Decoded-frame hashes, observed
errors and an MP4 hash are retained in JSON. No binary video is uploaded.
The 2 MB per-file limit, temporary decoding directory, pinned FFmpeg,
and file-metadata validation are unchanged.

A fourth `VHS_VideoCombine` output uses pinned upstream
`video/ProRes`, explicitly setting `profile=4444`, 2 FPS and
`save_output=false`, producing one temporary MOV through `prores_ks`.
The harness retrieves the MOV only over the loopback `/view` API,
enforces strict temporary filename/subfolder and 2 MB size limits,
and requires a QuickTime/MP4 `ftyp` signature. The CPU FFmpeg decoder
must identify a real **ProRes 4444** stream with `yuv444p12le` storage,
decode exactly two 64×64 RGB24 frames, and verify **every pixel**
against the red/blue source colours in order within a 24/255 maximum
absolute channel error. Only observed errors, decoded-frame SHA-256
values, MOV SHA-256 and size go in the JSON evidence.

**Observed upstream profile discrepancy:** The first exploratory
`profile=hq` test returned an MP4/MOV video stream marked
`prores (HQ) (apch)`, but FFmpeg reported `yuv444p10le` output,
not the anticipated HQ 4:2:2 layout. The HQ test therefore **failed**
and was not accepted. The acceptance case uses explicit ProRes 4444
and checks the reported profile *and* 4:4:4 storage. This does not
establish that the upstream HQ profile behaves correctly for every
codec or pixel format.

**ComfyUI/VHS precision boundary:** Although the ProRes 4444 stream
reports 12-bit 4:4:4 storage, this *ComfyUI graph* originates from
8-bit `EmptyImage` colour constants and is checked after RGB24 decode.
Its successful codec identification is **not** a 12-bit source-fidelity test.
The separate direct-FFmpeg 12-bit qualification below does not change
that VHS/ComfyUI input limitation.

These tests qualify narrow CPU VideoHelperSuite selection and GIF,
H.264, H.265 and ProRes 4444 encoding paths plus rgthree routing.
They do **not** qualify production-quality compression, sustained
processing, 10-bit/16-bit *fidelity*, colour-management accuracy, arbitrary
metadata, audio muxing, the eleven real workflows or pretrained models.

The loopback process is terminated in all normal and exceptional paths.

The only uploaded artifact is a small JSON report with source SHA, tool
versions, registration, synthetic output hashes and explicit exclusions.
No generated images, model weights, third-party source or logs containing
personal paths are uploaded.

## Independent real 12-bit ProRes source and fidelity gate

The same isolated CI job also runs
[`qualify_prores_12bit.py`](../scripts/qualify_prores_12bit.py) as a
**separate, model-free FFmpeg integration test**, not as an additional
ComfyUI/VHS node. It constructs two 64×64 frames of genuine planar
`yuv444p12le` source samples, with nonuniform patterns in **all three
12-bit planes**. The patterns contain four controlled luma comparisons,
each between values differing by only five 12-bit code levels and
mapping to the **same 8-bit code**. They make silent 8-bit truncation or
rounding observable.

The job feeds these raw 12-bit source bytes directly to the installed
`imageio-ffmpeg==0.6.0` executable with `prores_ks`,
`profile:v 4`, `pix_fmt yuv444p12le`, `qscale:v 1` and 2 fps.
It then identifies actual ProRes **4444** storage in the temporary MOV,
decodes back to planar `yuv444p12le` and verifies **every 12-bit
component** of both frames, with a maximum absolute permitted error
of **8/4095**. All four sub-8-bit luma distinctions must remain
strictly ordered after decoding. The public offline tests reject
8-bit quantization, reversed frames, truncation, out-of-range values
and even a single excessive sample error.

This proves a **bounded-error 12-bit source-to-ProRes-to-12-bit output
roundtrip for that particular synthetic pattern**. ProRes is lossy;
bit-for-bit equality is neither expected nor claimed. This is *not*
12-bit input acceptance through VideoHelperSuite or ComfyUI,
colour-managed camera input, HDR transfer-function preservation,
professional DI fidelity, or a full workflow test.

All raw source and decoded samples plus temporary MOV remain only on
the disposable runner. The 12-bit result is recorded separately in
`independent_real_12bit_ffmpeg_roundtrip` inside the JSON-only evidence,
including source/output hashes, 12-bit maximum/mean error, and the
four preserved fine-grained comparisons. No image/video binaries are
published.

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

## Real eleven-workflow node-registration coverage

The clean runner now performs a **read-only node-class coverage audit**
for the exact eleven `commercial-compatible` workflow JSON files in
the canonical `DEPENDENCIES.lock` and explicitly approved
[`prepare.py` profile](../runpod/commercial-compatible/prepare.py).
The [audit script](../scripts/audit_selected_workflow_nodes.py) reads
each original UI/API graph without editing or executing it, extracts its
actual node class IDs and exact source SHA-256, then compares them with
the **real live `/object_info` class registry** of the pinned disposable
ComfyUI + five external packages.

The report provides per-workflow node-instance counts, distinct class
IDs, exact registered IDs and every unregistered ID, grouped into:

- **pinned upstream ComfyUI native SAM3/SCAIL2:** `SAM3_Detect`,
  `SAM3_VideoTrack`, `SAM3_TrackPreview`, `SCAIL2ColoredMask`,
  `WanSCAILToVideo` are defined in
  `comfy_extras/nodes_sam3.py` and `comfy_extras/nodes_scail.py` of
  **upstream Comfy-Org/ComfyUI commit
  `08cf0284ff45723aa67841c80cabb0e3cb50c9d7`**. The real clean
  CPU `/object_info` run confirms all five are registered with valid
  node schemas. The acceptance code now **requires** this registration,
  rather than falsely calling these classes fork-only or absent.
  No associated model execution or functional equivalence with earlier
  patched forks has been qualified.
- **UI annotation/reroute:** `MarkdownNote`, `Note`, `Reroute`,
  `Label (rgthree)`; absence from the API registry alone does not
  establish missing execution support.
- **UUID-typed group/subgraph unresolved:** exported UI node types
  represented only by UUID strings. Their underlying definitions cannot
  be inferred from the ID.
- **other unregistered:** ordinary class IDs absent from this exact
  small installation. These require further source/dependency tracing;
  absence does not establish they are unsupported on a different fork
  or a complete installation.

This is **positive evidence only for classes actually registered** in
the pinned clean CPU runtime. The five upstream-native class registrations
are a strict CI requirement; other missing extensions remain diagnostics. It is not an attempt to claim that all
eleven selected workflows now run. Missing class lists are diagnostic
and do **not** cause the CPU smoke to fail. The audit itself fails
closed if the manifest differs from the approved eleven, graph source
is missing, malformed classes appear, or the live registry is absent.
Only JSON class IDs, per-workflow digests and counts enter the
metadata-only evidence artifact. No GPU/model inference is attempted.
The downstream full workflow, GPU, weights and rights acceptance
remains open in [issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).

## Crucial non-acceptance

This is **not a clean installation of all 11 selected workflows**.
It verifies five *representative* external node imports in addition to
OSF's own two node functions and executes the DownsampleFPS CPU frame-drop
method. It executes only the small synthetic VHS selection/GIF-encoding and rgthree routing operations described above.
It does **not** execute GGUF or UltimateSDUpscale nodes, nor VideoHelperSuite
external model loading or any full 11-workflow graph. It does not install
or qualify the remaining dependencies or verify SCAIL-2, SAM3,
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
