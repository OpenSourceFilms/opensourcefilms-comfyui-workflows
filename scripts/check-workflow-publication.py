#!/usr/bin/env python3
"""Offline release-hygiene checks for public ComfyUI JSON exports.

Detect selected private machine paths, accidental execution-cache metadata,
credentials and personal identifiers. Never echo suspicious source values.
This is a conservative prepublication lint, not a complete secret scanner.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


MAX_BYTES = 16 * 1024 * 1024
MAX_JSON_DEPTH = 256
MAX_JSON_VALUES = 250000
CACHE_KEYS = {"videopreview", "preview_data", "execution_cache", "cached_output"}
CHECKS = {
    "local_posix_path": re.compile(r"(?<![A-Za-z0-9])/(?:home|workspace|mnt|Users|tmp|var)/[^\s\"'<>]+"),
    "local_windows_user_path": re.compile(r"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]"),
    "private_endpoint": re.compile(
        r"(?:https?://)?(?:localhost|127\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"0\.0\.0\.0|169\.254\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
        r"\[(?:::1|f[cd][0-9a-f]{2}:[0-9a-f:]+|fe80:[0-9a-f:]+)\])"
        r"(?::\d+)?(?:/|\b)|https?://[^\s\"']*\.proxy\.runpod\.net", re.I
    ),
    "url_embedded_credentials": re.compile(
        r"\b(?:https?|ftp|sftp)://[^\s/@:?#]+:[^\s/@?#]+@[^\s/?#]+", re.I
    ),
    "credential_pattern": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{35,}|"
        r"sk-[A-Za-z0-9_-]{28,}|hf_[A-Za-z0-9]{24,}|AKIA[A-Z0-9]{16})\b"
    ),
    "nonpublic_storage_or_ping_url": re.compile(
        r"(?:s3|b2)://|https?://(?:hc-ping\.com/[A-Za-z0-9-]{28,}|"
        r"ntfy\.sh/osf-backup-[A-Fa-f0-9]{32})", re.I
    ),
    "local_file_uri": re.compile(r"file:///", re.I),
}
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
PUBLIC_EXAMPLE_DOMAINS = {"example.com", "example.net", "example.org", "opensourcefilms.org"}

# Workflows can embed screenshots without naming a preview/cache property.
# Detect common raster data-URIs and substantial raw PNG/JPEG base64 payloads.
# These are release-hygiene signals, not image decoding or full content inspection.
INLINE_MEDIA_DATA_URI = re.compile(r"data:image/(?:png|jpe?g|gif|webp|bmp|avif);base64,", re.I)
RAW_BASE64_IMAGE = re.compile(r"(?<![A-Za-z0-9+/])(?:iVBORw0KGgo|/9j/)[A-Za-z0-9+/=]{80,}")



def scan_data(data) -> list[dict]:
    issues = []

    def inspect_text(value, location):
        if INLINE_MEDIA_DATA_URI.search(value) or RAW_BASE64_IMAGE.search(value):
            issues.append({"rule": "embedded_image_data", "location": location})
        for rule, pattern in CHECKS.items():
            if pattern.search(value):
                issues.append({"rule": rule, "location": location})
        for match in EMAIL.finditer(value):
            if match.group(1).lower() not in PUBLIC_EXAMPLE_DOMAINS:
                issues.append({"rule": "personal_email", "location": location})

    # Explicit stack and budget: arbitrary nested JSON must fail closed rather
    # than causing RecursionError or unbounded resource consumption.
    stack = [(data, "$", 0)]
    visited = 0
    while stack:
        value, location, depth = stack.pop()
        visited += 1
        if visited > MAX_JSON_VALUES:
            issues.append({"rule": "json_scan_budget_exceeded", "location": location})
            break
        if depth > MAX_JSON_DEPTH:
            issues.append({"rule": "excessive_json_depth", "location": location})
            continue
        if isinstance(value, dict):
            if visited + len(stack) + len(value) > MAX_JSON_VALUES:
                issues.append({"rule": "json_scan_budget_exceeded", "location": location})
                break
            for index, (key, part) in reversed(list(enumerate(value.items()))):
                nested = f"{location}[{index}]"
                if isinstance(key, str):
                    if key.lower() in CACHE_KEYS:
                        issues.append({"rule": "embedded_preview_or_cache", "location": nested})
                    inspect_text(key, nested)
                stack.append((part, nested, depth + 1))
        elif isinstance(value, list):
            if visited + len(stack) + len(value) > MAX_JSON_VALUES:
                issues.append({"rule": "json_scan_budget_exceeded", "location": location})
                break
            for index in range(len(value) - 1, -1, -1):
                stack.append((value[index], f"{location}[{index}]", depth + 1))
        elif isinstance(value, str):
            inspect_text(value, location)
    return issues


def scan_file(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        return {"file": str(path), "issues": [{"rule": "not_regular_file", "location": "$"}]}
    if path.stat().st_size > MAX_BYTES:
        return {"file": str(path), "issues": [{"rule": "oversized_json", "location": "$"}]}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError):
        return {"file": str(path), "issues": [{"rule": "invalid_json", "location": "$"}]}
    return {"file": str(path), "issues": scan_data(data)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    files = []
    for path in args.paths:
        if path.is_dir() and not path.is_symlink():
            files.extend(sorted(path.rglob("*.json")))
        else:
            files.append(path)
    results = [scan_file(p) for p in dict.fromkeys(files)]
    if not results:
        print(json.dumps({"ok": False, "error": "no JSON workflow files"}))
        return 1
    print(json.dumps({"ok": all(not r["issues"] for r in results),
                      "files_scanned": len(results), "results": results},
                     sort_keys=True))
    return 1 if any(r["issues"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
