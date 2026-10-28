#!/usr/bin/env python3
"""Source-bound, read-only Custom-Scripts socket audit for mm_upscale groups.

The class contracts come from the reviewed historical upstream SHA embedded
in StringFunction nodes. The MathExpression nodes export a *different*
semver string. This is not proof that that alias resolves to the same source,
that the UI socket types equal the runtime API, or that expressions are safe
or executable in the target environment.

Do not evaluate the export's expressions or publish widget values.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "workflows/commercial-compatible/mm_upscale_video_workflow.json"
PROVIDER = "comfyui-custom-scripts"
REPOSITORY = "pythongosssss/ComfyUI-Custom-Scripts"
REVIEWED_SHA = "f2838ed5e59de4d73cde5c98354b87a8d3200190"
HISTORICAL_ALIAS = "1.2.5"
GROUP_NAMES = frozenset({
    "Image Batch Subgraph", "Blend Frames Subgraph",
    "Blend Saved Frames Subgraph", "Settings",
})
EXPECTED_GROUP_COUNTS = {
    "Image Batch Subgraph": 4,
    "Blend Frames Subgraph": 10,
    "Blend Saved Frames Subgraph": 9,
}
EXPECTED_CLASS_COUNTS = {
    "MathExpression|pysssss": 21,
    "StringFunction|pysssss": 2,
}
# Original upstream py/math_expression.py, INPUT_TYPES required expression:
# STRING; optional a, b, c: wildcard AnyType("*"). UI export instead shows
# a union-of-types socket for *all* four entries, including expression.
# That observed UI type is not equivalent to the source API type STRING.
MATH_UI_TYPE = "INT,FLOAT,IMAGE,LATENT"
SOURCE_CONTRACTS = {
    "MathExpression|pysssss": {
        "source_file": "py/math_expression.py",
        "source_required": (("expression", "STRING"),),
        "source_optional": (("a", "*"), ("b", "*"), ("c", "*")),
        "ui_inputs": (
            ("a", MATH_UI_TYPE), ("b", MATH_UI_TYPE),
            ("c", MATH_UI_TYPE), ("expression", MATH_UI_TYPE),
        ),
        "ui_outputs": (("INT", "INT"), ("FLOAT", "FLOAT")),
        "ui_widgets": 1,
        "version": HISTORICAL_ALIAS,
    },
    "StringFunction|pysssss": {
        "source_file": "py/string_function.py",
        "source_required": (("action", "COMBO"), ("tidy_tags", "COMBO")),
        "source_optional": (
            ("text_a", "STRING"), ("text_b", "STRING"),
            ("text_c", "STRING"),
        ),
        "ui_inputs": (
            ("action", "COMBO"), ("tidy_tags", "COMBO"),
            ("text_a", "STRING"), ("text_b", "STRING"), ("text_c", "STRING"),
        ),
        "ui_outputs": (("STRING", "STRING"),),
        "ui_widgets": 5,
        "version": REVIEWED_SHA,
    },
}


def _ports(node: dict, key: str) -> tuple[tuple[str, str], ...]:
    ports = node.get(key)
    if not isinstance(ports, list):
        raise ValueError("Missing Custom-Scripts " + key + " sockets")
    result = []
    for port in ports:
        if not isinstance(port, dict):
            raise ValueError("Malformed Custom-Scripts socket")
        name, type_ = port.get("name"), port.get("type")
        if not isinstance(name, str) or not isinstance(type_, str):
            raise ValueError("Custom-Scripts socket lacks name/type")
        result.append((name, type_))
    if len(result) != len(set(result)):
        raise ValueError("Duplicate Custom-Scripts socket")
    return tuple(result)


def audit_export(graph: object) -> dict:
    if not isinstance(graph, dict):
        raise ValueError("Expected a ComfyUI workflow JSON object")
    definitions = graph.get("definitions")
    groups = definitions.get("subgraphs") if isinstance(definitions, dict) else None
    if not isinstance(groups, list) or len(groups) != 4:
        raise ValueError("Expected precisely four embedded group definitions")
    group_names = set()
    classes: Counter[str] = Counter()
    group_counts: Counter[str] = Counter()
    versions: Counter[str] = Counter()
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("name"), str):
            raise ValueError("Malformed embedded group definition")
        name = group["name"]
        if name in group_names:
            raise ValueError("Duplicate embedded group name")
        group_names.add(name)
        nodes = group.get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("Missing embedded group nodes")
        for node in nodes:
            if not isinstance(node, dict):
                raise ValueError("Malformed embedded node")
            props = node.get("properties")
            if not isinstance(props, dict) or props.get("cnr_id") != PROVIDER:
                continue
            class_name = node.get("type")
            if class_name not in SOURCE_CONTRACTS:
                raise ValueError("New/unreviewed embedded Custom-Scripts class")
            contract = SOURCE_CONTRACTS[class_name]
            if _ports(node, "inputs") != contract["ui_inputs"]:
                raise ValueError("Custom-Scripts embedded input socket mismatch")
            if _ports(node, "outputs") != contract["ui_outputs"]:
                raise ValueError("Custom-Scripts embedded output socket mismatch")
            widgets = node.get("widgets_values")
            if not isinstance(widgets, list) or len(widgets) != contract["ui_widgets"]:
                raise ValueError("Custom-Scripts widget count mismatch")
            for port in node["inputs"]:
                link = port.get("link")
                widget = port.get("widget")
                if link is not None and (type(link) is not int or link < 0):
                    raise ValueError("Custom-Scripts link identifier invalid")
                if widget is not None and (
                    not isinstance(widget, dict) or widget.get("name") != port["name"]
                ):
                    raise ValueError("Custom-Scripts named widget metadata mismatch")
                if class_name == "MathExpression|pysssss":
                    # All Math widgets belong to the expression source STRING.
                    # a/b/c are optional and can have neither link nor widget.
                    if port["name"] == "expression" and (
                        link is not None or not isinstance(widget, dict)
                    ):
                        raise ValueError("MathExpression required expression widget missing")
                elif link is None and (
                    not isinstance(widget, dict) or widget.get("name") != port["name"]
                ):
                    raise ValueError("StringFunction input lacks link or named widget")
            version = props.get("ver")
            if version != contract["version"]:
                raise ValueError("Unreviewed Custom-Scripts version/source hint")
            classes[class_name] += 1
            group_counts[name] += 1
            versions[version] += 1
    if group_names != GROUP_NAMES:
        raise ValueError("Unexpected embedded group set")
    if classes != Counter(EXPECTED_CLASS_COUNTS):
        raise ValueError("Custom-Scripts class occurrence baseline changed")
    if group_counts != Counter(EXPECTED_GROUP_COUNTS):
        raise ValueError("Custom-Scripts group counts changed")
    if versions != Counter({HISTORICAL_ALIAS: 21, REVIEWED_SHA: 2}):
        raise ValueError("Custom-Scripts revision/provenance baseline changed")
    return {
        "status": "reviewed_custom_scripts_candidate_ui_socket_audit_only",
        "source_repository": REPOSITORY,
        "historical_source_sha": REVIEWED_SHA,
        "source_registration": "__init__.py dynamically loads py/*.py",
        "reviewed_source_files": [
            "py/math_expression.py", "py/string_function.py",
        ],
        "root_license": "MIT",
        "provider_hint": PROVIDER,
        "embedded_node_instances": sum(classes.values()),
        "classes": dict(sorted(classes.items())),
        "groups": dict(sorted(group_counts.items())),
        "export_version_counts": dict(sorted(versions.items())),
        "all_ui_sockets_match_reviewed_source_bound_export": True,
        "math_expression_source_string_vs_ui_union_difference": True,
        "math_expression_source_wildcard_inputs": ["a", "b", "c"],
        "math_expression_1_2_5_alias_equivalence_proven": False,
        "runtime_api_schema_equivalence_proven": False,
        "expression_evaluation_or_safety_qualified": False,
        "external_node_import_qualified": False,
        "embedded_group_execution_qualified": False,
        "manifest_source_commit_pinned": False,
        "transitive_licences_cleared": False,
        "eleven_workflows_qualified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if EXPORT.is_symlink() or not EXPORT.is_file():
        parser.error("Missing or symlinked workflow export")
    graph_bytes = EXPORT.read_bytes()
    report = audit_export(json.loads(graph_bytes))
    report["workflow_file_sha256"] = hashlib.sha256(graph_bytes).hexdigest()
    if args.output:
        if args.output.exists() or args.output.is_symlink():
            parser.error("Refusing to overwrite output path or symlink")
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, sort_keys=True)
            f.write("\n")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
