# Restricted-scope RunPod preparation profile

This is a **repository-only staging profile**, not a registered RunPod
template, custom container image, ComfyUI installer or commercially licensed
model bundle. It deliberately exports **exactly 11** OSF workflow JSON files
and their rights sidecars from `workflows/commercial-compatible/`.

The selected workflow classification means **OSF has identified no blanket
noncommercial prohibition in the reviewed dependency chain**. It is **not**
a warranty of legal clearance. For example, Meta SAM 3 has its own **custom
SAM License**, distinct from MIT/Apache/GPL. Validate your exact weights,
dependency versions, model output use, attribution and redistribution rights
before using any workflow commercially.

## Start on RunPod

Bring your own ComfyUI installation on a RunPod pod with a suitable GPU and
storage. Choose its template/image deliberately using RunPod's current
documentation. This profile **does not** choose an image, open a network
port, create a pod, install software, download weights or modify an existing
ComfyUI tree.

```bash
# On your pod, or locally, clone source:
git clone https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows.git
cd opensourcefilms-comfyui-workflows

# Purely read-only validation:
python3 runpod/commercial-compatible/prepare.py

# Build a new, isolated bundle. The parent must already exist; destination
# must not exist. The script will never overwrite an earlier bundle.
mkdir -p /tmp/osf-runpod-review
python3 runpod/commercial-compatible/prepare.py \
  --stage /tmp/osf-runpod-review/commercial-11

# Recheck all copied files using a recorded SHA-256 inventory:
python3 runpod/commercial-compatible/prepare.py \
  --verify /tmp/osf-runpod-review/commercial-11
```

From ComfyUI's interface use **Workflow → Open** on one of the staged
`workflows/commercial-compatible/*.json` graphs. The JSON can be read before
its external custom nodes and model weights are installed; it cannot be
expected to **execute** until each required dependency is separately installed
and compatible.

### What the bundle includes

- Exactly 11 workflow graphs, chosen from an **explicit approved allowlist**
  and checked against the canonical `DEPENDENCIES.lock` statuses.
- Exactly 11 matching `.md` sidecars, with rights notes and model requirements.
- OSF's `LICENSE`, `THIRD_PARTY_LICENSES.md` and this preparation guide.
- `BUNDLE_MANIFEST.json` with graph names, dependency names and SHA-256 file
  hashes for inspection and accidental modification detection.

### What it **does not** include

- All five `workflows/research-only/` graphs, or their deployment targets.
- Any executable ComfyUI core, SCAIL-2 fork, custom nodes, dependencies,
  pretrained weights, datasets, footage or generated outputs.
- An installer, launcher, ComfyUI GPU inference or a RunPod API template ID.
- A cryptographic **signature**. File hashes detect inconsistency with the
  generated manifest, but a party who edits both manifest and files can
  regenerate matching hashes.

The existing `scripts/install-dependencies.sh` does **not** implement this
strict profile. Its legacy default group contains some nodes used only by
research workflows and multiple unpinned `main` references. **Do not run it
as part of this narrowly scoped preparation procedure.** Install only the
precise external packages actually required for the graphs you select,
after reviewing their pinned source commits and applicable rights. Some
workflow dependencies (including SCAIL-2 fork features and the upstream
`ComfyUI-Custom-Scripts`) have additional setup decisions not resolved by
this staging profile.

The workflow-by-workflow external dependency list is included in the
generated `BUNDLE_MANIFEST.json`, and full conditions are in
`THIRD_PARTY_LICENSES.md`. No network calls are made to verify upstream
pins; the profile checks internal repository **classification consistency**,
not external package availability or licence compliance.

## Verification status

The accompanying stdlib-only
[`tests/test_runpod_commercial_profile.py`](../../tests/test_runpod_commercial_profile.py)
checks selection, research-only exclusion, read-only mode, staging,
SHA-256 bundle verification and fail-closed scenarios without a GPU, model
download or external dependency. It is part of public CI.

**Not yet accepted:** a genuinely clean RunPod/ComfyUI installation,
node-import compatibility, model availability, inference results, image
quality or runtime performance. Those remain separate project acceptance
tasks; see [issues #2 and #1](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues).
