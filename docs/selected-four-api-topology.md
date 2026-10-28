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
