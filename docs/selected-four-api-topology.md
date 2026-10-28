# Selected four API workflow topology preflight

This source-only check covers the **four API-format exports** from the exact
eleven-workflow, conditionally commercial-compatible RunPod staging profile.
It complements, but does not replace, the existing UI graph validator,
embedded `mm_upscale` link audit and consolidated release HOLD.

Run:

```sh
python -B scripts/audit_selected_api_topology.py \
  --output /tmp/osf-selected-four-api-topology.json
```

## What is checked

The auditor reuses the **canonical**
`runpod/commercial-compatible/prepare.py` selection, including its
manifest, sidecars and baseline structural validation. It rejects any
unexpected change to the four API graph identities and requires every
API node to have a numeric, nonzero string key, a nonempty class ID
and a dictionary of inputs.

All **array-valued inputs** in these exact four reviewed API exports
are `[upstream_node_id, output_slot]` connections. The auditor now
requires **every such array** to contain exactly two items, a canonical
positive decimal producer ID and an integer (not boolean) output index.
An array with a string-valued index, float index, missing/extra entry,
noncanonical producer ID or literal-array shape is rejected rather than
silently omitted from the dependency graph. Any future workflow that
genuinely uses literal list inputs needs an explicit source-reviewed
exception before this strict four-export gate can admit it.

For every accepted link, the auditor rejects a missing source node,
negative output slot and self-reference. It constructs a directed
dependency graph and requires an acyclic topological ordering, so
indirect cyclic references also fail. Repeated references to the same
upstream node count as separate connected inputs while the dependency
graph uses unique directed pairs.

The current four approved API exports have **60 node instances** and
**82 link input references**. Their exact workflow source SHA-256 hashes,
per-graph node and edge counts, root-node counts and maximum dependency
depths enter a small, source-only JSON report in disposable CI scratch.
No prompt strings, widget values, model filenames, image/video sources
or private file paths are included.

The offline tests reject missing references, malformed array link
shapes, noninteger/boolean slots, bad producer and node IDs,
negative slots, empty classes, direct and indirect cycles, and
deceptive claims of model or workflow execution. The unchanged seven UI-format
exports remain handled by the separate UI/embedded-group audits.

## Live socket type reconciliation, without weights

The [isolated clean ComfyUI CPU job](../.github/workflows/verify-clean-cpu-runtime.yml)
also evaluates [`audit_selected_four_live_api_links.py`](../scripts/audit_selected_four_live_api_links.py)
against the **actual** `/object_info` registry on the pinned public
ComfyUI revision with its five approved, commit-pinned external packages.
It reads the original four selected API exports, comprising **60 nodes
and 82 link references**, without reading their prompt strings or
model filenames into the emitted report.

For each API link whose source and destination classes are registered,
it validates the **real output slot index**, destination input-field
presence, and type declarations. A source type that exactly matches
one of the target types counts as an exact registered socket match.
A `*` wildcard, dynamic/enum input, or source/destination class absent
from the live registry is **unverified**, not passed. A registered
source-output type incompatible with its destination socket is counted
and reported by *public class and field identifiers* as a blocker.
Malformed links, vanished output slots, duplicated or missing
destination sockets, and changed four-graph cardinality fail the
validation. The tests cover contradictory types, dynamic links,
uninstalled custom providers, wrong output slots, and bad graph
references.

The custom SAM3 probe intentionally depends on a separately sourced
`LoadSAM3Model`/`SAM3Segmentation` package that is **not** among the
five clean-runtime external packages. Its uninstalled provider links
must remain explicit, even when adjacent core nodes are registered.
The three public-native SAM3/SCAIL workflows are included in the same
audit so the existing source-derived native-node binding check gains
external and core *source-to-destination* socket evidence. No missing
provider is auto-installed and no weight is downloaded.

A positive live type match verifies only the metadata available
in that exact registry. It is **not** a full prompt validation:
runtime model objects, model licences, widget values, actual tensors,
special wildcard rules, native SAM3 tracking, SCAIL inference, or GPU
execution remain unqualified. None of the four graphs is submitted
to `/prompt` by this audit. The evidence records acceptance flags
as false even if every resolvable link has matching types.

## Important limits

**Passing topology does not mean an API workflow is executable.** This
check cannot establish that the upstream output slot exists, that the
linked output type matches the downstream input socket, that custom
node packages and exact models are installed, that live ComfyUI accepts
the graph, or that licensed weights and adequate GPUs are available.
It never imports nodes, sends a `/prompt` request or executes inference.

In particular, the selected `sam3_custompkg_probe` graph references
SAM3 custom package nodes whose exact installed provider still requires
separate acceptance. The model/GPU, commercial-rights, UI-to-API
conversion and end-to-end output-acceptance HOLD remains in
[the selected-eleven release gate](selected11-release-hold.md) and
[issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3).

This preflight's positive conclusion is only **referential integrity and
acyclic topology of the four unchanged API graph exports**.
