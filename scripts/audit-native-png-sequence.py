#!/usr/bin/env python3
"""Read-only validation and hashing of native ComfyUI PNG sequences."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
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


def audit(directory: Path, pattern: str, count: int, width=None, height=None, depth=None):
    if not pattern or "/" in pattern or "\\" in pattern or ".." in pattern:
        raise AuditError("unsafe filename glob")
    if count < 1 or count > 100000:
        raise AuditError("count must be 1..100000")
    if directory.is_symlink() or not directory.is_dir():
        raise AuditError("directory missing or symlink")
    files = sorted(directory.glob(pattern))
    if len(files) != count:
        raise AuditError(f"frame count mismatch: expected {count}, found {len(files)}")
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
    return {"status": "PASS", "schema": "osf.native_sequence_audit.v1",
            "frame_count": len(entries), "manifest_sha256": digest, "frames": entries,
            "no_image_modification": True}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    p.add_argument("--pattern", default="*.png")
    p.add_argument("--count", required=True, type=int)
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--bit-depth", type=int)
    a = p.parse_args(argv)
    try:
        print(json.dumps(audit(a.directory, a.pattern, a.count, a.width, a.height, a.bit_depth), sort_keys=True))
        return 0
    except (AuditError, OSError, struct.error) as e:
        print(json.dumps({"status": "FAIL", "error": str(e)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
