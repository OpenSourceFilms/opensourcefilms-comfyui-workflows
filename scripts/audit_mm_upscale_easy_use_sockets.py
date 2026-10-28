#!/usr/bin/env python3
"""Read-only historical Easy-Use socket preflight for embedded mm_upscale.

The contracts below are transcribed from the exact reviewed upstream source,
NOT imported at runtime. Matching a source candidate and UI sockets does not
establish historical version equivalence, runtime API compatibility, rights
clearance, loop/subgraph execution, or a safe dependency installation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = Path("workflows/commercial-compatible/mm_upscale_video_workflow.json")
PROVIDER = "comfyui-easy-use"
REPOSITORY = "yolain/ComfyUI-Easy-Use"
REVIEWED_SHA = "b0b47ca1372117fce575d9e744655344ebff6bef"
LICENSE_ID = "GPL-3.0"
SOURCE_FILES = {"logic": "py/nodes/logic.py", "image": "py/nodes/image.py"}
GROUP_COUNTS = {
    "Image Batch Subgraph": 8,
    "Blend Frames Subgraph": 14,
    "Blend Saved Frames Subgraph": 12,
    "Settings": 8,
}
CLASS_COUNTS = {
    "easy compare": 7,
    "easy int": 13,
    "easy ifElse": 10,
    "easy forLoopStart": 3,
    "easy batchAnything": 3,
    "easy imageSave": 2,
    "easy forLoopEnd": 3,
    "easy boolean": 1,
}
HISTORICAL_IF_ELSE_SHA = "8ecc929cd41cf0f7ef6fcc45d4bbc5729c6f287f"
ALLOWED_VERSIONS = {
    "easy forLoopStart": {"1.3.0"},
    "easy forLoopEnd": {"1.3.0"},
    "easy ifElse": {"1.3.3", HISTORICAL_IF_ELSE_SHA},
}
for _class in CLASS_COUNTS:
    ALLOWED_VERSIONS.setdefault(_class, {"1.3.3"})

# Input/output contracts taken from exact upstream logic.py and image.py.
# For UI serialization the observed widget/link layout differs from the
# upstream runtime-required/optional grouping and, for ifElse and loopStart,
# from the source declaration order. Preserve those differences explicitly.
SOURCE_API = {
    "easy compare": {
        "origin": "logic", "required": (), "optional": (
            ("a", "*"), ("b", "*"), ("comparison", "COMBO")),
        "outputs": (("boolean", "BOOLEAN"),),
        "ui_inputs": (("a", "*"), ("b", "*"), ("comparison", "COMBO")),
        "widgets": 1,
    },
    "easy int": {
        "origin": "logic", "required": (("value", "INT"),),
        "optional": (), "outputs": (("int", "INT"),),
        "ui_inputs": (("value", "INT"),), "widgets": 1,
    },
    "easy ifElse": {
        "origin": "logic", "required": (
            ("boolean", "BOOLEAN"), ("on_true", "*"), ("on_false", "*")),
        "optional": (), "outputs": (("*", "*"),),
        "ui_inputs": (("on_true", "*"), ("on_false", "*"), ("boolean", "BOOLEAN")),
        "widgets": 1,
    },
    "easy forLoopStart": {
        "origin": "logic", "required": (("total", "INT"),),
        "optional": (("initial_value1", "*"), ("initial_value2", "*")),
        "outputs": (
            ("flow", "FLOW_CONTROL"), ("index", "INT"),
            ("value1", "*"), ("value2", "*")),
        "ui_inputs": (
            ("initial_value1", "*"), ("total", "INT"),
            ("initial_value2", "*")),
        "widgets": 1,
    },
    "easy batchAnything": {
        "origin": "logic", "required": (("any_1", "*"), ("any_2", "*")),
        "optional": (), "outputs": (("batch", "*"),),
        "ui_inputs": (("any_1", "*"), ("any_2", "*")), "widgets": 0,
    },
    "easy imageSave": {
        "origin": "image", "required": (
            ("images", "IMAGE"), ("filename_prefix", "STRING"),
            ("only_preview", "BOOLEAN")),
        "optional": (), "outputs": (),
        "ui_inputs": (
            ("images", "IMAGE"), ("filename_prefix", "STRING"),
            ("only_preview", "BOOLEAN")),
        "widgets": 2,
    },
    "easy forLoopEnd": {
        "origin": "logic", "required": (("flow", "FLOW_CONTROL"),),
        "optional": (("initial_value1", "*"), ("initial_value2", "*")),
        "outputs": (("value1", "*"), ("value2", "*")),
        "ui_inputs": (
            ("flow", "FLOW_CONTROL"), ("initial_value1", "*"),
            ("initial_value2", "*")),
        "widgets": 0,
    },
    "easy boolean": {
        "origin": "logic", "required": (("value", "BOOLEAN"),),
        "optional": (), "outputs": (("boolean", "BOOLEAN"),),
        "ui_inputs": (("value", "BOOLEAN"),), "widgets": 1,
    },
}


def ports(node: dict, field: str) -> tuple[tuple[str, str], ...]:
    data = node.get(field)
    if not isinstance(data, list):
        raise ValueError("Missing Easy-Use " + field + " list")
    result = []
    for port in data:
        if not isinstance(port, dict):
            raise ValueError("Malformed Easy-Use " + field + " entry")
        name, kind = port.get("name"), port.get("type")
        if not isinstance(name, str) or not name or not isinstance(kind, str) or not kind:
            raise ValueError("Easy-Use socket missing name/type")
        result.append((name, kind))
        if field == "inputs":
            link = port.get("link")
            if link is not None and (not isinstance(link, int) or isinstance(link, bool) or link < 0):
                raise ValueError("Invalid Easy-Use input link metadata")
        elif field == "outputs":
            links = port.get("links")
            if links is not None and (
                not isinstance(links, list) or
                any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in links)
            ):
                raise ValueError("Invalid Easy-Use output links metadata")
    if len(result) != len(set(result)):
        raise ValueError("Duplicate Easy-Use socket")
    return tuple(result)


def audit_export(graph: object) -> dict:
    if not isinstance(graph, dict):
        raise ValueError("Expected mm_upscale UI export object")
    defs = graph.get("definitions")
    groups = defs.get("subgraphs") if isinstance(defs, dict) else None
    if not isinstance(groups, list) or len(groups) != len(GROUP_COUNTS):
        raise ValueError("Expected four embedded mm_upscale groups")
    classes = Counter()
    counts = Counter()
    versions = Counter()
    seen = set()
    mismatched_source_ui_order = set()
    for group in groups:
        if not isinstance(group, dict) or group.get("name") not in GROUP_COUNTS:
            raise ValueError("Unknown embedded mm_upscale group")
        name = group["name"]
        if name in seen:
            raise ValueError("Duplicate embedded group name")
        seen.add(name)
        nodes = group.get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("Missing embedded group node array")
        for node in nodes:
            if not isinstance(node, dict):
                raise ValueError("Malformed embedded node entry")
            props = node.get("properties")
            if not isinstance(props, dict) or props.get("cnr_id") != PROVIDER:
                continue
            class_id = node.get("type")
            if class_id not in SOURCE_API:
                raise ValueError("Unreviewed embedded Easy-Use class")
            spec = SOURCE_API[class_id]
            if ports(node, "inputs") != spec["ui_inputs"]:
                raise ValueError("Easy-Use input socket differs from export/source candidate")
            if ports(node, "outputs") != spec["outputs"]:
                raise ValueError("Easy-Use output socket differs from source candidate")
            if set(spec["ui_inputs"]) != set(spec["required"] + spec["optional"]):
                raise ValueError("Source candidate input inventory differs from exported UI")
            widgets = node.get("widgets_values")
            if not isinstance(widgets, list) or len(widgets) != spec["widgets"]:
                raise ValueError("Easy-Use widget count differs from reviewed UI")
            for port in node["inputs"]:
                if port.get("widget") is not None:
                    widget = port["widget"]
                    if not isinstance(widget, dict) or not isinstance(widget.get("name"), str):
                        raise ValueError("Malformed Easy-Use widget binding")
            version = props.get("ver")
            if version not in ALLOWED_VERSIONS[class_id]:
                raise ValueError("Unreviewed Easy-Use exported version alias")
            versions[version] += 1
            classes[class_id] += 1
            counts[name] += 1
            if tuple(spec["ui_inputs"]) != tuple(spec["required"] + spec["optional"]):
                mismatched_source_ui_order.add(class_id)
    if dict(counts) != {k: v for k, v in GROUP_COUNTS.items()}:
        raise ValueError("Easy-Use embedded group counts drifted")
    if dict(classes) != CLASS_COUNTS:
        raise ValueError("Easy-Use embedded source class counts drifted")
    if sum(counts.values()) != 42 or set(seen) != set(GROUP_COUNTS):
        raise ValueError("Incomplete Easy-Use embedded inventory")
    if dict(versions) != {
        "1.3.0": 6, "1.3.3": 35, HISTORICAL_IF_ELSE_SHA: 1,
    }:
        raise ValueError("Unexpected Easy-Use version distribution")
    return {
        "schema": "osf-mm-upscale-easy-use-socket-preflight-v1",
        "provider_hint": PROVIDER,
        "reviewed_source_candidate": REPOSITORY,
        "reviewed_source_sha": REVIEWED_SHA,
        "reviewed_root_license": LICENSE_ID,
        "source_modules": SOURCE_FILES,
        "class_instance_counts": dict(sorted(classes.items())),
        "group_instance_counts": dict(sorted(counts.items())),
        "total_instances": sum(counts.values()),
        "distinct_class_ids": len(classes),
        "historical_export_version_counts": dict(sorted(versions.items())),
        "observed_ui_vs_source_input_order_differences": sorted(mismatched_source_ui_order),
        "exported_ui_socket_shapes_match_reviewed_candidate": True,
        "historical_version_aliases_equivalent_to_reviewed_sha": False,
        "actual_runtime_registration_qualified": False,
        "loop_execution_qualified": False,
        "dependency_manifest_updated": False,
        "transitive_licenses_cleared": False,
        "eleven_workflows_qualified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    path = ROOT / WORKFLOW
    if path.is_symlink() or not path.is_file():
        parser.error("Missing/symlinked mm_upscale workflow")
    graph = json.loads(path.read_text(encoding="utf-8"))
    result = audit_export(graph)
    if args.output is None:
        print(json.dumps(result, sort_keys=True, indent=2))
    else:
        dest = args.output
        if dest.is_symlink() or dest.exists():
            parser.error("Refusing existing or symlinked output")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
