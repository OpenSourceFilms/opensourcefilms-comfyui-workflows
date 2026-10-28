# Selected Wan native node source and socket binding audit

**Scope:** These five conditionally commercial-compatible UI/editor exports from the canonical `DEPENDENCIES.lock`:

- `wan22_fmlf_first_middle_last_frame.json`
- `video_wan2_2_14B_flf2v.json`
- `video_wan2_2_14B_fmlf2v.json`
- `video_wan2_2_14B_i2v.json`
- `video_wan_vace_14B_v2v.json`

The [source-only audit](../scripts/audit_wan_native_source_bindings.py) uses a disposable, exact Git checkout of public `Comfy-Org/ComfyUI@08cf0284ff45723aa67841c80cabb0e3cb50c9d7`. It parses the actual `comfy_extras/nodes_wan.py` via Python AST (no imports or model weights), extracts literal `define_schema` input and output names, and compares those names with **real UI node socket metadata** in the five selected exports. The runner verifies exact Git HEAD and uses only standard-library Python.

## Confirmed native-class bindings

The reviewed public source provides:

| Native class | Source contract |
|---|---|
| `WanFirstLastFrameToVideo` | positive, negative, VAE, start/end optional images and CLIP vision inputs, width, height, length, batch size; positive/negative/latent outputs |
| `WanVaceToVideo` | positive, negative, VAE, optional control video/masks/reference, spatial/temporal dimensions, batch size and strength; positive/negative/latent/trim_latent outputs |
| `TrimVideoLatent` | samples/trim_amount inputs; LATENT output |

The auditor compares **all** declared input names (including optional sockets) and output names against their UI graph instances, rejecting unexpected additions, deletions and renamings. This verifies source-level name parity only, not connected link types, latent shapes or actual execution.

## Unresolved classes in the five selected graphs

The pinned public `comfy_extras/nodes_wan.py` does **not** define:

| Unresolved class ID | Why it matters |
|---|---|
| `WanFirstMiddleLastFrameToVideo` | Appears in both first/middle/last-frame workflow exports; no audited matching native implementation |
| `WanFourFrameReferenceUltimate` | Four-frame reference workflow section in `wan22_fmlf_first_middle_last_frame.json` |
| `WanMultiFrameRefToVideo` | Multi-reference workflow section in the same UI export |

**HOLD:** These three identifiers need verified source providers, licence terms, exact revisions, installed node registrations and input/output schema checks. They may be supplied by another extension, version or fork; this audit does **not** assert that no implementation exists anywhere. Nor does it silently substitute `WanFirstLastFrameToVideo` or a different Wan node.

The auditor records occurrence counts and deterministic hashes of the five *public workflow files*, but does not include prompts, model filenames, widget values, media paths or footage. The resulting metadata-only JSON is retained for 14 days in a GitHub Actions artifact. A run can be **successful as an audit** while `all_wan_class_ids_available=false` and `wan_workflows_executable=false`, which are explicit negative acceptance flags. Unexpected changes to the missing-class baseline or native sockets **fail closed** rather than becoming an implicit acceptance.

## Execution and rights limitations

These are **UI/editor exports**, not automatically executable ComfyUI `/prompt` dictionaries. This check does not import models, install custom Wan extensions, convert graphs to API prompts, verify graph links and types, allocate GPUs, check weights or validate outputs. A native matching class name alone does not prove version/schema parity with a historical specialized workflow. Commercial suitability remains conditional on each dependency's actual licence and version.

The wider 11-workflow acceptance remains open in [issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
