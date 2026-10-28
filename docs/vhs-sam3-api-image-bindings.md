# Pinned VHS_LoadVideo to native SAM3 IMAGE API binding

**Status: source-only compatibility evidence, production HOLD.**

This [independent audit](../scripts/audit_vhs_sam3_api_image_edges.py)
reviews the three selected API-format SCAIL/SAM3 workflows:

- `step4_5_sam3_mask.json`
- `step6_animation_mode.json`
- `step7_replacement_mode.json`

The three graphs use `VHS_LoadVideo` node ID 3 as an input to pinned
public-core SAM3/SCAIL nodes. The exact-pinned upstream
`Kosinkadink/ComfyUI-VideoHelperSuite@2984ec4c4b93292421888f38db74a5e8802a8ff8`
source defines `VHS_LoadVideo` as `LoadVideoUpload` in
`videohelpersuite/nodes.py`. Its `RETURN_TYPES` declare output slot 0
as the `imageOrLatent` union; `videohelpersuite/utils.py` defines that
as IMAGE or LATENT. The `load_video` implementation in
`videohelpersuite/load_video_nodes.py` returns **IMAGE when `vae is
None`**, and a latent dictionary when `vae` is supplied.

The selected graphs all save exactly the expected eight loader input
names and **do not connect `vae` or `meta_batch`**. The source-only
checker therefore establishes the IMAGE branch at this historical pin.
It verifies **all six actual wires** originating at VHS node 3:
`SAM3_VideoTrack.images` in all three graphs, plus
`SAM3_TrackPreview.images` in step 4/5 or
`WanSCAILToVideo.pose_video` in steps 6 and 7. The target names and
IMAGE socket types come from the separately reviewed
[pinned native SAM3/SCAIL schema audit](sam3-scail-native-api-bindings.md).
Only upstream **output slot 0** is permitted. Saved class or input
changes, a new `vae` connection, changed slot indices or unexpected
destinations fail the gate.

[Disposable CI](../.github/workflows/audit-vhs-sam3-image-edges.yml)
checks out the exact pinned VHS Git commit, uses **Python AST without
importing external modules**, runs no-network mutation tests and records
only the three public workflow SHA-256 digests, counts and source
contracts in a JSON artifact retained for 14 days. It does not emit
the saved `video` file values, prompts, model names, images, footage
or credentials.

**Non-acceptance:** The check proves only a source-level, no-VAE IMAGE
routing choice at those exact revisions. It does **not** establish that
the saved video files exist, are decodable, retain expected frame rate
or resolution, load without memory pressure, or are permitted for use.
It never runs `VHS_LoadVideo`, SAM3 detection/tracking, SCAIL,
Wan inference, models or GPU operations. Native node input and output
types being compatible does not guarantee model compatibility,
successful end-to-end execution or commercial rights.

Full eleven-workflow production promotion remains **HOLD** under
[issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
