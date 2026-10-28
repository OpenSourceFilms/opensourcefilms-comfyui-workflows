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
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from io import BytesIO
import re

COMFY_SHA = "08cf0284ff45723aa67841c80cabb0e3cb50c9d7"
CLASSES = ("MaskPropagateOpticalFlow", "MaskPropagateFromFlow")
# Pinned source was checked against the public DEPENDENCIES.lock. These are
# nodes shared by the selected 11-workflow profile, not model or graph tests.
EXTERNAL_NODE_PINS = {
    "ComfyUI-VideoHelperSuite": {
        "sha": "2984ec4c4b93292421888f38db74a5e8802a8ff8",
        "classes": ("VHS_VideoCombine", "VHS_SelectEveryNthImage"),
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


EXPECTED_RGB = ((255, 0, 0), (0, 0, 255))
RASTER_LIMIT = 2_000_000


def build_model_free_external_prompt() -> dict:
    """Four distinct colours, VHS selection, rgthree, GIF, H.264, HEVC and ProRes.

    All image content is authored by native EmptyImage; no file inputs,
    model loaders, private media or user-supplied prompt fields.
    """
    colors = (0xFF0000, 0x00FF00, 0x0000FF, 0xFFFF00)
    graph = {
        str(i): {"class_type": "EmptyImage", "inputs": {
            "width": 64, "height": 64, "batch_size": 1, "color": color,
        }}
        for i, color in enumerate(colors, start=1)
    }
    graph.update({
        "5": {"class_type": "ImageBatch", "inputs": {
            "image1": ["1", 0], "image2": ["2", 0],
        }},
        "6": {"class_type": "ImageBatch", "inputs": {
            "image1": ["5", 0], "image2": ["3", 0],
        }},
        "7": {"class_type": "ImageBatch", "inputs": {
            "image1": ["6", 0], "image2": ["4", 0],
        }},
        "8": {"class_type": "VHS_SelectEveryNthImage", "inputs": {
            "images": ["7", 0], "select_every_nth": 2,
            "skip_first_images": 0,
        }},
        "9": {"class_type": "Any Switch (rgthree)", "inputs": {
            "any_01": ["8", 0],
        }},
        "10": {"class_type": "PreviewImage", "inputs": {
            "images": ["9", 0],
        }},
        "11": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["9", 0],
            "frame_rate": 2,
            "loop_count": 0,
            "filename_prefix": "osf_synthetic_vhs_gif",
            "format": "image/gif",
            "pingpong": False,
            "save_output": False,
        }},
        "12": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["9", 0],
            "frame_rate": 2,
            "loop_count": 0,
            "filename_prefix": "osf_synthetic_vhs_h264",
            "format": "video/h264-mp4",
            "pix_fmt": "yuv420p",
            "crf": 0,
            "pingpong": False,
            "save_output": False,
        }},
        "13": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["9", 0],
            "frame_rate": 2,
            "loop_count": 0,
            "filename_prefix": "osf_synthetic_vhs_hevc",
            "format": "video/h265-mp4",
            "pix_fmt": "yuv420p",
            "crf": 0,
            "pingpong": False,
            "save_output": False,
        }},
        "14": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["9", 0],
            "frame_rate": 2,
            "loop_count": 0,
            "filename_prefix": "osf_synthetic_vhs_prores",
            "format": "video/ProRes",
            "profile": "hq",
            "pingpong": False,
            "save_output": False,
        }},
    })
    return graph


def _validated_temp_asset(entry: object, extension: str) -> dict:
    if not isinstance(entry, dict):
        raise ValueError("Malformed ComfyUI temporary asset metadata")
    name = entry.get("filename")
    if (not isinstance(name, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,179}\." + extension, name)
            is None or entry.get("type") != "temp"
            or entry.get("subfolder") not in ("", None)):
        raise ValueError("Unsafe or unexpected temporary ComfyUI asset")
    return {"filename": name, "type": "temp", "subfolder": ""}


def validate_model_free_external_history(history: object, prompt_id: str) -> dict:
    """Reject incomplete graphs, missing previews and missing GIF output."""
    if not isinstance(history, dict):
        raise ValueError("Malformed ComfyUI history")
    record = history.get(prompt_id)
    if not isinstance(record, dict):
        raise ValueError("Missing external synthetic prompt history")
    state = record.get("status", {})
    if (not isinstance(state, dict) or state.get("completed") is not True
            or state.get("status_str") != "success"):
        raise ValueError("External synthetic prompt did not complete successfully")
    outputs = record.get("outputs", {})
    if not isinstance(outputs, dict):
        raise ValueError("Malformed external synthetic graph outputs")
    previews = outputs.get("10", {}).get("images") if isinstance(
        outputs.get("10"), dict) else None
    gifs = outputs.get("11", {}).get("gifs") if isinstance(
        outputs.get("11"), dict) else None
    if not isinstance(previews, list) or len(previews) != 2:
        raise ValueError("External model-free VHS/rgthree graph returned wrong image count")
    if not isinstance(gifs, list) or len(gifs) != 1:
        raise ValueError("External synthetic GIF encoder returned wrong output count")
    h264s = outputs.get("12", {}).get("gifs") if isinstance(
        outputs.get("12"), dict) else None
    if not isinstance(h264s, list) or len(h264s) != 1:
        raise ValueError("External synthetic H264 encoder returned wrong output count")
    h265s = outputs.get("13", {}).get("gifs") if isinstance(
        outputs.get("13"), dict) else None
    if not isinstance(h265s, list) or len(h265s) != 1:
        raise ValueError("External synthetic H265 encoder returned wrong output count")
    prores = outputs.get("14", {}).get("gifs") if isinstance(
        outputs.get("14"), dict) else None
    if not isinstance(prores, list) or len(prores) != 1:
        raise ValueError("External synthetic ProRes encoder returned wrong output count")
    for preview in previews:
        _validated_temp_asset(preview, "png")
    gif = _validated_temp_asset(gifs[0], "gif")
    if gifs[0].get("format") != "image/gif":
        raise ValueError("Unexpected external GIF codec")
    _validated_temp_asset(h264s[0], "mp4")
    if h264s[0].get("format") != "video/h264-mp4":
        raise ValueError("Unexpected external MP4 codec")
    _validated_temp_asset(h265s[0], "mp4")
    if h265s[0].get("format") != "video/h265-mp4":
        raise ValueError("Unexpected external HEVC codec")
    _validated_temp_asset(prores[0], "mov")
    if prores[0].get("format") != "video/ProRes":
        raise ValueError("Unexpected external ProRes codec")
    return {
        "status": "synthetic_api_graph_executed",
        "classes": ["EmptyImage", "ImageBatch", "VHS_SelectEveryNthImage",
                    "Any Switch (rgthree)", "PreviewImage", "VHS_VideoCombine"],
        "source_image_count": 4,
        "selected_image_count": len(previews),
        "gif_count": len(gifs),
        "h264_mp4_count": len(h264s),
        "h265_mp4_count": len(h265s),
        "prores_mov_count": len(prores),
        "route": "four colored core images -> VHS every-second -> rgthree -> PNG/GIF/H264/HEVC/ProRes",
        "model_weights_used": False,
        "binary_outputs_uploaded": False,
    }


def _assert_uniform_frame(image: object, expected_rgb: tuple[int, int, int]) -> str:
    """Validate every pixel, not just image dimensions or a representative pixel."""
    from PIL import Image

    if not isinstance(image, Image.Image) or image.size != (64, 64):
        raise ValueError("Synthetic output raster dimensions differ")
    frame = image.convert("RGB")
    extrema = frame.getextrema()
    if tuple(extrema) != tuple((value, value) for value in expected_rgb):
        raise ValueError("VHS/rgthree synthetic selected-frame RGB differs")
    return _sha(frame.tobytes())


def _fetch_temporary_asset(port: int, item: dict, extension: str) -> bytes:
    asset = _validated_temp_asset(item, extension)
    query = urlencode(asset)
    with urlopen(f"http://127.0.0.1:{port}/view?{query}", timeout=10) as resp:
        if resp.status != 200:
            raise RuntimeError("Temporary synthetic output retrieval failed")
        data = resp.read(RASTER_LIMIT + 1)
        if not data or len(data) > RASTER_LIMIT:
            raise ValueError("Synthetic output exceeds permitted byte size")
        return data


def validate_h265_decoded_rgb(raw: bytes) -> dict:
    """Check every HEVC frame pixel with the same YUV tolerance as H.264."""
    pixels_per_frame = 64 * 64 * 3
    if len(raw) != 2 * pixels_per_frame:
        raise ValueError("H265 decoded frame count or dimensions differ")
    errors = []
    hashes = []
    for index, rgb in enumerate(EXPECTED_RGB):
        frame = raw[index * pixels_per_frame:(index + 1) * pixels_per_frame]
        error = max(
            max(abs(value - target) for value in frame[channel::3])
            for channel, target in enumerate(rgb)
        )
        if error > 24:
            raise ValueError("H265 decoded RGB differs from expected red/blue order")
        hashes.append(_sha(frame))
        errors.append(error)
    return {
        "codec": "hevc",
        "pixel_format_requested": "yuv420p",
        "frames_decoded": 2,
        "width": 64,
        "height": 64,
        "expected_rgb": [list(color) for color in EXPECTED_RGB],
        "maximum_absolute_channel_error": errors,
        "maximum_permitted_channel_error": 24,
        "decoded_frame_sha256": hashes,
        "content": "bounded_full_frame_rgb_verified",
        "binary_outputs_uploaded": False,
    }


def verify_h265_video(port: int, item: dict) -> dict:
    """Inspect and decode the temporary VHS libx265/hvc1 MP4 via local FFmpeg."""
    from imageio_ffmpeg import get_ffmpeg_exe

    data = _fetch_temporary_asset(port, item, "mp4")
    if len(data) < 12 or data[4:8] != b"ftyp":
        raise ValueError("H265 asset lacks an MP4 ftyp signature")
    with tempfile.TemporaryDirectory(prefix="osf_hevc_cpu_") as scratch:
        video = Path(scratch) / "synthetic.mp4"
        video.write_bytes(data)
        result = subprocess.run(
            [get_ffmpeg_exe(), "-hide_banner", "-nostdin",
             "-i", str(video), "-map", "0:v:0", "-vsync", "0",
             "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
            capture_output=True, check=True, timeout=30,
        )
        stderr = result.stderr.decode("utf-8", "replace")
        if not re.search(r"Video:\s+hevc\b", stderr, flags=re.IGNORECASE):
            raise ValueError("FFmpeg did not identify the encoded stream as HEVC")
        return {
            **validate_h265_decoded_rgb(result.stdout),
            "container": "mp4",
            "output_mp4_sha256": _sha(data),
            "mp4_size_bytes": len(data),
        }


def validate_prores_decoded_rgb(raw: bytes) -> dict:
    """Validate all decoded ProRes RGB pixels, not a high-bit-depth source test."""
    pixels_per_frame = 64 * 64 * 3
    if len(raw) != 2 * pixels_per_frame:
        raise ValueError("ProRes decoded frame count or dimensions differ")
    errors = []
    hashes = []
    for index, rgb in enumerate(EXPECTED_RGB):
        frame = raw[index * pixels_per_frame:(index + 1) * pixels_per_frame]
        error = max(
            max(abs(value - target) for value in frame[channel::3])
            for channel, target in enumerate(rgb)
        )
        if error > 24:
            raise ValueError("ProRes decoded RGB differs from expected red/blue order")
        hashes.append(_sha(frame))
        errors.append(error)
    return {
        "codec": "prores",
        "profile_requested": "hq",
        "source_colour_precision_bits": 8,
        "frames_decoded": 2,
        "width": 64,
        "height": 64,
        "expected_rgb": [list(color) for color in EXPECTED_RGB],
        "maximum_absolute_channel_error": errors,
        "maximum_permitted_channel_error": 24,
        "decoded_frame_sha256": hashes,
        "content": "bounded_full_frame_rgb_verified",
        "high_bit_depth_fidelity_qualified": False,
        "binary_outputs_uploaded": False,
    }


def verify_prores_video(port: int, item: dict) -> dict:
    """Check temporary pinned VHS ProRes HQ MOV and decode via runner FFmpeg."""
    from imageio_ffmpeg import get_ffmpeg_exe

    data = _fetch_temporary_asset(port, item, "mov")
    if len(data) < 12 or data[4:8] != b"ftyp":
        raise ValueError("ProRes asset lacks an MOV/QuickTime ftyp signature")
    with tempfile.TemporaryDirectory(prefix="osf_prores_cpu_") as scratch:
        video = Path(scratch) / "synthetic.mov"
        video.write_bytes(data)
        result = subprocess.run(
            [get_ffmpeg_exe(), "-hide_banner", "-nostdin",
             "-i", str(video), "-map", "0:v:0", "-vsync", "0",
             "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
            capture_output=True, check=True, timeout=30,
        )
        stderr = result.stderr.decode("utf-8", "replace")
        if not re.search(r"Video:\s+prores\b", stderr, flags=re.IGNORECASE):
            raise ValueError("FFmpeg did not identify the encoded stream as ProRes")
        # The selected HQ profile is 10-bit 4:2:2 video storage, but our
        # synthetic EmptyImage frames originate as 8-bit RGB colours.
        if not re.search(r"\byuv422p10le\b", stderr):
            raise ValueError("ProRes HQ storage pixel format differs from expected")
        return {
            **validate_prores_decoded_rgb(result.stdout),
            "container": "mov",
            "storage_pixel_format": "yuv422p10le",
            "output_mov_sha256": _sha(data),
            "mov_size_bytes": len(data),
        }


def verify_model_free_raster_content(port: int, record: dict) -> dict:
    """Verify real preview and GIF pixels against red/blue source-frame order."""
    from PIL import Image

    outputs = record["outputs"]
    previews = outputs["10"]["images"]
    gif = outputs["11"]["gifs"][0]
    hashes = []
    for entry, rgb in zip(previews, EXPECTED_RGB):
        raw = _fetch_temporary_asset(port, entry, "png")
        with Image.open(BytesIO(raw)) as preview:
            if preview.format != "PNG":
                raise ValueError("Synthetic preview is not PNG")
            hashes.append(_assert_uniform_frame(preview, rgb))
    raw_gif = _fetch_temporary_asset(port, gif, "gif")
    gif_hashes = []
    with Image.open(BytesIO(raw_gif)) as image:
        if image.format != "GIF" or getattr(image, "n_frames", 0) != 2:
            raise ValueError("VHS synthetic GIF does not contain exactly two frames")
        for index, rgb in enumerate(EXPECTED_RGB):
            image.seek(index)
            gif_hashes.append(_assert_uniform_frame(image, rgb))
            if image.info.get("duration") != 500:
                raise ValueError("VHS GIF frame duration differs from two FPS")
    if hashes != gif_hashes:
        raise ValueError("VHS GIF pixels differ from rgthree-routed previews")
    h264 = verify_h264_video(port, outputs["12"]["gifs"][0])
    h265 = verify_h265_video(port, outputs["13"]["gifs"][0])
    prores = verify_prores_video(port, outputs["14"]["gifs"][0])
    return {
        "content": "exact_full_frame_RGB_verified",
        "expected_selected_rgb": [list(color) for color in EXPECTED_RGB],
        "preview_frame_sha256": hashes,
        "gif_frame_sha256": gif_hashes,
        "gif_frames": 2,
        "h264_mp4": h264,
        "h265_mp4": h265,
        "prores_mov": prores,
        "gif_frame_duration_ms": 500,
        "temporary_assets_inspected": 6,
        "binary_outputs_uploaded": False,
    }


def validate_h264_decoded_rgb(raw: bytes) -> dict:
    """Enforce all decoded pixels and frame order with bounded YUV roundtrip error.

    Unlike the PNG/GIF assertions, H.264/yuv420p necessarily changes RGB by
    small amounts during colour conversion. Reject content beyond tolerance.
    """
    pixels_per_frame = 64 * 64 * 3
    if len(raw) != 2 * pixels_per_frame:
        raise ValueError("H264 decoded frame count or dimensions differ")
    max_errors = []
    frame_hashes = []
    for index, rgb in enumerate(EXPECTED_RGB):
        frame = raw[index * pixels_per_frame:(index + 1) * pixels_per_frame]
        error = max(
            max(abs(value - target) for value in frame[channel::3])
            for channel, target in enumerate(rgb)
        )
        if error > 24:
            raise ValueError("H264 decoded RGB differs from expected red/blue order")
        frame_hashes.append(_sha(frame))
        max_errors.append(error)
    return {
        "codec": "h264",
        "pixel_format_requested": "yuv420p",
        "frames_decoded": 2,
        "width": 64,
        "height": 64,
        "expected_rgb": [list(rgb) for rgb in EXPECTED_RGB],
        "maximum_absolute_channel_error": max_errors,
        "maximum_permitted_channel_error": 24,
        "decoded_frame_sha256": frame_hashes,
        "content": "bounded_full_frame_rgb_verified",
        "binary_outputs_uploaded": False,
    }


def verify_h264_video(port: int, item: dict) -> dict:
    """Decode an actual temporary VHS H.264 MP4 using pinned CPU FFmpeg.

    Verifies codec identity and all decoded pixels. The MP4 is placed only
    in a temporary scratch directory and not retained in CI artifacts.
    """
    from imageio_ffmpeg import get_ffmpeg_exe

    data = _fetch_temporary_asset(port, item, "mp4")
    if len(data) < 12 or data[4:8] != b"ftyp":
        raise ValueError("H264 asset lacks an MP4 ftyp signature")
    with tempfile.TemporaryDirectory(prefix="osf_h264_cpu_") as scratch:
        video = Path(scratch) / "synthetic.mp4"
        video.write_bytes(data)
        args = [
            get_ffmpeg_exe(), "-hide_banner", "-nostdin",
            "-i", str(video), "-map", "0:v:0", "-vsync", "0",
            "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1",
        ]
        result = subprocess.run(
            args, capture_output=True, timeout=30, check=True,
        )
        stderr = result.stderr.decode("utf-8", "replace")
        if not re.search(r"Video:\s+h264\b", stderr, flags=re.IGNORECASE):
            raise ValueError("FFmpeg did not identify the encoded stream as H264")
        output = validate_h264_decoded_rgb(result.stdout)
        return {
            **output,
            "container": "mp4",
            "output_mp4_sha256": _sha(data),
            "mp4_size_bytes": len(data),
        }


def execute_model_free_external_prompt(port: int, child: subprocess.Popen,
                                       *, timeout_seconds: int = 60) -> dict:
    graph = build_model_free_external_prompt()
    payload = json.dumps({"prompt": graph}).encode("utf-8")
    req = Request(
        f"http://127.0.0.1:{port}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=12) as resp:
        if resp.status != 200:
            raise RuntimeError("ComfyUI rejected model-free external prompt")
        response = json.loads(resp.read(100_000))
    prompt_id = response.get("prompt_id") if isinstance(response, dict) else None
    if not isinstance(prompt_id, str) or len(prompt_id) > 100 or not prompt_id:
        raise ValueError("Missing external synthetic graph prompt ID")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("ComfyUI exited before external graph completed")
        with urlopen(f"http://127.0.0.1:{port}/history/{prompt_id}", timeout=8) as resp:
            if resp.status != 200:
                raise RuntimeError("ComfyUI history response status not 200")
            history = json.loads(resp.read(150_000))
        if isinstance(history, dict) and prompt_id in history:
            outcome = validate_model_free_external_history(history, prompt_id)
            pixels = verify_model_free_raster_content(port, history[prompt_id])
            return {**outcome, "raster_verification": pixels}
        time.sleep(1)
    raise TimeoutError("External synthetic VHS/rgthree graph did not complete")


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
        # Check the interpreter will actually load our no-download guard
        # before running any third-party package initialization.
        subprocess.run(
            [sys.executable, "-c",
             "import sitecustomize, urllib.request; "
             "assert urllib.request.urlretrieve is sitecustomize._reject_urlretrieve"],
            env=env, check=True, capture_output=True, text=True, timeout=15,
        )
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
                external_graph = execute_model_free_external_prompt(port, child)
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
        "external_model_free_api_graph": external_graph,
        "model_weights_installed": False,
        "third_party_custom_nodes_installed": True,
        "third_party_source_commits": external_versions,
        "pinned_usdu_submodule": usdu_submodule,
        "third_party_nodes_imported": registration["external_classes"],
        "third_party_graphs_executed": True,
        "third_party_graph_scope": "one four-node synthetic VHS+rgthree API graph only",
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
