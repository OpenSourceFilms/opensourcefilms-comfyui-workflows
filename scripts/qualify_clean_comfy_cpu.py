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


def ensure_loopback_object_info(document: object, expected: str) -> None:
    """Require actual ComfyUI node metadata, not merely HTTP status 200."""
    if not isinstance(document, dict) or expected not in document:
        raise ValueError("Required OSF node not registered: " + expected)
    entry = document[expected]
    if not isinstance(entry, dict):
        raise ValueError("Invalid ComfyUI object_info entry: " + expected)
    if entry.get("output") != ["MASK"] or not isinstance(entry.get("input"), dict):
        raise ValueError("OSF node has unexpected API schema: " + expected)


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
                return {"status": "registered", "classes": list(CLASSES)}
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
        "model_weights_installed": False,
        "third_party_custom_nodes_installed": False,
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
