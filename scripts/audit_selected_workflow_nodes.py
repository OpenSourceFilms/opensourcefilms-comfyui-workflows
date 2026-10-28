"""Read-only coverage audit: eleven selected graph node IDs vs live /object_info.

A missing class is a *registration gap in this disposable CPU environment*,
not a model/GPU incompatibility finding. Visual/UI metadata and UUID-typed
group/subgraph nodes are separated from ordinary class registration gaps.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "runpod" / "commercial-compatible" / "prepare.py"
GRAPH_DIR = ROOT / "workflows" / "commercial-compatible"
FORK_NATIVE = frozenset({
    "SAM3_Detect", "SAM3_VideoTrack",
    "SCAIL2ColoredMask", "WanSCAILToVideo",
})
# UI annotations and link reroutes, not assertions of executable node support.
UI_DECORATION = frozenset({"MarkdownNote", "Note", "Reroute", "Label (rgthree)"})
UUID_TYPE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _profile_module():
    if PROFILE.is_symlink() or not PROFILE.is_file():
        raise ValueError("Selected workflow profile script missing or symlinked")
    spec = importlib.util.spec_from_file_location("osf_profile_for_coverage", PROFILE)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load selected workflow profile")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_class_ids(document: object) -> tuple[str, Counter]:
    """Validate the shallow UI/API node shape and count exact class IDs."""
    if not isinstance(document, dict):
        raise ValueError("Workflow graph root must be an object")
    if "nodes" in document:
        mode = "ui"
        nodes = document["nodes"]
        if not isinstance(nodes, list):
            raise ValueError("UI graph 'nodes' must be an array")
    else:
        mode = "api"
        if not document:
            raise ValueError("Empty API graph")
        if any(not isinstance(k, str) or not k.isdigit() for k in document):
            raise ValueError("Unexpected API graph node identifier")
        nodes = list(document.values())
    found = Counter()
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("Malformed UI/API graph node")
        key = "type" if mode == "ui" else "class_type"
        value = node.get(key)
        if not isinstance(value, str) or not value or len(value) > 180:
            raise ValueError("Graph node missing a valid class/type")
        found[value] += 1
    if not found:
        raise ValueError("No workflow node classes")
    return mode, found


def load_selected_graphs(root: Path = ROOT) -> dict[str, dict]:
    """Match the canonical manifest and explicit 11-workflow profile exactly."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Missing/symlinked root")
    module = _profile_module()
    selected = {
        path: entry for path, entry in module.manifest_entries().items()
        if entry["commercial_status"] == "commercial-compatible"
    }
    if (len(selected) != 11
            or {Path(path).stem for path in selected} != module.ALLOWED
            or any(not path.startswith("workflows/commercial-compatible/")
                   for path in selected)):
        raise ValueError("11 selected workflow manifest and explicit profile mismatch")
    records = {}
    for relative in sorted(selected):
        file = root / relative
        if file.is_symlink() or not file.is_file():
            raise ValueError("Selected workflow graph missing or symlinked: " + relative)
        raw = file.read_bytes()
        if len(raw) > 4_000_000:
            raise ValueError("Selected workflow graph unexpectedly large")
        try:
            document = json.loads(raw)
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Invalid selected workflow JSON: " + relative) from exc
        graph_format, classes = extract_class_ids(document)
        records[relative] = {
            "graph_format": graph_format,
            "classes": classes,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
        }
    return records


def classify_missing(class_id: str) -> str:
    if class_id in FORK_NATIVE:
        return "documented_scail_sam3_fork_native"
    if class_id in UI_DECORATION:
        return "ui_annotation_or_reroute"
    if UUID_TYPE.fullmatch(class_id):
        return "uuid_typed_group_or_subgraph_unresolved"
    return "other_unregistered"


def coverage_from_registry(graphs: dict[str, dict], live: object) -> dict:
    """Represent accurate per-graph coverage without claiming inference."""
    if not isinstance(live, dict) or not live:
        raise ValueError("Live ComfyUI /object_info inventory required")
    if any(not isinstance(k, str) for k in live):
        raise ValueError("Non-string live class registration")
    results = {}
    seen = set()
    all_present = set()
    all_missing = set()
    class_instance_count = 0
    for path, details in sorted(graphs.items()):
        if not isinstance(details, dict):
            raise ValueError("Malformed selected graph coverage input")
        classes = details["classes"]
        if not isinstance(classes, Counter) or not classes:
            raise ValueError("Missing graph class counter")
        seen.update(classes)
        present = sorted(set(classes) & set(live))
        missing = sorted(set(classes) - set(live))
        all_present.update(present)
        all_missing.update(missing)
        class_instance_count += sum(classes.values())
        categories = {c: classify_missing(c) for c in missing}
        results[path] = {
            "format": details["graph_format"],
            "source_sha256": details["source_sha256"],
            "node_instances": sum(classes.values()),
            "unique_class_ids": len(classes),
            "registered_class_ids": present,
            "missing_class_ids_by_category": {
                category: [c for c in missing if categories[c] == category]
                for category in (
                    "documented_scail_sam3_fork_native",
                    "ui_annotation_or_reroute",
                    "uuid_typed_group_or_subgraph_unresolved",
                    "other_unregistered",
                ) if any(v == category for v in categories.values())
            },
            "registered_unique_classes": len(present),
            "unregistered_unique_classes": len(missing),
            "fully_registered_for_import_only": not missing,
        }
    if len(results) != 11:
        raise ValueError("Coverage must include exactly 11 selected workflows")
    return {
        "status": "live_class_registration_coverage_only",
        "source": "exact_commercial_profile_and_live_loopback_object_info",
        "selected_workflows": len(results),
        "total_node_instances": class_instance_count,
        "unique_class_ids": len(seen),
        "registered_unique_class_ids": len(all_present),
        "unregistered_unique_class_ids": len(all_missing),
        "known_fork_only_missing": sorted(c for c in all_missing if c in FORK_NATIVE),
        "unregistered_other_across_workflows": sorted(
            c for c in all_missing
            if classify_missing(c) == "other_unregistered"
        ),
        "per_workflow": results,
        "all_11_runtime_compatible": False,
        "model_inference_tested": False,
        "license_rights_cleared": False,
        "interpretation": "Missing classes may require other pins, fork or UI-only handling; no weights/inference checked",
    }
