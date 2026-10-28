# Historical upstream source pins recovered from mm_upscale groups

This is **source-provenance review**, not a deployment recipe, licence clearance, or executable graph qualification. It complements [the manifest-provider gap report](embedded-mm-upscale-provider-gaps.md) without modifying the canonical dependency manifest.

The public mm_upscale_video_workflow UI export contains four embedded group definitions with **89 internal node instances**. Of those, **82 instances** (15 distinct classes) carry provider hints for the four external repositories below; seven instances are labelled comfy-core.

## Exact revisions in exported metadata

The exports contain both semantic-version strings and 40-character Git SHAs in node properties. On 28 October 2026, each SHA was resolved in the original public GitHub repository. The root LICENSE and selected node-registration source files were also checked at each revision.

| Exported provider | Original upstream at exported SHA | Root licence | Instances | Classes |
|---|---|---|---:|---:|
| comfyui-custom-scripts | [pythongosssss/ComfyUI-Custom-Scripts @ f2838ed5](https://github.com/pythongosssss/ComfyUI-Custom-Scripts/tree/f2838ed5e59de4d73cde5c98354b87a8d3200190) | MIT | 23 | 2 |
| comfyui-easy-use | [yolain/ComfyUI-Easy-Use @ 8ecc929c](https://github.com/yolain/ComfyUI-Easy-Use/tree/8ecc929cd41cf0f7ef6fcc45d4bbc5729c6f287f) | GPLv3 | 42 | 8 |
| comfyui-kjnodes | [kijai/ComfyUI-KJNodes @ 468fcc86](https://github.com/kijai/ComfyUI-KJNodes/tree/468fcc86f0b29e79a8510e8239eb15714d6747a6) | GPLv3 | 7 | 3 |
| comfyui_essentials | [cubiq/ComfyUI_essentials @ 9d9f4bed](https://github.com/cubiq/ComfyUI_essentials/tree/9d9f4bedfc9f0321c19faf71855e228c93bd0dc9) | MIT | 10 | 2 |

### Reviewed registration source files

- **Custom-Scripts:** MathExpression|pysssss in py/math_expression.py; StringFunction|pysssss in py/string_function.py. Root __init__.py aggregates dynamic Python module mappings.
- **Easy-Use:** easy compare, easy int, easy ifElse, easy forLoopStart, easy batchAnything, easy forLoopEnd and easy boolean in py/nodes/logic.py; easy imageSave in py/nodes/image.py.
- **KJNodes:** ImageBatchJoinWithTransition, ImageBatchMulti and ImagePass in root __init__.py's NODE_CONFIG, which generates node mappings.
- **Essentials:** ImageFromBatch+ in image.py and SimpleMathSlider+ in misc.py; root __init__.py combines their class mappings.

These are source-registration matches, **not** proof that the modules import under the current pinned ComfyUI runtime, have compatible sockets or execute correctly when the embedded UI groups expand.

### Exported version labels remain unresolved

The same provider groups also contain semver-style labels (for example, 1.3.0, 1.3.3, 1.2.5, 1.1.0 and 1.1.4). These aliases have **not** been proven equivalent to the candidate Git commit from that provider. Finding one exact commit in combined exported metadata does not certify that every instance originally used that SHA. Version-by-version compatibility remains a gate.

GPLv3 at Easy-Use and KJNodes creates obligations when covered software is distributed. The root licences alone do not clear transitive packages, models, datasets or the whole workflow.

## Offline drift gate

Run this without a GPU, network, package installation or model weights:

    python -B scripts/audit_mm_upscale_historical_source_pins.py --output /tmp/osf-mm-upscale-historical-pins.json

The tool verifies the current public embedded export against the four reviewed commits and 15 source-backed node-class names. It fails closed for new providers, unreviewed class IDs, removed or changed candidate SHAs, malformed version hints or missing group definitions. The public regression suite includes positive and negative contracts. Output contains only provider IDs, classes, source paths, candidate SHAs, licence labels and explicit non-acceptance flags, not prompts, media, credentials or upstream binaries.

This is not a live GitHub refetch inside CI. The precise commits, root licences and mapping files were checked on the review date. Changed sources require fresh review.

## Remaining acceptance gates

1. Establish which code version supports every class instance, including semver-labelled instances, and validate group expansion in the target editor/runtime.
2. Review and pin nested dependencies and import-time effects.
3. Update the canonical DEPENDENCIES.lock only after compatibility and licence requirements are reviewed.
4. Test node socket parity, runtime group execution, model rights, GPU inference and output quality.

**No manifest update, production install, model download, GPU inference or commercial approval is made by this audit.** Track the remaining work under [issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
