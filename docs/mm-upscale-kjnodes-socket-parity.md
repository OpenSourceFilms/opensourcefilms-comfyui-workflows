# Embedded mm_upscale: KJNodes historical source socket parity

This is a **source-only, read-only** comparison of the seven exported
`comfyui-kjnodes` instances inside the four embedded groups of
[`mm_upscale_video_workflow.json`](../workflows/commercial-compatible/mm_upscale_video_workflow.json).
It neither installs nor imports KJNodes.

The **actual 40-character SHA exported by one `ImagePass` node** is
[`kijai/ComfyUI-KJNodes@468fcc86f0b29e79a8510e8239eb15714d6747a6`](https://github.com/kijai/ComfyUI-KJNodes/tree/468fcc86f0b29e79a8510e8239eb15714d6747a6).
The root `LICENSE` is **GPLv3**. At that revision, the original
`nodes/image_nodes.py` defines the three classes, and root
`__init__.py` registers them through `NODE_CONFIG`.

| Source class | Reviewed source inputs | Source output | Export instances |
|---|---|---|---:|
| `ImageBatchJoinWithTransition` | required `images_1:IMAGE`, `images_2:IMAGE`, `start_index:INT`, `interpolation:COMBO`, `transition_type:COMBO`, `transitioning_frames:INT`, `blur_radius:FLOAT`, `reverse:BOOLEAN`, `device:COMBO` | `IMAGE` | 2 |
| `ImageBatchMulti` | required `inputcount:INT`, `image_1:IMAGE`; optional `image_2:IMAGE` | `images:IMAGE` | 4 |
| `ImagePass` | optional `image:IMAGE` | `IMAGE` | 1 |

The [audit](../scripts/audit_mm_upscale_kjnodes_sockets.py) checks **seven
actual instances** in **two groups**: four in `Blend Frames Subgraph`
and three in `Blend Saved Frames Subgraph`. It verifies input/output
names and types, connection/widget coverage, expected UI widget counts,
version metadata, group counts, and exact source-bound class inventory.

**Dynamic input and source/UI ordering caveat:** The historical source's
`ImageBatchMulti.INPUT_TYPES` declares `inputcount` before `image_1`,
then optional `image_2`. The exported UI orders those three sockets
`image_1`, `image_2`, `inputcount`, and records two `widgets_values`.
The audit explicitly checks this observed **UI representation**, but does
not claim that its order is the runtime API schema or that arbitrary
`inputcount` changes are executable. The `ImagePass` source input is
**optional**, although the exported instance currently connects it.

**Unresolved version provenance:** Six nodes export `ver=1.1.4`; the
remaining `ImagePass` exports the reviewed full source SHA. No evidence
establishes that `1.1.4` is equivalent to the reviewed commit or that
all historical instances were installed from the same revision. The
audit therefore validates source **candidate** schemas only and
explicitly reports alias compatibility as **unverified**.

Run locally with only Python's standard library:

```bash
python -B scripts/audit_mm_upscale_kjnodes_sockets.py --output /tmp/mm-kjnodes-sockets.json
```

The public CI suite runs this read-only gate and negative tests. Reports
contain only node class names, version labels, provider counts, licence,
source SHA and explicit non-acceptance flags. No prompts, widget values,
image data, model weights or private paths are published.

**HOLD:** Do not insert KJNodes into canonical `DEPENDENCIES.lock` or
declare full commercial-compatible runtime coverage from this audit.
Import-time third-party requirements (historical `requirements.txt`
includes e.g. color-matcher, scipy and opencv), nested dependencies,
GPLv3 distribution obligations, actual ComfyUI API registrations,
embedded group expansion, image processing, GPU model inference and
all-11-workflow execution remain unverified. See the
[embedded provider gap report](embedded-mm-upscale-provider-gaps.md) and
[issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).
