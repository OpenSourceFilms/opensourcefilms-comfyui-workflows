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

# These five SCAIL/SAM3 node IDs originated in the specialized fork.
# At public Comfy-Org/ComfyUI@08cf0284ff45723aa67841c80cabb0e3cb50c9d7,
# they are also present in comfy_extras/nodes_sam3.py/nodes_scail.py,
# and have passed live /object_info registration in an isolated CPU runner.
# This SOURCE-ONLY preflight does not verify any live class registration,
# model weights, native input schemas, or inference compatibility.
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
        return "sam3_scail_native_class_runtime_unverified"
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
        native = sorted(by_status["sam3_scail_native_class_runtime_unverified"])
        results.append({
            "workflow": path,
            "graph_format": graph_format,
            "node_instances": len(nodes),
            "unique_node_classes": len({n["class"] for n in nodes}),
            "node_class_status_counts": dict(sorted(statuses.items())),
            "node_classes_by_status": {
                k: sorted(v) for k, v in sorted(by_status.items()) if v
            },
            "sam3_scail_native_class_ids": native,
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
        "sam3_scail_historic_native_class_ids": sorted(FORK_NATIVE),
        "unresolved_uuid_node_classes": sorted(c for c in all_unique
                                               if UUID.fullmatch(c)),
        "gpu_inference_verified": False,
        "all_eleven_workflows_executable": False,
        "commercial_rights_verified": False,
        "workflows": results,
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
