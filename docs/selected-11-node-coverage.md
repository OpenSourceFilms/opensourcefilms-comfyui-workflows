# Eleven-workflow node-class coverage preflight (source only)

The approved RunPod staging profile contains exactly eleven conditionally commercial-compatible workflow exports. The canonical selection and dependency status come from DEPENDENCIES.lock, not from a filename guess.

To run without a GPU, ComfyUI server, model weights, or network:

    python scripts/audit-selected-11-node-coverage.py --output /tmp/osf-11-coverage.json

The report is generated in a disposable CI temp directory. It is not uploaded as a production validation certificate.

## What the preflight establishes

- Both editor/UI graph exports (nodes in a nodes array, with a type) and executable-prompt-style API dictionaries (node class_type) are parsed. Seven of the eleven selected files are UI exports and four are API-format exports. UI JSON cannot be sent directly as a standard ComfyUI /prompt API payload without conversion.
- Across the eleven graphs there are 81 distinct node type strings. Their total occurrences are counted, not silently deduplicated.
- Four UUID-shaped node types occur in `mm_upscale_video_workflow`. **All four have matching embedded `definitions.subgraphs` entries in that exact UI export**, containing respectively 16, 35, 28 and 10 internal nodes (89 total). These are *not* missing external definition files. The historical `unresolved_group_uuid` class label means their **runtime execution remains unresolved**, not that their definitions are absent. The new `embedded_group_definition_preflight` records the matching IDs, internal node-class names, unresolved nested references and explicit runtime-negative flags. Internal classes such as `easy forLoopStart` and `ImageBatchJoinWithTransition` still require exact source, install, schema and licence verification. Neither the 89 internal instances nor their classes are silently added to the 81 top-level class count.
- The historically fork-native identifiers `SAM3_Detect`, `SAM3_VideoTrack`, `SAM3_TrackPreview`, `SCAIL2ColoredMask` and `WanSCAILToVideo` are **SAM3/SCAIL native, runtime unverified by this source-only audit**. The earlier assumption that a special fork is mandatory merely for these class *names* has been superseded. Pinned public `Comfy-Org/ComfyUI@08cf0284ff45723aa67841c80cabb0e3cb50c9d7` contains `comfy_extras/nodes_sam3.py` and `nodes_scail.py`, and the [PR #26 live CPU registry](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/pull/26) confirms all five register without a specialized fork. This does **not** establish input/output schema parity, model loading or correct inference.
- class_registered_on_clean_cpu_only applies only to the exact six class identifiers required by the independently passing clean CPU runtime check: VHS_VideoCombine, VHS_SelectEveryNthImage, Any Switch (rgthree), DownsampleFPSNode, UnetLoaderGGUF and UltimateSDUpscale. This does not extend to adjacent classes from those packages. In particular, UltimateSDUpscaleNoUpscale is not interchangeable with the imported UltimateSDUpscale.
- Other node names remain unqualified, even when a source graph labels them comfy-core, declares an extension cnr_id, or resembles a core node identifier. Editor widgets/notes are not assumed to be safely ignorable in a working UI.
- The independent clean CPU runtime also compares **all internal class names from the four embedded `mm_upscale_video_workflow` definitions** to the actual pinned ComfyUI `/object_info` registry. The live evidence separates **89 internal node instances** from the 81 distinct top-level graph class strings, lists registered/unregistered *unique internal class IDs* per group, and classifies absent names as fork-native, editor/layout, nested UUID or otherwise unregistered. The group UUID itself is never treated as a verified executable node merely because its string appears in the registry. Registration is **not** group expansion, API prompt conversion, node schema compatibility, model loading, or execution. These remain explicit negative flags.

The report omits prompt texts, model filenames, paths to footage and images. It includes public workflow paths, node-class names, canonical dependency names and explicit negative acceptance flags.

For an explicit per-provider reconciliation of the four embedded groups' 89 internal nodes against the canonical mm_upscale dependency block, see [embedded provider gaps](embedded-mm-upscale-provider-gaps.md). The exported metadata identifies three unlisted provider hints (Easy-Use, KJNodes and Essentials) and an unpinned listed Custom-Scripts provider. This is **not** installation, licence or runtime acceptance.

## Embedded `mm_upscale` link integrity, source-only

A second [read-only structural audit](../scripts/audit_embedded_group_links.py)
checks the **actual four embedded `mm_upscale_video_workflow` UI
subgraphs**, using the same canonical selected-eleven manifest:

```sh
python -B scripts/audit_embedded_group_links.py --output /tmp/osf-mm-upscale-links.json
```

This distinct check understands LiteGraph embedded-group pseudo-node IDs
`-10` (external input) and `-20` (external output). Those are valid
endpoints, **not missing node IDs**. It verifies that all **171 active
link records** reference present internal node outputs/inputs or valid
exposed group port indices, that the active link IDs are unique, and
that the active forward records agree with node/port backreferences.

However, the published source also retains **16 unresolved reverse
references** not present among those 171 active links. Per group, the
counts are **4, 3, 3 and 6**. They occur in node-output `links` lists
and exposed group-input `linkIds`, not as invalid active edges. These
may be stale editor serialization rather than fatal runtime defects,
but the audit deliberately **does not repair, hide, or declare them
harmless**. A zero-warning structural sign-off is therefore **HOLD**.

The script reports only public group UUIDs, numeric link identifiers,
counts, a hash of the selected graph bytes, and explicit negative
acceptance flags. It prints no widget values, prompts, model filenames,
media paths or personal data; its CI output remains in runner scratch.
Regression tests reject missing nodes, slot mismatches, duplicate
link IDs, inconsistent active backreferences, malformed reference
types and corrupted group pseudo-port connections.

Neither structurally consistent active links nor an embedded group
definition establish frontend import, subgraph expansion, valid
API-prompt conversion, availability of Easy-Use/other custom nodes,
licensing, or actual inference. The selected workflow is unchanged.

## Required downstream acceptance

1. Verify all **embedded subgraph internal dependencies**, including each required package, node input/output schema, extension version and licence. Confirm the four matching definitions load and execute correctly in the target ComfyUI frontend and API conversion. Other workflow group definitions, if introduced, must be validated before acceptance.
2. Compare public-core SAM3/SCAIL input/output schemas with the original specialized fork and actual workflow bindings. All five class IDs register on the pinned public commit; schema parity, model-weight loading, GPU execution and output fidelity remain unverified.
3. Acquire and verify permitted model weights on an independently authorised GPU environment, respecting source and weight licences and production media confidentiality.
4. Convert the seven UI graphs to validated API prompts for automated execution, then verify node input and output types, weights, shapes and end-to-end GPU inference. This source-only report does not attempt conversion.

**No workflow is marked executable, GPU-qualified or rights-cleared by this preflight.** Full RunPod/model acceptance remains open under issue #3: https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3

Sources: DEPENDENCIES.lock, runpod/commercial-compatible/prepare.py and scripts/qualify_clean_comfy_cpu.py.
