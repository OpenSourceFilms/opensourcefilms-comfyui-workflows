# Eleven-workflow node-class coverage preflight (source only)

The approved RunPod staging profile contains exactly eleven conditionally commercial-compatible workflow exports. The canonical selection and dependency status come from DEPENDENCIES.lock, not from a filename guess.

To run without a GPU, ComfyUI server, model weights, or network:

    python scripts/audit-selected-11-node-coverage.py --output /tmp/osf-11-coverage.json

The report is generated in a disposable CI temp directory. It is not uploaded as a production validation certificate.

## What the preflight establishes

- Both editor/UI graph exports (nodes in a nodes array, with a type) and executable-prompt-style API dictionaries (node class_type) are parsed. Seven of the eleven selected files are UI exports and four are API-format exports. UI JSON cannot be sent directly as a standard ComfyUI /prompt API payload without conversion.
- Across the eleven graphs there are 81 distinct node type strings. Their total occurrences are counted, not silently deduplicated.
- Four UUID-shaped node types occur in mm_upscale_video_workflow. These are reported as unresolved_group_uuid, not mislabelled as built-in ComfyUI nodes. They need separate group-node definition/provenance validation.
- The historically fork-native identifiers `SAM3_Detect`, `SAM3_VideoTrack`, `SAM3_TrackPreview`, `SCAIL2ColoredMask` and `WanSCAILToVideo` are classified as **SAM3/SCAIL native, runtime unverified by this source-only audit**. Earlier documentation assumed the modified SAM3/SCAIL-2 fork was mandatory. However, exact public `Comfy-Org/ComfyUI@08cf0284ff45723aa67841c80cabb0e3cb50c9d7` includes `comfy_extras/nodes_sam3.py` and `comfy_extras/nodes_scail.py`, and [PR #26](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/pull/26) confirmed all five classes register in the disposable clean CPU runtime. This does **not** prove node schema equivalence, model loading, or inference.
- class_registered_on_clean_cpu_only applies only to the exact six class identifiers required by the independently passing clean CPU runtime check: VHS_VideoCombine, VHS_SelectEveryNthImage, Any Switch (rgthree), DownsampleFPSNode, UnetLoaderGGUF and UltimateSDUpscale. This does not extend to adjacent classes from those packages. In particular, UltimateSDUpscaleNoUpscale is not interchangeable with the imported UltimateSDUpscale.
- Other node names remain unqualified, even when a source graph labels them comfy-core, declares an extension cnr_id, or resembles a core node identifier. Editor widgets/notes are not assumed to be safely ignorable in a working UI.

The report omits prompt texts, model filenames, paths to footage and images. It includes public workflow paths, node-class names, canonical dependency names and explicit negative acceptance flags.

## Required downstream acceptance

1. Resolve every UUID/group definition, verify owner/source and runtime class for all unqualified dependencies. Pin and review licences separately.
2. Compare the pinned **public** ComfyUI SAM3/SCAIL class input/output schemas against the actual workflow input bindings and the historical specialized-fork implementations. All five IDs register on the pinned public commit, but schema parity, SAM3/SCAIL model weights and actual processing are still untested.
3. Acquire and verify permitted model weights on an independently authorised GPU environment, respecting source and weight licences and production media confidentiality.
4. Convert the seven UI graphs to validated API prompts for automated execution, then verify node input and output types, weights, shapes and end-to-end GPU inference. This source-only report does not attempt conversion.

**No workflow is marked executable, GPU-qualified or rights-cleared by this preflight.** Full RunPod/model acceptance remains open under issue #3: https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3

Sources: DEPENDENCIES.lock, runpod/commercial-compatible/prepare.py and scripts/qualify_clean_comfy_cpu.py.
