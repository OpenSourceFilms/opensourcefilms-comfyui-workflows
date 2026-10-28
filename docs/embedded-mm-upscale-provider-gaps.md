# Embedded group extension-provider provenance for mm_upscale

This is a **source-only, read-only discrepancy report**. It reconciles the four
embedded group definitions in
[`mm_upscale_video_workflow.json`](../workflows/commercial-compatible/mm_upscale_video_workflow.json)
with the *same workflow's* canonical [`DEPENDENCIES.lock`](../DEPENDENCIES.lock)
block. It does not install extensions, call any live ComfyUI instance, access
model weights or test whether groups execute.

Run without a GPU or network:

```bash
python scripts/audit_embedded_group_provider_dependencies.py --output /tmp/mm-upscale-provider-gaps.json
```

## Reconciled export metadata

The four UUID subgraphs contain **89 internal node instances**, **17 distinct
internal node type strings**, and these exported `properties.cnr_id` hints:

| Exported provider hint | Instances | Distinct internal classes | Corresponding manifest entry |
|---|---:|---:|---|
| `comfyui-custom-scripts` | 23 | 2 | Listed as `ComfyUI-Custom-Scripts (pysssss)`, but without a source commit pin |
| `comfyui-easy-use` | 42 | 8 | **Missing** `ComfyUI-Easy-Use` |
| `comfyui-kjnodes` | 7 | 3 | **Missing** `ComfyUI-KJNodes` |
| `comfyui_essentials` | 10 | 2 | **Missing** `ComfyUI_essentials` |
| `comfy-core` | 7 | 2 | Provided by ComfyUI core; separately qualified |

These are counts from the *graph's UI metadata*. Exported `ver` values vary
within some providers, for example Easy-Use includes `1.3.0`, `1.3.3`
and a commit-like string. Those are **not** a coherent installed-version
lockfile, and must never be treated as verified installed SHAs or licences.

The canonical `mm_upscale_video_workflow.json` block currently lists
Florence2, GGUF, UltimateSDUpscale, rgthree, Custom-Scripts and
VideoHelperSuite but **not** Easy-Use, KJNodes or Essentials. The repository's
[`THIRD_PARTY_LICENSES.md`](../THIRD_PARTY_LICENSES.md) separately mentions
these three packages, but that does not insert them into this workflow's
canonical dependency list or establish the versions required by its exported
groups. In particular, Easy-Use is noted as **unpinned** there. Read and
validate the exact upstream sources, licences, source commits, registered
node schemas, and possible nested dependencies before selecting an install.

The [dated candidate upstream source and licence review](mm-upscale-upstream-candidate-snapshot.md)
also identifies exact **candidate** Git commits and the source locations
of all 15 exported class names. Its CI preflight is read-only: those
revisions are not automatically added to the canonical manifest, installed
or qualified as runtime compatible.

## Acceptance boundary and resolution

The CI preflight detects missing provider declarations and unpinned declared
provider hints; it does **not automatically patch `DEPENDENCIES.lock`**.
Automatically adding dependencies would silently change the provenance and
commercial-use assessment of a conditionally compatible profile without
verifying licences and reproducibility. The appropriate follow-on is to
review a compatible exact revision and rights for each required provider,
then update the manifest *and* requalify the real embedded group behaviour.

The source-only audit also rejects internally contradictory class-to-provider
hints, malformed group IDs, or missing provider/version properties. Reports
contain only public class names, provider hints, counts, benign export-version
strings and the graph hash. No prompt text, widget values, media paths, private
files, binary artifacts or model checkpoints are included.

**Not accepted:** actual source/package installation, all group internals
registering, UI-to-API group conversion, graph execution, full 11-workflow
inference, GPU compatibility or commercial rights. Keep
[issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3)
open until these separate conditions are demonstrated.
