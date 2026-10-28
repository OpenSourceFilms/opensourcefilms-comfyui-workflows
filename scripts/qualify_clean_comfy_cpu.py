#!/usr/bin/env python3
"""One-shot, no-weight CPU acceptance for a disposable upstream ComfyUI checkout.

Requires installed ComfyUI requirements + torch/OpenCV. Starts a loopback-only
ComfyUI server, verifies OSF node registration, executes synthetic CPU inputs,
records metadata and tears down the server. Does NOT test pretrained models.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

COMFY_SHA = "08cf0284ff45723aa67841c80cabb0e3cb50c9d7"
CLASSES = ("MaskPropagateOpticalFlow", "MaskPropagateFromFlow")
# Pinned source was checked against the public DEPENDENCIES.lock. These are
# nodes shared by the selected 11-workflow profile, not model or graph tests.
EXTERNAL_NODE_PINS = {
    "ComfyUI-VideoHelperSuite": {
        "sha": "2984ec4c4b93292421888f38db74a5e8802a8ff8",
        "classes": ("VHS_VideoCombine",),
    },
    "rgthree-comfy": {
        "sha": "d92cad68a6e92a1c5d4032d3ac53f79ea44b08e4",
        "classes": ("Any Switch (rgthree)",),
    },
    "ComfyUI-DownsampleFPS": {
        "sha": "4d741ef8e33b0c5111ad21033f9408acffc63651",
        "classes": ("DownsampleFPSNode",),
    },
    "ComfyUI-GGUF": {
        "sha": "6ea2651e7df66d7585f6ffee804b20e92fb38b8a",
        "classes": ("UnetLoaderGGUF",),
    },
    "ComfyUI_UltimateSDUpscale": {
        "sha": "a5547db9e1d07d3318bb21e9e9c474f4c1e9c8df",
        "classes": ("UltimateSDUpscale",),
    },
}


def ensure_loopback_object_info(document: object, expected: str) -> None:
    """Require actual ComfyUI node metadata, not merely HTTP status 200."""
    if not isinstance(document, dict) or expected not in document:
        raise ValueError("Required OSF node not registered: " + expected)
    entry = document[expected]
    if not isinstance(entry, dict):
        raise ValueError("Invalid ComfyUI object_info entry: " + expected)
    if entry.get("output") != ["MASK"] or not isinstance(entry.get("input"), dict):
        raise ValueError("OSF node has unexpected API schema: " + expected)


def verify_external_node_sources(custom_nodes: Path) -> dict:
    """Fail closed on missing, symlinked or unexpected Git revisions."""
    versions = {}
    # Check *all* paths before running any Git command. A later symlink must
    # not cause earlier unreviewed directories to be inspected first.
    for name in EXTERNAL_NODE_PINS:
        package = custom_nodes / name
        if package.is_symlink() or not package.is_dir():
            raise ValueError("Missing or symlinked external custom node: " + name)
    for name, spec in EXTERNAL_NODE_PINS.items():
        package = custom_nodes / name
        result = subprocess.run(
            ["git", "-C", str(package), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=15, check=True,
        )
        found = result.stdout.strip()
        if found != spec["sha"]:
            raise ValueError("Unapproved external custom-node SHA: " + name)
        versions[name] = found
    return dict(sorted(versions.items()))


USDU_SUBMODULE_COMMIT = "2322caa480535b1011a1f9c18126d85ea444f146"
USDU_SUBMODULE_RELATIVE = "repositories/ultimate_sd_upscale"


def validate_usdu_gitlink(line: str) -> str:
    """Require the exact original source gitlink, not just a directory name."""
    expected = ("160000 commit " + USDU_SUBMODULE_COMMIT + "\t"
                + USDU_SUBMODULE_RELATIVE)
    if line.strip() != expected:
        raise ValueError("UltimateSDUpscale gitlink differs from reviewed submodule pin")
    return USDU_SUBMODULE_COMMIT


def verify_usdu_submodule(custom_nodes: Path) -> dict:
    parent = custom_nodes / "ComfyUI_UltimateSDUpscale"
    child = parent / USDU_SUBMODULE_RELATIVE
    if parent.is_symlink() or child.is_symlink() or not child.is_dir():
        raise ValueError("Missing/symlinked UltimateSDUpscale submodule")
    gitlink = subprocess.run(
        ["git", "-C", str(parent), "ls-tree", "HEAD", USDU_SUBMODULE_RELATIVE],
        check=True, capture_output=True, text=True, timeout=15,
    ).stdout
    validate_usdu_gitlink(gitlink)
    child_sha = subprocess.run(
        ["git", "-C", str(child), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, timeout=15,
    ).stdout.strip()
    if child_sha != USDU_SUBMODULE_COMMIT:
        raise ValueError("Unapproved UltimateSDUpscale nested revision")
    for part in ("LICENSE", "scripts/ultimate-upscale.py"):
        component = child / part
        if component.is_symlink() or not component.is_file() or component.stat().st_size == 0:
            raise ValueError("Missing UltimateSDUpscale pinned submodule component: " + part)
    return {
        "parent_commit": EXTERNAL_NODE_PINS["ComfyUI_UltimateSDUpscale"]["sha"],
        "submodule_commit": child_sha,
        "submodule_path": USDU_SUBMODULE_RELATIVE,
        "fallback_urlretrieve_blocked": True,
        "license": "GPL-3.0",
    }


def ensure_external_object_info(document: dict, expected: dict) -> dict:
    """Require each actual pinned-package class in live ComfyUI registry."""
    found = {}
    for package, spec in expected.items():
        names = []
        for name in spec["classes"]:
            entry = document.get(name)
            if not isinstance(entry, dict):
                raise ValueError("Missing external ComfyUI class: " + name)
            if (not isinstance(entry.get("input"), dict)
                    or not isinstance(entry.get("output"), list)):
                raise ValueError("Invalid external ComfyUI class API: " + name)
            names.append(name)
        found[package] = names
    return found


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _probe_server(port: int, child: subprocess.Popen, *, seconds: int = 120) -> dict:
    end = time.monotonic() + seconds
    last_reason = "not started"
    while time.monotonic() < end:
        if child.poll() is not None:
            raise RuntimeError("ComfyUI process exited before node discovery")
        try:
            with urlopen(f"http://127.0.0.1:{port}/object_info", timeout=4) as resp:
                if resp.status != 200:
                    raise ValueError("ComfyUI object_info HTTP status not 200")
                data = resp.read(2_500_000)
                if len(data) >= 2_500_000:
                    raise ValueError("ComfyUI node inventory exceeds size limit")
                info = json.loads(data)
                for name in CLASSES:
                    ensure_loopback_object_info(info, name)
                external = ensure_external_object_info(info, EXTERNAL_NODE_PINS)
                return {
                    "status": "registered",
                    "classes": list(CLASSES),
                    "external_classes": external,
                }
        except (URLError, HTTPError, OSError, ValueError, TimeoutError) as exc:
            last_reason = type(exc).__name__
        time.sleep(2)
    raise TimeoutError("ComfyUI did not register expected nodes: " + last_reason)


def _load_osf_classes(path: Path):
    module_file = path / "__init__.py"
    if not module_file.is_file() or module_file.is_symlink():
        raise ValueError("Missing or symlinked OSF custom-node package")
    spec = importlib.util.spec_from_file_location(
        "osf_fresh_node", module_file, submodule_search_locations=[str(path)]
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load isolated OSF node package")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS


def execute_synthetic(node_directory: Path) -> dict:
    import cv2
    import numpy as np
    import torch

    classes = _load_osf_classes(node_directory)
    if not set(CLASSES).issubset(classes):
        raise RuntimeError("OSF source lacks its two declared nodes")
    image = torch.zeros((3, 48, 48, 3), dtype=torch.float32)
    image[:, 9:33, 9:33, :] = 0.7
    init_mask = torch.zeros((48, 48), dtype=torch.float32)
    init_mask[15:27, 15:27] = 1.0
    zero_flow = torch.zeros((2, 48, 48, 2), dtype=torch.float32)
    propagated, = classes["MaskPropagateFromFlow"]().propagate_from_flow(
        zero_flow, init_mask, threshold=0.5, blur_radius=0
    )
    if tuple(propagated.shape) != (3, 48, 48):
        raise RuntimeError("FromFlow returned incorrect shape")
    if not torch.equal(propagated[0], propagated[1]) or not torch.equal(
        propagated[1], propagated[2]
    ):
        raise RuntimeError("Zero-motion synthetic mask changed between frames")
    estimated, = classes["MaskPropagateOpticalFlow"]().propagate(
        image, init_mask, threshold=0.5, blur_radius=0
    )
    if tuple(estimated.shape) != (3, 48, 48):
        raise RuntimeError("Farneback returned incorrect batch shape")
    if not torch.equal(estimated[0], init_mask):
        raise RuntimeError("Farneback initial mask not preserved")
    if not torch.isfinite(estimated).all():
        raise RuntimeError("Farneback produced nonfinite values")
    return {
        "status": "synthetic_cpu_execution_passed",
        "results": {
            "MaskPropagateFromFlow": {"frames": 3, "zero_flow_identical": True,
                "result_sha256": _sha(propagated.numpy().tobytes())},
            "MaskPropagateOpticalFlow": {"frames": 3, "initial_frame_preserved": True,
                "result_sha256": _sha(estimated.numpy().tobytes())},
        },
        "versions": {
            "torch": torch.__version__,
            "numpy": np.__version__,
            "opencv": cv2.__version__,
        },
        "device": "cpu",
    }


def execute_downsample_fps_synthetic(node_directory: Path) -> dict:
    """Execute the real upstream CPU frame-drop node, without model weights."""
    import torch

    package = _load_osf_classes(node_directory)
    node_type = package.get("DownsampleFPSNode")
    if node_type is None:
        raise RuntimeError("Pinned DownsampleFPS source lacks its registered node")
    # Fixed exactly-representable values ensure deterministic 8-to-4 indexing.
    frames = torch.zeros((8, 16, 16, 3), dtype=torch.float32)
    for i in range(8):
        frames[i, :, :, :] = float(i) / 8.0
    downsampled, = node_type().downsample(
        frames, input_fps=8, target_fps=4, method="Frame dropping", cpu_threads="1"
    )
    expected = frames[::2]
    if (tuple(downsampled.shape) != (4, 16, 16, 3)
            or not torch.isfinite(downsampled).all()
            or not torch.allclose(downsampled, expected, atol=1 / 255, rtol=0)):
        raise RuntimeError("Pinned DownsampleFPS synthetic output differs from expected")
    return {
        "node": "DownsampleFPSNode",
        "method": "Frame dropping",
        "source_frames": 8,
        "result_frames": 4,
        "status": "synthetic_cpu_execution_passed",
        "result_sha256": _sha(downsampled.numpy().tobytes()),
    }


def qualify(comfy: Path, report: Path, port: int) -> dict:
    comfy = comfy.resolve(strict=True)
    package = comfy / "custom_nodes" / "mask_propagate_optical_flow"
    if not (comfy / "main.py").is_file() or not package.is_dir():
        raise ValueError("No isolated ComfyUI root with OSF optical flow package")
    version = subprocess.run(
        ["git", "-C", str(comfy), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, timeout=15,
    ).stdout.strip()
    if version != COMFY_SHA:
        raise ValueError("Unreviewed ComfyUI source SHA")
    external_versions = verify_external_node_sources(comfy / "custom_nodes")
    usdu_submodule = verify_usdu_submodule(comfy / "custom_nodes")
    guard = Path(__file__).resolve().parent / "usdu_offline_guard"
    if (guard.is_symlink() or not (guard / "sitecustomize.py").is_file()
            or (guard / "sitecustomize.py").is_symlink()):
        raise ValueError("Fail-closed URL download guard missing")
    report = Path(report)
    if report.exists() or report.is_symlink():
        raise FileExistsError("Will not overwrite prior acceptance evidence")
    with tempfile.TemporaryDirectory(prefix="osf_cpu_qualification_") as scratch:
        scratch = Path(scratch)
        # Keep server workspace in its disposable checkout. Setting an
        # alternate ComfyUI base would also change custom-node search paths.
        env = os.environ.copy()
        env.update({
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
            "CUDA_VISIBLE_DEVICES": "", "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": str(guard) + os.pathsep + env.get("PYTHONPATH", ""),
        })
        cmd = [
            sys.executable, "main.py", "--cpu", "--offline",
            "--listen", "127.0.0.1", "--port", str(port),
        ]
        log_path = scratch / "startup.log"
        with log_path.open("w+", encoding="utf-8") as log:
            child = subprocess.Popen(
                cmd, cwd=comfy, env=env, stdout=log, stderr=subprocess.STDOUT
            )
            try:
                registration = _probe_server(port, child)
                synthetic = execute_synthetic(package)
                downsample = execute_downsample_fps_synthetic(
                    comfy / "custom_nodes" / "ComfyUI-DownsampleFPS"
                )
            except Exception as exc:
                log.flush()
                log.seek(0)
                output = log.read()[-6000:]
                print("Runtime smoke failure: " + type(exc).__name__, file=sys.stderr)
                # Log is from the disposable CI process; do not emit its paths,
                # environment or full output into public CI.
                print("Startup log contains " + str(len(output)) + " tail characters",
                      file=sys.stderr)
                raise
            finally:
                child.terminate()
                try:
                    child.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=8)
    result = {
        "schema": "osf-comfy-cpu-runtime-smoke-v1",
        "osf_repo_commit": os.environ.get("GITHUB_SHA"),
        "upstream_comfyui_commit": version,
        "runtime": "isolated_github_actions_ubuntu_cpu_only",
        "registration": registration,
        "synthetic_execution": synthetic,
        "external_synthetic_execution": downsample,
        "model_weights_installed": False,
        "third_party_custom_nodes_installed": True,
        "third_party_source_commits": external_versions,
        "pinned_usdu_submodule": usdu_submodule,
        "third_party_nodes_imported": registration["external_classes"],
        "third_party_graphs_executed": False,
        "gpu_or_model_inference_qualified": False,
        "eleven_workflows_qualified": False,
    }
    with report.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    return result


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--comfy-root", type=Path, required=True)
    cli.add_argument("--report", type=Path, required=True)
    cli.add_argument("--port", type=int, default=18188)
    args = cli.parse_args()
    if not 1024 <= args.port <= 65535:
        cli.error("Unsupported port")
    result = qualify(args.comfy_root, args.report, args.port)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
