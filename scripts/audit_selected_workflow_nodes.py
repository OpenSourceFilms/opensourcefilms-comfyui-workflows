"""Live class registration coverage for the *existing* selected-11 source audit.

The canonical source parser/validator is audit-selected-11-node-coverage.py,
merged in PR #25. This supplementary module compares that approved inventory
to the real pinned clean ComfyUI /object_info class registry. No graph is
converted, submitted or executed by this coverage analysis.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE_AUDIT = ROOT / "scripts" / "audit-selected-11-node-coverage.py"


def _source_module(root: Path):
    path = root / "scripts" / SOURCE_AUDIT.name
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing/symlinked canonical selected-workflow auditor")
    spec = importlib.util.spec_from_file_location("osf_selected_11_canonical", path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot import canonical selected-workflow auditor")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_selected_graphs(root: Path = ROOT) -> dict:
    """Reuse the canonical graph preflight, no second inventory/parser."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Missing/symlinked root")
    source = _source_module(root)
    result = source.audit(root=root)
    if (result.get("schema") != "osf-selected-11-node-coverage-v1"
            or result.get("selected_workflow_count") != 11
            or result.get("unique_node_class_count", 0) < 1
            or len(result.get("workflows", [])) != 11):
        raise ValueError("Canonical selected-workflow preflight failed inventory check")
    return result


def classify_missing(class_id: str, source: object = None) -> str:
    """Classify missing IDs conservatively; registered status comes from HTTP."""
    if source is None:
        source = _source_module(ROOT)
    if class_id in source.FORK_NATIVE:
        return "documented_scail_sam3_fork_native"
    if class_id in source.EDITOR_OR_LAYOUT_TYPES:
        return "editor_or_extension_type_unqualified"
    if source.UUID.fullmatch(class_id):
        return "unresolved_group_uuid"
    return "other_unregistered_in_current_cpu_installation"



def embedded_registration_coverage(groups: object, live: dict, source) -> dict | None:
    """Inventory subgraph *internal* classes against actual /object_info.

    Embedded definitions and registered internal classes still do not prove
    a UI subgraph wrapper can be expanded, submitted, or executed. Keep this
    entirely separate from the original 81 top-level type strings.
    """
    if groups is None:
        return None
    if not isinstance(groups, dict):
        raise ValueError("Malformed embedded group source preflight")
    definitions = groups.get("embedded_definitions")
    if not isinstance(definitions, list):
        raise ValueError("Missing source-verified embedded definitions")
    if not isinstance(groups.get("all_referenced_uuid_definitions_embedded"), bool):
        raise ValueError("Missing embedded group definition completeness flag")
    group_results = {}
    registered_total = set()
    unregistered_total = set()
    total_instances = 0
    for definition in definitions:
        if not isinstance(definition, dict):
            raise ValueError("Malformed embedded definition entry")
        group_id = definition.get("group_uuid")
        classes = definition.get("internal_unique_class_ids")
        instances = definition.get("internal_node_instances")
        if (not isinstance(group_id, str) or not source.UUID.fullmatch(group_id)
                or group_id in group_results
                or not isinstance(classes, list) or not classes
                or any(not isinstance(name, str) or not name
                       or len(name) > 200 or any(ord(c) < 32 for c in name)
                       for name in classes)
                or len(classes) != len(set(classes))
                or not isinstance(instances, int) or isinstance(instances, bool)
                or instances < len(classes)
                or definition.get("definition_embedded_in_workflow") is not True):
            raise ValueError("Malformed source-verified embedded internal classes")
        # A UUID-shaped nested group is a UI wrapper, never a proven
        # executable API class even if the live registry contains its string.
        present = sorted(c for c in classes if c in live
                         and not source.UUID.fullmatch(c))
        missing = sorted(set(classes).difference(present))
        registered_total.update(present)
        unregistered_total.update(missing)
        total_instances += instances
        categories = {c: classify_missing(c, source) for c in missing}
        group_results[group_id] = {
            "internal_node_instances": instances,
            "distinct_internal_class_ids": len(classes),
            "registered_internal_class_ids": present,
            "unregistered_internal_class_ids_by_category": {
                category: [c for c in missing if categories[c] == category]
                for category in (
                    "documented_scail_sam3_fork_native",
                    "editor_or_extension_type_unqualified",
                    "unresolved_group_uuid",
                    "other_unregistered_in_current_cpu_installation",
                ) if category in categories.values()
            },
            "registered_distinct_internal_classes": len(present),
            "unregistered_distinct_internal_classes": len(missing),
            "all_internal_classes_registered": not missing,
            "group_wrapper_runtime_executed": False,
            "executable_api_prompt_proven": False,
        }
    if total_instances != groups.get("embedded_internal_node_instances"):
        raise ValueError("Embedded definition instance sum differs from source")
    unique = registered_total | unregistered_total
    if unique != set(groups.get("unique_embedded_internal_class_ids", [])):
        raise ValueError("Embedded source internal class union differs")
    return {
        "embedded_definition_count": len(group_results),
        "all_referenced_uuid_definitions_embedded":
            groups["all_referenced_uuid_definitions_embedded"],
        "internal_node_instances": total_instances,
        "unique_internal_class_ids": len(unique),
        "registered_unique_internal_class_ids": sorted(registered_total),
        "unregistered_unique_internal_class_ids": sorted(unregistered_total),
        "per_embedded_group": dict(sorted(group_results.items())),
        "all_internal_classes_registered": not unregistered_total,
        "embedded_group_runtime_qualified": False,
        "eleven_workflow_api_execution_proven": False,
    }



def coverage_from_registry(source_audit: dict, live: object) -> dict:
    """Compare all 11 real graph IDs with actual loopback /object_info.

    Missing classes are expected and do NOT fail the CPU smoke. They are
    installation diagnostics, not evidence of GPU failure or rights status.
    """
    if not isinstance(live, dict) or not live:
        raise ValueError("Live ComfyUI /object_info inventory required")
    if any(not isinstance(name, str) or not name for name in live):
        raise ValueError("Non-string/empty live registration")
    if (not isinstance(source_audit, dict)
            or source_audit.get("schema") != "osf-selected-11-node-coverage-v1"
            or source_audit.get("selected_workflow_count") != 11
            or len(source_audit.get("workflows", [])) != 11):
        raise ValueError("Coverage must use the canonical 11-workflow source report")
    source = _source_module(ROOT)
    seen = set()
    registered = set()
    missing_all = set()
    node_instances = 0
    entries = {}
    embedded_registered_total = set()
    embedded_missing_total = set()
    embedded_unique_total = set()
    embedded_instances_total = 0
    for entry in source_audit["workflows"]:
        path = entry.get("workflow")
        if (not isinstance(path, str)
                or not re.fullmatch(r"workflows/commercial-compatible/[A-Za-z0-9_.-]+\.json", path)
                or path in entries):
            raise ValueError("Malformed/duplicate canonical selected workflow path")
        categories = entry.get("node_classes_by_status")
        if not isinstance(categories, dict):
            raise ValueError("Canonical source report missing classes")
        all_classes = set()
        for group in categories.values():
            if (not isinstance(group, list) or any(
                    not isinstance(cls, str) or not cls for cls in group)):
                raise ValueError("Malformed canonical class-name list")
            all_classes.update(group)
        if not all_classes or len(all_classes) != entry.get("unique_node_classes"):
            raise ValueError("Canonical graph classes mismatch declared count")
        present = sorted(all_classes.intersection(live))
        absent = sorted(all_classes.difference(live))
        registered.update(present)
        missing_all.update(absent)
        seen.update(all_classes)
        count = entry.get("node_instances")
        if not isinstance(count, int) or count < len(all_classes):
            raise ValueError("Canonical graph node count invalid")
        node_instances += count
        file = ROOT / path
        if file.is_symlink() or not file.is_file():
            raise ValueError("Missing/symlinked selected graph in live coverage")
        sha = hashlib.sha256(file.read_bytes()).hexdigest()
        classification = {c: classify_missing(c, source) for c in absent}
        embedded = embedded_registration_coverage(
            entry.get("embedded_group_definition_preflight"), live, source,
        )
        if embedded is not None:
            embedded_registered_total.update(
                embedded["registered_unique_internal_class_ids"]
            )
            embedded_missing_total.update(
                embedded["unregistered_unique_internal_class_ids"]
            )
            embedded_unique_total.update(
                embedded["registered_unique_internal_class_ids"]
            )
            embedded_unique_total.update(
                embedded["unregistered_unique_internal_class_ids"]
            )
            embedded_instances_total += embedded["internal_node_instances"]
        entries[path] = {
            "graph_format": entry.get("graph_format"),
            "source_sha256": sha,
            "node_instances": count,
            "distinct_node_classes": len(all_classes),
            "registered_class_ids": present,
            "unregistered_class_ids_by_category": {
                cat: [c for c in absent if classification[c] == cat]
                for cat in (
                    "documented_scail_sam3_fork_native",
                    "editor_or_extension_type_unqualified",
                    "unresolved_group_uuid",
                    "other_unregistered_in_current_cpu_installation",
                ) if cat in classification.values()
            },
            "registered_distinct_classes": len(present),
            "unregistered_distinct_classes": len(absent),
            "full_class_registration_in_this_cpu_install": not absent,
            "embedded_group_internal_class_registration": embedded,
        }
    if len(entries) != 11 or len(seen) != source_audit["unique_node_class_count"]:
        raise ValueError("Canonical source coverage total differs")
    return {
        "status": "real_live_cpu_class_registration_coverage_only",
        "source_schema": source_audit["schema"],
        "selected_workflows": 11,
        "total_node_instances": node_instances,
        "unique_graph_class_ids": len(seen),
        "registered_unique_class_ids": len(registered),
        "unregistered_unique_class_ids": len(missing_all),
        "embedded_internal_node_instances": embedded_instances_total,
        "embedded_unique_internal_class_ids": len(embedded_unique_total),
        "embedded_registered_unique_internal_class_ids": sorted(
            embedded_registered_total
        ),
        "embedded_unregistered_unique_internal_class_ids": sorted(
            embedded_missing_total
        ),
        "embedded_groups_runtime_qualified": False,
        "missing_documented_fork_native": sorted(
            c for c in missing_all if c in source.FORK_NATIVE
        ),
        "missing_other_unregistered": sorted(
            c for c in missing_all
            if classify_missing(c, source) ==
            "other_unregistered_in_current_cpu_installation"
        ),
        "per_workflow": dict(sorted(entries.items())),
        "all_11_workflows_executable": False,
        "gpu_inference_tested": False,
        "commercial_rights_cleared": False,
        "interpretation": "This is class registration only, not prompt execution, node input schema or weight compatibility",
    }
