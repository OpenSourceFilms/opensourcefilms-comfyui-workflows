# Embedded mm_upscale: Essentials source socket parity

This is a **source-only input/output schema preflight**, not an installed
ComfyUI extension or runnable embedded-group test.

The source reference is the immutable, previously reviewed
[`cubiq/ComfyUI_essentials@9d9f4bedfc9f0321c19faf71855e228c93bd0dc9`](https://github.com/cubiq/ComfyUI_essentials/tree/9d9f4bedfc9f0321c19faf71855e228c93bd0dc9),
whose root licence is MIT. The reviewed source defines:

| Exported class | Source definition | Required inputs | Outputs | Export instances |
|---|---|---|---|---:|
| `ImageFromBatch+` | `image.py` class `ImageFromBatch` | `image: IMAGE`, `start: INT`, `length: INT` | `IMAGE` | 9 |
| `SimpleMathSlider+` | `misc.py` class `SimpleMathSlider` | `value: FLOAT`, `min: FLOAT`, `max: FLOAT`, `rounding: INT` | `FLOAT`, `INT` | 1 |

The [new read-only audit](../scripts/audit_mm_upscale_essentials_sockets.py)
checks all **10 actual instances** across the four embedded
`mm_upscale_video_workflow.json` group definitions, including port
names and types in their declared order, required input links/widgets,
output slot schemas, expected class/group counts, and export version
metadata. It rejects new classes, changed source-bound schemas, malformed
links, and missing groups. No prompt text, model filenames, source
widget **values**, or private paths appear in its report.

Execute without model weights, GitHub access, ComfyUI runtime or GPU:

```bash
python -B scripts/audit_mm_upscale_essentials_sockets.py --output /tmp/mm-essentials-sockets.json
```

**Important provenance limitation:** The exported `ver` fields are
mixed. Some record the reviewed full source SHA, but others record
`1.1.0`, which is not verified here as equivalent to that commit.
The audit checks socket metadata against the reviewed **candidate**
implementation; it does **not** prove that a historical node of
version `1.1.0` behaves the same. Nor does a root MIT licence
constitute transitive rights clearance for the entire dependency set.

**Still on HOLD:** Adding this provider to the canonical
`DEPENDENCIES.lock`, installing its additional Python dependencies
(including `rembg` and `transparent-background`), confirming live
class registration and method execution, resolving embedded group
links/versions, converting UI exports to API graphs, commercial
rights for the full workflow, model weights and GPU inference.

See [embedded provider gaps](embedded-mm-upscale-provider-gaps.md)
and [selected eleven-workflow coverage](selected-11-node-coverage.md).
Keep [issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3)
open until all required runtime and rights gates have independently passed.
