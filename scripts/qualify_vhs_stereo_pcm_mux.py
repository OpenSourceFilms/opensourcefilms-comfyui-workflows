"""Validate pinned VHS ProRes 4444 stereo PCM16 mux on disposable CPU.

Fixed left 440 Hz / 0.20 amplitude; right 660 Hz / 0.14 amplitude.
Distinguishable channels detect swapping, duplication, mono collapse and
cross-channel contamination. This is not a production audio-sync test.
"""
from __future__ import annotations

from array import array
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


RATE = 48_000
CHANNEL_TONES = ((440, 0.20), (660, 0.14))
MAX_BINARY_SIZE = 2_000_000


def build_stereo_mux_graph() -> dict:
    return {
        "1": {"class_type": "EmptyImage", "inputs": {
            "width": 64, "height": 64, "batch_size": 2, "color": 0,
        }},
        "2": {"class_type": "OSFTestStereoAudio", "inputs": {}},
        "3": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["1", 0], "audio": ["2", 0],
            "frame_rate": 2, "loop_count": 0,
            "filename_prefix": "osf_synthetic_stereo_mux",
            "format": "video/ProRes", "profile": "4444",
            "pingpong": False, "save_output": False,
        }},
    }


def validate_stereo_history(record: object) -> dict:
    if not isinstance(record, dict):
        raise ValueError("Missing stereo mux history")
    state = record.get("status")
    if (not isinstance(state, dict) or state.get("completed") is not True
            or state.get("status_str") != "success"):
        raise ValueError("Synthetic stereo mux did not complete")
    outputs = record.get("outputs")
    entries = outputs.get("3", {}).get("gifs") if isinstance(outputs, dict) else None
    if not isinstance(entries, list) or len(entries) != 1:
        raise ValueError("Stereo mux requires exactly one MOV output")
    item = entries[0]
    if not isinstance(item, dict):
        raise ValueError("Malformed stereo MOV metadata")
    filename = item.get("filename")
    if (not isinstance(filename, str)
            or re.fullmatch(
                r"osf_synthetic_stereo_mux_[A-Za-z0-9_.-]{1,110}-audio\.mov",
                filename) is None
            or item.get("type") != "temp"
            or item.get("subfolder") not in ("", None)
            or item.get("format") != "video/ProRes"):
        raise ValueError("Unsafe or non-stereo MOV output metadata")
    return {"filename": filename, "type": "temp", "subfolder": ""}


def check_decoded_stereo_pcm(samples: array) -> dict:
    """Check all 48,000 stereo sample frames against distinct analytic tones."""
    if len(samples) % 2:
        raise ValueError("Stereo PCM has an odd interleaved sample count")
    frames = len(samples) // 2
    if frames != RATE:
        raise ValueError("Stereo PCM must have exactly 48000 sample frames with no padding")
    if not all(math.isfinite(x) for x in samples):
        raise ValueError("Stereo PCM contains nonfinite values")
    errors = [0.0, 0.0]
    peaks = [0.0, 0.0]
    # Validate both channels at every single position, including the tail.
    for i in range(RATE):
        for ch, (frequency, amplitude) in enumerate(CHANNEL_TONES):
            observed = samples[2 * i + ch]
            expected = amplitude * math.sin(2 * math.pi * frequency * i / RATE)
            errors[ch] = max(errors[ch], abs(observed - expected))
            peaks[ch] = max(peaks[ch], abs(observed))
    if errors[0] > 0.003 or errors[1] > 0.003:
        raise ValueError("Stereo PCM channel identity, phase or leakage differs")
    if not 0.195 <= peaks[0] <= 0.205 or not 0.135 <= peaks[1] <= 0.145:
        raise ValueError("Stereo PCM channel amplitudes differ")
    return {
        "status": "stereo_pcm16_channel_identity_verified",
        "sample_rate_hz": RATE,
        "channels": 2,
        "channel_frequencies_hz": [440, 660],
        "channel_amplitudes": [0.20, 0.14],
        "decoded_sample_frames": frames,
        "checked_sample_frames": RATE,
        "peak_amplitudes": [round(x, 6) for x in peaks],
        "maximum_channel_errors": [round(x, 7) for x in errors],
        "interleaved_pcm_sha256": hashlib.sha256(samples.tobytes()).hexdigest(),
        "binary_media_uploaded": False,
    }


def verify_stereo_prores_pcm_mov(raw: bytes) -> dict:
    from imageio_ffmpeg import get_ffmpeg_exe

    if len(raw) < 12 or len(raw) > MAX_BINARY_SIZE or raw[4:8] != b"ftyp":
        raise ValueError("Stereo mux output has invalid QuickTime MOV header")
    with tempfile.TemporaryDirectory(prefix="osf_stereo_mux_") as scratch:
        path = Path(scratch) / "synthetic_stereo.mov"
        path.write_bytes(raw)
        ffmpeg = get_ffmpeg_exe()
        video = subprocess.run(
            [ffmpeg, "-hide_banner", "-nostdin", "-i", str(path),
             "-map", "0:v:0", "-vsync", "0",
             "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
            check=True, capture_output=True, timeout=25,
        )
        if not re.search(
            r"Video:\s+prores\s+\(4444\)\s",
            video.stderr.decode("utf-8", "replace"), flags=re.IGNORECASE,
        ):
            raise ValueError("Stereo mux video is not ProRes 4444")
        if len(video.stdout) != 2 * 64 * 64 * 3 or any(p > 3 for p in video.stdout):
            raise ValueError("Stereo mux did not preserve two black source frames")
        audio = subprocess.run(
            [ffmpeg, "-hide_banner", "-nostdin", "-i", str(path),
             "-map", "0:a:0", "-ac", "2", "-ar", str(RATE),
             "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"],
            check=True, capture_output=True, timeout=25,
        )
        info = audio.stderr.decode("utf-8", "replace")
        if not re.search(r"Audio:\s+pcm_s16le\b", info, re.IGNORECASE):
            raise ValueError("Stereo mux audio is not uncompressed PCM16")
        if not re.search(r"48000 Hz,\s+stereo\b", info, re.IGNORECASE):
            raise ValueError("Stereo mux track does not report stereo 48kHz")
        if len(audio.stdout) % 8:
            raise ValueError("Stereo PCM byte count is not frame aligned")
        pcm = array("f")
        pcm.frombytes(audio.stdout)
        if sys.byteorder != "little":
            pcm.byteswap()
        return {
            "video_codec": "prores_4444",
            "video_frames": 2,
            "video_dimensions": [64, 64],
            "video_black_source_verified": True,
            "audio": check_decoded_stereo_pcm(pcm),
            "mov_sha256": hashlib.sha256(raw).hexdigest(),
            "mov_size_bytes": len(raw),
            "binary_media_uploaded": False,
            "production_audio_or_video_used": False,
            "production_audio_sync_verified": False,
        }


def execute_synthetic_vhs_stereo_mux(
    port: int, child: subprocess.Popen, timeout_seconds: int = 60
) -> dict:
    payload = json.dumps({"prompt": build_stereo_mux_graph()}).encode("utf-8")
    req = Request(
        f"http://127.0.0.1:{port}/prompt", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urlopen(req, timeout=10) as resp:
        if resp.status != 200:
            raise ValueError("ComfyUI rejected synthetic stereo PCM graph")
        response = json.loads(resp.read(100_000))
    pid = response.get("prompt_id") if isinstance(response, dict) else None
    if not isinstance(pid, str) or not 1 <= len(pid) <= 100:
        raise ValueError("Synthetic stereo graph has no valid prompt ID")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("ComfyUI exited before stereo mux completed")
        with urlopen(f"http://127.0.0.1:{port}/history/{pid}", timeout=10) as resp:
            history = json.loads(resp.read(150_000))
        if isinstance(history, dict) and pid in history:
            item = validate_stereo_history(history[pid])
            with urlopen(f"http://127.0.0.1:{port}/view?{urlencode(item)}", timeout=10) as resp:
                raw = resp.read(MAX_BINARY_SIZE + 1)
            return {
                "status": "synthetic_vhs_stereo_pcm_mux_verified",
                "graph_classes": [
                    "EmptyImage", "OSFTestStereoAudio", "VHS_VideoCombine",
                ],
                **verify_stereo_prores_pcm_mov(raw),
            }
        time.sleep(1)
    raise TimeoutError("Synthetic VHS stereo mux graph did not complete")
