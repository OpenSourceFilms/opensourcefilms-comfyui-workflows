#!/usr/bin/env python3
"""Source-only graph topology acceptance for the exact four selected API exports.

Does not load ComfyUI, validate custom-node output schemas, execute a graph,
access model weights, or establish licensing/GPU readiness. The selected
eleven inventory comes only from the canonical prepare.py profile.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "runpod" / "commercial-compatible" / "prepare.py"
API_FILES = frozenset({
    "sam3_custompkg_probe",
    "step4_5_sam3_mask",
    "step6_animation_mode",
    "step7_replacement_mode",
})
NODE_ID = re.compile(r"[1-9][0-9]*\Z")
PATH = re.compile(r"workflows/commercial-compatible/[A-Za-z0-9_.-]+\.json\Z")


def audit_api_graph(graph: object) -> dict:
    """Require node-key validity, link referential integrity and a true DAG."""
    if not isinstance(graph, dict) or not graph:
        raise ValueError("API graph must be a nonempty node dictionary")
    if any(not isinstance(key, str) or not NODE_ID.fullmatch(key)
           for key in graph):
        raise ValueError("API graph has invalid node keys")
    for key, node in graph.items():
        if (not isinstance(node, dict)
                or not isinstance(node.get("class_type"), str)
                or not node["class_type"]
                or not isinstance(node.get("inputs"), dict)):
            raise ValueError("Malformed API node or inputs: " + key)
    adjacency = {key: set() for key in graph}
    indegree = {key: 0 for key in graph}
    edge_count = 0
    for dest, node in graph.items():
        for input_name, value in node["inputs"].items():
            if not isinstance(input_name, str) or not input_name:
                raise ValueError("Malformed API input name")
            if not isinstance(value, list):
                continue
            # All array-valued inputs in the exact approved four API exports
            # are [node_id, output_slot] links, never literal arrays. Do not
            # silently skip malformed tuples and falsely certify topology.
            # New literal-array inputs require separate source review.
            if len(value) != 2:
                raise ValueError("Selected API array is not a two-item link")
            upstream, slot = value
            if not isinstance(upstream, str) or NODE_ID.fullmatch(upstream) is None:
                raise ValueError("Selected API link has invalid producer node ID")
            if type(slot) is not int:
                raise ValueError("Selected API link output slot must be an integer")
            if upstream not in graph:
                raise ValueError("API edge references missing upstream node")
            if slot < 0:
                raise ValueError("API edge has negative output slot")
            if upstream == dest:
                raise ValueError("API node directly references its own output")
            edge_count += 1
            if dest not in adjacency[upstream]:
                adjacency[upstream].add(dest)
                indegree[dest] += 1

    queue = deque(sorted(k for k, degree in indegree.items() if degree == 0))
    reached = 0
    longest_path = {key: 0 for key in graph}
    while queue:
        current = queue.popleft()
        reached += 1
        for downstream in sorted(adjacency[current]):
            longest_path[downstream] = max(
                longest_path[downstream], longest_path[current] + 1
            )
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                queue.append(downstream)
    if reached != len(graph):
        raise ValueError("Selected API graph contains a dependency cycle")
    if edge_count < 1:
        raise ValueError("Selected API graph has no upstream links")
    return {
        "node_count": len(graph),
        "link_input_count": edge_count,
        "directed_dependency_pairs": sum(len(x) for x in adjacency.values()),
        "root_node_count": sum(1 for x in graph if longest_path[x] == 0),
        "maximum_dependency_depth": max(longest_path.values()),
        "missing_references": 0,
        "negative_output_slots": 0,
        "cycles_detected": False,
        "topology_verified": True,
        "output_slot_schema_verified": False,
        "installed_provider_completeness_verified": False,
        "executable_prompt_qualified": False,
    }


def audit_selected_api(root: Path = ROOT) -> dict:
    """Reuse the approved eleven-workflow canonical staging validator."""
    script = root / "runpod" / "commercial-compatible" / "prepare.py"
    if script.is_symlink() or not script.is_file():
        raise ValueError("Cannot load approved eleven-workflow profile")
    spec = importlib.util.spec_from_file_location("osf_api_profile_prepare", script)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load approved eleven-workflow profile")
    prepare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prepare)
    # prepare's module ROOT is derived from this exact source location.
    sources, manifest = prepare.choose_files()
    selected = {
        path: entry for path, entry in manifest.items()
        if entry["format"] == "api"
    }
    required = {
        f"workflows/commercial-compatible/{name}.json" for name in API_FILES
    }
    if (len(manifest) != 11 or len(selected) != 4
            or set(selected) != required):
        raise ValueError("Approved four API exports differ from canonical eleven")
    results = {}
    for name in sorted(required):
        if not PATH.fullmatch(name) or name not in sources:
            raise ValueError("Unsafe/missing approved API graph source")
        raw = sources[name]
        graph = json.loads(raw)
        result = audit_api_graph(graph)
        result["source_sha256"] = hashlib.sha256(raw).hexdigest()
        results[name] = result
    return {
        "schema": "osf-selected-four-api-topology-v1",
        "source_scope": "approved_selected_eleven_source_only",
        "approved_selected_workflows": 11,
        "api_workflows_audited": 4,
        "ui_workflows_not_executed": 7,
        "total_api_nodes": sum(x["node_count"] for x in results.values()),
        "total_api_link_inputs": sum(x["link_input_count"] for x in results.values()),
        "workflows": results,
        "all_api_topologies_valid": True,
        "output_index_upper_bounds_checked": False,
        "input_output_types_checked": False,
        "model_or_gpu_inference_qualified": False,
        "commercial_rights_qualified": False,
        "full_eleven_workflows_qualified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        parser.error("Evidence output must not already exist")
    report = audit_selected_api()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write("\n")
    # Do not log prompt contents, file paths, model names or media values.
    print("Selected four API graph topologies valid; full release remains HOLD.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
