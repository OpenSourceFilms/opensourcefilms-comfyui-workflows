# Pinned public SAM3/SCAIL native API binding preflight

This is a **source-derived input/output binding preflight**, not GPU or model inference qualification.

The reference is `Comfy-Org/ComfyUI@08cf0284ff45723aa67841c80cabb0e3cb50c9d7`, specifically the published `comfy_extras/nodes_sam3.py` and `comfy_extras/nodes_scail.py` schema definitions. The source snapshot is represented in [the standalone audit](../scripts/audit_sam3_scail_api_bindings.py). It is deliberately not a declaration that the original specialized SCAIL fork and public ComfyUI are behaviourally interchangeable.

The audit reads **three actual selected executable API-format graphs**: `step4_5_sam3_mask`, `step6_animation_mode`, and `step7_replacement_mode`. Together these contain twelve instances of five native classes: `SAM3_Detect`, `SAM3_VideoTrack`, `SAM3_TrackPreview`, `SCAIL2ColoredMask`, and `WanSCAILToVideo`.

For each native node instance the audit fails closed on unknown input names, missing essential input fields, incorrect literal scalar/enum types, malformed or missing link sources, out-of-range native source output indices, and incompatible native-to-native source/output types. The pinned upstream `SAM3_Detect` schema also declares optional `bboxes`, `positive_coords`, and `negative_coords` with `force_input=True`. If present, these three sockets must be API links; literal coordinate strings or boxes do not pass the preflight. They may still be omitted. It permits the published `SAM3TrackData | MASK` union for `SCAIL2ColoredMask.ref_track_data` and recognizes that `SAM3_TrackPreview` is an output node without linkable data outputs.

Run `python -B scripts/audit_sam3_scail_api_bindings.py` for a compact, non-sensitive JSON report. The general publication CI also discovers and runs [the negative contract tests](../tests/test_sam3_scail_api_bindings.py), which read the actual three published graphs. Neither the script nor CI outputs prompt texts, model filenames, or media paths.

## Pinned core and VideoHelperSuite source-output bindings

The source-only audit now additionally checks all **31 edges** that connect
reviewed non-native provider nodes into the twelve native SAM3/SCAIL instances:
seven edges in `step4_5_sam3_mask`, twelve in `step6_animation_mode`
and twelve in `step7_replacement_mode`. The output slot schemas are
transcribed from these **exact pinned sources**, not inferred from names:

- `Comfy-Org/ComfyUI@08cf0284ff45723aa67841c80cabb0e3cb50c9d7`,
  `nodes.py`: `CheckpointLoaderSimple` (MODEL, CLIP, VAE),
  `CLIPTextEncode` (CONDITIONING), `LoadImage` (IMAGE, MASK),
  `VAELoader` (VAE), and `CLIPVisionEncode` (CLIP_VISION_OUTPUT).
- `Kosinkadink/ComfyUI-VideoHelperSuite@2984ec4c4b93292421888f38db74a5e8802a8ff8`,
  `videohelpersuite/load_video_nodes.py` and `utils.py`:
  `VHS_LoadVideo` resolves to `LoadVideoUpload`; its first output
  is `imageOrLatent`, a `MultiInput("IMAGE", ["IMAGE", "LATENT"])`.
  Its other outputs are INT, AUDIO, VHS_VIDEOINFO.

For each connected native input, the audit now requires a real declared
source output slot and a matching output type. **Six** VHS-to-native
IMAGE links are conditionally accepted at the *schema* level because
the exact selected API graphs do **not** supply the optional `vae`
input. If a future graph adds `vae` to `VHS_LoadVideo`, this check
fails closed: the node could produce LATENT instead of IMAGE. It is
not a claim that the actual video loader's runtime tensors have been
tested. A change to any of the 31 provider links, any unreviewed
source class, or the expected provider baseline fails the consolidated
three-graph audit.

The report explicitly retains
`vhs_runtime_output_type_verified=false`,
`full_graph_link_type_verification=false`,
`all_other_workflow_nodes_qualified=false`,
and `model_weights_or_inference_tested=false`. Unreviewed intermediate
edges across the complete API graphs have not been promoted to
type-verified status.

**Explicit non-acceptance:** This checks **source-visible field names, scalar shapes, published source output slots and type declarations**, including the pinned core and VideoHelperSuite inputs to native nodes. It does not prove actual connected tensor compatibility, optional runtime branches, model weights, SAM3 tracking, SCAIL latent conditioning or Wan sampling execution. It does not convert the seven UI workflow exports, execute any real workflow, install weights, or assess GPU VRAM, performance, licence obligations or production media fidelity. The full eleven-workflow acceptance remains open in [issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).

Changes in public ComfyUI's schema after the pinned revision require a fresh source review. The snapshot is not automatically authoritative for newer builds.
