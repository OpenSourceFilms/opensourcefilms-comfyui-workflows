# Pinned public SAM3/SCAIL native API binding preflight

This is a **source-derived input/output binding preflight**, not GPU or model inference qualification.

The reference is `Comfy-Org/ComfyUI@08cf0284ff45723aa67841c80cabb0e3cb50c9d7`, specifically the published `comfy_extras/nodes_sam3.py` and `comfy_extras/nodes_scail.py` schema definitions. The source snapshot is represented in [the standalone audit](../scripts/audit_sam3_scail_api_bindings.py). It is deliberately not a declaration that the original specialized SCAIL fork and public ComfyUI are behaviourally interchangeable.

The audit reads **three actual selected executable API-format graphs**: `step4_5_sam3_mask`, `step6_animation_mode`, and `step7_replacement_mode`. Together these contain twelve instances of five native classes: `SAM3_Detect`, `SAM3_VideoTrack`, `SAM3_TrackPreview`, `SCAIL2ColoredMask`, and `WanSCAILToVideo`.

For each native node instance the audit fails closed on unknown input names, missing essential input fields, incorrect literal scalar/enum types, malformed or missing link sources, out-of-range native source output indices, and incompatible native-to-native source/output types. It permits the published `SAM3TrackData | MASK` union for `SCAIL2ColoredMask.ref_track_data` and recognizes that `SAM3_TrackPreview` is an output node without linkable data outputs.

Run `python -B scripts/audit_sam3_scail_api_bindings.py` for a compact, non-sensitive JSON report. The general publication CI also discovers and runs [the negative contract tests](../tests/test_sam3_scail_api_bindings.py), which read the actual three published graphs. Neither the script nor CI outputs prompt texts, model filenames, or media paths.

**Explicit non-acceptance:** This checks **source-visible field names, scalar shapes, published native output slots and native-to-native type names only**. It cannot prove that external/custom-node output types match the native inputs, or that connected tensors, optional parameters, model weights, SAM3 tracking, SCAIL latent conditioning or Wan sampling execute successfully. It does not convert the seven UI workflow exports, execute any real workflow, install weights, or assess GPU VRAM, performance, licence obligations or production media fidelity. The full eleven-workflow acceptance remains open in [issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).

Changes in public ComfyUI's schema after the pinned revision require a fresh source review. The snapshot is not automatically authoritative for newer builds.
