"""Live model-free native SCAIL2ColoredMask CPU execution on synthetic tracks.

The pinned public ComfyUI SAM3/SCAIL node performs the rendering itself.
No SAM3 or Wan model weights, image inputs, GPU or production assets are used.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
import subprocess
import time
from urllib.request import Request, urlopen


SOURCE = "OSF_CI_SCAILTrack"
REFERENCE = "OSF_CI_SCAILReferenceMask"
NATIVE = "SCAIL2ColoredMask"
WIDTH = HEIGHT = 64
EXPECTED_COUNTS = {"4": 2, "5": 1, "7": 2, "8": 1}


def build_scail_cpu_prompt() -> dict:
    """Two native SCAIL output modes fed exactly the same synthetic identities."""
    def scail(replacement):
        return {
            "class_type": NATIVE,
            "inputs": {
                "driving_track_data": ["1", 0],
                "ref_track_data": ["2", 0],
                "object_indices": "",
                "sort_by": "left_to_right",
                "replacement_mode": replacement,
            },
        }

    return {
        "1": {"class_type": SOURCE, "inputs": {}},
        "2": {"class_type": REFERENCE, "inputs": {}},
        "3": scail(False),
        "4": {"class_type": "PreviewImage", "inputs": {"images": ["3", 0]}},
        "5": {"class_type": "PreviewImage", "inputs": {"images": ["3", 1]}},
        "6": scail(True),
        "7": {"class_type": "PreviewImage", "inputs": {"images": ["6", 0]}},
        "8": {"class_type": "PreviewImage", "inputs": {"images": ["6", 1]}},
    }


def validate_scail_history(history: object, prompt_id: str) -> dict:
    if not isinstance(history, dict):
        raise ValueError("Malformed SCAIL synthetic history")
    entry = history.get(prompt_id)
    if not isinstance(entry, dict):
        raise ValueError("Missing SCAIL synthetic history")
    status = entry.get("status")
    if (not isinstance(status, dict) or status.get("completed") is not True
            or status.get("status_str") != "success"):
        raise ValueError("Native SCAIL synthetic graph did not complete")
    outputs = entry.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("Native SCAIL output metadata missing")
    for node_id, count in EXPECTED_COUNTS.items():
        meta = outputs.get(node_id)
        images = meta.get("images") if isinstance(meta, dict) else None
        if not isinstance(images, list) or len(images) != count:
            raise ValueError("Native SCAIL output image count mismatch: " + node_id)
        for item in images:
            if not isinstance(item, dict):
                raise ValueError("Malformed native SCAIL preview item")
    return entry


def _expected_rgb(mode: str, category: str) -> bytes:
    """Expected full raster for native sort and animation/replacement modes."""
    if mode not in ("animation", "replacement") or category not in ("drive", "ref"):
        raise ValueError("Unrecognized SCAIL synthetic expectation")
    background = (
        (255, 255, 255)
        if (mode == "replacement") == (category == "drive")
        else (0, 0, 0)
    )
    if category == "ref":
        # Animation: white background. Replacement: black background.
        background = (255, 255, 255) if mode == "animation" else (0, 0, 0)
    data = bytearray()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            pixel = background
            if category == "drive":
                if 16 <= y < 48 and 8 <= x < 24:
                    pixel = (0, 0, 255)  # left sorted to palette[0] blue
                elif 16 <= y < 48 and 40 <= x < 56:
                    pixel = (255, 0, 0)  # right sorted to palette[1] red
            elif 24 <= y < 40 and 24 <= x < 40:
                pixel = (0, 0, 255)  # ref MASK is single blue identity
            data.extend(pixel)
    return bytes(data)


def inspect_scail_rasters(port: int, entry: dict, fetch_asset) -> dict:
    from PIL import Image

    specs = (
        ("4", "animation", "drive"),
        ("5", "animation", "ref"),
        ("7", "replacement", "drive"),
        ("8", "replacement", "ref"),
    )
    hashes = {}
    inspected = 0
    for node_id, mode, category in specs:
        expected = _expected_rgb(mode, category)
        images = entry["outputs"][node_id]["images"]
        seen = []
        for item in images:
            raw = fetch_asset(port, item, "png")
            with Image.open(BytesIO(raw)) as image:
                if image.format != "PNG" or image.size != (WIDTH, HEIGHT):
                    raise ValueError("Native SCAIL preview has invalid image format/size")
                actual = image.convert("RGB").tobytes()
            if actual != expected:
                raise ValueError(
                    "Native SCAIL output pixels differ: " + mode + " " + category
                )
            inspected += 1
            seen.append(hashlib.sha256(actual).hexdigest())
        hashes[mode + "_" + category] = seen
    return {
        "status": "native_scail_colored_masks_executed_on_cpu",
        "public_native_class": NATIVE,
        "models_used": False,
        "input_source": "synthetic_2identity_bitpacked_sam3_track_plus_plain_mask",
        "frames": 2,
        "resolution": [WIDTH, HEIGHT],
        "all_preview_pixels_verified": True,
        "left_identity_blue_right_identity_red": True,
        "animation_drive_background_black": True,
        "animation_reference_background_white": True,
        "replacement_drive_background_white": True,
        "replacement_reference_background_black": True,
        "preview_images_checked": inspected,
        "pixel_sha256": hashes,
        "media_uploaded": False,
        "sam3_tracking_executed": False,
        "wan_scail_inference_executed": False,
    }


def execute_scail_cpu_graph(port: int, child: subprocess.Popen, *,
                            fetch_asset, timeout_seconds: int = 55) -> dict:
    for cls in (SOURCE, REFERENCE, NATIVE):
        with urlopen(f"http://127.0.0.1:{port}/object_info/{cls}", timeout=8) as response:
            info = json.loads(response.read(100_000))
        if not isinstance(info, dict) or cls not in info:
            raise ValueError("Missing actual SCAIL CPU source/native node: " + cls)
    req = Request(
        f"http://127.0.0.1:{port}/prompt",
        data=json.dumps({"prompt": build_scail_cpu_prompt()}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urlopen(req, timeout=10) as response:
        data = json.loads(response.read(90_000))
    prompt_id = data.get("prompt_id") if isinstance(data, dict) else None
    if not isinstance(prompt_id, str) or not 1 <= len(prompt_id) <= 100:
        raise ValueError("SCAIL synthetic prompt ID missing")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("ComfyUI exited during SCAIL synthetic CPU execution")
        with urlopen(f"http://127.0.0.1:{port}/history/{prompt_id}", timeout=8) as response:
            history = json.loads(response.read(160_000))
        if isinstance(history, dict) and prompt_id in history:
            entry = validate_scail_history(history, prompt_id)
            return inspect_scail_rasters(port, entry, fetch_asset)
        time.sleep(1)
    raise TimeoutError("Native SCAIL synthetic CPU graph did not complete")
