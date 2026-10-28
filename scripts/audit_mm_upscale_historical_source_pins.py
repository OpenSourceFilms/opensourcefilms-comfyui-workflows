#!/usr/bin/env python3
"""Offline pin evidence for embedded mm_upscale UI subgraphs.

These are *historical candidates* exported in properties.ver, not new
canonical dependency pins or proof of installed package compatibility.
The upstream commits, root licence texts, and listed registration source
files were reviewed independently on 2026-10-28. CI checks only the
public workflow export against that fixed evidence. No network or imports.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
GRAPH = "workflows/commercial-compatible/mm_upscale_video_workflow.json"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SAFE_VERSION = re.compile(r"[A-Za-z0-9_.+-]{1,80}\Z")

# Source-registration locations were inspected at each exact candidate SHA.
# Neither exported non-SHA versions nor other dependency revisions are resolved.
REVIEWED_PINS = {
    "comfyui-custom-scripts": {
        "upstream": "pythongosssss/ComfyUI-Custom-Scripts",
        "sha": "f2838ed5e59de4d73cde5c98354b87a8d3200190",
        "root_license": "MIT",
        "class_source": {
            "MathExpression|pysssss": "py/math_expression.py",
            "StringFunction|pysssss": "py/string_function.py",
        },
    },
    "comfyui-easy-use": {
        "upstream": "yolain/ComfyUI-Easy-Use",
        "sha": "8ecc929cd41cf0f7ef6fcc45d4bbc5729c6f287f",
        "root_license": "GPL-3.0",
        "class_source": {
            "easy compare": "py/nodes/logic.py",
            "easy int": "py/nodes/logic.py",
            "easy ifElse": "py/nodes/logic.py",
            "easy forLoopStart": "py/nodes/logic.py",
            "easy batchAnything": "py/nodes/logic.py",
            "easy forLoopEnd": "py/nodes/logic.py",
            "easy boolean": "py/nodes/logic.py",
            "easy imageSave": "py/nodes/image.py",
        },
    },
    "comfyui-kjnodes": {
        "upstream": "kijai/ComfyUI-KJNodes",
        "sha": "468fcc86f0b29e79a8510e8239eb15714d6747a6",
        "root_license": "GPL-3.0",
        "class_source": {
            "ImageBatchJoinWithTransition": "__init__.py",
            "ImageBatchMulti": "__init__.py",
            "ImagePass": "__init__.py",
        },
    },
    "comfyui_essentials": {
        "upstream": "cubiq/ComfyUI_essentials",
        "sha": "9d9f4bedfc9f0321c19faf71855e228c93bd0dc9",
        "root_license": "MIT",
        "class_source": {
            "ImageFromBatch+": "image.py",
            "SimpleMathSlider+": "misc.py",
        },
    },
}


def reconcile(graph: object, *, source_sha256: str) -> dict:
    """Fail on pin/class drift while retaining every explicit non-acceptance."""
    if not isinstance(graph, dict) or not isinstance(source_sha256, str):
        raise ValueError("Invalid mm_upscale exported workflow")
    definitions = graph.get("definitions")
    groups = definitions.get("subgraphs") if isinstance(definitions, dict) else None
    if not isinstance(groups, list) or len(groups) != 4:
        raise ValueError("Expected exactly four reviewed embedded group definitions")
    hints = {}
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("nodes"), list):
            raise ValueError("Malformed embedded group")
        for node in group["nodes"]:
            if not isinstance(node, dict) or not isinstance(node.get("properties"), dict):
                raise ValueError("Malformed embedded node provenance")
            kind = node.get("type")
            provider = node["properties"].get("cnr_id")
            version = node["properties"].get("ver")
            if (not isinstance(kind, str) or not isinstance(provider, str)
                    or not isinstance(version, str) or not SAFE_VERSION.fullmatch(version)):
                raise ValueError("Unusable exported provider, class or version")
            if provider == "comfy-core":
                continue
            if provider not in REVIEWED_PINS:
                raise ValueError("Unreviewed embedded upstream provider: " + provider)
            row = hints.setdefault(provider, {"classes": set(), "versions": set(), "instances": 0})
            row["classes"].add(kind)
            row["versions"].add(version)
            row["instances"] += 1
    if set(hints) != set(REVIEWED_PINS):
        raise ValueError("Missing reviewed embedded upstream provider")
    report = []
    for provider, reviewed in sorted(REVIEWED_PINS.items()):
        observed = hints[provider]
        reviewed_sha = reviewed["sha"]
        if not SHA40.fullmatch(reviewed_sha):
            raise ValueError("Reviewed upstream SHA malformed")
        exported_shas = {v for v in observed["versions"] if SHA40.fullmatch(v)}
        if exported_shas != {reviewed_sha}:
            raise ValueError("Exported historical source commit differs: " + provider)
        if observed["classes"] != set(reviewed["class_source"]):
            raise ValueError("Exported classes differ from reviewed upstream source: " + provider)
        report.append({
            "exported_provider_id": provider,
            "upstream_repository": reviewed["upstream"],
            "candidate_source_commit": reviewed_sha,
            "root_license_file_reviewed": reviewed["root_license"],
            "exported_internal_instances": observed["instances"],
            "reviewed_class_source_files": dict(sorted(reviewed["class_source"].items())),
            "other_exported_version_aliases_unverified": sorted(
                v for v in observed["versions"] if not SHA40.fullmatch(v)
            ),
            "source_commit_and_class_strings_reviewed": True,
            "installed_runtime_nodes_verified": False,
            "version_aliases_mapped_to_commit": False,
            "nested_dependencies_verified": False,
            "commercial_distribution_obligations_cleared": False,
        })
    return {
        "schema": "osf-mm-upscale-historical-upstream-pins-v1",
        "workflow": GRAPH,
        "workflow_sha256": source_sha256,
        "reviewed_date": "2026-10-28",
        "source_candidate_providers": report,
        "candidate_source_pins_count": len(report),
        "reviewed_external_node_class_ids": sum(
            len(entry["reviewed_class_source_files"]) for entry in report
        ),
        "reviewed_external_node_instances": sum(
            entry["exported_internal_instances"] for entry in report
        ),
        "canonical_manifest_modified": False,
        "github_commit_resolution_repeated_in_ci": False,
        "full_nested_dependency_compatibility_qualified": False,
        "group_execution_qualified": False,
        "rights_cleared": False,
        "gpu_model_workflows_qualified": False,
    }


def audit(root: Path = ROOT) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Unsafe audit root")
    file = root / GRAPH
    if file.is_symlink() or not file.is_file():
        raise ValueError("Missing or symlinked exported workflow")
    raw = file.read_bytes()
    return reconcile(json.loads(raw), source_sha256=hashlib.sha256(raw).hexdigest())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit()
    if args.output:
        if args.output.exists() or args.output.is_symlink():
            parser.error("Refusing to overwrite an output or symlink")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
