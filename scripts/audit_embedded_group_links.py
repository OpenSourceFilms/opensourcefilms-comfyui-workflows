#!/usr/bin/env python3
"""Source-only structural link preflight for the four embedded mm_upscale groups.

This never rewrites the published graph and never claims groups are executable.
It distinguishes valid active LiteGraph links from unresolved references
retained in node output and exposed-port metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
APPROVED = "workflows/commercial-compatible/mm_upscale_video_workflow.json"
PREPARE = ROOT / "runpod" / "commercial-compatible" / "prepare.py"


def _positive_id(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError("Invalid " + label)
    return value


def _slot(value: object, label: str, length: int) -> int:
    if type(value) is not int or not 0 <= value < length:
        raise ValueError("Invalid " + label)
    return value


def _ref_ids(value: object, label: str) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Malformed " + label)
    refs = [_positive_id(item, label) for item in value]
    if len(refs) != len(set(refs)):
        raise ValueError("Duplicated " + label)
    return refs


def _ports(node: dict, key: str) -> list:
    parts = node.get(key, [])
    if not isinstance(parts, list) or any(not isinstance(x, dict) for x in parts):
        raise ValueError("Malformed embedded node " + key)
    return parts


def inspect_group(group: dict) -> dict:
    """Fail on corrupt ACTIVE links, report dangling reverse references.

    -10 and -20 are LiteGraph's embedded input/output pseudo-node IDs.
    They are NOT absent internal nodes and must be matched to group ports.
    """
    if not isinstance(group, dict):
        raise ValueError("Malformed embedded group")
    nodes = group.get("nodes")
    links = group.get("links")
    inputs = group.get("inputs")
    outputs = group.get("outputs")
    if (not isinstance(nodes, list) or not nodes
            or not isinstance(links, list)
            or not isinstance(inputs, list) or not isinstance(outputs, list)
            or any(not isinstance(x, dict) for x in inputs + outputs)):
        raise ValueError("Missing embedded group nodes, links, or exposed ports")
    if group.get("inputNode", {}).get("id") != -10:
        raise ValueError("Missing embedded input pseudo-node -10")
    if group.get("outputNode", {}).get("id") != -20:
        raise ValueError("Missing embedded output pseudo-node -20")

    by_node: dict[int, dict] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("Malformed embedded node")
        key = _positive_id(node.get("id"), "embedded node ID")
        if key in by_node:
            raise ValueError("Duplicate embedded node ID")
        _ports(node, "inputs")
        _ports(node, "outputs")
        by_node[key] = node

    by_link: dict[int, dict] = {}
    for link in links:
        if not isinstance(link, dict):
            raise ValueError("Malformed embedded link")
        link_id = _positive_id(link.get("id"), "embedded link ID")
        if link_id in by_link:
            raise ValueError("Duplicate embedded active link ID")
        by_link[link_id] = link

    for link_id, link in by_link.items():
        origin = link.get("origin_id")
        target = link.get("target_id")
        if type(origin) is not int or type(target) is not int:
            raise ValueError("Noninteger active link endpoint")
        if origin == -10:
            output_slot = _slot(link.get("origin_slot"), "embedded group input slot", len(inputs))
            if link_id not in _ref_ids(inputs[output_slot].get("linkIds"),
                                       "embedded group input linkIds"):
                raise ValueError("Active link missing from group input port")
        else:
            if origin not in by_node:
                raise ValueError("Active embedded link has absent origin node")
            ports = _ports(by_node[origin], "outputs")
            output_slot = _slot(link.get("origin_slot"), "embedded origin output slot", len(ports))
            if link_id not in _ref_ids(ports[output_slot].get("links"),
                                       "embedded node output links"):
                raise ValueError("Active link missing from node output port")
        if target == -20:
            input_slot = _slot(link.get("target_slot"), "embedded group output slot", len(outputs))
            if link_id not in _ref_ids(outputs[input_slot].get("linkIds"),
                                       "embedded group output linkIds"):
                raise ValueError("Active link missing from group output port")
        else:
            if target not in by_node:
                raise ValueError("Active embedded link has absent target node")
            ports = _ports(by_node[target], "inputs")
            input_slot = _slot(link.get("target_slot"), "embedded target input slot", len(ports))
            if ports[input_slot].get("link") != link_id:
                raise ValueError("Active link missing from node input port")

    stale = {
        "node_input": [],
        "node_output": [],
        "group_input": [],
        "group_output": [],
    }
    for node_id, node in by_node.items():
        for slot, port in enumerate(_ports(node, "inputs")):
            ref = port.get("link")
            if ref is None:
                continue
            ref = _positive_id(ref, "embedded node input link")
            if ref not in by_link:
                stale["node_input"].append(ref)
            elif by_link[ref].get("target_id") != node_id or by_link[ref].get("target_slot") != slot:
                raise ValueError("Embedded input references another node's active link")
        for slot, port in enumerate(_ports(node, "outputs")):
            for ref in _ref_ids(port.get("links"), "embedded node output links"):
                if ref not in by_link:
                    stale["node_output"].append(ref)
                elif (by_link[ref].get("origin_id") != node_id
                      or by_link[ref].get("origin_slot") != slot):
                    raise ValueError("Embedded output references another node's active link")

    for slot, port in enumerate(inputs):
        for ref in _ref_ids(port.get("linkIds"), "embedded group input linkIds"):
            if ref not in by_link:
                stale["group_input"].append(ref)
            elif (by_link[ref].get("origin_id") != -10
                  or by_link[ref].get("origin_slot") != slot):
                raise ValueError("Embedded group input references unrelated active link")
    for slot, port in enumerate(outputs):
        for ref in _ref_ids(port.get("linkIds"), "embedded group output linkIds"):
            if ref not in by_link:
                stale["group_output"].append(ref)
            elif (by_link[ref].get("target_id") != -20
                  or by_link[ref].get("target_slot") != slot):
                raise ValueError("Embedded group output references unrelated active link")

    unresolved = {key: sorted(set(ids)) for key, ids in stale.items()}
    count = sum(len(ids) for ids in unresolved.values())
    return {
        "group_uuid": group.get("id"),
        "internal_node_count": len(nodes),
        "active_link_count": len(links),
        "active_link_endpoints_consistent": True,
        "unresolved_reverse_reference_ids_by_location": unresolved,
        "unresolved_reverse_reference_count": count,
        "all_reverse_references_resolved": count == 0,
        "ui_group_executable_proven": False,
        "api_conversion_proven": False,
    }


def audit(root: Path = ROOT) -> dict:
    source = root / "runpod/commercial-compatible/prepare.py"
    if source.is_symlink() or not source.is_file():
        raise ValueError("Missing or symlinked canonical approved staging source")
    spec = importlib.util.spec_from_file_location("osf_mm_group_canonical", source)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load canonical selected workflow manifest")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    selected, manifest = module.choose_files()
    if len(manifest) != 11 or APPROVED not in manifest:
        raise ValueError("Canonical selected eleven-workflow profile changed")
    if manifest[APPROVED]["format"] != "ui" or APPROVED not in selected:
        raise ValueError("mm_upscale graph not a selected UI export")
    raw = selected[APPROVED]
    graph = json.loads(raw)
    definitions = graph.get("definitions", {})
    groups = definitions.get("subgraphs") if isinstance(definitions, dict) else None
    if not isinstance(groups, list) or len(groups) != 4:
        raise ValueError("Expected exactly four embedded mm_upscale subgraphs")
    ids = [x.get("id") for x in groups if isinstance(x, dict)]
    if len(ids) != 4 or len(set(ids)) != 4:
        raise ValueError("Malformed or duplicate embedded group IDs")
    results = sorted((inspect_group(g) for g in groups), key=lambda x: x["group_uuid"])
    return {
        "schema": "osf-mm-upscale-embedded-link-preflight-v1",
        "scope": "source_only_read_only_not_executable",
        "approved_workflow": APPROVED,
        "graph_sha256": hashlib.sha256(raw).hexdigest(),
        "group_count": len(results),
        "total_internal_nodes": sum(x["internal_node_count"] for x in results),
        "total_active_links": sum(x["active_link_count"] for x in results),
        "total_unresolved_reverse_references": sum(
            x["unresolved_reverse_reference_count"] for x in results
        ),
        "active_links_structurally_consistent": True,
        "all_reverse_references_resolved": all(
            x["all_reverse_references_resolved"] for x in results
        ),
        "embedded_group_runtime_qualified": False,
        "eleven_workflows_gpu_qualified": False,
        "results": results,
    }


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", type=Path)
    args = cli.parse_args()
    result = audit()
    payload = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        if args.output.exists() or args.output.is_symlink():
            cli.error("Output must be a new regular file")
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
