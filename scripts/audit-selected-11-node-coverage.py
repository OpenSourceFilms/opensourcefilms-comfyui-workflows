#!/usr/bin/env python3
"""Fail-closed, model-free node class coverage inventory for the selected 11.

Parses BOTH API prompt dictionaries and ComfyUI UI/editor node arrays.
Source hints and clean CPU registrations do NOT mean that an entire workflow
can load, execute, has weights, or is cleared for commercial use.
No media paths, model filenames or prompt text are copied to the report.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "runpod" / "commercial-compatible" / "prepare.py"
CPU_DRIVER = ROOT / "scripts" / "qualify_clean_comfy_cpu.py"
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

# These five node classes were authored as native features of the modified
# SCAIL/SAM3 ComfyUI fork. They are NOT in vanilla ComfyUI by implication.
FORK_NATIVE = frozenset({
    "SAM3_Detect", "SAM3_VideoTrack", "SAM3_TrackPreview",
    "SCAIL2ColoredMask", "WanSCAILToVideo",
})
# Editor-only/extension UI elements still need separate UI compatibility
# checks; this category deliberately does not mean "safe to ignore".
EDITOR_OR_LAYOUT_TYPES = frozenset({
    "Reroute", "MarkdownNote", "Note", "Label (rgthree)",
    "Fast Groups Muter (rgthree)",
})
CORE_API_CANDIDATES = frozenset({
    "LoadImage", "SaveImage", "MaskToImage", "CheckpointLoaderSimple",
    "CLIPTextEncode", "CLIPLoader", "CLIPVisionEncode", "CLIPVisionLoader",
    "VAELoader", "VAEDecode", "UNETLoader", "KSampler",
    "CreateVideo", "SaveVideo", "ModelSamplingSD3",
})


def _load_python(path: Path, module_name: str):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Source-only auditor has a missing/symlinked dependency")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load repository-owned source verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def registered_cpu_classes(driver) -> dict[str, str]:
    """Use actual accepted qualification contract, not an inferred prefix."""
    result = {}
    for package, pins in driver.EXTERNAL_NODE_PINS.items():
        if not re.fullmatch(r"[0-9a-f]{40}", pins["sha"]):
            raise ValueError("Missing exact public CPU registration source pin")
        for name in pins["classes"]:
            if name in result and result[name] != package:
                raise ValueError("Conflicting registered node ownership")
            result[name] = package
    return result


def extract_nodes(graph: dict, graph_format: str) -> list[dict]:
    """Parse exactly the two vetted ComfyUI exported graph representations."""
    result = []
    if graph_format == "ui":
        if not isinstance(graph.get("nodes"), list):
            raise ValueError("Missing UI node array")
        for node in graph["nodes"]:
            if not isinstance(node, dict) or not isinstance(node.get("type"), str):
                raise ValueError("Malformed UI workflow node")
            props = node.get("properties")
            owner = props.get("cnr_id") if isinstance(props, dict) else None
            result.append({"class": node["type"], "owner_hint":
                           owner if isinstance(owner, str) else None})
    elif graph_format == "api":
        if not isinstance(graph, dict):
            raise ValueError("Malformed API graph")
        for node in graph.values():
            if not isinstance(node, dict) or not isinstance(node.get("class_type"), str):
                raise ValueError("Malformed API prompt node")
            result.append({"class": node["class_type"], "owner_hint": None})
    else:
        raise ValueError("Unsupported graph format")
    if not result or any(not node["class"] for node in result):
        raise ValueError("Empty or blank node class in selected workflow")
    return result


def classify_node(node: dict, cpu_registry: dict[str, str]) -> str:
    """No class is classified as executable from a source hint alone."""
    name = node["class"]
    hint = node["owner_hint"]
    if UUID.fullmatch(name):
        return "unresolved_group_uuid"
    if name in FORK_NATIVE:
        return "requires_modified_scail_sam3_fork"
    if name in cpu_registry:
        return "class_registered_on_clean_cpu_only"
    if name in EDITOR_OR_LAYOUT_TYPES:
        return "editor_or_extension_type_unqualified"
    if hint == "comfy-core" or name in CORE_API_CANDIDATES:
        return "core_candidate_not_runtime_verified"
    if hint:
        return "extension_declared_not_runtime_verified"
    return "unmapped_node_not_runtime_verified"


def audit(root: Path = ROOT) -> dict:
    """Use the canonical allowlist, lock status and graph validator in prepare.py."""
    # The real prepare.py enforces all 11 exact allowlisted names and sidecars.
    prepare = _load_python(root / "runpod/commercial-compatible/prepare.py",
                           "osf_approved_bundle_preflight")
    driver = _load_python(root / "scripts/qualify_clean_comfy_cpu.py",
                          "osf_accepted_cpu_class_pins")
    approved, manifest = prepare.choose_files()
    cpu = registered_cpu_classes(driver)
    if len(manifest) != 11:
        raise ValueError("Selected profile must have exactly eleven entries")
    results = []
    summary = Counter()
    all_unique = set()
    for path in sorted(p for p in approved if p.endswith(".json")):
        entry = manifest[path]
        graph_format = entry["format"]
        graph = json.loads(approved[path].decode("utf-8"))
        nodes = extract_nodes(graph, graph_format)
        by_status = defaultdict(set)
        statuses = Counter()
        for node in nodes:
            classification = classify_node(node, cpu)
            by_status[classification].add(node["class"])
            statuses[classification] += 1
            all_unique.add(node["class"])
        summary.update(statuses)
        fork = sorted(by_status["requires_modified_scail_sam3_fork"])
        results.append({
            "workflow": path,
            "graph_format": graph_format,
            "node_instances": len(nodes),
            "unique_node_classes": len({n["class"] for n in nodes}),
            "node_class_status_counts": dict(sorted(statuses.items())),
            "node_classes_by_status": {
                k: sorted(v) for k, v in sorted(by_status.items()) if v
            },
            "requires_modified_scail_sam3_fork": fork,
            "requires_model_weight_and_gpu_acceptance": True,
            "gpu_inference_verified": False,
            "executable_api_prompt_proven": False,
            "commercial_rights_verified": False,
            "manifest_dependency_names": entry["dependencies"],
        })
    if len(results) != 11:
        raise ValueError("Approved profile must contain eleven selected graphs")
    return {
        "schema": "osf-selected-11-node-coverage-v1",
        "scope": "source_only_no_runtime_no_models_no_license_clearance",
        "selected_workflow_count": len(results),
        "workflow_graph_format_counts": dict(sorted(Counter(
            w["graph_format"] for w in results).items())),
        "unique_node_class_count": len(all_unique),
        "node_instance_status_counts": dict(sorted(summary.items())),
        "cpu_registration_contract_classes": dict(sorted(cpu.items())),
        "fork_native_required_classes": sorted(FORK_NATIVE),
        "unresolved_uuid_node_classes": sorted(c for c in all_unique
                                               if UUID.fullmatch(c)),
        "gpu_inference_verified": False,
        "all_eleven_workflows_executable": False,
        "commercial_rights_verified": False,
        "workflows": results,
    }



def compare_live_registry(source_report: dict, object_info: object) -> dict:
    """Compare 11 source graph class names against a real ComfyUI object_info.

    This is *registration-only*: a positive match cannot establish inputs,
    workflow execution, source/weight licences or GPU/model readiness.
    """
    if (not isinstance(source_report, dict)
            or source_report.get("schema") != "osf-selected-11-node-coverage-v1"
            or source_report.get("selected_workflow_count") != 11
            or source_report.get("unique_node_class_count") != 81):
        raise ValueError("Unexpected/unreviewed selected-11 source inventory")
    if not isinstance(object_info, dict):
        raise ValueError("Invalid live ComfyUI object_info response")

    workflows = source_report.get("workflows")
    if not isinstance(workflows, list) or len(workflows) != 11:
        raise ValueError("Selected workflow inventory is incomplete")
    declared = set()
    workflow_types = []
    for item in workflows:
        if not isinstance(item, dict) or not isinstance(item.get("workflow"), str):
            raise ValueError("Malformed selected workflow entry")
        statuses = item.get("node_classes_by_status")
        if not isinstance(statuses, dict):
            raise ValueError("Missing class status inventory")
        names = set()
        for category, values in statuses.items():
            if not isinstance(category, str) or not isinstance(values, list):
                raise ValueError("Malformed selected workflow class statuses")
            if any(not isinstance(v, str) or not v for v in values):
                raise ValueError("Malformed selected workflow node class")
            overlap = names.intersection(values)
            if overlap:
                raise ValueError("Selected class appears in multiple source categories")
            names.update(values)
        if not names or len(names) != item.get("unique_node_classes"):
            raise ValueError("Selected workflow class count differs")
        workflow_types.append((item["workflow"], names, item["graph_format"]))
        declared.update(names)
    if len(declared) != 81:
        raise ValueError("Selected source report node-class union differs")

    required = source_report.get("cpu_registration_contract_classes")
    if not isinstance(required, dict) or len(required) != 6:
        raise ValueError("Missing exact accepted clean CPU registration contract")
    for node_name in required:
        if node_name not in object_info:
            raise ValueError("Accepted pinned clean CPU class is absent: " + node_name)
    forbidden = (
        set(source_report.get("fork_native_required_classes", ()))
        | set(source_report.get("unresolved_uuid_node_classes", ()))
    )
    if (not FORK_NATIVE.issubset(forbidden)
            or any(not UUID.fullmatch(name) for name in
                   source_report.get("unresolved_uuid_node_classes", ()))):
        raise ValueError("Modified-fork/UUID holds lost from source report")
    unexpected = sorted(forbidden.intersection(object_info))
    if unexpected:
        raise ValueError("Unexpected fork/UUID class in vanilla CPU registry: "
                         + unexpected[0])

    registered = sorted(declared.intersection(object_info))
    for node_name in registered:
        entry = object_info[node_name]
        if (not isinstance(entry, dict)
                or not isinstance(entry.get("input"), dict)
                or not isinstance(entry.get("output"), list)):
            raise ValueError("Malformed live class schema: " + node_name)
    unregistered = sorted(declared.difference(object_info))
    per_workflow = []
    for path, names, graph_format in sorted(workflow_types):
        available = sorted(names.intersection(object_info))
        absent = sorted(names.difference(object_info))
        per_workflow.append({
            "workflow": path,
            "graph_format": graph_format,
            "source_class_count": len(names),
            "registered_on_this_cpu": len(available),
            "not_registered_on_this_cpu": len(absent),
            "registered_class_names": available,
            "missing_class_names": absent,
            "all_nodes_registered_on_this_cpu": not bool(absent),
            "executable_api_prompt_proven": False,
            "gpu_inference_verified": False,
        })
    return {
        "schema": "osf-selected-11-live-cpu-registry-delta-v1",
        "scope": "real_clean_cpu_object_info_registration_only",
        "source_class_count": len(declared),
        "registered_selected_class_count": len(registered),
        "unregistered_selected_class_count": len(unregistered),
        "registered_selected_classes": registered,
        "unregistered_selected_classes": unregistered,
        "accepted_pinned_contract_class_count": len(required),
        "fork_native_absent_as_expected": True,
        "unresolved_uuid_absent_as_expected": True,
        "workflow_count": len(per_workflow),
        "workflows": per_workflow,
        "all_selected_workflows_executable": False,
        "gpu_inference_verified": False,
        "commercial_rights_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        if args.output.is_symlink() or args.output.exists():
            parser.error("Coverage report output must be a new regular file")
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
