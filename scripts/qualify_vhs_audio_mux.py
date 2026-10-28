"""Qualify one real VHS ProRes video + PCM audio mux on disposable CPU.

Uses only test-generated images and a 48kHz/440Hz mono sine. No pretrained
weights, live production audio, GPU jobs, or retained media.
"""
from __future__ import annotations

from array import array
from io import BytesIO
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SAMPLE_RATE = 48_000
TONE_HZ = 440
TONE_AMPLITUDE = 0.2
MAX_BINARY_SIZE = 2_000_000


def build_synthetic_audio_mux_graph() -> dict:
    return {
        "1": {"class_type": "EmptyImage", "inputs": {
            "width": 64, "height": 64, "batch_size": 2, "color": 0,
        }},
        "2": {"class_type": "OSFTestSineAudio", "inputs": {}},
        "3": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["1", 0], "audio": ["2", 0], "frame_rate": 2,
            "loop_count": 0, "filename_prefix": "osf_synthetic_pcm_mux",
            "format": "video/ProRes", "profile": "4444",
            "pingpong": False, "save_output": False,
        }},
    }


def validate_mux_history(record: object) -> dict:
    if not isinstance(record, dict):
        raise ValueError("Missing synthetic audio mux history")
    state = record.get("status")
    if (not isinstance(state, dict) or state.get("completed") is not True
            or state.get("status_str") != "success"):
        raise ValueError("Synthetic audio mux did not complete")
    outputs = record.get("outputs")
    entries = outputs.get("3", {}).get("gifs") if isinstance(outputs, dict) else None
    if not isinstance(entries, list) or len(entries) != 1:
        raise ValueError("Synthetic audio mux requires exactly one MOV output")
    asset = entries[0]
    if not isinstance(asset, dict):
        raise ValueError("Malformed synthetic audio MOV metadata")
    name = asset.get("filename")
    if (not isinstance(name, str)
            or re.fullmatch(r"osf_synthetic_pcm_mux_[A-Za-z0-9_.-]{1,110}-audio\.mov",
                            name) is None
            or asset.get("type") != "temp"
            or asset.get("subfolder") not in ("", None)
            or asset.get("format") != "video/ProRes"):
        raise ValueError("Unsafe or non-audio ProRes output metadata")
    return {"filename": name, "type": "temp", "subfolder": ""}


def check_decoded_mono_pcm(samples: array) -> dict:
    """Validate audio frequency, amplitude, initial waveform and channel count."""
    count = len(samples)
    if not SAMPLE_RATE - 512 <= count <= SAMPLE_RATE + 4096:
        raise ValueError("PCM audio sample count is inconsistent with one second")
    if not all(math.isfinite(value) for value in samples):
        raise ValueError("PCM audio contains nonfinite samples")
    first = samples[:SAMPLE_RATE - 1024]
    peak = max(abs(value) for value in first)
    if not 0.195 <= peak <= 0.205:
        raise ValueError("PCM audio tone peak amplitude differs")
    checkpoints = (0, 1, 2, 11, 12, 15, 97, 111, 1024, 2048,
                   4096, 8888, 12345, 23456, 34567, 44000)
    max_sample_error = max(
        abs(samples[i] - TONE_AMPLITUDE *
            math.sin(2 * math.pi * TONE_HZ * i / SAMPLE_RATE))
        for i in checkpoints
    )
    if max_sample_error > 0.003:
        raise ValueError("Decoded PCM source frequency/phase differs")
    return {
        "status": "synthetic_pcm_s16le_audio_verified",
        "sample_rate_hz": SAMPLE_RATE,
        "channels": 1,
        "source_tone_hz": TONE_HZ,
        "source_amplitude": TONE_AMPLITUDE,
        "samples_decoded": count,
        "peak_amplitude": round(peak, 6),
        "maximum_checkpoint_error": round(max_sample_error, 7),
        "sample_sha256": hashlib.sha256(samples.tobytes()).hexdigest(),
    }


def verify_synthetic_prores_pcm_mov(data: bytes) -> dict:
    from imageio_ffmpeg import get_ffmpeg_exe

    if len(data) < 12 or len(data) > MAX_BINARY_SIZE or data[4:8] != b"ftyp":
        raise ValueError("Synthetic PCM mux output has invalid QuickTime MOV header")
    with tempfile.TemporaryDirectory(prefix="osf_pcm_mux_cpu_") as scratch:
        path = Path(scratch) / "synthetic_audio.mov"
        path.write_bytes(data)
        ffmpeg = get_ffmpeg_exe()
        video = subprocess.run(
            [ffmpeg, "-hide_banner", "-nostdin", "-i", str(path),
             "-map", "0:v:0", "-vsync", "0", "-pix_fmt", "rgb24",
             "-f", "rawvideo", "pipe:1"],
            check=True, capture_output=True, timeout=25,
        )
        video_info = video.stderr.decode("utf-8", "replace")
        if not re.search(r"Video:\s+prores\s+\(4444\)\s", video_info,
                         flags=re.IGNORECASE):
            raise ValueError("Synthetic audio mux video stream is not ProRes 4444")
        if len(video.stdout) != 2 * 64 * 64 * 3:
            raise ValueError("Synthetic audio mux video is not two 64x64 frames")
        if any(pixel > 3 for pixel in video.stdout):
            raise ValueError("Synthetic audio mux video lost black source frames")
        audio = subprocess.run(
            [ffmpeg, "-hide_banner", "-nostdin", "-i", str(path),
             "-map", "0:a:0", "-ac", "1", "-ar", str(SAMPLE_RATE),
             "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"],
            check=True, capture_output=True, timeout=25,
        )
        audio_info = audio.stderr.decode("utf-8", "replace")
        if not re.search(r"Audio:\s+pcm_s16le\b", audio_info,
                         flags=re.IGNORECASE):
            raise ValueError("Synthetic audio mux track is not uncompressed PCM16")
        if not re.search(r"48000 Hz,\s+mono\b", audio_info,
                         flags=re.IGNORECASE):
            raise ValueError("Synthetic audio mux sample rate or channels differ")
        if len(audio.stdout) % 4:
            raise ValueError("Decoded mono PCM32 sample alignment differs")
        samples = array("f")
        samples.frombytes(audio.stdout)
        if sys.byteorder != "little":
            samples.byteswap()
        return {
            "video_codec": "prores_4444",
            "video_frames": 2,
            "video_dimensions": [64, 64],
            "video_black_source_verified": True,
            "audio": check_decoded_mono_pcm(samples),
            "mov_sha256": hashlib.sha256(data).hexdigest(),
            "mov_size_bytes": len(data),
            "binary_media_uploaded": False,
            "production_audio_or_video_used": False,
        }


def execute_synthetic_vhs_pcm_mux(port: int, child: subprocess.Popen,
                                  timeout_seconds: int = 60) -> dict:
    payload = json.dumps({"prompt": build_synthetic_audio_mux_graph()}).encode()
    req = Request(f"http://127.0.0.1:{port}/prompt", data=payload,
                  headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=10) as resp:
        if resp.status != 200:
            raise ValueError("ComfyUI rejected synthetic audio mux graph")
        response = json.loads(resp.read(100_000))
    prompt_id = response.get("prompt_id") if isinstance(response, dict) else None
    if not isinstance(prompt_id, str) or not 1 <= len(prompt_id) <= 100:
        raise ValueError("Synthetic audio mux missing prompt ID")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("ComfyUI exited before synthetic audio mux completed")
        with urlopen(f"http://127.0.0.1:{port}/history/{prompt_id}",
                     timeout=10) as resp:
            history = json.loads(resp.read(150_000))
        if isinstance(history, dict) and prompt_id in history:
            asset = validate_mux_history(history[prompt_id])
            with urlopen(f"http://127.0.0.1:{port}/view?{urlencode(asset)}",
                         timeout=10) as resp:
                data = resp.read(MAX_BINARY_SIZE + 1)
            return {
                "status": "synthetic_vhs_pcm_mux_verified",
                "graph_classes": [
                    "EmptyImage", "OSFTestSineAudio", "VHS_VideoCombine",
                ],
                **verify_synthetic_prores_pcm_mov(data),
            }
        time.sleep(1)
    raise TimeoutError("Synthetic ProRes PCM mux graph did not complete")
