"""Disposable VHS ProRes 4444 RGB-channel sub-8-bit detail acceptance.

Three test-only float32 ComfyUI IMAGE frames vary red, green and blue
independently by eight 12-bit code levels, values that collapse in VHS's
default RGB24 input. The opt-in RGB48 path must preserve differences in
the appropriate decoded ProRes YUV444 component (V, Y and U respectively).

This is not a calibrated colour-conversion, source-component accuracy,
HDR, or camera-input acceptance test. No private media or model weights.
"""
from __future__ import annotations

from array import array
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen

from qualify_vhs_16bit import (
    FORMAT_NAME,
    FULL_INTERIOR_OFFSETS,
    _read_mov,
    validate_precision_history,
)


FRAMES = 3
WIDTH = HEIGHT = 64
PIXELS = WIDTH * HEIGHT
COMPONENTS_PER_FRAME = 3 * PIXELS
EXPECTED_BYTES = FRAMES * COMPONENTS_PER_FRAME * 2
# Frame R -> V, frame G -> luma Y, frame B -> U.
PROBED_YUV_PLANES = (2, 0, 1)
# All 16x16 central tile pixels in each of the 3 RGB-channel source frames.
GRID_PAIR_COUNT = FRAMES * len(FULL_INTERIOR_OFFSETS) ** 2
MAX_FINE_DETAIL_DELTA = 32


def build_chroma_precision_prompt() -> dict:
    common = {
        "images": ["1", 0],
        "frame_rate": 2,
        "loop_count": 0,
        "profile": "4444",
        "pingpong": False,
        "save_output": False,
    }
    return {
        "1": {"class_type": "OSFTestChromaPrecisionFrames", "inputs": {}},
        "2": {"class_type": "VHS_VideoCombine", "inputs": {
            **common, "format": "video/ProRes",
            "filename_prefix": "osf_ci_rgb_default8",
        }},
        "3": {"class_type": "VHS_VideoCombine", "inputs": {
            **common, "format": "video/" + FORMAT_NAME,
            "filename_prefix": "osf_ci_rgb_optin16",
        }},
    }


def _decode_three_frame_mov(data: bytes) -> tuple[array, dict]:
    from imageio_ffmpeg import get_ffmpeg_exe

    with tempfile.TemporaryDirectory(prefix="osf_vhs_rgb_") as temp:
        path = Path(temp) / "rgb_chroma.mov"
        path.write_bytes(data)
        process = subprocess.run(
            [get_ffmpeg_exe(), "-hide_banner", "-nostdin",
             "-i", str(path), "-map", "0:v:0", "-fps_mode", "passthrough",
             "-pix_fmt", "yuv444p12le", "-f", "rawvideo", "pipe:1"],
            capture_output=True, timeout=30, check=True,
        )
    stream = process.stderr.decode("utf-8", "replace")
    if (not re.search(r"Video:\s+prores\s+\(4444\)\s", stream, re.I)
            or not re.search(r"\byuv444p12le\b", stream)):
        raise ValueError("VHS RGB precision MOV is not ProRes 4444 12-bit")
    if len(process.stdout) != EXPECTED_BYTES:
        raise ValueError("VHS RGB precision decoded wrong frame count or size")
    samples = array("H")
    samples.frombytes(process.stdout)
    if samples.itemsize != 2:
        raise RuntimeError("Unexpected uint16 representation")
    if sys.byteorder != "little":
        samples.byteswap()
    if len(samples) != FRAMES * COMPONENTS_PER_FRAME or any(v > 4095 for v in samples):
        raise ValueError("Invalid 12-bit RGB precision decoded values")
    return samples, {
        "encoded_mov_sha256": hashlib.sha256(data).hexdigest(),
        "encoded_mov_size_bytes": len(data),
    }


def _grid_pairs_in_target_planes(samples: array) -> list[tuple[int, int]]:
    if len(samples) != FRAMES * COMPONENTS_PER_FRAME:
        raise ValueError("RGB precision decoded sample count incorrect")
    result = []
    for frame, plane in enumerate(PROBED_YUV_PLANES):
        base = frame * COMPONENTS_PER_FRAME + plane * PIXELS
        for dy in FULL_INTERIOR_OFFSETS:
            for dx in FULL_INTERIOR_OFFSETS:
                row = base + dy * WIDTH
                result.append((samples[row + dx], samples[row + 32 + dx]))
    return result


def verify_rgb_chroma_detail(default8: array, optin16: array) -> dict:
    control = _grid_pairs_in_target_planes(default8)
    precise = _grid_pairs_in_target_planes(optin16)
    if len(control) != GRID_PAIR_COUNT or len(precise) != GRID_PAIR_COUNT:
        raise ValueError("RGB precision grid comparisons incomplete")
    if any(left != right for left, right in control):
        raise ValueError("VHS default 8-bit RGB control retained unexpected fine detail")
    deltas = [right - left for left, right in precise]
    if any(not 1 <= diff <= MAX_FINE_DETAIL_DELTA for diff in deltas):
        raise ValueError("VHS opt-in RGB48 lost or reversed chroma/luma fine detail")
    channel_ranges = []
    points_per_frame = len(FULL_INTERIOR_OFFSETS) ** 2
    for frame, channel in enumerate(("R", "G", "B")):
        frame_deltas = deltas[frame * points_per_frame:(frame + 1) * points_per_frame]
        channel_ranges.append({
            "source_rgb_component": channel,
            "decoded_yuv_component": ("V", "Y", "U")[frame],
            "minimum_positive_difference_12bit": min(frame_deltas),
            "maximum_positive_difference_12bit": max(frame_deltas),
            "verified_interior_pairs": len(frame_deltas),
        })
    return {
        "status": "vhs_16bit_rgb_channel_fine_detail_preserved",
        "source": "three float32 IMAGE frames, each one RGB channel +8/4095",
        "default_input_path": "rgb24",
        "optin_input_path": "rgb48",
        "codec": "prores_ks",
        "profile": "4444",
        "storage_format": "yuv444p12le",
        "frames": FRAMES,
        "dimensions": [WIDTH, HEIGHT],
        "source_rgb_channels_checked": 3,
        "control_collapsed_pairs": len(control),
        "optin_preserved_pairs": len(precise),
        "grid_offsets": list(FULL_INTERIOR_OFFSETS),
        "test_region": "central_16x16_interior_pixels_per_source_RGB_channel",
        "per_channel_grid_results": channel_ranges,
        "max_permitted_positive_difference_12bit": MAX_FINE_DETAIL_DELTA,
        "rgb_source_component_accuracy_qualified": False,
        "hdr_transfer_function_qualified": False,
        "binary_outputs_uploaded": False,
    }


def execute_disposable_vhs_rgb_precision(port: int, child,
                                          timeout_seconds: int = 70) -> dict:
    graph = build_chroma_precision_prompt()
    request = Request(
        "http://127.0.0.1:" + str(port) + "/prompt",
        data=json.dumps({"prompt": graph}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=12) as response:
        if response.status != 200:
            raise ValueError("ComfyUI rejected RGB-channel precision graph")
        data = json.loads(response.read(100_000))
    ident = data.get("prompt_id") if isinstance(data, dict) else None
    if not isinstance(ident, str) or not ident or len(ident) > 100:
        raise ValueError("Invalid RGB-channel precision prompt ID")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("ComfyUI exited before RGB precision graph completed")
        with urlopen("http://127.0.0.1:" + str(port) + "/history/" + ident,
                     timeout=8) as response:
            if response.status != 200:
                raise RuntimeError("Invalid RGB precision history HTTP status")
            history = json.loads(response.read(200_000))
        if isinstance(history, dict) and ident in history:
            control, optin = validate_precision_history(history, ident)
            a, meta_a = _decode_three_frame_mov(_read_mov(port, control))
            b, meta_b = _decode_three_frame_mov(_read_mov(port, optin))
            return {
                **verify_rgb_chroma_detail(a, b),
                "default8_mov": meta_a,
                "optin16_mov": meta_b,
            }
        time.sleep(1)
    raise TimeoutError("VHS RGB precision graph exceeded bounded timeout")
