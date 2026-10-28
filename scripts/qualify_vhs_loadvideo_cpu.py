"""Actual pinned VHS_LoadVideo upload IMAGE branch on disposable ComfyUI CPU.

Generate a tiny deterministic MP4 in the disposable ComfyUI input directory.
Run the real pinned VHS_LoadVideo (without optional vae/meta_batch), require
the live /prompt graph to execute through PreviewImage, decode all returned
preview pixels and check red/blue order. No user data or model weights.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

WIDTH = 64
HEIGHT = 64
FRAMES = 2
VIDEO_NAME = "osf_generated_vhs_loader_2frame_cpu_probe.mp4"
RGB = ((255, 0, 0), (0, 0, 255))
MAX_CHANNEL_ERROR_8BIT = 24
MAX_RESPONSE_BYTES = 150_000
MAX_MEDIA_BYTES = 1_000_000


def synthetic_video_rgb24() -> bytes:
    return b"".join(bytes(colour) * (WIDTH * HEIGHT) for colour in RGB)


def build_vhs_upload_probe() -> dict:
    """Exactly the selected saved eight loader input names, no optional VAE."""
    return {
        "1": {"class_type": "VHS_LoadVideo", "inputs": {
            "video": VIDEO_NAME,
            "force_rate": 0,
            "custom_width": 0,
            "custom_height": 0,
            "frame_load_cap": 49,
            "skip_first_frames": 0,
            "select_every_nth": 1,
            "format": "AnimateDiff",
        }},
        "2": {"class_type": "PreviewImage", "inputs": {
            "images": ["1", 0],
        }},
    }


def validate_vhs_loader_history(history: object, prompt_id: str) -> list[dict]:
    if not isinstance(history, dict) or prompt_id not in history:
        raise ValueError("Missing VHS_LoadVideo prompt history")
    record = history[prompt_id]
    if not isinstance(record, dict):
        raise ValueError("Malformed VHS_LoadVideo history")
    status = record.get("status")
    if not isinstance(status, dict) or status.get("completed") is not True or status.get("status_str") != "success":
        raise ValueError("VHS_LoadVideo did not complete successfully")
    outputs = record.get("outputs")
    if not isinstance(outputs, dict) or not isinstance(outputs.get("2"), dict):
        raise ValueError("VHS_LoadVideo PreviewImage output missing")
    images = outputs["2"].get("images")
    if not isinstance(images, list) or len(images) != FRAMES:
        raise ValueError("VHS_LoadVideo produced wrong decoded frame count")
    result = []
    for image in images:
        if not isinstance(image, dict):
            raise ValueError("Malformed VHS_LoadVideo preview metadata")
        name = image.get("filename")
        if (not isinstance(name, str)
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,179}\.png", name) is None
                or image.get("type") != "temp"
                or image.get("subfolder") not in ("", None)):
            raise ValueError("Unsafe VHS_LoadVideo temporary preview metadata")
        result.append({"filename": name, "type": "temp", "subfolder": ""})
    return result


def validate_decoded_vhs_pixels(images: list[bytes]) -> dict:
    from PIL import Image

    if len(images) != FRAMES:
        raise ValueError("VHS_LoadVideo preview list does not have two frames")
    errors = []
    hashes = []
    for binary, expected in zip(images, RGB):
        if not binary or len(binary) > MAX_MEDIA_BYTES:
            raise ValueError("VHS_LoadVideo preview exceeds size boundary")
        with Image.open(BytesIO(binary)) as image:
            if image.format != "PNG" or image.size != (WIDTH, HEIGHT):
                raise ValueError("VHS_LoadVideo preview image format/dimensions differ")
            rgb = image.convert("RGB")
            data = rgb.tobytes()
        error = max(max(abs(v - target) for v in data[channel::3])
                    for channel, target in enumerate(expected))
        if error > MAX_CHANNEL_ERROR_8BIT:
            raise ValueError("VHS_LoadVideo decoded content or colour order differs")
        errors.append(error)
        hashes.append(sha256(data).hexdigest())
    return {
        "status": "real_vhs_loadvideo_cpu_image_branch_executed",
        "loader": "VHS_LoadVideo",
        "source_media": "generated_2frame_h264_mp4",
        "saved_input_mode": "AnimateDiff",
        "connected_vae": False,
        "connected_meta_batch": False,
        "output_slot": 0,
        "sink": "PreviewImage",
        "decoded_frames": FRAMES,
        "dimensions": [WIDTH, HEIGHT],
        "expected_rgb": [list(c) for c in RGB],
        "maximum_absolute_channel_error_8bit": errors,
        "maximum_permitted_channel_error_8bit": MAX_CHANNEL_ERROR_8BIT,
        "decoded_frame_sha256": hashes,
        "sam3_scail_nodes_executed": False,
        "model_weights_used": False,
        "binary_media_uploaded": False,
    }


def _make_mp4(ffmpeg: str, destination: Path) -> bytes:
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Refuse to replace existing VHS probe input media")
    subprocess.run(
        [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-n",
         "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-video_size", "64x64", "-framerate", "8",
         "-i", "pipe:0", "-an", "-frames:v", "2", "-c:v", "libx264",
         "-preset", "ultrafast", "-crf", "0", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", "-f", "mp4", str(destination)],
        input=synthetic_video_rgb24(), capture_output=True, check=True,
        timeout=25,
    )
    data = destination.read_bytes()
    if not 12 <= len(data) <= MAX_MEDIA_BYTES or data[4:8] != b"ftyp":
        raise ValueError("Synthetic VHS loader source is not a bounded MP4")
    return data


def execute_vhs_loadvideo_cpu(port: int, child: subprocess.Popen,
                              comfy: Path, *, timeout_seconds: int = 65) -> dict:
    """Require actual pinned VHS reader, IMAGE output slot and PNG content."""
    from imageio_ffmpeg import get_ffmpeg_exe

    input_dir = comfy / "input"
    if input_dir.is_symlink() or not input_dir.is_dir():
        raise ValueError("Disposable ComfyUI input directory missing or symlinked")
    media = input_dir / VIDEO_NAME
    if media.exists() or media.is_symlink():
        raise FileExistsError("Disposable VHS loader input file already exists")
    try:
        encoded = _make_mp4(get_ffmpeg_exe(), media)
        request = Request(
            f"http://127.0.0.1:{port}/prompt",
            data=json.dumps({"prompt": build_vhs_upload_probe()}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=12) as response:
            if response.status != 200:
                raise ValueError("VHS_LoadVideo prompt HTTP response not 200")
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise ValueError("Oversized VHS_LoadVideo prompt response")
            reply = json.loads(data)
        prompt_id = reply.get("prompt_id") if isinstance(reply, dict) else None
        if not isinstance(prompt_id, str) or not 1 <= len(prompt_id) <= 100:
            raise ValueError("VHS_LoadVideo prompt ID invalid")

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError("Disposable ComfyUI exited during VHS load")
            with urlopen(f"http://127.0.0.1:{port}/history/{prompt_id}",
                         timeout=8) as response:
                if response.status != 200:
                    raise ValueError("VHS_LoadVideo history HTTP response not 200")
                content = response.read(MAX_RESPONSE_BYTES + 1)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise ValueError("Oversized VHS_LoadVideo history response")
                history = json.loads(content)
            if isinstance(history, dict) and prompt_id in history:
                items = validate_vhs_loader_history(history, prompt_id)
                previews = []
                for item in items:
                    url = f"http://127.0.0.1:{port}/view?" + urlencode(item)
                    with urlopen(url, timeout=10) as response:
                        if response.status != 200:
                            raise ValueError("VHS_LoadVideo preview retrieval failed")
                        binary = response.read(MAX_MEDIA_BYTES + 1)
                        if len(binary) > MAX_MEDIA_BYTES:
                            raise ValueError("VHS_LoadVideo preview exceeds bounded read")
                        previews.append(binary)
                result = validate_decoded_vhs_pixels(previews)
                result["generated_h264_source_sha256"] = sha256(encoded).hexdigest()
                result["generated_h264_source_size_bytes"] = len(encoded)
                return result
            time.sleep(1)
        raise TimeoutError("Actual VHS_LoadVideo synthetic image graph timed out")
    finally:
        if media.is_file() and not media.is_symlink():
            media.unlink()
