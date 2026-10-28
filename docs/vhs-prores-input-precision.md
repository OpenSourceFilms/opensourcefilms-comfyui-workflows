# VideoHelperSuite ProRes input-precision boundary

**Status:** The default pinned VideoHelperSuite ProRes preset truncates tensor inputs to 8-bit. A separate disposable CPU test **has verified preservation of four controlled sub-8-bit luma distinctions** using an opt-in 16-bit input preset. Calibrated, bit-exact or production 12-bit source fidelity is **not qualified**.

This is separate from the [accepted direct FFmpeg 12-bit ProRes roundtrip](clean-cpu-runtime-qualification.md#independent-real-12-bit-prores-source-and-fidelity-gate), which bypasses VideoHelperSuite.

## Pinned source and observed branch

The clean CPU qualification pins
`Kosinkadink/ComfyUI-VideoHelperSuite@2984ec4c4b93292421888f38db74a5e8802a8ff8`.

Its `video_formats/ProRes.json` specifies `prores_ks` and a MOV
extension but **does not define `input_color_depth`**. The same revision's
`videohelpersuite/nodes.py`, in `VideoCombine.combine_video`, explicitly
tests `video_format.get('input_color_depth', '8bit') == '16bit'`.
Only the explicit `16bit` branch uses `tensor_to_shorts` and feeds
`rgb48` raw input (without alpha) to FFmpeg. The **default else branch**
uses `tensor_to_bytes` and `rgb24`, quantizing incoming float tensor
values to 8-bit RGB **before ProRes encoding**.

The resulting ProRes 4444 MOV can legitimately report 12-bit
`yuv444p12le` *storage* even when its source values passed through
8-bit input quantization. The upstream codec profile, on its own, does
not establish preserved 12-bit detail in the source pipeline.

## Synthetic evidence and fail-closed gate

The disposable CPU runner executes
[`scripts/audit_vhs_prores_precision.py`](../scripts/audit_vhs_prores_precision.py)
**after verifying the exact pinned third-party Git revision**. The
auditor parses the real upstream node and ProRes preset, requires the
reviewed input-precision conditional and mapping calls, then evaluates
only three extracted pixel-conversion helpers from that source.

It sends two distinct normalized 12-bit source values, `2038/4095`
and `2043/4095`, through both converters. The values occupy the
same 8-bit bucket; the default converter must collapse them to the
same byte, while `tensor_to_shorts` must preserve distinct 16-bit
integer values. The JSON evidence includes the observed values and
the hashes of the pinned source files, but no media binary. An
unexpected upstream precision branch or changed configuration fails
the CI job rather than silently changing the interpretation.

Offline regressions reject a changed default, missing `rgb24` or
`tensor_to_bytes` path, unexpected encoder format and missing
upstream node definition.

## Later live ComfyUI/VHS evidence: opt-in 16-bit input

The separate [experimental 16-bit input qualification](vhs-prores-16bit-qualification.md)
has **already completed** the limited test previously proposed here.
[PR #37](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/pull/37)
merged at `9172f21cd77b71819e63eaacfffa9d8d3907669b`; its
[independent merged-main CPU run](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/actions/runs/40634457603)
and [public regressions](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/actions/runs/40634457613)
both passed.

On **identical** generated two-frame 64×64 float32 ComfyUI `IMAGE`
tensors containing controlled 12-bit-indexed grayscale values, the
actual pinned `VHS_VideoCombine` ran twice:

- The unmodified upstream `video/ProRes` default accepted 8-bit
  `rgb24` input and collapsed **all four** tested fine-value pairs.
- A **CI-only, untracked copy** of that preset adding only
  `"input_color_depth": "16bit"` sent 16-bit `rgb48` input.
  All **four** tested pairs remained distinct after ProRes 4444
  encoding and 12-bit `yuv444p12le` decoding, with differences of
  **[4, 4, 4, 4] code levels** on the decoded 12-bit scale.

This is **actual ComfyUI node execution**, not just a source audit or
a direct-FFmpeg demonstration. It establishes the specific fine-detail
preservation comparison under the reviewed temporary preset. The default
upstream ProRes preset remains 8-bit, and the opt-in preset was **not
published as a production configuration**. The test does not establish
bit-exact 12-bit source fidelity, calibrated RGB/YUV conversion,
colour-transfer and range metadata, HDR camera input, or full resolution,
duration and workflow reliability.

## Remaining requirements for production high-bit-depth acceptance

Qualify an explicitly approved and reproducible high-bit-depth preset
across representative frame dimensions, gradients, colour matrices,
range/transfer functions, realistic scene variation, frame timing,
and source precision. Independently review the exact dependency versions
and deployment rights. A successful synthetic A/B comparison must not
be treated as an accepted production format or full 11-workflow GPU/model
qualification.

No production dependencies, upstream formats or RunPod ComfyUI
instances were changed by either isolated test. No GPUs, models or
project footage were used.
