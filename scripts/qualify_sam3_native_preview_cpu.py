"""Native SAM3_TrackPreview CPU acceptance on synthetic prepacked track masks.

Executes pinned public ComfyUI's real SAM3 preview node, but NOT any SAM3
detection, video tracking, segmentation model, weights or GPU inference.
The only track input is the existing OSF disposable CI fixture.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen


SOURCE = "OSF_CI_SCAILTrack"
NATIVE = "SAM3_TrackPreview"
HEIGHT = WIDTH = 64
FPS = 2
FRAME_COUNT = 2
MAX_RGB_ERROR = 32
# Pinned core SAM3_TrackPreview.COLORS. Right identity is index 0.
EXPECTED_PROBES = (
    (0, 0, (0, 0, 0)),
    (32, 0, (0, 0, 0)),
    (63, 63, (0, 0, 0)),
    (12, 20, (255, 128, 13)),  # left identity, original track index 1
    (46, 20, (31, 120, 181)),  # right identity, original track index 0
)


def build_native_sam3_preview_prompt() -> dict:
    return {
        "1": {"class_type": SOURCE, "inputs": {}},
        "2": {"class_type": NATIVE, "inputs": {
            "track_data": ["1", 0], "opacity": 1.0, "fps": FPS,
        }},
    }


def validate_sam3_preview_history(history: object, prompt_id: str) -> dict:
    if not isinstance(history, dict):
        raise ValueError("Malformed native SAM3 preview history")
    entry = history.get(prompt_id)
    if not isinstance(entry, dict):
        raise ValueError("Missing native SAM3 preview history")
    status = entry.get("status")
    if (not isinstance(status, dict) or status.get("completed") is not True
            or status.get("status_str") != "success"):
        raise ValueError("Native SAM3 preview graph did not complete successfully")
    outputs = entry.get("outputs")
    result = outputs.get("2") if isinstance(outputs, dict) else None
    images = result.get("images") if isinstance(result, dict) else None
    if not isinstance(images, list) or len(images) != 1:
        raise ValueError("Expected one native SAM3 animated preview")
    item = images[0]
    if not isinstance(item, dict):
        raise ValueError("Malformed native SAM3 preview asset")
    filename = item.get("filename")
    if (not isinstance(filename, str)
            or re.fullmatch(r"sam3_track_preview_[a-f0-9]{8}\.mp4", filename) is None
            or item.get("type") != "temp"
            or item.get("subfolder") not in ("", None)):
        raise ValueError("Unsafe native SAM3 preview asset")
    if result.get("animated") not in ([True], (True,)):
        raise ValueError("Native SAM3 video preview not marked animated")
    return {"filename": filename, "subfolder": "", "type": "temp"}


def validate_sam3_preview_pixels(raw: bytes) -> dict:
    stride = HEIGHT * WIDTH * 3
    if len(raw) != FRAME_COUNT * stride:
        raise ValueError("SAM3 preview decoded frame count or size differs")
    hashes = []
    errors = []
    for frame_index in range(FRAME_COUNT):
        frame = raw[frame_index * stride:(frame_index + 1) * stride]
        frame_errors = []
        for x, y, expected in EXPECTED_PROBES:
            if frame_index == 1 and x in (12, 46):
                expected = (31, 120, 181) if x == 12 else (255, 128, 13)
            offset = (y * WIDTH + x) * 3
            observed = frame[offset:offset + 3]
            error = max(abs(value - target)
                        for value, target in zip(observed, expected))
            if error > MAX_RGB_ERROR:
                raise ValueError("SAM3 preview mask/background colour differs")
            frame_errors.append(error)
        errors.append(max(frame_errors))
        hashes.append(hashlib.sha256(frame).hexdigest())
    return {
        "status": "native_sam3_track_preview_cpu_executed",
        "native_class": NATIVE,
        "source": "synthetic_two_identity_crossing_bitpacked_track",
        "track_index_colours_preserved_after_crossing": True,
        "resolution": [WIDTH, HEIGHT],
        "frames": FRAME_COUNT,
        "fps_requested": FPS,
        "frame_sha256": hashes,
        "source_object_index_order": "right_then_left",
        "colour_probes_checked": FRAME_COUNT * len(EXPECTED_PROBES),
        "maximum_rgb_channel_error_by_frame": errors,
        "maximum_permitted_rgb_channel_error": MAX_RGB_ERROR,
        "real_sam3_detection_or_tracking_executed": False,
        "gpu_inference_executed": False,
        "video_binary_uploaded": False,
    }


def execute_sam3_trackpreview_cpu(port: int, child: subprocess.Popen,
                                 *, fetch_asset, timeout_seconds: int = 60) -> dict:
    """Execute real ComfyUI HTTP graph, decode its temp H264 using pinned FFmpeg."""
    from imageio_ffmpeg import get_ffmpeg_exe

    for name in (SOURCE, NATIVE):
        with urlopen(f"http://127.0.0.1:{port}/object_info/{name}", timeout=8) as resp:
            info = json.loads(resp.read(120_000))
        if not isinstance(info, dict) or name not in info:
            raise ValueError("Native SAM3 preview source or class not registered: " + name)
    req = Request(
        f"http://127.0.0.1:{port}/prompt",
        data=json.dumps({"prompt": build_native_sam3_preview_prompt()}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=12) as resp:
        answer = json.loads(resp.read(100_000))
    prompt_id = answer.get("prompt_id") if isinstance(answer, dict) else None
    if not isinstance(prompt_id, str) or not 1 <= len(prompt_id) <= 100:
        raise ValueError("Missing SAM3 preview prompt ID")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("ComfyUI exited before native SAM3 preview completed")
        with urlopen(f"http://127.0.0.1:{port}/history/{prompt_id}", timeout=8) as resp:
            history = json.loads(resp.read(160_000))
        if isinstance(history, dict) and prompt_id in history:
            item = validate_sam3_preview_history(history, prompt_id)
            data = fetch_asset(port, item, "mp4")
            if len(data) < 12 or data[4:8] != b"ftyp":
                raise ValueError("SAM3 preview is not an MP4 container")
            with tempfile.TemporaryDirectory(prefix="osf_sam3_preview_") as scratch:
                path = Path(scratch) / "native_track_preview.mp4"
                path.write_bytes(data)
                result = subprocess.run(
                    [get_ffmpeg_exe(), "-hide_banner", "-nostdin",
                     "-i", str(path), "-map", "0:v:0", "-vsync", "0",
                     "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
                    capture_output=True, check=True, timeout=30,
                )
                stream = result.stderr.decode("utf-8", "replace")
                if not re.search(r"Video:\s+h264\b", stream, re.I):
                    raise ValueError("Native SAM3 preview stream is not H264")
                return {
                    **validate_sam3_preview_pixels(result.stdout),
                    "codec": "h264",
                    "container": "mp4",
                    "encoded_size_bytes": len(data),
                    "encoded_sha256": hashlib.sha256(data).hexdigest(),
                }
        time.sleep(1)
    raise TimeoutError("Native SAM3 synthetic preview did not complete")
