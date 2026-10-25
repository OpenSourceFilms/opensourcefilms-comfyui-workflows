# Validate exported ComfyUI workflow graphs offline

`scripts/validate-workflow-json.py` is a small standard-library-only check for
graph connectivity before installing model checkpoints or spending GPU time.
It handles both ComfyUI's editor/UI export (nodes and links) and API prompt
format (node IDs with class_type and inputs).

```bash
python3 scripts/validate-workflow-json.py workflows/
python3 -m unittest discover -s tests -p 'test_validate_workflow_json.py'
```

**What is checked:** JSON decoding, recognized export format, node identifiers,
duplicate or missing links, bad input/output slots and missing upstream API nodes.

**What is not checked:** installation or version of custom nodes, model availability
or licensing, tensor dimensions, correctness of runtime execution, temporal
coherence, provenance or visual quality. Static graph validity is not proof of
successful inference.

A workflow may reference a model that is licensed for research only. Always
consult the adjacent `.md` sidecar and `THIRD_PARTY_LICENSES.md`.
Do not publish actual production plates, actor likenesses, access tokens,
private storage locations or user-specific workflow metadata in examples.

A failed check produces JSON diagnostics and exit status 1. A structurally
valid graph exits 0. This tool reads its inputs only; it never executes a
workflow or writes output images.
