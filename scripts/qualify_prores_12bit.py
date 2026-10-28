"""Independent genuine 12-bit ProRes 4444 source/roundtrip acceptance.

This is deliberately separate from ComfyUI/VHS: the pinned VHS node's
synthetic EmptyImage path is 8-bit RGB source material, even though the
output MOV reports 12-bit storage. Here FFmpeg receives actual 12-bit
YUV444 planar source values and returns decoded 12-bit YUV444 samples.

All data is generated deterministically. No user footage, model weights,
production video, or media files are uploaded. The codec is lossy, so
bounded numerical error, not bit-for-bit roundtrip, is required.
"""
from __future__ import annotations

from array import array
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile


WIDTH = 64
HEIGHT = 64
FRAMES = 2
BIT_DEPTH = 12
SAMPLES_PER_PLANE = WIDTH * HEIGHT
SAMPLE_COUNT = FRAMES * 3 * SAMPLES_PER_PLANE
BYTE_LENGTH = SAMPLE_COUNT * 2
MAX_ABSOLUTE_ERROR_12BIT = 8


def _samples_from_bytes(data: bytes) -> array:
    if len(data) != BYTE_LENGTH:
        raise ValueError("ProRes 12-bit source/decoded sample length is incorrect")
    samples = array("H")
    samples.frombytes(data)
    if samples.itemsize != 2:
        raise RuntimeError("Unexpected platform uint16 representation")
    if sys.byteorder != "little":
        samples.byteswap()
    if any(sample > 4095 for sample in samples):
        raise ValueError("Invalid sample outside 12-bit component range")
    return samples


def _bytes_from_samples(samples: array) -> bytes:
    if samples.itemsize != 2:
        raise RuntimeError("Unexpected platform uint16 representation")
    if sys.byteorder == "little":
        return samples.tobytes()
    copy = array("H", samples)
    copy.byteswap()
    return copy.tobytes()


def make_genuine_12bit_yuv444p_source() -> bytes:
    """Two frames, three nonuniform 12-bit planes, including sub-8-bit steps.

    Adjacent 32x32 Y tiles have values 2038/2043 and 2048/2053
    (frame zero); each adjacent pair collapses under 12->8-bit truncation.
    A true high-precision decode must retain their ordering.
    """
    samples = array("H")
    for frame in range(FRAMES):
        for plane in range(3):
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    tile = (1 if x >= 32 else 0) + (2 if y >= 32 else 0)
                    if plane == 0:
                        value = 2038 + 32 * frame + 5 * tile
                    elif plane == 1:
                        value = 2048 + 3 * frame + 5 * tile
                    else:
                        value = 2028 + 3 * frame + 5 * tile
                    samples.append(value)
    if len(samples) != SAMPLE_COUNT:
        raise RuntimeError("Bad deterministic 12-bit source generator")
    return _bytes_from_samples(samples)


def validate_genuine_12bit_roundtrip(source: bytes, decoded: bytes) -> dict:
    """Compare every 12-bit decoded component and require sub-8-bit detail."""
    original = _samples_from_bytes(source)
    recovered = _samples_from_bytes(decoded)
    frame_stride = 3 * SAMPLES_PER_PLANE
    errors = []
    frame_hashes = []
    max_by_frame = []
    for frame in range(FRAMES):
        start = frame * frame_stride
        stop = start + frame_stride
        source_samples = original[start:stop]
        returned_samples = recovered[start:stop]
        diffs = [abs(a - b) for a, b in zip(source_samples, returned_samples)]
        maximum = max(diffs)
        if maximum > MAX_ABSOLUTE_ERROR_12BIT:
            raise ValueError("12-bit ProRes roundtrip exceeded channel error threshold")
        errors.extend(diffs)
        max_by_frame.append(maximum)
        frame_hashes.append(
            hashlib.sha256(
                _bytes_from_samples(returned_samples)
            ).hexdigest()
        )

    preserved_pairs = 0
    for frame in range(FRAMES):
        y_start = frame * frame_stride
        # Pairs within the same 8-bit bucket. Input differences of 5
        # must survive in correct order, not round/truncate to one value.
        for left, right in ((0, 33), (33 * WIDTH, 33 * WIDTH + 33)):
            a = y_start + left
            b = y_start + right
            if not (original[a] >> 4 == original[b] >> 4
                    and original[a] < original[b]):
                raise ValueError("12-bit source does not contain the specified fine steps")
            if recovered[a] >= recovered[b]:
                raise ValueError("12-bit ProRes lost a sub-8-bit luma distinction")
            preserved_pairs += 1

    return {
        "status": "real_12bit_yuv444p_roundtrip_verified",
        "source_format": "yuv444p12le",
        "decoded_format": "yuv444p12le",
        "source_precision_bits": BIT_DEPTH,
        "frames": FRAMES,
        "dimensions": [WIDTH, HEIGHT],
        "component_sample_count": SAMPLE_COUNT,
        "maximum_permitted_error_12bit": MAX_ABSOLUTE_ERROR_12BIT,
        "maximum_observed_error_by_frame_12bit": max_by_frame,
        "maximum_observed_error_12bit": max(errors),
        "mean_absolute_error_12bit": round(sum(errors) / len(errors), 4),
        "sub_8bit_luma_distinctions_preserved": preserved_pairs,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "decoded_frame_sha256": frame_hashes,
        "video_binary_uploaded": False,
        "vhs_node_12bit_input_qualified": False,
    }


def qualify_genuine_12bit_ffmpeg() -> dict:
    """Encode/decode a real 12-bit source with the CI-pinned FFmpeg binary."""
    from imageio_ffmpeg import get_ffmpeg_exe

    ffmpeg = get_ffmpeg_exe()
    source = make_genuine_12bit_yuv444p_source()
    with tempfile.TemporaryDirectory(prefix="osf_true12bit_") as scratch:
        output = Path(scratch) / "synthetic_12bit_prores4444.mov"
        encoder = [
            ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
            "-f", "rawvideo", "-pixel_format", "yuv444p12le",
            "-video_size", "64x64", "-framerate", "2",
            "-i", "pipe:0", "-an", "-c:v", "prores_ks",
            "-profile:v", "4", "-pix_fmt", "yuv444p12le",
            "-qscale:v", "1", str(output),
        ]
        subprocess.run(
            encoder, input=source, capture_output=True,
            check=True, timeout=30,
        )
        encoded = output.read_bytes()
        if not 12 <= len(encoded) <= 2_000_000 or encoded[4:8] != b"ftyp":
            raise ValueError("12-bit ProRes encoder produced invalid MOV")

        decoder = [
            ffmpeg, "-hide_banner", "-nostdin", "-i", str(output),
            "-map", "0:v:0", "-fps_mode", "passthrough",
            "-pix_fmt", "yuv444p12le", "-f", "rawvideo", "pipe:1",
        ]
        process = subprocess.run(
            decoder, capture_output=True, check=True, timeout=30,
        )
        stream = process.stderr.decode("utf-8", "replace")
        if not re.search(r"Video:\s+prores\s+\(4444\)\s", stream, re.IGNORECASE):
            raise ValueError("Genuine 12-bit source did not encode as ProRes 4444")
        if not re.search(r"\byuv444p12le\b", stream):
            raise ValueError("Genuine 12-bit ProRes stream storage is not YUV444 12-bit")
        result = validate_genuine_12bit_roundtrip(source, process.stdout)
        return {
            **result,
            "codec": "prores_ks",
            "profile": "4444",
            "storage_pixel_format": "yuv444p12le",
            "encoded_mov_size_bytes": len(encoded),
            "encoded_mov_sha256": hashlib.sha256(encoded).hexdigest(),
        }
