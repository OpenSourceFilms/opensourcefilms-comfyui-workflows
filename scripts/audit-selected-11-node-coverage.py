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

# These classes exist in pinned upstream Comfy-Org/ComfyUI (not only a fork):
# 08cf0284ff45723aa67841c80cabb0e3cb50c9d7, nodes_sam3.py/nodes_scail.py.
# Source presence is not evidence of GPU/model compatibility or usage rights.
PINNED_UPSTREAM_SAM_SCAIL = frozenset({
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


def inspect_embedded_subgraphs(graph: dict, nodes: list[dict]) -> dict:
    """Match UUID-shaped UI nodes to definitions actually embedded in export.

    Inspect only class IDs and schema counts. No widget values, prompts, input
    paths, model filenames or arbitrary user-authored graph metadata are output.
    Even matching definitions do NOT prove the group's internal classes are
    installed or that the expanded graph will execute.
    """
    refs = {node["class"] for node in nodes if UUID.fullmatch(node["class"])}
    definitions = graph.get("definitions", {})
    if not isinstance(definitions, dict):
        raise ValueError("UI graph definitions must be an object")
    subgraphs = definitions.get("subgraphs", [])
    if not isinstance(subgraphs, list):
        raise ValueError("Embedded subgraphs must be an array")
    by_id = {}
    for subgraph in subgraphs:
        if not isinstance(subgraph, dict):
            raise ValueError("Malformed embedded subgraph")
        identifier = subgraph.get("id")
        if not isinstance(identifier, str) or not UUID.fullmatch(identifier):
            raise ValueError("Malformed embedded subgraph UUID")
        if identifier in by_id:
            raise ValueError("Duplicate embedded subgraph UUID")
        by_id[identifier] = subgraph
    missing = sorted(refs.difference(by_id))
    resolved = []
    for identifier in sorted(refs.intersection(by_id)):
        subgraph = by_id[identifier]
        internal = subgraph.get("nodes")
        if not isinstance(internal, list) or not internal:
            raise ValueError("Referenced embedded subgraph has no internal nodes")
        internal_types = []
        for node in internal:
            if (not isinstance(node, dict) or
                    not isinstance(node.get("type"), str) or
                    not node["type"] or
                    len(node["type"]) > 200 or
                    any(ord(char) < 32 for char in node["type"])):
                raise ValueError("Malformed embedded internal node class")
            internal_types.append(node["type"])
        internal_uuid = sorted(set(t for t in internal_types if UUID.fullmatch(t)))
        resolved.append({
            "group_uuid": identifier,
            "definition_embedded_in_workflow": True,
            "internal_node_instances": len(internal_types),
            "internal_unique_class_ids": sorted(set(internal_types)),
            "nested_group_uuid_class_ids": internal_uuid,
            "runtime_registered": False,
            "internal_nodes_runtime_qualified": False,
            "executable_api_prompt_proven": False,
        })
    return {
        "referenced_group_uuid_class_ids": sorted(refs),
        "embedded_definitions": resolved,
        "missing_embedded_definition_ids": missing,
        "all_referenced_uuid_definitions_embedded": not missing,
        "embedded_internal_node_instances": sum(
            d["internal_node_instances"] for d in resolved
        ),
        "unique_embedded_internal_class_ids": sorted(set(
            c for d in resolved for c in d["internal_unique_class_ids"]
        )),
        "runtime_qualified": False,
    }


def classify_node(node: dict, cpu_registry: dict[str, str]) -> str:
    """No class is classified as executable from a source hint alone."""
    name = node["class"]
    hint = node["owner_hint"]
    if UUID.fullmatch(name):
        return "unresolved_group_uuid"
    if name in PINNED_UPSTREAM_SAM_SCAIL:
        return "pinned_upstream_sam_scail_class_unverified"
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
        groups = (inspect_embedded_subgraphs(graph, nodes)
                  if graph_format == "ui" else None)
        by_status = defaultdict(set)
        statuses = Counter()
        for node in nodes:
            classification = classify_node(node, cpu)
            by_status[classification].add(node["class"])
            statuses[classification] += 1
            all_unique.add(node["class"])
        summary.update(statuses)
        upstream = sorted(by_status["pinned_upstream_sam_scail_class_unverified"])
        results.append({
            "workflow": path,
            "graph_format": graph_format,
            "node_instances": len(nodes),
            "unique_node_classes": len({n["class"] for n in nodes}),
            "node_class_status_counts": dict(sorted(statuses.items())),
            "node_classes_by_status": {
                k: sorted(v) for k, v in sorted(by_status.items()) if v
            },
            "pinned_upstream_sam_scail_classes": upstream,
            "embedded_group_definition_preflight": groups,
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
        "pinned_upstream_sam_scail_class_names": sorted(PINNED_UPSTREAM_SAM_SCAIL),
        "pinned_upstream_comfyui_commit": "08cf0284ff45723aa67841c80cabb0e3cb50c9d7",
        "unresolved_uuid_node_classes": sorted(c for c in all_unique
                                               if UUID.fullmatch(c)),
        "embedded_group_uuid_classes": sorted(set(
            group_id
            for w in results
            if w["embedded_group_definition_preflight"]
            for group_id in w["embedded_group_definition_preflight"][
                "referenced_group_uuid_class_ids"]
        )),
        "embedded_group_internal_node_instances": sum(
            w["embedded_group_definition_preflight"][
                "embedded_internal_node_instances"]
            for w in results if w["embedded_group_definition_preflight"]
        ),
        "missing_embedded_group_uuid_definitions": sorted(set(
            group_id
            for w in results
            if w["embedded_group_definition_preflight"]
            for group_id in w["embedded_group_definition_preflight"][
                "missing_embedded_definition_ids"]
        )),
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
