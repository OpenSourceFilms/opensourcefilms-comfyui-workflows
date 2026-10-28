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

The two SGM class names appear in the pinned Tween mapping. A separate
source-only check below now verifies their exact UI socket types,
inheritance, output ports and two selected graph links. Weights, model
provenance, all other links and CUDA execution remain unqualified.
Tween's loader may download a missing model and uses CuPy.
No such functions are executed by either source audit.

## Non-destructive class-name migration candidate

[The source-only candidate planner](../scripts/plan_gimm_vfi_class_migration.py)
reviews the **same exact-pinned kijai source** and original exported UI
graph, but never writes a replacement workflow. At these revisions,
the two GIMM source interfaces have the following *provisional*
class-name substitutions:

| UI node ID | Historical graph type | Exact pinned kijai registration |
|---|---|---|
| 1 | `GIMMVFI_loader` | `DownloadAndLoadGIMMVFIModel` |
| 2 | `GIMMVFIInterpolate` | `GIMMVFI_interpolate` |

The planner statically compares **every input socket name and type**,
required input presence, **all output types and names**, and the
original `ComfyUI-GIMM-VFI` source revision. It constructs the
candidate *only in memory* and verifies that restoring the two
historical class names also restores the **entire exact input graph**,
including all links, widget values and unrelated nodes. The CI
artifact contains only bounded diff metadata and a hash of the
canonical in-memory candidate, **not a deployable JSON graph**.
Seven negative tests reject schema drift and accidental mutations.

This establishes a possible **two-class GIMM migration**, not a
completed workflow migration. The SGM source classes remain separate;
they have not passed their full socket/link, weights or CuPy/GPU
acceptance. Model checkpoint provenance, licence conditions and
actual GIMM/SGM inference still require independent checks. The
candidate's decision remains `CANDIDATE_ONLY_HOLD`, and the selected
released workflow is **not modified** or ready for production.

## SGM loader and segment socket parity (source only)

The separate [SGM socket audit](../scripts/audit_sgm_source_socket_parity.py)
inspects the pinned `ComfyUI-Tween@91947c0b8c795cf504d3848274d4217f0432a324`
`__init__.py` registration and `nodes.py` via static Python AST. It does
**not** import Tween or invoke its CuPy, checkpoint or auto-download paths.

It validates all three `LoadSGMVFIModel` input sockets
(`model_path` COMBO, `tta` BOOLEAN, `num_key_points` FLOAT), its
`SGM_VFI_MODEL` output, and every inherited
`SGMVFISegmentInterpolate` socket. The latter has the base
`SGMVFIInterpolate` inputs plus two required integer
`segment_index` and `segment_size` sockets, and returns `IMAGE`
and `SGM_VFI_MODEL`. The parser rejects unreviewed dynamic
registration, changes to the base/subclass relationship or mutations
beyond exactly these two inherited socket additions.

The same audit checks exact UI graph socket names/types, source
revision metadata, widget counts, model link ID 18 from loader
node 21 to segment node 22, and the segment image-output link ID 27.
It rejects changed or absent link records, reversed/missing source
bindings and incompatible output ports. It verifies no graph JSON
was modified and uploads only aggregate metadata, not model paths,
widget values or rewritten workflows.

A **successful** source-parity check is reported as
`SOURCE_INTERFACE_PARITY_ONLY_HOLD`: it establishes that these two
**SGM interfaces and reviewed connections** match the exact pinned
source. It does **not** establish that the nodes execute successfully,
that the SGM model checkpoint is available or legally usable, that
the model's CuPy/CUDA dependencies work, or that all other GIMM/SGM
graph connections and model semantics are compatible. Those gates
remain unresolved and the original graph remains unchanged.

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
