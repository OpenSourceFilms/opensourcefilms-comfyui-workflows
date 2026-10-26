#!/usr/bin/env python3
"""Prepare or verify a bounded RunPod workflow bundle without network or install.

Stages exactly 11 explicitly approved OSF workflow graphs and sidecars.
This does not install ComfyUI, custom nodes, models or Python requirements.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "runpod" / "commercial-compatible"
MANIFEST = ROOT / "DEPENDENCIES.lock"
ALLOWED = frozenset({
    "gimm_sgm_vfi_video_interpolate",
    "mm_upscale_video_workflow",
    "sam3_custompkg_probe",
    "step4_5_sam3_mask",
    "step6_animation_mode",
    "step7_replacement_mode",
    "video_wan2_2_14B_flf2v",
    "video_wan2_2_14B_fmlf2v",
    "video_wan2_2_14B_i2v",
    "video_wan_vace_14B_v2v",
    "wan22_fmlf_first_middle_last_frame",
})
BUNDLED_DOCS = (
    ("LICENSE", ROOT / "LICENSE"),
    ("THIRD_PARTY_LICENSES.md", ROOT / "THIRD_PARTY_LICENSES.md"),
    ("START_HERE.md", PROFILE / "README.md"),
)
HEADING = re.compile(r"(?m)^(workflows/(?:commercial-compatible|research-only)/[A-Za-z0-9_.-]+\.json):\s*$")
STATUS = re.compile(r"(?m)^  commercial_status:\s*([a-z-]+)\s*$")
DEP_NAME = re.compile(r"(?m)^    - name:\s*(.+?)\s*$")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regular_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or symlinked source: " + str(path))
    return path.read_bytes()


def manifest_entries(text: str | None = None) -> dict[str, dict]:
    if text is None:
        text = regular_file(MANIFEST).decode("utf-8")
    matches = list(HEADING.finditer(text))
    result = {}
    for index, match in enumerate(matches):
        name = match.group(1)
        if name in result:
            raise ValueError("Duplicate manifest declaration: " + name)
        block = text[match.end():matches[index + 1].start()
                     if index + 1 < len(matches) else len(text)]
        statuses = STATUS.findall(block)
        if len(statuses) != 1:
            raise ValueError("Expected one workflow status for " + name)
        result[name] = {
            "commercial_status": statuses[0],
            "dependencies": DEP_NAME.findall(block),
            "source_block": block.rstrip(),
        }
    if not result:
        raise ValueError("No manifest entries")
    return result


def choose_files() -> tuple[dict[str, bytes], dict[str, dict]]:
    entries = manifest_entries()
    selected = {
        path: entry for path, entry in entries.items()
        if entry["commercial_status"] == "commercial-compatible"
    }
    names = {Path(path).stem for path in selected}
    if names != ALLOWED or len(selected) != len(ALLOWED):
        raise ValueError("Commercial manifest differs from explicitly approved 11-workflow profile")
    if any(not path.startswith("workflows/commercial-compatible/") for path in selected):
        raise ValueError("A non-commercial graph was labelled as commercial-compatible")
    files = {}
    for path in sorted(selected):
        json_path = ROOT / path
        side_path = json_path.with_suffix(".md")
        raw = regular_file(json_path)
        try:
            doc = json.loads(raw)
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Invalid graph JSON: " + path) from exc
        is_ui = (isinstance(doc, dict) and isinstance(doc.get("nodes"), list)
                 and isinstance(doc.get("links"), list))
        is_api = (isinstance(doc, dict) and bool(doc)
                  and all(isinstance(v, dict) and isinstance(v.get("class_type"), str)
                          and v["class_type"] for v in doc.values()))
        if not (is_ui or is_api):
            raise ValueError("Not a ComfyUI UI/API graph: " + path)
        side = regular_file(side_path)
        side_text = side.decode("utf-8")
        if not re.search(r"(?m)^source:\s*" + re.escape(path) + r"\s*$", side_text):
            raise ValueError("Source reference missing from sidecar: " + path)
        if not re.search(r"(?m)^commercial_status:\s*commercial-compatible\s*$", side_text):
            raise ValueError("Sidecar not commercial-compatible: " + path)
        files[path] = raw
        files[Path(path).with_suffix(".md").as_posix()] = side
    all_graphs = {p.relative_to(ROOT).as_posix() for p in (ROOT / "workflows").rglob("*.json")}
    if all_graphs != set(entries):
        raise ValueError("Workflow files and canonical manifest inventory disagree")
    # Preserve original commit/license/distribution fields for this subset.
    # The five research-only workflow declarations are never staged.
    lock_lines = [
        "# Filtered from DEPENDENCIES.lock: eleven commercial-compatible graphs.",
        "# Source-level rights evidence only; no custom nodes or weights included.",
        "",
    ]
    for name in sorted(selected):
        lock_lines.extend((name + ":", selected[name]["source_block"], ""))
    files["DEPENDENCIES.selected.lock"] = ("\n".join(lock_lines) + "\n").encode("utf-8")
    for name, path in BUNDLED_DOCS:
        files[name] = regular_file(path)
    return files, selected


def plan() -> tuple[dict[str, bytes], dict]:
    files, selected = choose_files()
    info = {
        "profile": "osf-runpod-commercial-workflows-staging-v1",
        "scope": "OSF graph/sidecar staging only; not a RunPod official template or rights clearance",
        "workflow_count": len(selected),
        "source_dependency_manifest_sha256": digest(regular_file(MANIFEST)),
        "workflows": sorted(selected),
        "dependencies_by_workflow": {
            name: selected[name]["dependencies"] for name in sorted(selected)
        },
        "files_sha256": {p: digest(data) for p, data in sorted(files.items())},
        "excluded": "all research-only workflows, model weights, third-party node source",
        "requires_separate_review": "custom node/model licences, compatibility and GPU acceptance",
    }
    return files, info


def stage(destination: Path, files: dict[str, bytes], info: dict) -> None:
    if destination.exists() or destination.is_symlink():
        raise ValueError("Destination already exists, refusing overwrite: " + str(destination))
    parent = destination.parent
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError("Destination parent must be an existing nonsymlink directory")
    if ROOT == parent.resolve() or ROOT in parent.resolve().parents:
        raise ValueError("Stage outside the source checkout, not inside the repository")
    temp = Path(tempfile.mkdtemp(prefix=".osf-commercial-stage-", dir=parent))
    try:
        for name, data in files.items():
            target = temp / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (temp / "BUNDLE_MANIFEST.json").write_text(
            json.dumps(info, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        temp.rename(destination)
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def verify(destination: Path) -> dict:
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("Not a nonsymlink staged directory")
    meta = destination / "BUNDLE_MANIFEST.json"
    info = json.loads(regular_file(meta).decode("utf-8"))
    expected = set(info["files_sha256"]) | {"BUNDLE_MANIFEST.json"}
    actual = {
        p.relative_to(destination).as_posix()
        for p in destination.rglob("*") if p.is_file() or p.is_symlink()
    }
    if actual != expected:
        raise ValueError("Staged files differ from the recorded inventory list")
    selected = info["workflows"]
    if (info["workflow_count"] != 11 or len(selected) != 11
            or {Path(name).stem for name in selected} != ALLOWED
            or any(not name.startswith("workflows/commercial-compatible/") for name in selected)):
        raise ValueError("Staged manifest has unexpected workflow selection")
    required = set(selected)
    required.update(str(Path(name).with_suffix(".md")) for name in selected)
    required.update(("LICENSE", "THIRD_PARTY_LICENSES.md",
                     "START_HERE.md", "DEPENDENCIES.selected.lock"))
    if set(info["files_sha256"]) != required:
        raise ValueError("Staged manifest missing required sidecars or dependency evidence")
    subset = manifest_entries(
        regular_file(destination / "DEPENDENCIES.selected.lock").decode("utf-8")
    )
    if (set(subset) != set(selected)
            or any(row["commercial_status"] != "commercial-compatible"
                   for row in subset.values())
            or {name: subset[name]["dependencies"] for name in sorted(selected)}
               != info["dependencies_by_workflow"]):
        raise ValueError("Filtered dependency manifest differs from selected workflows")
    if not isinstance(info.get("source_dependency_manifest_sha256"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", info["source_dependency_manifest_sha256"]):
        raise ValueError("Missing source dependency manifest digest")
    for name, sha in info["files_sha256"].items():
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("Unsafe recorded path")
        data = regular_file(destination / name)
        if digest(data) != sha:
            raise ValueError("Tampered or mismatched staged file: " + name)
    return info


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--stage", type=Path, help="Create a new output directory. Never overwrite.")
    group.add_argument("--verify", type=Path, help="Read-only verify a previously staged bundle.")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            info = verify(args.verify)
            print("VERIFIED 11-workflow RunPod staging bundle: " + str(args.verify))
        else:
            files, info = plan()
            if args.stage:
                stage(args.stage, files, info)
                verify(args.stage)
                print("STAGED 11-workflow RunPod bundle: " + str(args.stage))
            else:
                print("CHECK PASS: 11 explicitly approved workflows, sidecars and canonical manifest agree")
            print("No ComfyUI install, network access, models or third-party nodes modified")
        return 0
    except (ValueError, OSError, KeyError, TypeError, UnicodeError) as exc:
        print("PROFILE ERROR: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
