#!/usr/bin/env bash
# scripts/install-dependencies.sh - Install ComfyUI custom nodes required by
# the workflows in this repo. Does not vendor third-party code (clones
# pinned commits from upstream) and does not download model weights.
set -o pipefail

usage() {
    echo "Usage: $0 /path/to/ComfyUI" >&2
    exit 1
}

# Check arguments
if [ $# -ne 1 ]; then
    usage
fi
COMFYUI_DIR="$1"
if [ ! -d "$COMFYUI_DIR" ]; then
    echo "Error: ComfyUI directory not found: $COMFYUI_DIR" >&2
    usage
fi

CUSTOM_NODES_DIR="$COMFYUI_DIR/custom_nodes"
mkdir -p "$CUSTOM_NODES_DIR"

# Resolve repository root directory (since this script now lives in scripts/)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- package list: commercial-compatible dependencies ---
PACKAGES='ComfyUI-VideoHelperSuite|https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite|2984ec4c4b93292421888f38db74a5e8802a8ff8|all video workflows
rgthree-comfy|https://github.com/rgthree/rgthree-comfy|d92cad68a6e92a1c5d4032d3ac53f79ea44b08e4|several workflows (UI convenience nodes)
ComfyUI-KJNodes|https://github.com/kijai/ComfyUI-KJNodes|3f20054214fec9f9234fd3841ae6f1e4287948f6|matting/masking workflows
ComfyUI-SAM3|https://github.com/PozzettiAndrea/ComfyUI-SAM3|de0ff5d2c2ea435d29f800abfa568cffdfb94773|SAM3-based workflows
ComfyUI-Easy-Sam3|https://github.com/yolain/ComfyUI-Easy-Sam3|88fe578a1a5e03d95281197303d5d3a73fd5a089|VideoMaMa split workflow
ComfyUI-Easy-Use|https://github.com/yolain/ComfyUI-Easy-Use|main|VideoMaMa/EffectErase workflows (verify commit before use)
ComfyUI-Video-Reverse|https://github.com/Sean-Bradley/ComfyUI-Video-Reverse|main|verify commit before use
ComfyUI-Florence2|https://github.com/kijai/ComfyUI-Florence2|9ece3de914214c5f581d725167bc9d0eeb0d1120|upscale workflow
ComfyUI_essentials|https://github.com/cubiq/ComfyUI_essentials|9d9f4bedfc9f0321c19faf71855e228c93bd0dc9|upscale workflow
ComfyUI-GGUF|https://github.com/city96/ComfyUI-GGUF|6ea2651e7df66d7585f6ffee804b20e92fb38b8a|upscale workflow
ComfyUI_UltimateSDUpscale|https://github.com/ssitu/ComfyUI_UltimateSDUpscale|a5547db9e1d07d3318bb21e9e9c474f4c1e9c8df|upscale workflow
ComfyUI-GIMM-VFI|https://github.com/kijai/ComfyUI-GIMM-VFI|4c9a3123762af85e7c796e41737da0b70c75d72d|interpolation workflows
ComfyUI-Tween|https://github.com/Ethanfel/ComfyUI-Tween|91947c0b8c795cf504d3848274d4217f0432a324|interpolation workflows
ComfyUI-DownsampleFPS|https://github.com/Austat/ComfyUI-DownsampleFPS|4d741ef8e33b0c5111ad21033f9408acffc63651|interpolation workflows
ComfyUI-WanVideoWrapper|https://github.com/kijai/ComfyUI-WanVideoWrapper|088128b224242e110d3906c6750e9a3a348a659b|Wan video workflows
comfyui_controlnet_aux|https://github.com/Fannovel16/comfyui_controlnet_aux|main|optical-flow preprocessing (verify commit before use)
ComfyUI-RMBG|https://github.com/1038lab/ComfyUI-RMBG|main|matting workflows (verify commit before use)'

# --- package list: research-only / commercially-restricted dependencies ---
RESTRICTED_PACKAGES='BiM-VFI|https://github.com/KAIST-VICLab/BiM-VFI|df79cbcad4214d48911040def459174d0a4c9791|frame_interpolation_test.json, tween_interpolate_loop.json (research/education only - see THIRD_PARTY_LICENSES.md)
ComfyUI-VideoMaMa|https://github.com/okdalto/ComfyUI-VideoMaMa|main|videomama_*.json (CC-BY-NC-4.0 code + Stability AI Community License checkpoint - see THIRD_PARTY_LICENSES.md)'

FAILED_PACKAGES=""

install_pkg() {
    local name="$1" url="$2" ref="$3"
    local dest="$CUSTOM_NODES_DIR/$name"

    # A matching path may be a file or dangling symlink, not an installed
    # checkout. Never let a failed git clone trigger rm -rf on user-owned
    # content that existed before this invocation.
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        if [ -d "$dest" ]; then
            echo "skip $name (already present at $dest)"
            echo "WARNING: existing $name was not checked for Git origin, revision or node imports; verify it independently." >&2
            return 0
        fi
        echo "ERROR: cannot clone $name: destination already exists and is not a directory; preserving $dest" >&2
        FAILED_PACKAGES="$FAILED_PACKAGES $name"
        return 1
    fi

    echo "cloning $name from $url (ref $ref)..."
    git clone "$url" "$dest" || {
        echo "ERROR: failed to clone $name" >&2
        rm -rf "$dest"
        FAILED_PACKAGES="$FAILED_PACKAGES $name"
        return 1
    }
    ( cd "$dest" && git checkout "$ref" ) || {
        echo "ERROR: failed to checkout $ref for $name -- pin may be stale (tag/commit no longer exists upstream)." >&2
        # Don't leave a directory sitting on the wrong (default-branch) commit:
        # a bad checkout would otherwise look "already present" on the next run
        # and get silently skipped forever, masking the failure.
        rm -rf "$dest"
        FAILED_PACKAGES="$FAILED_PACKAGES $name"
        return 1
    }
}

echo "== commercial-compatible dependencies =="
while IFS='|' read -r name url ref used_by; do
    install_pkg "$name" "$url" "$ref"
done <<< "$PACKAGES"

echo ""
echo "== Open Source Films' own node (vendored in this repo) =="
dest_dir="$CUSTOM_NODES_DIR/mask_propagate_optical_flow"
if [ -e "$dest_dir" ] || [ -L "$dest_dir" ]; then
    echo "skip mask_propagate_optical_flow (already present at $dest_dir)"
else
    echo "copying mask_propagate_optical_flow (OSF, vendored in this repo)..."
    # Copy into a newly created sibling first. A failing cp must never leave
    # a partial directory that a later invocation silently treats as installed.
    staging_dir="$(mktemp -d "$CUSTOM_NODES_DIR/.mask_propagate_optical_flow.XXXXXXXX")" || {
        echo "ERROR: failed to stage mask_propagate_optical_flow" >&2
        FAILED_PACKAGES="$FAILED_PACKAGES mask_propagate_optical_flow"
        staging_dir=""
    }
    if [ -n "$staging_dir" ]; then
        if cp -r "$REPO_ROOT/custom_nodes/mask_propagate_optical_flow/." "$staging_dir/" &&
           mv -T -- "$staging_dir" "$dest_dir"; then
            echo "installed mask_propagate_optical_flow"
        else
            echo "ERROR: failed to install mask_propagate_optical_flow" >&2
            # Only remove our own mktemp-created staging directory.
            rm -rf -- "$staging_dir"
            FAILED_PACKAGES="$FAILED_PACKAGES mask_propagate_optical_flow"
        fi
    fi
fi

echo ""
echo "== research-only dependencies (only needed for workflows/research-only/*) =="
echo "(Set INSTALL_RESTRICTED=1 to install these.)"

if [ "${INSTALL_RESTRICTED}" = "1" ]; then
    while IFS='|' read -r name url ref used_by; do
        install_pkg "$name" "$url" "$ref"
    done <<< "$RESTRICTED_PACKAGES"
else
    while IFS='|' read -r name url ref used_by; do
        echo "(skipped) $name - $used_by"
    done <<< "$RESTRICTED_PACKAGES"
fi

echo ""
echo "============================================================================="
echo "REMINDER: This script does NOT install model weights for SAM 3, SCAIL-2/Wan, and (research-only) VideoMaMa/EffectErase workflows."
echo "         Please refer to each workflow's .md sidecar file and THIRD_PARTY_LICENSES.md for download instructions."
echo "============================================================================="
echo ""
echo "Restart ComfyUI after installing new custom nodes."

if [ -n "$FAILED_PACKAGES" ]; then
    echo ""
    echo "============================================================================="
    echo "FAILED to install:$FAILED_PACKAGES"
    echo "See the ERROR lines above. A pinned tag/commit may have gone stale upstream"
    echo "(this has happened before -- see DEPENDENCIES.lock / THIRD_PARTY_LICENSES.md"
    echo "and please report it). Re-run this script after the pin is fixed; nothing"
    echo "was left half-installed for the packages listed above."
    echo "============================================================================="
    exit 1
fi
