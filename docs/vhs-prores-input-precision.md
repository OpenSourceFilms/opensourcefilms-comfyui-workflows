# VideoHelperSuite ProRes input-precision boundary

**Status: 12-bit input fidelity through the pinned VideoHelperSuite/ComfyUI path is NOT qualified.**

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

## Requirements for eventual ComfyUI/VHS high-bit-depth acceptance

A positive acceptance would need a **separately reviewed,
reproducible format configuration** explicitly selecting
`input_color_depth=16bit`, an actual ComfyUI tensor with controlled
sub-8-bit component variation, real VideoHelperSuite encoding,
verification of the encoded codec/pixel format, and high-bit-depth
decoding that demonstrates those specific distinctions survive.
It should also evaluate RGB-to-YUV transforms, transfer functions,
matrix/range metadata, image dimensions and target codec profile.

That is **not** implied by the direct FFmpeg ProRes 4444 result or by
the existing 8-bit `EmptyImage` VHS codec graph.

No production dependencies or upstream formats have been changed by
this audit. No GPUs, models, project footage or existing RunPod
ComfyUI instances are involved.
