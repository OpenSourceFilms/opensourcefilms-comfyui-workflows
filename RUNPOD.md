# Running on RunPod

Open Source Films develops and runs these workflows on [RunPod](https://www.runpod.io/) GPU
pods. This is a **historical setup recipe**, not a currently accepted
fresh-pod installation or a guarantee that every graph will open and run.
The exact installed custom-node versions and model dependencies require
separate compatibility testing.

## Choosing a pod

**Base image/template:** choose a RunPod PyTorch or ComfyUI image suitable for
your GPU's CUDA architecture and the exact model/node versions you intend to
use. A CUDA-enabled image by itself does **not** establish compatibility.
This repository ships graphs and some custom-node pins, not a validated
container image or deployable RunPod template.

**GPU/VRAM, by workflow family** (from the README's own guidance):

| Workflow family | Comfortable on |
|---|---|
| SAM 3 segmentation, frame interpolation (GIMM-VFI/SGM-VFI/BiM-VFI), upscale | A single mid-range GPU (16-24GB class, e.g. RTX 4090) |
| Wan 2.2 14B (i2v/flf2v/fmlf2v/VACE v2v), SCAIL-2 | 24GB+ VRAM (e.g. RTX 4090/5090, L40S, A100 40GB+) |

These are guidelines, not measured minimums for every workflow — if you're near the edge, start
a pod, watch VRAM usage on a real run, and resize if needed rather than over-provisioning up front.

**Storage:** attach a RunPod Network Volume rather than relying on the pod's container disk.
Model weights for these workflows run from single-digit GB (interpolation) to tens of GB (Wan
14B, SCAIL-2, SAM 3) each, and a Network Volume survives pod termination — the container disk
does not. Size it for whichever workflow families you're actually installing weights for; there's
no fixed number that's honest for "all of them." This is recommended, not strictly required: for
a single short session where you don't mind re-downloading weights (or re-running the install
script) next time, the container disk alone works fine and it's one less thing to set up. It
matters once you're running pods repeatedly and don't want to re-download tens of GB of weights
each time.

## Setup

From a terminal on the pod:

```bash
# 1. Clone this repo
git clone https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows.git
cd opensourcefilms-comfyui-workflows

# 2. Legacy broad installer: includes nodes beyond the strict 11-workflow
#    profile, plus mutable main refs; review licences and exact revisions first.
./scripts/install-dependencies.sh /path/to/ComfyUI

# ...or use the wrapper, which finds a conventional ComfyUI path for you:
./scripts/setup-runpod.sh
```

To also install the dependencies needed for `workflows/research-only/*`:

```bash
INSTALL_RESTRICTED=1 ./scripts/install-dependencies.sh /path/to/ComfyUI
```

The historical upstream pins were compared against their sources twice: once while writing this document
(one pin, `ComfyUI-WanVideoWrapper`, had gone stale and was repinned to the last commit on its
default branch), and again on 2026-08-20, which caught five more stale tags
(`rgthree-comfy`, `ComfyUI-KJNodes`, `ComfyUI-SAM3`, `ComfyUI-Florence2`, `ComfyUI-GGUF`,
`ComfyUI_UltimateSDUpscale` — their upstream repos had dropped the tagged releases entirely, not
just moved them). All six are now pinned to commit SHAs instead of tags, matching the rest of
`DEPENDENCIES.lock`, since a commit can't go stale the way a mutable tag can. The install script
was also hardened at the same time: previously, a failed checkout (stale pin) left the custom-node
directory cloned-but-unpinned and the script still exited `0`, so a later re-run would silently
"skip" that node forever without ever getting the right commit. It now removes the bad clone and
exits non-zero with a clear summary if any pin fails to resolve — re-run the script after such a
failure is fixed rather than assuming a `0` exit meant everything installed correctly.

**Repeated installer runs:** running `install-dependencies.sh` again against
a `ComfyUI` directory skips existing `custom_nodes/<name>` directories.
This is not version verification or a safe upgrade mechanism. It does
*not* check whether an existing directory is actually at the pinned commit, though (that's only
enforced on first install); if you suspect drift, delete the specific `custom_nodes/<name>`
directory and re-run.

**Where custom nodes land, and the Network Volume:** `install-dependencies.sh` clones custom nodes
into `<ComfyUI dir>/custom_nodes/`, i.e. wherever your ComfyUI installation itself lives. If your
`ComfyUI` directory is on the pod's container disk rather than the Network Volume, the custom nodes
cloned into it are just as ephemeral as ComfyUI itself and would need to be
reinstalled after pod termination. Installer duration and compatibility are
not verified for a fresh 2026 environment. Put the whole `ComfyUI`
directory, not just a `models/` folder, on the Network Volume if you
want custom nodes to survive restarts too.

## Model weights

**Not installed by the script above, and not bundled in this repo.** Each workflow's `.md`
sidecar names the models it needs; [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)'s
"Models" table has the upstream project for each one and its licence/commercial-use verdict.
Download weights from those upstream sources yourself, place them where ComfyUI expects them
(`models/checkpoints/`, `models/sam3/`, etc., per the node package's own README), and store them
on your Network Volume so they persist across pod restarts.

## Running ComfyUI and opening a workflow

```bash
cd /path/to/ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

**Security:** this binds ComfyUI to all interfaces. Only use it behind
intentional access controls, such as authenticated ingress or a protected
private network; **do not expose an unauthenticated ComfyUI API to the
public internet**. If those controls are unavailable, use localhost binding
with a secure operator-controlled tunnel rather than the public proxy.

Use RunPod's exposed HTTP port (map/forward 8188, or whatever port your template exposes) to
reach the ComfyUI web UI. Once it's open: **Workflow → Open**, and pick a `.json` from
[`workflows/commercial-compatible/`](workflows/commercial-compatible/) or
[`workflows/research-only/`](workflows/research-only/) (only after an `INSTALL_RESTRICTED=1`
install and other separately required nodes/models — see [README.md](README.md)
for the commercial-use distinction between the two).

## What this is and isn't

This is a documented setup path, **not a current independently verified
clean-pod GPU acceptance test or a one-click deploy**. Repository-only
structural validation and historical upstream pin checks do not prove node
import compatibility, installed model rights or successful GPU inference.
The remaining genuine clean ComfyUI install test is tracked in
[issue #2](https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows/issues/2).

For a safer first publication target, the [strict 11-workflow RunPod staging
profile](runpod/commercial-compatible/README.md) packages only the
commercial-compatible JSON/sidecars. It is deliberately **not** a registered
RunPod template, Dockerfile, node installer or Hub listing. The older generic
installer above includes additional dependencies not required for that subset.
