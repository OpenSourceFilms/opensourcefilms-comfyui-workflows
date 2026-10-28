# Pinned GIMM-VFI + SGM-VFI source socket audit

**Status: HOLD.** This is a source-only compatibility gate for
`workflows/commercial-compatible/gimm_sgm_vfi_video_interpolate.json`.
It does not change the exported graph, download checkpoints, import third-party
Python, allocate a GPU, or execute inference.

## Evidence bound to canonical dependency commits

| Provider | Reviewed revision | Source file |
|---|---|---|
| [kijai/ComfyUI-GIMM-VFI](https://github.com/kijai/ComfyUI-GIMM-VFI) | `4c9a3123762af85e7c796e41737da0b70c75d72d` | `nodes.py` |
| [Ethanfel/ComfyUI-Tween](https://github.com/Ethanfel/ComfyUI-Tween) | `91947c0b8c795cf504d3848274d4217f0432a324` | `__init__.py`, `nodes.py` |

Both revisions are specified by the selected workflow's
`DEPENDENCIES.lock` block. The CI job fetches exactly those Git commits,
then parses `NODE_CLASS_MAPPINGS` and `INPUT_TYPES` via Python AST
without executing the downloaded source. If the repository revision,
source format, selected graph or manifest drifts, the gate fails
closed and requires a new review.

## Deterministic incompatibilities

The current UI export requests:

| Graph node ID | Requested class | Result from pinned source |
|---|---|---|
| 1 | `GIMMVFI_loader` | **Missing in both pinned registries** |
| 2 | `GIMMVFIInterpolate` | Present in **Tween**, not in pinned kijai wrapper; Tween defines different required input names |
| 21 | `LoadSGMVFIModel` | Present in Tween (registration only) |
| 22 | `SGMVFISegmentInterpolate` | Present in Tween (registration only) |

Pinned kijai/GIMM instead registers
`DownloadAndLoadGIMMVFIModel` and `GIMMVFI_interpolate` (underscore
and capitalization are meaningful). Its loader uses `model`, and
optionally `precision` and `torch_compile`. Its interpolator expects
`gimmvfi_model`, `images`, `ds_factor`,
`interpolation_factor`, `seed`, and optionally `output_flows`.
The exported workflow uses those kijai-style sockets but names
its classes differently.

Tween does register `GIMMVFIInterpolate`, but that node requires
`images`, `model`, `multiplier`, `single_pass`, and further control
sockets rather than the graph's `gimmvfi_model`, `ds_factor`,
`interpolation_factor`, `seed` and `output_flows`.
Tween's `LoadGIMMVFIModel` uses a separate model interface from the
kijai `DownloadAndLoadGIMMVFIModel` class.
**A matching node name alone is not equivalent to compatible socket
schema or model-type semantics.**

The two SGM node class names are present in the pinned Tween mapping;
the audit does not imply that their exact sockets, weights or CUDA
execution are qualified. Tween's loader may download a missing model
and uses CuPy. No such functions are executed by this source audit.

## Reproducible gate

[The isolated Actions job](../.github/workflows/audit-gimm-sgm-source.yml)
checks out only selected source files at exact historical commits, runs
[offline regression tests](../tests/test_gimm_source_bindings.py), then
writes a **metadata-only** JSON audit. Its expected result is explicitly
`status: HOLD`, `source_binding_qualified: false`. A successful
CI job means **the HOLD finding was reproduced**, not that the workflow
is ready for use.

The machine-readable audit source is
[`audit_gimm_sgm_source_bindings.py`](../scripts/audit_gimm_sgm_source_bindings.py).

**Unblock requirements:** Identify the exact historical source revision
that originally defined `GIMMVFI_loader` and the intended interpolator
socket schema, or deliberately revise and revalidate the workflow against
current pinned package classes, links and model-type contracts. Only then
attempt installation, checkpoint/licence verification and GPU inference.
Do not silently rename nodes or reinterpret the present
`commercial-compatible` label as demonstrated runtime compatibility.
