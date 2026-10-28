"""Model-free real ComfyUI/VHS 16-bit-input ProRes 4444 probe.

Uses CI-only test fixtures, never a production workflow or upstream preset.
"""
from __future__ import annotations

from array import array
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen


INPUT_LEVELS_12BIT = ((2038, 2043), (2048, 2053))
FRAME_DIMENSION = 64
FRAME_COUNT = 2
CHANNELS = 3
BYTES_PER_SAMPLE = 2
MAX_ERROR_RGB16 = 256
FORMAT_NAME = "video/osf-prores4444-rgb48-16bit"
SOURCE_CLASS = "OSF_CI_Precision12BitSource"


def make_ci_only_precision_graph() -> dict:
    return {
        "201": {"class_type": SOURCE_CLASS, "inputs": {}},
        "202": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["201", 0],
                "frame_rate": 2, "loop_count": 0,
                "filename_prefix": "osf_ci_12bit_vhs_probe",
                "format": FORMAT_NAME,
                "pingpong": False, "save_output": False,
            },
        },
    }


def _little_endian_u16(data: bytes) -> array:
    required = FRAME_COUNT * FRAME_DIMENSION * FRAME_DIMENSION * CHANNELS * BYTES_PER_SAMPLE
    if len(data) != required:
        raise ValueError("Precision VHS decoded frame count/dimensions differ")
    samples = array("H")
    samples.frombytes(data)
    if samples.itemsize != 2:
        raise RuntimeError("Host uint16 is not two bytes")
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def validate_vhs_16bit_rgb_roundtrip(decoded: bytes) -> dict:
    """Require sub-eight-bit input distinctions remain after real VHS encode."""
    samples = _little_endian_u16(decoded)
    sample_frame = FRAME_DIMENSION * FRAME_DIMENSION * CHANNELS
    max_by_frame = []
    frame_hashes = []
    retained = 0
    for frame, (left, right) in enumerate(INPUT_LEVELS_12BIT):
        max_error = 0
        base = frame * sample_frame
        if left >> 4 != right >> 4:
            raise ValueError("Synthetic inputs unexpectedly differ at 8-bit precision")
        for y in range(FRAME_DIMENSION):
            for x in range(FRAME_DIMENSION):
                src = left if x < 32 else right
                expected = int(src / 4095.0 * 65535.0 + .5)
                for channel in range(CHANNELS):
                    actual = samples[base + (y * FRAME_DIMENSION + x) * CHANNELS + channel]
                    err = abs(actual - expected)
                    if err > max_error:
                        max_error = err
                    if err > MAX_ERROR_RGB16:
                        raise ValueError("Precision VHS decoded RGB48 exceeded error limit")
        # Each selected sample pair is separated by 5/4095; collapse to an
        # 8-bit input branch must fail this ordered-distinction requirement.
        left_luma = samples[base + (16 * FRAME_DIMENSION + 16) * CHANNELS]
        right_luma = samples[base + (16 * FRAME_DIMENSION + 48) * CHANNELS]
        if right_luma <= left_luma:
            raise ValueError("Precision VHS lost a sub-8-bit component distinction")
        retained += 1
        frame_hashes.append(hashlib.sha256(
            decoded[frame * sample_frame * 2:(frame+1) * sample_frame * 2]
        ).hexdigest())
        max_by_frame.append(max_error)
    return {
        "status": "vhs_explicit_16bit_input_prores4444_roundtrip_verified",
        "source_precision_bits": 12,
        "source_node": SOURCE_CLASS,
        "format": FORMAT_NAME,
        "input_color_depth": "16bit",
        "raw_ffmpeg_input_pixel_format_from_pinned_branch": "rgb48",
        "decoded_pixel_format": "rgb48le",
        "source_levels_12bit": [list(x) for x in INPUT_LEVELS_12BIT],
        "sub_8bit_frame_distinctions_preserved": retained,
        "frames": FRAME_COUNT,
        "dimensions": [FRAME_DIMENSION, FRAME_DIMENSION],
        "max_error_rgb16_by_frame": max_by_frame,
        "max_allowed_error_rgb16": MAX_ERROR_RGB16,
        "decoded_sha256_by_frame": frame_hashes,
        "fixture_only_not_production_default": True,
        "binary_outputs_uploaded": False,
    }


def execute_vhs_16bit_precision_graph(port: int, child: subprocess.Popen,
                                      *, fetch_asset, timeout_seconds: int = 55) -> dict:
    """Send the real API graph and verify temporary MOV with FFmpeg RGB48."""
    from imageio_ffmpeg import get_ffmpeg_exe

    with urlopen(f"http://127.0.0.1:{port}/object_info/{SOURCE_CLASS}", timeout=8) as response:
        info = json.loads(response.read(100_000))
        if SOURCE_CLASS not in info:
            raise ValueError("CI-only high-precision source node was not registered")
    with urlopen("http://127.0.0.1:%d/object_info/VHS_VideoCombine" % port, timeout=8) as response:
        node_info = json.loads(response.read(300_000))
        formats = node_info["VHS_VideoCombine"]["input"]["required"]["format"][0]
        if FORMAT_NAME not in formats:
            raise ValueError("CI-only 16-bit VHS ProRes format was not discovered")

    req = Request(
        f"http://127.0.0.1:{port}/prompt",
        data=json.dumps({"prompt": make_ci_only_precision_graph()}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urlopen(req, timeout=12) as response:
        result = json.loads(response.read(80_000))
    ident = result.get("prompt_id")
    if not isinstance(ident, str) or len(ident) > 100:
        raise ValueError("No accepted ComfyUI precision prompt ID")
    end = time.monotonic() + timeout_seconds
    while time.monotonic() < end:
        if child.poll() is not None:
            raise RuntimeError("ComfyUI exited during precision graph")
        with urlopen(f"http://127.0.0.1:{port}/history/{ident}", timeout=10) as response:
            history = json.loads(response.read(150_000))
        if ident in history:
            entry = history[ident]
            if (entry.get("status", {}).get("completed") is not True
                    or entry.get("status", {}).get("status_str") != "success"):
                raise ValueError("Precision ComfyUI API graph failed")
            outputs = entry.get("outputs", {}).get("202", {}).get("gifs", [])
            if not isinstance(outputs, list) or len(outputs) != 1:
                raise ValueError("Precision ComfyUI graph did not emit one MOV")
            item = outputs[0]
            if item.get("format") != FORMAT_NAME:
                raise ValueError("Precision graph returned unexpected output format")
            raw = fetch_asset(port, item, "mov")
            if len(raw) < 12 or raw[4:8] != b"ftyp":
                raise ValueError("Precision ComfyUI output is not MOV")
            with tempfile.TemporaryDirectory(prefix="osf_ci_vhs_highbit_") as scratch:
                movie = Path(scratch) / "input_precision.mov"
                movie.write_bytes(raw)
                p = subprocess.run([
                    get_ffmpeg_exe(), "-hide_banner", "-nostdin", "-i", str(movie),
                    "-map", "0:v:0", "-vsync", "0", "-pix_fmt", "rgb48le",
                    "-f", "rawvideo", "pipe:1",
                ], capture_output=True, check=True, timeout=30)
            stderr = p.stderr.decode("utf-8", "replace")
            if (not re.search(r"Video:\s+prores\s+\(4444\)\s", stderr, re.I)
                    or not re.search(r"\byuv444p12le\b", stderr)):
                raise ValueError("Precision ComfyUI output codec/storage was not ProRes 4444")
            return {
                **validate_vhs_16bit_rgb_roundtrip(p.stdout),
                "codec": "prores",
                "profile": "4444",
                "storage_pixel_format": "yuv444p12le",
                "mov_size_bytes": len(raw),
                "mov_sha256": hashlib.sha256(raw).hexdigest(),
            }
        time.sleep(1)
    raise TimeoutError("Precision ComfyUI graph timed out")
