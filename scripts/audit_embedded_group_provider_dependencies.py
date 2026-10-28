#!/usr/bin/env python3
"""Read-only exported-subgraph extension provenance vs canonical lock.

This is a source-only dependency *gap* preflight. Exported cnr_id/ver/aux_id
are UI metadata and are not installed-source, version or licence proof.
The report does not contain user prompts, widget values, media or credentials.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
GRAPH = "workflows/commercial-compatible/mm_upscale_video_workflow.json"
UUID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
TOKEN = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")
VERSION = re.compile(r"^[A-Za-z0-9_.+-]{1,80}$")

# Attribution from export metadata is only a hint, not proof the named
# upstream source actually defines a specific class in the selected version.
PROVIDER_HINT_TO_MANIFEST_NAME = {
    "comfyui-custom-scripts": "ComfyUI-Custom-Scripts (pysssss)",
    "comfyui-easy-use": "ComfyUI-Easy-Use",
    "comfyui-kjnodes": "ComfyUI-KJNodes",
    "comfyui_essentials": "ComfyUI_essentials",
}
CORE_HINT = "comfy-core"


def _manifest_names(lock: str) -> dict[str, dict[str, object]]:
    """Extract exactly the named mm_upscale dependency block, never another."""
    header = GRAPH + ":"
    if lock.count("\n" + header + "\n") != 1:
        raise ValueError("Expected one exact canonical mm_upscale lock section")
    block = lock.split("\n" + header + "\n", 1)[1].split("\nworkflows/", 1)[0]
    if "\n  dependencies:\n" not in "\n" + block:
        raise ValueError("Canonical block missing dependencies")
    names = {}
    name = None
    for line in block.splitlines():
        if line.startswith("    - name: "):
            name = line.partition(": ")[2].strip()
            if not name or name in names:
                raise ValueError("Blank/duplicate dependency in manifest")
            names[name] = {"commit_pinned": False, "version_pinned": False}
        elif name and line.startswith("      commit: "):
            commit = line.partition(": ")[2].strip()
            if not re.fullmatch(r"[0-9a-f]{40}", commit):
                raise ValueError("Invalid canonical dependency SHA")
            names[name]["commit_pinned"] = True
        elif name and line.startswith("      version: "):
            version = line.partition(": ")[2].strip()
            if not VERSION.fullmatch(version):
                raise ValueError("Malformed canonical dependency version")
            names[name]["version_pinned"] = True
    if not names:
        raise ValueError("No dependencies in manifest profile")
    return names


def reconcile(graph: object, lock: str, *, graph_sha256: str) -> dict:
    """Inventory all 89 embedded instances with explicit manifest gaps."""
    if not isinstance(graph, dict):
        raise ValueError("Malformed workflow export")
    defs = graph.get("definitions")
    if not isinstance(defs, dict) or not isinstance(defs.get("subgraphs"), list):
        raise ValueError("Missing embedded subgraphs")
    groups = defs["subgraphs"]
    if not groups:
        raise ValueError("No embedded group definitions")
    canonical = _manifest_names(lock)
    providers = defaultdict(lambda: {"classes": set(), "instances": 0, "versions": set()})
    class_owners = {}
    group_summaries = []
    all_classes = set()
    total = 0
    for group in groups:
        if not isinstance(group, dict) or not UUID.fullmatch(str(group.get("id", ""))):
            raise ValueError("Bad embedded group UUID")
        nodes = group.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            raise ValueError("Empty/bad embedded group")
        group_classes = set()
        for node in nodes:
            if not isinstance(node, dict):
                raise ValueError("Malformed embedded node")
            class_id = node.get("type")
            properties = node.get("properties")
            if (not isinstance(class_id, str) or not class_id
                    or len(class_id) > 160 or any(ord(c) < 32 for c in class_id)
                    or not isinstance(properties, dict)):
                raise ValueError("Invalid class or missing provenance properties")
            hint = properties.get("cnr_id")
            version = properties.get("ver")
            if (not isinstance(hint, str) or not TOKEN.fullmatch(hint)
                    or not isinstance(version, str) or not VERSION.fullmatch(version)):
                raise ValueError("Unusable exported provider/version metadata")
            owner = class_owners.setdefault(class_id, hint)
            if owner != hint:
                raise ValueError("One internal class has conflicting provider hints")
            providers[hint]["instances"] += 1
            providers[hint]["classes"].add(class_id)
            providers[hint]["versions"].add(version)
            all_classes.add(class_id)
            group_classes.add(class_id)
            total += 1
        group_summaries.append({
            "group_uuid": group["id"],
            "internal_instances": len(nodes),
            "distinct_internal_classes": len(group_classes),
        })
    if len(group_summaries) != len({g["group_uuid"] for g in group_summaries}):
        raise ValueError("Duplicate embedded group UUID")
    external = []
    unmapped = []
    core = []
    for hint in sorted(providers):
        p = providers[hint]
        row = {
            "exported_cnr_id": hint,
            "internal_instances": p["instances"],
            "distinct_classes": sorted(p["classes"]),
            "exported_version_hints": sorted(p["versions"]),
            "metadata_is_source_or_license_proof": False,
        }
        if hint == CORE_HINT:
            core.append(row)
        elif hint in PROVIDER_HINT_TO_MANIFEST_NAME:
            name = PROVIDER_HINT_TO_MANIFEST_NAME[hint]
            declared = canonical.get(name)
            row.update({
                "expected_manifest_dependency": name,
                "declared_in_mm_upscale_manifest": declared is not None,
                "manifest_commit_pinned": bool(declared and declared["commit_pinned"]),
                "manifest_version_pinned": bool(declared and declared["version_pinned"]),
                "source_and_license_verified_for_exact_export": False,
            })
            external.append(row)
        else:
            unmapped.append(row)

    missing = sorted(r["expected_manifest_dependency"] for r in external
                     if not r["declared_in_mm_upscale_manifest"])
    unpinned = sorted(r["expected_manifest_dependency"] for r in external
                      if r["declared_in_mm_upscale_manifest"]
                      and not r["manifest_commit_pinned"])
    return {
        "schema": "osf-mm-upscale-embedded-provider-manifest-gap-v1",
        "workflow": GRAPH,
        "source_sha256": graph_sha256,
        "embedded_group_definitions": len(group_summaries),
        "embedded_internal_node_instances": total,
        "distinct_internal_class_ids": len(all_classes),
        "groups": group_summaries,
        "exported_external_provider_hints": external,
        "core_provider_hints": core,
        "unmapped_provider_hints": unmapped,
        "external_provider_hints_missing_from_canonical_manifest": missing,
        "declared_but_not_commit_pinned_provider_hints": unpinned,
        "all_external_providers_declared_and_commit_pinned": not missing and not unpinned and not unmapped,
        "source_versions_licenses_runtime_confirmed": False,
        "embedded_groups_executable": False,
        "workflow_gpu_inference_qualified": False,
        "commercial_rights_cleared": False,
    }


def audit(root: Path = ROOT) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Untrusted audit root")
    graph = root / GRAPH
    lock = root / "DEPENDENCIES.lock"
    for file in (graph, lock):
        if file.is_symlink() or not file.is_file():
            raise ValueError("Missing or symlinked canonical source")
    raw = graph.read_bytes()
    return reconcile(
        json.loads(raw), lock.read_text(encoding="utf-8"),
        graph_sha256=hashlib.sha256(raw).hexdigest(),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit()
    if args.output:
        if args.output.is_symlink() or args.output.exists():
            parser.error("Output already exists or is a symlink")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
