# Running on RunPod

Open Source Films develops and runs these workflows on [RunPod](https://www.runpod.io/) GPU
pods. This document is the concrete path from a fresh pod to one of the workflows in this
repo open and running in ComfyUI.

## Choosing a pod

**Base image/template:** any RunPod pod template that gives you a CUDA-enabled PyTorch
environment works — RunPod's own official PyTorch template, or a community ComfyUI template
if you'd rather start from one with ComfyUI pre-installed. Nothing here depends on a specific
template; this repo brings the workflow graphs and custom-node pins, not a container image.

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
no fixed number that's honest for "all of them."

## Setup

From a terminal on the pod:

```bash
# 1. Clone this repo
git clone https://github.com/OpenSourceFilms/opensourcefilms-comfyui-workflows.git
cd opensourcefilms-comfyui-workflows

# 2. Point the installer at your ComfyUI installation and install pinned
#    custom-node dependencies (commercial-compatible workflows only by default)
./scripts/install-dependencies.sh /path/to/ComfyUI

# ...or use the wrapper, which finds a conventional ComfyUI path for you:
./scripts/setup-runpod.sh
```

To also install the dependencies needed for `workflows/research-only/*`:

```bash
INSTALL_RESTRICTED=1 ./scripts/install-dependencies.sh /path/to/ComfyUI
```

This step was re-verified against the live upstream repos while writing this document — one
pin (`ComfyUI-WanVideoWrapper`) had gone stale (its `v1.4.7` tag no longer exists upstream) and
has been repinned to the last commit on its default branch. The rest resolved cleanly.

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

Use RunPod's exposed HTTP port (map/forward 8188, or whatever port your template exposes) to
reach the ComfyUI web UI. Once it's open: **Workflow → Open**, and pick a `.json` from
[`workflows/commercial-compatible/`](workflows/commercial-compatible/) or
[`workflows/research-only/`](workflows/research-only/) (only after an `INSTALL_RESTRICTED=1`
install — see [README.md](README.md) for the commercial-use distinction between the two).

## What this is and isn't

This is a documented, verified "fresh pod → clone → install → open workflow" path, not a
one-click deploy. There's no Dockerfile, RunPod template definition, or Hub listing here yet —
those aren't necessary for the repo to be genuinely reproducible on RunPod today, and adding them
without a real use case behind them would just be unused surface area.
