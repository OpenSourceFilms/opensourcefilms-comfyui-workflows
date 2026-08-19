#!/usr/bin/env bash
# scripts/setup-runpod.sh - Turn a fresh RunPod ComfyUI pod into this repo's
# expected environment. Thin wrapper around install-dependencies.sh: finds a
# ComfyUI install at a conventional path if you don't name one, then prints
# what's left to do (model weights, launch) since neither is automated here.
# See RUNPOD.md for the full walkthrough.
set -o pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

COMFYUI_DIR="${1:-}"
if [ -z "$COMFYUI_DIR" ]; then
    for candidate in /workspace/ComfyUI /ComfyUI "$HOME/ComfyUI"; do
        if [ -d "$candidate" ]; then
            COMFYUI_DIR="$candidate"
            break
        fi
    done
fi

if [ -z "$COMFYUI_DIR" ] || [ ! -d "$COMFYUI_DIR" ]; then
    echo "Could not find a ComfyUI installation at any conventional path." >&2
    echo "Usage: $0 /path/to/ComfyUI" >&2
    exit 1
fi

echo "Using ComfyUI at: $COMFYUI_DIR"
echo ""

bash "$REPO_ROOT/scripts/install-dependencies.sh" "$COMFYUI_DIR" || exit 1

echo ""
echo "============================================================================="
echo "Next steps:"
echo "  1. Download the model weights you need -- see THIRD_PARTY_LICENSES.md's"
echo "     'Models' table for upstream sources. Nothing is fetched automatically."
echo "  2. Launch ComfyUI:"
echo "       cd \"$COMFYUI_DIR\" && python main.py --listen 0.0.0.0 --port 8188"
echo "  3. On RunPod, use the pod's exposed HTTP port to reach the web UI."
echo "  4. In ComfyUI: Workflow -> Open, and pick a .json from"
echo "       $REPO_ROOT/workflows/"
echo "============================================================================="
