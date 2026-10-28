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

For UI-format graphs, use ComfyUI's **Workflow → Open** to select one of
the staged JSON files. **`sam3_custompkg_probe.json` is an API-prompt-format
file**, not a UI canvas graph, and may require submitting via ComfyUI's API
or conversion rather than opening with the normal canvas importer. The profile uses the repository's full offline UI/API **link validator**
before staging, then again while verifying the staged files. It rejects
dangling node references and malformed links rather than only checking for
a top-level `nodes` array or `class_type` field. Neither format can be
expected to **execute** until its required external custom nodes and model
weights are separately installed and compatible.

### What the bundle includes

- Exactly 11 workflow graphs, chosen from an **explicit approved allowlist**
  and checked against the canonical `DEPENDENCIES.lock` statuses.
- Exactly 11 matching `.md` sidecars, with rights notes and model requirements.
- OSF's `LICENSE`, `THIRD_PARTY_LICENSES.md` and this preparation guide.
- `DEPENDENCIES.selected.lock`: only the 11 selected blocks from the canonical
  `DEPENDENCIES.lock`, preserving original upstream revision pins, licences,
  distribution fields, and custom model terms; no five research-only blocks.
- `BUNDLE_MANIFEST.json` with graph names, detected UI-versus-API JSON
  formats, dependency names, the original full manifest SHA-256 and per-file
  SHA-256 hashes for consistency checks.

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

The restricted staging profile has **source-only structural, inventory,
hash and dependency-provenance checks**. It is not a clean RunPod GPU
installation, does not install weights and does not execute the eleven
selected workflows.

Separately, a fresh disposable GitHub-hosted **CPU** runner has successfully
installed pinned public ComfyUI and a limited set of pinned third-party
custom nodes, verified live node registration, executed synthetic
OSF/third-party CPU paths and checked generated PNG, GIF, H.264, HEVC
and ProRes results. There is also a separate genuine 12-bit direct-FFmpeg
ProRes roundtrip. See the [narrow CPU acceptance scope](../../docs/clean-cpu-runtime-qualification.md).
These tests are **not** evidence that the eleven selected workflows are
installable, inference-capable, GPU-qualified or rights-cleared. Their
individual source-only barriers are consolidated under the
[selected-eleven release HOLD](../../docs/selected11-release-hold.md).

Before testing on GPU, follow the [per-workflow GPU and model acceptance
protocol](../../docs/gpu-acceptance-protocol.md). It requires a registered
dedicated ComfyUI target, an approved project and GPU reservation,
exact reviewed provider/model revisions and rights, separate UI-to-API
conversion where needed, and per-workflow inference/output evidence.
A running GPU pod or an installed node family does not itself establish
any of these conditions.

**Current production decision: HOLD for all eleven.** Track model and
GPU admission in [issue #3](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/3)
and legacy installer compatibility in [issue #2](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/2).
