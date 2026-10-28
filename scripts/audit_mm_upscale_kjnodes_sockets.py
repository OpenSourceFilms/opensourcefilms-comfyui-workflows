#!/usr/bin/env python3
"""Read-only KJNodes socket drift preflight for embedded mm_upscale groups.

Contracts are transcribed from original upstream source at the exact Git SHA
embedded in the export. This does not install/import KJNodes, resolve the
older 1.1.4 alias, execute the nested groups or clear GPLv3 obligations.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "workflows/commercial-compatible/mm_upscale_video_workflow.json"
PROVIDER = "comfyui-kjnodes"
REVIEWED_REPOSITORY = "kijai/ComfyUI-KJNodes"
REVIEWED_SOURCE_SHA = "468fcc86f0b29e79a8510e8239eb15714d6747a6"
REVIEWED_SOURCE_FILE = "nodes/image_nodes.py"
SOURCE_REGISTRATION_FILE = "__init__.py"
HISTORICAL_VERSION_ALIAS = "1.1.4"
OBSERVED_VERSIONS = frozenset({REVIEWED_SOURCE_SHA, HISTORICAL_VERSION_ALIAS})
ALL_GROUP_NAMES = frozenset({
    "Image Batch Subgraph", "Blend Frames Subgraph",
    "Blend Saved Frames Subgraph", "Settings",
})
EXPECTED_CLASS_COUNTS = {
    "ImageBatchJoinWithTransition": 2,
    "ImageBatchMulti": 4,
    "ImagePass": 1,
}
EXPECTED_GROUP_COUNTS = {
    "Blend Frames Subgraph": 4,
    "Blend Saved Frames Subgraph": 3,
}
# INPUT_TYPES and RETURN_TYPES at the historical pinned upstream revision.
# COMBO denotes a source-declared selection from a list, not a literal
# string: the UI export represents it as a COMBO input socket.
SOURCE_CONTRACTS = {
    "ImageBatchJoinWithTransition": {
        "required": (
            ("images_1", "IMAGE"), ("images_2", "IMAGE"),
            ("start_index", "INT"), ("interpolation", "COMBO"),
            ("transition_type", "COMBO"), ("transitioning_frames", "INT"),
            ("blur_radius", "FLOAT"), ("reverse", "BOOLEAN"),
            ("device", "COMBO"),
        ),
        "optional": (),
        "outputs": (("IMAGE", "IMAGE"),),
        "ui_widgets": 7,
    },
    "ImageBatchMulti": {
        # Source-required order is inputcount, image_1, but the UI export
        # serializes image_1, optional image_2, inputcount. Both are checked
        # explicitly. Do not claim direct API order parity here.
        "required": (("inputcount", "INT"), ("image_1", "IMAGE")),
        "optional": (("image_2", "IMAGE"),),
        "ui_inputs": (
            ("image_1", "IMAGE"), ("image_2", "IMAGE"),
            ("inputcount", "INT"),
        ),
        "outputs": (("images", "IMAGE"),),
        "ui_widgets": 2,
    },
    "ImagePass": {
        "required": (),
        "optional": (("image", "IMAGE"),),
        "outputs": (("IMAGE", "IMAGE"),),
        "ui_widgets": 0,
    },
}


def _ports(node: dict, key: str) -> tuple[tuple[str, str], ...]:
    entries = node.get(key)
    if not isinstance(entries, list):
        raise ValueError("Missing KJNodes " + key + " sockets")
    result = []
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Malformed KJNodes socket entry")
        name, type_ = item.get("name"), item.get("type")
        if not isinstance(name, str) or not isinstance(type_, str):
            raise ValueError("KJNodes socket lacks name/type")
        result.append((name, type_))
    if len(result) != len(set(result)):
        raise ValueError("Duplicate KJNodes socket")
    return tuple(result)


def audit_export(graph: object) -> dict:
    if not isinstance(graph, dict):
        raise ValueError("Expected a UI/editor workflow object")
    defs = graph.get("definitions")
    groups = defs.get("subgraphs") if isinstance(defs, dict) else None
    if not isinstance(groups, list) or len(groups) != 4:
        raise ValueError("Expected exactly four embedded group definitions")
    class_counts: Counter[str] = Counter()
    group_counts: Counter[str] = Counter()
    versions: Counter[str] = Counter()
    seen_groups: set[str] = set()
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("name"), str):
            raise ValueError("Malformed mm_upscale embedded group")
        name = group["name"]
        if name in seen_groups:
            raise ValueError("Duplicate embedded group name")
        seen_groups.add(name)
        nodes = group.get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("Missing embedded node list")
        for node in nodes:
            if not isinstance(node, dict):
                raise ValueError("Malformed embedded node")
            props = node.get("properties")
            if not isinstance(props, dict) or props.get("cnr_id") != PROVIDER:
                continue
            node_type = node.get("type")
            if node_type not in SOURCE_CONTRACTS:
                raise ValueError("New/unreviewed embedded KJNodes class")
            spec = SOURCE_CONTRACTS[node_type]
            source_inputs = spec["required"] + spec["optional"]
            expected_ui_inputs = spec.get("ui_inputs", source_inputs)
            actual_inputs = _ports(node, "inputs")
            actual_outputs = _ports(node, "outputs")
            if actual_inputs != expected_ui_inputs:
                raise ValueError("KJNodes embedded input socket/schema mismatch")
            if actual_outputs != spec["outputs"]:
                raise ValueError("KJNodes embedded output socket/schema mismatch")
            if set(actual_inputs) != set(source_inputs):
                raise ValueError("KJNodes embedded source input coverage mismatch")
            widgets = node.get("widgets_values")
            if not isinstance(widgets, list) or len(widgets) != spec["ui_widgets"]:
                raise ValueError("KJNodes embedded widget count mismatch")
            for port in node["inputs"]:
                link = port.get("link")
                widget = port.get("widget")
                if link is not None and (type(link) is not int or link < 0):
                    raise ValueError("KJNodes embedded input link ID malformed")
                if link is None and (not isinstance(widget, dict)
                                     or widget.get("name") != port["name"]):
                    raise ValueError("KJNodes input lacks link or named widget")
            version = props.get("ver")
            if version not in OBSERVED_VERSIONS:
                raise ValueError("Unreviewed KJNodes version/provenance")
            class_counts[node_type] += 1
            group_counts[name] += 1
            versions[version] += 1
    if seen_groups != ALL_GROUP_NAMES:
        raise ValueError("Unexpected embedded group set")
    if class_counts != Counter(EXPECTED_CLASS_COUNTS):
        raise ValueError("KJNodes class occurrence baseline changed")
    if group_counts != Counter(EXPECTED_GROUP_COUNTS):
        raise ValueError("KJNodes group occurrence baseline changed")
    if versions[REVIEWED_SOURCE_SHA] != 1 or versions[HISTORICAL_VERSION_ALIAS] != 6:
        raise ValueError("KJNodes exact-source and historical alias counts changed")
    return {
        "status": "reviewed_kjnodes_historical_source_socket_parity_only",
        "provider": PROVIDER,
        "source_repository": REVIEWED_REPOSITORY,
        "historical_source_sha": REVIEWED_SOURCE_SHA,
        "source_definition_file": REVIEWED_SOURCE_FILE,
        "source_registration_file": SOURCE_REGISTRATION_FILE,
        "root_license": "GPL-3.0",
        "embedded_node_instances": sum(class_counts.values()),
        "classes": dict(sorted(class_counts.items())),
        "groups": dict(sorted(group_counts.items())),
        "export_version_counts": dict(sorted(versions.items())),
        "input_and_output_names_types_match_reviewed_source": True,
        "dynamic_image_batch_optional_input_qualified_only_as_export": True,
        "historical_1_1_4_alias_equivalence_proven": False,
        "candidate_runtime_import_qualified": False,
        "embedded_group_runtime_executable": False,
        "nested_dependencies_cleared": False,
        "commercial_rights_cleared": False,
        "eleven_workflows_qualified": False,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if EXPORT.is_symlink() or not EXPORT.is_file():
        raise ValueError("Missing or symlinked workflow export")
    result = audit_export(json.loads(EXPORT.read_text(encoding="utf-8")))
    if args.output:
        if args.output.exists() or args.output.is_symlink():
            p.error("Refusing to overwrite existing output or symlink")
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(result, out, indent=2, sort_keys=True)
            out.write("\n")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
