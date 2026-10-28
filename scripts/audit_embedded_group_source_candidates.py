#!/usr/bin/env python3
"""Read-only candidate upstream source inventory for embedded mm_upscale nodes.

All revisions/source paths/licence identifiers are a dated source-review
snapshot. No live upstream fetch occurs, and a source-string match does NOT
prove custom-node registration, dependency closure, UI group import, runtime
compatibility or commercial clearance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from audit_embedded_group_provider_dependencies import audit as provider_gap_audit

ROOT = Path(__file__).resolve().parents[1]
REVIEW_DATE = "2026-10-28"

# Exact source snapshots and the files actually inspected on 28 October.
# A provider source module's containing text is weaker than runtime registration.
# Key: exported properties.cnr_id. Values: exported class ID -> reviewed source path.
REVIEWED = {
    "comfyui-custom-scripts": {
        "repository": "pythongosssss/ComfyUI-Custom-Scripts",
        "commit": "609f3afaa74b2f88ef9ce8d939626065e3247469",
        "license_file": "LICENSE",
        "license": "MIT",
        "classes": {
            "MathExpression|pysssss": "py/math_expression.py",
            "StringFunction|pysssss": "py/string_function.py",
        },
    },
    "comfyui-easy-use": {
        "repository": "yolain/ComfyUI-Easy-Use",
        "commit": "b0b47ca1372117fce575d9e744655344ebff6bef",
        "license_file": "LICENSE",
        "license": "GPL-3.0",
        "classes": {
            "easy batchAnything": "py/nodes/logic.py",
            "easy boolean": "py/nodes/logic.py",
            "easy compare": "py/nodes/logic.py",
            "easy forLoopEnd": "py/nodes/logic.py",
            "easy forLoopStart": "py/nodes/logic.py",
            "easy ifElse": "py/nodes/logic.py",
            "easy imageSave": "py/nodes/image.py",
            "easy int": "py/nodes/logic.py",
        },
    },
    "comfyui-kjnodes": {
        "repository": "kijai/ComfyUI-KJNodes",
        "commit": "2371136d2fa6fd0914e514cd99b36dabe5db9adf",
        "license_file": "LICENSE",
        "license": "GPL-3.0",
        "classes": {
            "ImageBatchJoinWithTransition": "nodes/image_nodes.py",
            "ImageBatchMulti": "nodes/image_nodes.py",
            "ImagePass": "nodes/image_nodes.py",
        },
    },
    "comfyui_essentials": {
        "repository": "cubiq/ComfyUI_essentials",
        "commit": "9d9f4bedfc9f0321c19faf71855e228c93bd0dc9",
        "license_file": "LICENSE",
        "license": "MIT",
        "classes": {
            "ImageFromBatch+": "image.py",
            "SimpleMathSlider+": "misc.py",
        },
    },
}


def collect(root: Path = ROOT) -> dict:
    """Ensure reviewed IDs still match the actual embedded export and lock."""
    graph_audit = provider_gap_audit(root)
    rows_by_hint = {
        row["exported_cnr_id"]: row
        for row in graph_audit["exported_external_provider_hints"]
    }
    if set(rows_by_hint) != set(REVIEWED):
        raise ValueError("Unreviewed/missing embedded extension-provider hint")
    result = []
    for hint, source in sorted(REVIEWED.items()):
        row = rows_by_hint[hint]
        actual = set(row["distinct_classes"])
        reviewed = set(source["classes"])
        if actual != reviewed:
            raise ValueError("Embedded class inventory differs from reviewed source candidates: " + hint)
        commit = source["commit"]
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Invalid candidate commit: " + hint)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source["repository"]):
            raise ValueError("Invalid candidate repository: " + hint)
        if source["license"] not in ("MIT", "GPL-3.0"):
            raise ValueError("Unreviewed candidate licence: " + hint)
        paths = source["classes"]
        if any(not path.endswith(".py") or ".." in path or path.startswith("/")
               for path in paths.values()):
            raise ValueError("Invalid source path: " + hint)
        result.append({
            "exported_provider_hint": hint,
            "canonical_manifest_name": row["expected_manifest_dependency"],
            "currently_declared_in_canonical_manifest": row["declared_in_mm_upscale_manifest"],
            "currently_commit_pinned_in_canonical_manifest": row["manifest_commit_pinned"],
            "reviewed_repository": source["repository"],
            "reviewed_commit_candidate": commit,
            "reviewed_license_file": source["license_file"],
            "reviewed_license_id": source["license"],
            "exported_instances": row["internal_instances"],
            "reviewed_exact_class_source_paths": dict(sorted(paths.items())),
            "reviewed_class_count": len(paths),
            "snapshot_source_text_examined": True,
            "snapshot_checked_live_in_this_run": False,
            "licence_obligations_cleared": False,
            "registered_or_import_qualified": False,
            "exact_source_compatible_with_export": False,
            "nested_requirements_reviewed": False,
        })
    return {
        "schema": "osf-mm-upscale-upstream-candidate-snapshot-v1",
        "reviewed_on": REVIEW_DATE,
        "workflow": graph_audit["workflow"],
        "workflow_source_sha256": graph_audit["source_sha256"],
        "external_provider_hints": len(result),
        "reviewed_external_classes": sum(x["reviewed_class_count"] for x in result),
        "candidate_sources": result,
        "manifest_mutated": False,
        "weights_downloaded": False,
        "commercial_rights_cleared": False,
        "embedded_group_runtime_qualified": False,
        "eleven_workflows_qualified": False,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    report = collect()
    if args.output is not None:
        path = args.output
        if path.is_symlink() or path.exists():
            p.error("Output already exists or is a symlink")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
