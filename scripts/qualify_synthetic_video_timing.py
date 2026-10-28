"""Validate actual synthetic codec frame timing using the pinned FFmpeg.

Only checks short, disposable two-frame/2-fps VHS-generated videos. No
production media or model inference. The caller writes temporary data
that is deleted after the check and retains only timing metadata.
"""
from __future__ import annotations

import math
from pathlib import Path
import re
import subprocess


FRAME_LOG = re.compile(
    r"\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+"
    r"pts_time:([0-9]+(?:\.[0-9]+)?)\s+"
    r"duration:\s*(\d+)\s+duration_time:([0-9]+(?:\.[0-9]+)?)\b"
)
RATE_LOG = re.compile(r"\bframe_rate:\s*2/1\b")


def validate_video_timing_log(stderr: str) -> dict:
    """Require 2 fps, 2 frames, 0/500ms PTS, and 500ms per frame.

    The FFmpeg showinfo filter outputs one header and one frame line
    per decoded frame. Reject missing data and duplicated/reordered frames.
    """
    if not isinstance(stderr, str) or len(stderr) > 500_000:
        raise ValueError("Invalid or oversized FFmpeg timing diagnostic")
    rate_lines = [line for line in stderr.splitlines()
                  if "Parsed_showinfo" in line and "config in time_base:" in line]
    if len(rate_lines) != 1 or not RATE_LOG.search(rate_lines[0]):
        raise ValueError("Video timing nominal frame rate is not 2/1")
    frame_lines = [line for line in stderr.splitlines()
                   if "Parsed_showinfo" in line and " pts_time:" in line]
    if len(frame_lines) != 2:
        raise ValueError("Video timing must contain exactly two decoded frames")
    details = []
    for line in frame_lines:
        match = FRAME_LOG.search(line)
        if match is None:
            raise ValueError("Video timing sample is missing required fields")
        number, ticks, pts, duration_ticks, duration = match.groups()
        details.append({
            "n": int(number), "pts": float(pts),
            "pts_ticks": int(ticks), "duration_ticks": int(duration_ticks),
            "duration": float(duration),
        })
    if [item["n"] for item in details] != [0, 1]:
        raise ValueError("Video timing frame order or index is incorrect")
    if (details[0]["pts_ticks"] != 0 or
            details[1]["pts_ticks"] <= details[0]["pts_ticks"] or
            any(item["duration_ticks"] <= 0 for item in details)):
        raise ValueError("Video timing timestamps are not increasing")
    expected_pts = (0.0, 0.5)
    for item, expected in zip(details, expected_pts):
        if not math.isfinite(item["pts"]) or abs(item["pts"] - expected) > 0.001:
            raise ValueError("Video timing presentation timestamp is incorrect")
        if not math.isfinite(item["duration"]) or abs(item["duration"] - 0.5) > 0.001:
            raise ValueError("Video timing per-frame duration is incorrect")
    return {
        "status": "two_frame_2fps_pts_verified",
        "nominal_frame_rate": "2/1",
        "decoded_frame_indices": [0, 1],
        "presentation_times_seconds": [item["pts"] for item in details],
        "frame_durations_seconds": [item["duration"] for item in details],
        "total_sampled_duration_seconds": 1.0,
        "media_bytes_uploaded": False,
    }


def verify_video_timing(ffmpeg: str, video: Path) -> dict:
    """Inspect timing after the existing full-pixel codec validation."""
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "info",
         "-i", str(video), "-map", "0:v:0", "-vf", "showinfo",
         "-vsync", "0", "-an", "-f", "null", "-"],
        capture_output=True, timeout=30, check=True,
    )
    return validate_video_timing_log(result.stderr.decode("utf-8", "replace"))
