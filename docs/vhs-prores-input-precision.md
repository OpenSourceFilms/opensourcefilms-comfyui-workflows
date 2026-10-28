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

## CI-only explicit RGB48/16-bit source probe

The disposable clean CPU job additionally stages **two OSF-authored test
fixtures**, never an upstream patch or production dependency:

- `tests/fixtures/osf_ci_precision_probe/__init__.py` registers a
  deterministic `OSF_CI_Precision12BitSource` test node producing
  floating-point ComfyUI `IMAGE` tensors with adjacent 12-bit levels
  `2038/2043` and `2048/2053`. In each pair, both values share
  one 8-bit bucket.
- `tests/fixtures/osf-prores4444-rgb48-16bit.json` supplies a **test-only**
  `video/osf-prores4444-rgb48-16bit` preset with
  `input_color_depth=16bit`, `prores_ks`, ProRes 4444 and
  `yuv444p12le` storage. It is copied as a new untracked format file
  into the disposable pinned VHS checkout. No tracked upstream file or
  production preset is modified.

A second *actual* ComfyUI `/prompt` graph invokes the fixture source
and pinned `VHS_VideoCombine`. The harness requires a temporary MOV
with ProRes 4444/12-bit 4:4:4 storage, decodes to packed `rgb48le`,
checks every 16-bit RGB sample against the original normalized 12-bit
source with a **256/65535** maximum absolute channel error, and requires
the two subtle same-8-bit-bucket distinctions to survive in strict order.
A returned video lacking real sub-8-bit differentiation **must fail**,
even if its output file is labelled ProRes 4444.

This is a **test-only alternative preset** and a restricted synthetic
two-frame smoke test, not acceptance of VideoHelperSuite's *default*
ProRes preset, production pipeline, HDR mastering, image formats or
arbitrary 12/16-bit source input. Generated MOV and source frames remain
on the disposable runner; only metadata and hashes enter JSON evidence.

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
