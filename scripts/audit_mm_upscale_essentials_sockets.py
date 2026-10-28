#!/usr/bin/env python3
"""Read-only ComfyUI_essentials embedded-group socket parity on mm_upscale.

The class contracts were transcribed from reviewed upstream files at the
exact candidate commit listed below; this tool does NOT import or execute
the upstream extension. It cannot prove that historical ver=1.1.0 nodes
are compatible with the reviewed commit or that UI groups execute.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "workflows/commercial-compatible/mm_upscale_video_workflow.json"
PROVIDER = "comfyui_essentials"
CANDIDATE_SHA = "9d9f4bedfc9f0321c19faf71855e228c93bd0dc9"
SOURCE_REPOSITORY = "cubiq/ComfyUI_essentials"
# Source reviewed at exact SHA:
# image.py: ImageFromBatch.INPUT_TYPES / RETURN_TYPES
# misc.py: SimpleMathSlider.INPUT_TYPES / RETURN_TYPES
CONTRACTS = {
    "ImageFromBatch+": {
        "inputs": (("image", "IMAGE"), ("start", "INT"), ("length", "INT")),
        "outputs": (("IMAGE", "IMAGE"),),
        "widgets": 2,
        "instances": 9,
    },
    "SimpleMathSlider+": {
        "inputs": (
            ("value", "FLOAT"), ("min", "FLOAT"), ("max", "FLOAT"),
            ("rounding", "INT"),
        ),
        "outputs": (("FLOAT", "FLOAT"), ("INT", "INT")),
        "widgets": 4,
        "instances": 1,
    },
}
EXPECTED_GROUP_COUNTS = {
    "Image Batch Subgraph": 1,
    "Blend Frames Subgraph": 4,
    "Blend Saved Frames Subgraph": 4,
    "Settings": 1,
}
# Historical exports carry both these values. This source comparison
# verifies names/types only; version 1.1.0 is not resolved to source.
OBSERVED_EXPORT_VERSIONS = frozenset({CANDIDATE_SHA, "1.1.0"})


def _ports(node: dict, field: str) -> tuple[tuple[str, str], ...]:
    ports = node.get(field)
    if not isinstance(ports, list):
        raise ValueError("Embedded Essentials node has missing " + field)
    checked = []
    for port in ports:
        if not isinstance(port, dict):
            raise ValueError("Embedded Essentials node port must be an object")
        name, type_ = port.get("name"), port.get("type")
        if not isinstance(name, str) or not isinstance(type_, str):
            raise ValueError("Embedded Essentials node port lacks name/type")
        checked.append((name, type_))
    return tuple(checked)


def audit_export(graph: dict) -> dict:
    if not isinstance(graph, dict):
        raise ValueError("Expected ComfyUI UI/editor export object")
    defs = graph.get("definitions")
    groups = defs.get("subgraphs") if isinstance(defs, dict) else None
    if not isinstance(groups, list) or len(groups) != 4:
        raise ValueError("mm_upscale must retain exactly four embedded group definitions")
    by_class: Counter[str] = Counter()
    by_group: Counter[str] = Counter()
    version_counts: Counter[str] = Counter()
    group_names = set()
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("name"), str):
            raise ValueError("Malformed embedded group")
        group_name = group["name"]
        if group_name in group_names:
            raise ValueError("Duplicate embedded group name")
        group_names.add(group_name)
        nodes = group.get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("Missing embedded node list")
        for node in nodes:
            if not isinstance(node, dict):
                raise ValueError("Malformed embedded group node")
            props = node.get("properties")
            if not isinstance(props, dict) or props.get("cnr_id") != PROVIDER:
                continue
            type_ = node.get("type")
            if type_ not in CONTRACTS:
                raise ValueError("New/unreviewed embedded Essentials class")
            spec = CONTRACTS[type_]
            actual_inputs = _ports(node, "inputs")
            actual_outputs = _ports(node, "outputs")
            if actual_inputs != spec["inputs"]:
                raise ValueError("Essentials embedded input socket/schema mismatch")
            if actual_outputs != spec["outputs"]:
                raise ValueError("Essentials embedded output socket/schema mismatch")
            widgets = node.get("widgets_values")
            if not isinstance(widgets, list) or len(widgets) != spec["widgets"]:
                raise ValueError("Essentials embedded widget count mismatch")
            for input_ in node["inputs"]:
                # Required fields may be connected or take a corresponding
                # widget. This does not evaluate widget payloads.
                connected = input_.get("link")
                widget = input_.get("widget")
                if connected is not None and (type(connected) is not int or connected < 0):
                    raise ValueError("Essentials input link ID is malformed")
                if connected is None and (
                    not isinstance(widget, dict)
                    or widget.get("name") != input_["name"]
                ):
                    raise ValueError("Essentials required input has no link/widget")
            version = props.get("ver")
            if version not in OBSERVED_EXPORT_VERSIONS:
                raise ValueError("Unknown Essentials export version/provenance")
            version_counts[version] += 1
            by_class[type_] += 1
            by_group[group_name] += 1
    if by_class != Counter({name: spec["instances"] for name, spec in CONTRACTS.items()}):
        raise ValueError("Essentials class occurrence baseline changed")
    if by_group != Counter(EXPECTED_GROUP_COUNTS):
        raise ValueError("Essentials group occurrence baseline changed")
    if set(group_names) != set(EXPECTED_GROUP_COUNTS):
        raise ValueError("Unexpected embedded group set")
    return {
        "status": "reviewed_essentials_candidate_socket_parity_only",
        "provider": PROVIDER,
        "candidate_repository": SOURCE_REPOSITORY,
        "candidate_sha": CANDIDATE_SHA,
        "upstream_root_license": "MIT",
        "embedded_node_instances": sum(by_class.values()),
        "classes": dict(sorted(by_class.items())),
        "groups": dict(sorted(by_group.items())),
        "export_version_counts": dict(sorted(version_counts.items())),
        "exact_input_and_output_names_and_types_match_reviewed_source": True,
        "historical_1_1_0_version_compatibility_verified": False,
        "candidate_installed_or_live_registered": False,
        "embedded_groups_executable": False,
        "eleven_workflows_qualified": False,
        "licence_or_transitive_dependencies_cleared": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if EXPORT.is_symlink() or not EXPORT.is_file():
        raise ValueError("Missing or symlinked selected workflow export")
    report = audit_export(json.loads(EXPORT.read_text(encoding="utf-8")))
    if args.output:
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Refusing to overwrite existing audit report")
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(report, out, sort_keys=True, indent=2)
            out.write("\n")
    else:
        print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
