# Eleven-workflow node-class coverage preflight (source only)

The approved RunPod staging profile contains exactly eleven conditionally commercial-compatible workflow exports. The canonical selection and dependency status come from DEPENDENCIES.lock, not from a filename guess.

To run without a GPU, ComfyUI server, model weights, or network:

    python scripts/audit-selected-11-node-coverage.py --output /tmp/osf-11-coverage.json

The report is generated in a disposable CI temp directory. It is not uploaded as a production validation certificate.

## What the preflight establishes

- Both editor/UI graph exports (nodes in a nodes array, with a type) and executable-prompt-style API dictionaries (node class_type) are parsed. Seven of the eleven selected files are UI exports and four are API-format exports. UI JSON cannot be sent directly as a standard ComfyUI /prompt API payload without conversion.
- Across the eleven graphs there are 81 distinct node type strings. Their total occurrences are counted, not silently deduplicated.
- Four UUID-shaped node types occur in mm_upscale_video_workflow. These are reported as unresolved_group_uuid, not mislabelled as built-in ComfyUI nodes. They need separate group-node definition/provenance validation.
- The fork-native identifiers SAM3_Detect, SAM3_VideoTrack, SAM3_TrackPreview, SCAIL2ColoredMask and WanSCAILToVideo are explicitly classified as requiring the modified SAM3/SCAIL-2 ComfyUI core, not ordinary ComfyUI plus generic downloaded packages.
- class_registered_on_clean_cpu_only applies only to the exact six class identifiers required by the independently passing clean CPU runtime check: VHS_VideoCombine, VHS_SelectEveryNthImage, Any Switch (rgthree), DownsampleFPSNode, UnetLoaderGGUF and UltimateSDUpscale. This does not extend to adjacent classes from those packages. In particular, UltimateSDUpscaleNoUpscale is not interchangeable with the imported UltimateSDUpscale.
- Other node names remain unqualified, even when a source graph labels them comfy-core, declares an extension cnr_id, or resembles a core node identifier. Editor widgets/notes are not assumed to be safely ignorable in a working UI.

The report omits prompt texts, model filenames, paths to footage and images. It includes public workflow paths, node-class names, canonical dependency names and explicit negative acceptance flags.


## Live registry comparison on disposable CPU

The independent [clean ComfyUI CPU acceptance job](../.github/workflows/verify-clean-cpu-runtime.yml)
now obtains the real `/object_info` response from the pinned vanilla ComfyUI
core and the five installed pinned external packages, and compares it to
**this exact source-only 11-graph inventory**. It requires actual API
`input` and `output` schema fields for every matched class and all six
previously accepted pinned class registrations. It explicitly rejects
any appearance of the five modified-fork native types or the four
unresolved group UUID classes on this clean vanilla deployment.

The JSON-only acceptance artifact records, for each selected workflow,
the list and count of class names actually registered *in that one
specific CPU environment*, and those still absent from it. It also
records the aggregate registered/missing counts across the 81 distinct
source node-type strings. Names are node class identifiers only.
**No source graph values, model paths, user prompt text, footage,
raw object-info schemas, weights or binary media are uploaded.**

A missing name means **not registered in this deliberately minimal
CPU install**, not globally nonexistent. A registered name means only
the class schema appeared in `/object_info`; it does not mean the
selected UI export is a valid API prompt, any model weight is available,
the node executes successfully, or a model/use licence is cleared.
The report permanently keeps workflow execution, rights and GPU flags
**false**. This is a diagnostic dependency gap map, **not an
installation-ready or production-deployment certificate**.

## Required downstream acceptance

1. Resolve every UUID/group definition, verify owner/source and runtime class for all unqualified dependencies. Pin and review licences separately.
2. For fork-native SCAIL-2/SAM3 classes, identify and verify the exact modified ComfyUI commit and runtime object schemas. Vanilla ComfyUI acceptance does not cover these classes.
3. Acquire and verify permitted model weights on an independently authorised GPU environment, respecting source and weight licences and production media confidentiality.
4. Convert the seven UI graphs to validated API prompts for automated execution, then verify node input and output types, weights, shapes and end-to-end GPU inference. This source-only report does not attempt conversion.

**No workflow is marked executable, GPU-qualified or rights-cleared by this preflight.** Full RunPod/model acceptance remains open under issue #3: https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3

Sources: DEPENDENCIES.lock, runpod/commercial-compatible/prepare.py and scripts/qualify_clean_comfy_cpu.py.
