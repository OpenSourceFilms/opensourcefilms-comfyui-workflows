# mm_upscale: candidate upstream source and licence snapshot

**Dated source review: 28 October 2026. This is not an installation plan or runtime acceptance.**

The four embedded group definitions in
[`mm_upscale_video_workflow.json`](../workflows/commercial-compatible/mm_upscale_video_workflow.json)
contain 15 distinct external node class identifiers across four exported
`properties.cnr_id` hints. The canonical workflow section of
[`DEPENDENCIES.lock`](../DEPENDENCIES.lock) currently omits three providers
and lists the fourth without a source commit pin.

The following **candidate revisions**, source files and root licence texts were
inspected in the upstream public GitHub repositories. The referenced revisions
are immutable full Git commit identifiers. They are source evidence candidates,
**not evidence that the exported workflow works with those revisions**.

| Exported provider | Candidate source at reviewed commit | Root licence | Required classes and verified source locations |
|---|---|---|---|
| `comfyui-custom-scripts` | [pythongosssss/ComfyUI-Custom-Scripts @ `609f3af`](https://github.com/pythongosssss/ComfyUI-Custom-Scripts/tree/609f3afaa74b2f88ef9ce8d939626065e3247469) | MIT | `MathExpression\|pysssss` in `py/math_expression.py`; `StringFunction\|pysssss` in `py/string_function.py` |
| `comfyui-easy-use` | [yolain/ComfyUI-Easy-Use @ `b0b47ca`](https://github.com/yolain/ComfyUI-Easy-Use/tree/b0b47ca1372117fce575d9e744655344ebff6bef) | GPL-3.0 | `easy batchAnything`, `easy boolean`, `easy compare`, `easy forLoopStart`, `easy forLoopEnd`, `easy ifElse`, `easy int` in `py/nodes/logic.py`; `easy imageSave` in `py/nodes/image.py` |
| `comfyui-kjnodes` | [kijai/ComfyUI-KJNodes @ `2371136`](https://github.com/kijai/ComfyUI-KJNodes/tree/2371136d2fa6fd0914e514cd99b36dabe5db9adf) | GPL-3.0 | `ImageBatchJoinWithTransition`, `ImageBatchMulti`, `ImagePass` defined in `nodes/image_nodes.py` |
| `comfyui_essentials` | [cubiq/ComfyUI_essentials @ `9d9f4be`](https://github.com/cubiq/ComfyUI_essentials/tree/9d9f4bedfc9f0321c19faf71855e228c93bd0dc9) | MIT | `ImageFromBatch+` in `image.py`; `SimpleMathSlider+` in `misc.py` |

Root `LICENSE` content was read at each exact SHA. Some source files expose
actual `NODE_CLASS_MAPPINGS` entries, while KJNodes class names were
confirmed as Python definitions, **not** by an executed registration test.
A source-name match cannot establish compatible socket schemas, logic,
nested dependencies, installed Python requirements or successful group
expansion in ComfyUI. Likewise, root licence review does not substitute
for a full third-party dependency and distribution-obligation review.

## Reproduce the offline mapping check

```bash
python -B scripts/audit_embedded_group_source_candidates.py \
  --output /tmp/osf-mm-upscale-provider-candidates.json
```

This source-only script compares the **actual embedded class inventory**
against the dated reviewed mapping above, reports the four candidate
commits and current canonical-manifest declaration/pin state, and fails
if the exported provider/class inventory drifts. Its regression tests
reject unreviewed providers, incorrect SHAs, unknown licence labels,
source-path anomalies and missing class evidence.

**The offline check does not fetch GitHub.** The initial 28 October source
review is a fixed snapshot, not automatically revalidated against later
upstream changes. Before any production install, independently obtain the
exact commits, compare licences and transitive dependencies, verify all 15
classes and their required sockets on a clean runtime, and establish that
the embedded groups import, expand, convert into executable prompts and
run with the actual intended model weights.

`DEPENDENCIES.lock`, workflow JSONs and third-party source remain
**unchanged** by this audit. Commercial rights, GPU execution, model
inference and the full 11-workflow profile remain **unqualified**.
