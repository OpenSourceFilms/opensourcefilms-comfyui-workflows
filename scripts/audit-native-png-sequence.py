#!/usr/bin/env python3
"""Read-only validation and hashing of native ComfyUI PNG sequences."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import zlib

MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_FILE = 256 * 1024 * 1024
VALID = {(0, 1), (0, 2), (0, 4), (0, 8), (0, 16), (2, 8), (2, 16),
         (3, 1), (3, 2), (3, 4), (3, 8), (4, 8), (4, 16), (6, 8), (6, 16)}


class AuditError(ValueError):
    pass


def inspect_png(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise AuditError(f"{path.name}: not a regular file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        with os.fdopen(fd, "rb", closefd=True) as f:
            fd = -1
            before = os.fstat(f.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE:
                raise AuditError(f"{path.name}: not regular or exceeds file size limit")
            b = f.read(MAX_FILE + 1)
            after = os.fstat(f.fileno())
            identity = lambda st: (st.st_ino, st.st_dev, st.st_size, st.st_mtime_ns)
            if identity(before) != identity(after) or len(b) != before.st_size:
                raise AuditError(f"{path.name}: changed while reading")
    finally:
        if fd >= 0:
            os.close(fd)
    if not b.startswith(MAGIC):
        raise AuditError(f"{path.name}: invalid PNG signature")
    pos, header, idat = len(MAGIC), None, 0
    for _ in range(100000):
        if len(b) - pos < 12:
            raise AuditError(f"{path.name}: truncated PNG")
        length, kind = struct.unpack_from(">I4s", b, pos)
        pos += 8
        if length > MAX_FILE or length + 4 > len(b) - pos:
            raise AuditError(f"{path.name}: invalid/oversized PNG chunk")
        content = b[pos:pos + length]
        expected_crc = struct.unpack_from(">I", b, pos + length)[0]
        if zlib.crc32(kind + content) & 0xFFFFFFFF != expected_crc:
            raise AuditError(f"{path.name}: CRC mismatch")
        pos += length + 4
        if header is None and kind != b"IHDR":
            raise AuditError(f"{path.name}: IHDR not first")
        if kind == b"IHDR":
            if header is not None or length != 13:
                raise AuditError(f"{path.name}: malformed IHDR")
            w, h, depth, colour, compression, filtering, interlace = struct.unpack(">IIBBBBB", content)
            if not w or not h or compression or filtering or interlace not in (0, 1) or (colour, depth) not in VALID:
                raise AuditError(f"{path.name}: invalid PNG dimensions/colour")
            header = (w, h, depth, colour, interlace)
        elif kind == b"IDAT":
            idat += 1
        elif kind == b"IEND":
            if length or not idat or pos != len(b):
                raise AuditError(f"{path.name}: invalid IEND or trailing data")
            break
    else:
        raise AuditError(f"{path.name}: too many PNG chunks")
    return {"name": path.name, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
            "width": header[0], "height": header[1], "bit_depth": header[2],
            "colour_type": header[3], "interlace": header[4]}


def _contiguous_numbered_frames(files: list[Path]) -> tuple[int, int]:
    """Check one consistent ASCII-decimal frame index per filename.

    Opt-in only: arbitrary PNG collections and diagnostic frame subsets may
    deliberately omit indices. For a numbered shot delivery, count alone is
    insufficient: N files can contain a gap and an extra later frame.
    """
    pattern = re.compile(
        r"(?P<prefix>[^0-9]*)(?P<index>[0-9]+)(?P<suffix>[^0-9]*[.]png)",
        re.IGNORECASE,
    )
    expected_parts = None
    first = None
    previous = None
    for path in files:
        match = pattern.fullmatch(path.name)
        if not match:
            raise AuditError(
                f"{path.name}: --contiguous requires exactly one ASCII frame-number run "
                "in a .png filename"
            )
        prefix, digits, suffix = match.group("prefix", "index", "suffix")
        parts = (prefix, suffix, len(digits))
        if expected_parts is None:
            expected_parts = parts
        elif parts != expected_parts:
            raise AuditError(f"{path.name}: inconsistent frame prefix, suffix or padding")
        index = int(digits)
        if previous is not None and index != previous + 1:
            raise AuditError(
                f"{path.name}: non-contiguous frame indices: "
                f"expected {previous + 1:0{len(digits)}d}, found {digits}"
            )
        if first is None:
            first = index
        previous = index
    return first, previous


def audit(directory: Path, pattern: str, count: int, width=None, height=None, depth=None,
          contiguous: bool = False):
    if not pattern or "/" in pattern or "\\" in pattern or ".." in pattern:
        raise AuditError("unsafe filename glob")
    if count < 1 or count > 100000:
        raise AuditError("count must be 1..100000")
    if directory.is_symlink() or not directory.is_dir():
        raise AuditError("directory missing or symlink")
    files = sorted(directory.glob(pattern))
    if len(files) != count:
        raise AuditError(f"frame count mismatch: expected {count}, found {len(files)}")
    frame_indices = _contiguous_numbered_frames(files) if contiguous else None
    entries = []
    for f in files:
        if f.parent != directory:
            raise AuditError("nested file refused")
        item = inspect_png(f)
        for field, target in (("width", width), ("height", height), ("bit_depth", depth)):
            if target is not None and item[field] != target:
                raise AuditError(f"{f.name}: {field} expected {target}, got {item[field]}")
        entries.append(item)
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result = {"status": "PASS", "schema": "osf.native_sequence_audit.v1",
              "frame_count": len(entries), "manifest_sha256": digest, "frames": entries,
              "no_image_modification": True}
    if frame_indices is not None:
        result.update({"contiguous_indices_verified": True,
                       "first_frame_index": frame_indices[0],
                       "last_frame_index": frame_indices[1]})
    return result



MAX_REFERENCE_BYTES = 32 * 1024 * 1024


def verify_reference(current: dict, path: Path) -> dict:
    """Compare new source-byte identity to a previously saved audit report.

    A reference JSON is evidence only if stored in a trusted location;
    this checks its internal hash, not its signature or provenance.
    """
    if path.is_symlink() or not path.is_file():
        raise AuditError("reference report missing or symlink")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        with os.fdopen(fd, "rb", closefd=True) as f:
            fd = -1
            before = os.fstat(f.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_REFERENCE_BYTES:
                raise AuditError("reference report too large or not regular")
            payload = f.read(MAX_REFERENCE_BYTES + 1)
            after = os.fstat(f.fileno())
            identity = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns)
            if identity(before) != identity(after) or len(payload) != before.st_size:
                raise AuditError("reference report changed during read")
    finally:
        if fd >= 0:
            os.close(fd)
    try:
        saved = json.loads(payload)
    except (UnicodeError, ValueError) as exc:
        raise AuditError("reference report invalid JSON") from exc
    if (not isinstance(saved, dict) or saved.get("status") != "PASS"
            or saved.get("schema") != current["schema"]):
        raise AuditError("reference report schema or status mismatch")
    entries = saved.get("frames")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 100000:
        raise AuditError("reference report has invalid frame list")
    check = hashlib.sha256(json.dumps(
        entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if (saved.get("manifest_sha256") != check
            or saved.get("frame_count") != len(entries)):
        raise AuditError("reference report has inconsistent manifest identity")
    if (saved["frame_count"] != current["frame_count"]
            or saved["manifest_sha256"] != current["manifest_sha256"]):
        different = next((
            new["name"] for old, new in zip(entries, current["frames"])
            if old != new
        ), None)
        label = different or "different frame count/metadata"
        raise AuditError(f"source sequence differs from reference: {label}")
    return {**current, "reference_match": True}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    p.add_argument("--pattern", default="*.png")
    p.add_argument("--count", required=True, type=int)
    p.add_argument("--contiguous", action="store_true",
                   help="require fixed-width consecutive numeric .png frame names")
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--bit-depth", type=int)
    p.add_argument("--reference", type=Path, help="previously saved audit JSON to verify against")
    a = p.parse_args(argv)
    try:
        report = audit(a.directory, a.pattern, a.count, a.width, a.height, a.bit_depth,
                       contiguous=a.contiguous)
        if a.reference is not None:
            report = verify_reference(report, a.reference)
        print(json.dumps(report, sort_keys=True))
        return 0
    except (AuditError, OSError, struct.error) as e:
        print(json.dumps({"status": "FAIL", "error": str(e)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
