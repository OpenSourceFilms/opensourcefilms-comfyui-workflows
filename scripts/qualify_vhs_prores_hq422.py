"""Disposable ProRes HQ 4:2:2 correction probe for pinned VideoHelperSuite.

The upstream ProRes profile=hq preset selects ProRes HQ (apch), but its
8-bit RGB24 source path can yield yuv444p10le. This probe keeps the
original preset intact and adds an explicitly forced yuv422p10le variant
in the disposable GitHub Actions runner only.

Both graphs use identical 8-bit red/blue synthetic source images. The
evidence qualifies only video storage profile/pixel format and decoded
8-bit RGB, NOT 10-bit source fidelity or a production deployment preset.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


FORMAT_NAME = "osf_ci_proreshq422"
EXPECTED_COLORS = ((255, 0, 0), (0, 0, 255))
FRAME_BYTES = 64 * 64 * 3
MAX_MOV_BYTES = 2_000_000


def prepare_disposable_hq422_preset(comfy: Path) -> dict:
    base = comfy / "custom_nodes" / "ComfyUI-VideoHelperSuite" / "video_formats"
    source = base / "ProRes.json"
    target = base / (FORMAT_NAME + ".json")
    if (base.is_symlink() or source.is_symlink() or not source.is_file()
            or target.is_symlink() or target.exists()):
        raise ValueError("Unsafe or missing ProRes source/preset path")
    raw = source.read_bytes()
    definition = json.loads(raw)
    if (not isinstance(definition, dict)
            or definition.get("extension") != "mov"
            or not isinstance(definition.get("main_pass"), list)
            or definition["main_pass"][:3] != ["-n", "-c:v", "prores_ks"]
            or "-pix_fmt" in [x for x in definition["main_pass"]
                               if isinstance(x, str)]
            or definition.get("extra_widgets") != [[
                "profile", ["lt", "standard", "hq", "4444", "4444xq"],
                {"default": "hq"},
            ]]):
        raise ValueError("Unreviewed upstream ProRes source or profile contract")
    clone = {
        **definition,
        "main_pass": [*definition["main_pass"], "-pix_fmt", "yuv422p10le"],
    }
    with target.open("x", encoding="utf-8") as f:
        json.dump(clone, f, sort_keys=True)
    if source.read_bytes() != raw:
        raise ValueError("Pinned ProRes source was altered")
    return {
        "upstream_source_sha256": hashlib.sha256(raw).hexdigest(),
        "ci_only_preset": FORMAT_NAME,
        "override": "append -pix_fmt yuv422p10le to ProRes main_pass",
        "upstream_source_unmodified": True,
        "on_disposable_runner_only": True,
    }


def build_hq422_probe_prompt() -> dict:
    common = {
        "images": ["3", 0],
        "frame_rate": 2,
        "loop_count": 0,
        "profile": "hq",
        "pingpong": False,
        "save_output": False,
    }
    return {
        "1": {"class_type": "EmptyImage", "inputs": {
            "width": 64, "height": 64, "batch_size": 1, "color": 0xFF0000,
        }},
        "2": {"class_type": "EmptyImage", "inputs": {
            "width": 64, "height": 64, "batch_size": 1, "color": 0x0000FF,
        }},
        "3": {"class_type": "ImageBatch", "inputs": {
            "image1": ["1", 0], "image2": ["2", 0],
        }},
        "4": {"class_type": "VHS_VideoCombine", "inputs": {
            **common, "format": "video/ProRes",
            "filename_prefix": "osf_ci_hq_original",
        }},
        "5": {"class_type": "VHS_VideoCombine", "inputs": {
            **common, "format": "video/" + FORMAT_NAME,
            "filename_prefix": "osf_ci_hq_explicit422",
        }},
    }


def _safe_temp_asset(value: object, expected_format: str) -> dict:
    if (not isinstance(value, dict)
            or value.get("format") != expected_format
            or value.get("type") != "temp"
            or value.get("subfolder") not in (None, "")):
        raise ValueError("Unexpected ProRes HQ temporary output metadata")
    name = value.get("filename")
    if (not isinstance(name, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,175}\.mov", name)
            is None):
        raise ValueError("Unsafe ProRes HQ output filename")
    return {"filename": name, "type": "temp", "subfolder": ""}


def validate_hq422_history(history: object, prompt_id: str) -> tuple[dict, dict]:
    if not isinstance(history, dict) or not isinstance(history.get(prompt_id), dict):
        raise ValueError("Missing ProRes HQ prompt history")
    record = history[prompt_id]
    status = record.get("status")
    if (not isinstance(status, dict)
            or status.get("completed") is not True
            or status.get("status_str") != "success"):
        raise ValueError("ProRes HQ graph did not complete successfully")
    outputs = record.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("Malformed ProRes HQ prompt outputs")
    selected = []
    for key, fmt in (("4", "video/ProRes"), ("5", "video/" + FORMAT_NAME)):
        item = outputs.get(key)
        files = item.get("gifs") if isinstance(item, dict) else None
        if not isinstance(files, list) or len(files) != 1:
            raise ValueError("Missing exactly one required ProRes HQ MOV")
        selected.append(_safe_temp_asset(files[0], fmt))
    if selected[0]["filename"] == selected[1]["filename"]:
        raise ValueError("ProRes HQ outputs reused a filename")
    return selected[0], selected[1]


def validate_hq_decoded_rgb(payload: bytes) -> dict:
    if len(payload) != 2 * FRAME_BYTES:
        raise ValueError("ProRes HQ decoded count or raster dimensions differ")
    errors = []
    frame_hashes = []
    for index, rgb in enumerate(EXPECTED_COLORS):
        data = payload[index * FRAME_BYTES:(index + 1) * FRAME_BYTES]
        error = max(
            max(abs(v - expected) for v in data[channel::3])
            for channel, expected in enumerate(rgb)
        )
        if error > 24:
            raise ValueError("ProRes HQ red/blue frame content differs")
        errors.append(error)
        frame_hashes.append(hashlib.sha256(data).hexdigest())
    return {
        "decoded_frames": 2,
        "decoded_dimensions": [64, 64],
        "source_colour_precision_bits": 8,
        "maximum_absolute_rgb_error_by_frame": errors,
        "maximum_permitted_rgb_error": 24,
        "frame_sha256": frame_hashes,
    }


def _fetch_temp_mov(port: int, metadata: dict) -> bytes:
    with urlopen(
        f"http://127.0.0.1:{port}/view?" + urlencode(metadata), timeout=10
    ) as response:
        if response.status != 200:
            raise RuntimeError("Synthetic ProRes HQ loopback fetch failed")
        raw = response.read(MAX_MOV_BYTES + 1)
    if not 12 <= len(raw) <= MAX_MOV_BYTES or raw[4:8] != b"ftyp":
        raise ValueError("Synthetic ProRes HQ MOV signature/size invalid")
    return raw


def _decode_hq_mov(port: int, metadata: dict, *, expected_pixel_format: str) -> dict:
    from imageio_ffmpeg import get_ffmpeg_exe

    raw = _fetch_temp_mov(port, metadata)
    with tempfile.TemporaryDirectory(prefix="osf_hq422_cpu_") as tmp:
        path = Path(tmp) / "source.mov"
        path.write_bytes(raw)
        cmd = [
            get_ffmpeg_exe(), "-hide_banner", "-nostdin", "-i", str(path),
            "-map", "0:v:0", "-vsync", "0", "-pix_fmt", "rgb24",
            "-f", "rawvideo", "pipe:1",
        ]
        process = subprocess.run(cmd, capture_output=True, timeout=30, check=True)
    stderr = process.stderr.decode("utf-8", "replace")
    descriptor = re.search(
        r"Video:\s+prores\s+\(HQ\)\s+\(apch\b[^\n]{0,190}",
        stderr, flags=re.IGNORECASE,
    )
    if descriptor is None:
        raise ValueError("ProRes HQ stream codec/profile identification failed")
    if not re.search(r"\b" + re.escape(expected_pixel_format) + r"\b", descriptor.group()):
        raise ValueError("ProRes HQ decoded pixel format differs from expected")
    return {
        **validate_hq_decoded_rgb(process.stdout),
        "codec": "prores",
        "profile": "HQ",
        "pixel_format": expected_pixel_format,
        "mov_sha256": hashlib.sha256(raw).hexdigest(),
        "mov_size_bytes": len(raw),
    }


def execute_disposable_vhs_hq422(port: int, child, timeout_seconds: int = 70) -> dict:
    req = Request(
        f"http://127.0.0.1:{port}/prompt",
        data=json.dumps({"prompt": build_hq422_probe_prompt()}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urlopen(req, timeout=12) as response:
        if response.status != 200:
            raise ValueError("ProRes HQ synthetic prompt was rejected")
        result = json.loads(response.read(100_000))
    prompt_id = result.get("prompt_id") if isinstance(result, dict) else None
    if not isinstance(prompt_id, str) or not 0 < len(prompt_id) <= 100:
        raise ValueError("Invalid ProRes HQ prompt ID")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("ComfyUI exited during ProRes HQ synthetic prompt")
        with urlopen(f"http://127.0.0.1:{port}/history/{prompt_id}",
                     timeout=8) as response:
            if response.status != 200:
                raise ValueError("ProRes HQ history request failed")
            history = json.loads(response.read(200_000))
        if isinstance(history, dict) and prompt_id in history:
            original, corrected = validate_hq422_history(history, prompt_id)
            stock = _decode_hq_mov(port, original,
                                   expected_pixel_format="yuv444p10le")
            variant = _decode_hq_mov(port, corrected,
                                     expected_pixel_format="yuv422p10le")
            return {
                "status": "disposable_prores_hq422_candidate_verified",
                "stock_hq": stock,
                "explicit_422_candidate": variant,
                "same_source_rgb": True,
                "candidate_only": True,
                "production_preset_modified": False,
                "high_bit_depth_source_fidelity_qualified": False,
                "binary_media_uploaded": False,
            }
        time.sleep(1)
    raise TimeoutError("ProRes HQ synthetic prompt did not finish")
