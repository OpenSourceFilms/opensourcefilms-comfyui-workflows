"""Exercise pinned VHS_LoadVideo's real no-VAE IMAGE output on disposable CPU.

A synthetic two-frame H.264 input is created locally before ComfyUI starts,
then loaded through the real VHS_LoadVideo API node. Native PreviewImage must
accept its IMAGE output and return two red/blue previews. Nothing is uploaded.
This is not a SAM3 or SCAIL model-inference test.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import time
from urllib.request import Request, urlopen

SOURCE_BASENAME = "osf_ci_vhs_no_vae_red_blue.mp4"
SOURCE_RGB = ((255, 0, 0), (0, 0, 255))
PIXELS_PER_FRAME = 64 * 64 * 3
MAX_CHANNEL_ERROR = 24
MAX_INPUT_FILE_BYTES = 2_000_000


def build_no_vae_video_prompt() -> dict:
    return {
        "1": {"class_type": "VHS_LoadVideo", "inputs": {
            "video": SOURCE_BASENAME,
            "force_rate": 0,
            "custom_width": 0,
            "custom_height": 0,
            "frame_load_cap": 2,
            "skip_first_frames": 0,
            "select_every_nth": 1,
            "format": "None",
            # Deliberately NO optional 'vae' input: require real IMAGE.
        }},
        "2": {"class_type": "PreviewImage", "inputs": {
            "images": ["1", 0],
        }},
    }


def prepare_synthetic_video_input(comfy: Path) -> dict:
    """Write exactly one deterministic synthetic test MP4 in the scratch input dir."""
    from imageio_ffmpeg import get_ffmpeg_exe

    parent = comfy / "input"
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("ComfyUI scratch input folder missing or symlinked")
    output = parent / SOURCE_BASENAME
    if output.exists() or output.is_symlink():
        raise FileExistsError("Synthetic VHS source path already exists")
    raw = b"".join(bytes(rgb) * (64 * 64) for rgb in SOURCE_RGB)
    if len(raw) != 2 * PIXELS_PER_FRAME:
        raise ValueError("Bad synthetic source length")
    args = [
        get_ffmpeg_exe(), "-hide_banner", "-nostdin", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-video_size", "64x64",
        "-framerate", "2", "-i", "pipe:0", "-an", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-crf", "0", "-movflags", "+faststart",
        "-frames:v", "2", str(output),
    ]
    try:
        subprocess.run(args, input=raw, check=True, capture_output=True, timeout=30)
        if output.is_symlink() or not output.is_file():
            raise ValueError("Synthetic VHS video output was not a regular file")
        content = output.read_bytes()
        if not 12 <= len(content) <= MAX_INPUT_FILE_BYTES or content[4:8] != b"ftyp":
            raise ValueError("Synthetic VHS source MP4 not valid")
        return {
            "status": "generated_synthetic_h264_input",
            "source_frames": 2,
            "dimensions": [64, 64],
            "source_mp4_sha256": hashlib.sha256(content).hexdigest(),
            "source_mp4_bytes": len(content),
            "private_media_used": False,
        }
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def validate_no_vae_video_history(history: object, prompt_id: str) -> list[dict]:
    if not isinstance(history, dict) or not isinstance(history.get(prompt_id), dict):
        raise ValueError("VHS no-VAE prompt missing from ComfyUI history")
    record = history[prompt_id]
    status = record.get("status")
    if (not isinstance(status, dict) or status.get("completed") is not True
            or status.get("status_str") != "success"):
        raise ValueError("VHS no-VAE video graph did not complete")
    outputs = record.get("outputs")
    previews = outputs.get("2", {}).get("images") if isinstance(outputs, dict) else None
    if not isinstance(previews, list) or len(previews) != 2:
        raise ValueError("VHS no-VAE IMAGE output did not produce two previews")
    for item in previews:
        if (not isinstance(item, dict) or item.get("type") != "temp"
                or item.get("subfolder") not in (None, "")
                or not isinstance(item.get("filename"), str)):
            raise ValueError("VHS no-VAE preview metadata malformed")
    return previews


def validate_no_vae_rgb_frames(decoded: list[bytes]) -> dict:
    if len(decoded) != 2 or any(len(raw) != PIXELS_PER_FRAME for raw in decoded):
        raise ValueError("VHS no-VAE preview count or dimensions differ")
    errors = []
    hashes = []
    for actual, expected in zip(decoded, SOURCE_RGB):
        maximum = max(
            max(abs(v - target) for v in actual[channel::3])
            for channel, target in enumerate(expected)
        )
        if maximum > MAX_CHANNEL_ERROR:
            raise ValueError("VHS no-VAE IMAGE pixel content or order differs")
        errors.append(maximum)
        hashes.append(hashlib.sha256(actual).hexdigest())
    return {
        "status": "real_vhs_no_vae_image_tensor_path_verified",
        "input_frames": 2,
        "output_preview_frames": 2,
        "expected_rgb": [list(rgb) for rgb in SOURCE_RGB],
        "maximum_absolute_channel_error": errors,
        "maximum_permitted_channel_error": MAX_CHANNEL_ERROR,
        "preview_frame_sha256": hashes,
        "vae_input_present": False,
        "image_output_accepted_by_native_preview": True,
        "sam3_inference_qualified": False,
        "scail_inference_qualified": False,
        "source_files_uploaded": False,
    }


def execute_no_vae_video_graph(port: int, process: subprocess.Popen,
                               *, fetch_asset) -> dict:
    """Submit pinned VHS_LoadVideo -> native PreviewImage and compare actual RGB."""
    from PIL import Image

    graph = build_no_vae_video_prompt()
    request = Request(
        f"http://127.0.0.1:{port}/prompt",
        data=json.dumps({"prompt": graph}).encode("utf-8"),
        method="POST", headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=12) as response:
        if response.status != 200:
            raise RuntimeError("VHS no-VAE prompt rejected")
        queued = json.loads(response.read(100_000))
    pid = queued.get("prompt_id") if isinstance(queued, dict) else None
    if not isinstance(pid, str) or not 1 <= len(pid) <= 100:
        raise ValueError("VHS no-VAE graph missing prompt ID")

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("ComfyUI stopped before VHS no-VAE graph finished")
        with urlopen(f"http://127.0.0.1:{port}/history/{pid}", timeout=8) as response:
            if response.status != 200:
                raise RuntimeError("VHS no-VAE history request failed")
            history = json.loads(response.read(150_000))
        if isinstance(history, dict) and pid in history:
            previews = validate_no_vae_video_history(history, pid)
            frames = []
            for item in previews:
                # The parent driver applies its tested filename/type/subfolder
                # controls and 2 MB cap before returning the temporary PNG.
                raw = fetch_asset(port, item, "png")
                with Image.open(BytesIO(raw)) as image:
                    if image.format != "PNG" or image.size != (64, 64):
                        raise ValueError("VHS no-VAE preview format or dimensions differ")
                    frames.append(image.convert("RGB").tobytes())
            return validate_no_vae_rgb_frames(frames)
        time.sleep(1)
    raise TimeoutError("VHS no-VAE graph did not complete in disposable CI")
