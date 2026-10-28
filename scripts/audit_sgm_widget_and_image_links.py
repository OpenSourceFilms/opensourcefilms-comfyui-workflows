#!/usr/bin/env python3
"""Supplemental SGM widget value and IMAGE wire audit, source-only HOLD.

Extends the existing exact-pinned AST SGM interface gate. Never executes
third-party source, downloads checkpoints or mutates selected workflow.
No model filename or widget value is emitted in report metadata.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re

import audit_sgm_segment_source_parity as baseline


EXPECTED_IMAGE_WIRES = (
    [17, 4, 0, 22, 0, "IMAGE"],
    [27, 22, 0, 31, 0, "IMAGE"],
)


def _source_widgets(source: str) -> dict[int, dict[str, dict]]:
    """Parse reviewed source field constraints, without executing its getters."""
    module = ast.parse(source)
    specs = {}
    for node_id, class_name in (
        (21, "LoadSGMVFIModel"), (22, "SGMVFIInterpolate"),
    ):
        klass = baseline._class(module, class_name)
        method = baseline._method(klass, "INPUT_TYPES")
        literal_returns = [
            node.value for node in ast.walk(method)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
        ]
        if len(literal_returns) != 1:
            raise ValueError("SGM widget source declaration no longer literal")
        sockets = {}
        for outer_name, outer in zip(
            literal_returns[0].keys, literal_returns[0].values
        ):
            if not isinstance(outer_name, ast.Constant) or not isinstance(outer, ast.Dict):
                raise ValueError("Unreviewed SGM source widget categories")
            for name_ast, declaration in zip(outer.keys, outer.values):
                if (not isinstance(name_ast, ast.Constant)
                        or not isinstance(name_ast.value, str)
                        or not isinstance(declaration, (ast.List, ast.Tuple))
                        or not declaration.elts):
                    raise ValueError("SGM widget declaration no longer inspectable")
                name = name_ast.value
                first = declaration.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    typ = first.value
                    choices = None
                elif isinstance(first, (ast.List, ast.Tuple)):
                    typ = "COMBO"
                    choices = ast.literal_eval(first)
                    if (not isinstance(choices, (list, tuple)) or not choices
                            or any(type(choice) not in (int, float, str) for choice in choices)):
                        raise ValueError("SGM enumerated widget values changed")
                elif (name == "model_path" and isinstance(first, ast.Call)
                      and isinstance(first.func, ast.Name)
                      and first.func.id == "get_available_sgm_models"
                      and not first.args and not first.keywords):
                    typ = "COMBO"
                    choices = None  # depends on installed checkpoints; HOLD
                else:
                    raise ValueError("Unreviewed dynamic SGM widget type")
                minimum = maximum = None
                if len(declaration.elts) > 1:
                    options = declaration.elts[1]
                    if not isinstance(options, ast.Dict):
                        raise ValueError("SGM widget metadata no longer literal dict")
                    for key, value in zip(options.keys, options.values):
                        if isinstance(key, ast.Constant) and key.value in ("min", "max"):
                            if (not isinstance(value, ast.Constant) or
                                    type(value.value) not in (int, float)):
                                raise ValueError("Dynamic SGM widget numeric bounds")
                            if key.value == "min":
                                minimum = value.value
                            else:
                                maximum = value.value
                sockets[name] = {
                    "type": typ, "choices": choices,
                    "min": minimum, "max": maximum,
                }
        specs[node_id] = sockets
    segment = baseline._class(module, "SGMVFISegmentInterpolate")
    for statement in baseline._method(segment, "INPUT_TYPES").body:
        if not isinstance(statement, ast.Assign):
            continue
        target = statement.targets[0] if len(statement.targets) == 1 else None
        if not isinstance(target, ast.Subscript) or not isinstance(target.slice, ast.Constant):
            continue
        name = target.slice.value
        if name not in ("segment_index", "segment_size"):
            continue
        if name in specs[22] or not isinstance(statement.value, (ast.List, ast.Tuple)):
            raise ValueError("Unexpected SGM inherited widget source")
        value = statement.value
        if not value.elts or not isinstance(value.elts[0], ast.Constant) or value.elts[0].value != "INT":
            raise ValueError("Unexpected SGM segment widget type")
        opts = value.elts[1] if len(value.elts) > 1 else None
        if not isinstance(opts, ast.Dict):
            raise ValueError("Missing source SGM segment bounds")
        bounds = {}
        for k, v in zip(opts.keys, opts.values):
            if isinstance(k, ast.Constant) and k.value in ("min", "max"):
                if not isinstance(v, ast.Constant) or type(v.value) not in (int, float):
                    raise ValueError("Dynamic SGM segment widget bounds")
                bounds[k.value] = v.value
        specs[22][name] = {
            "type": "INT", "choices": None,
            "min": bounds.get("min"), "max": bounds.get("max"),
        }
    return specs


def _check_value(value: object, name: str, constraint: dict) -> None:
    typ = constraint["type"]
    if typ == "BOOLEAN":
        valid = type(value) is bool
    elif typ == "INT":
        valid = type(value) is int
    elif typ == "FLOAT":
        valid = type(value) in (int, float)
    elif typ == "COMBO":
        if name == "model_path":
            # Check only that graph uses a nonempty checkpoint selection.
            # Cannot verify actual file availability or legal rights.
            valid = isinstance(value, str) and bool(value.strip())
        else:
            choices = constraint["choices"]
            valid = choices is not None and any(
                type(value) is type(option) and value == option
                for option in choices
            )
    else:
        # IMAGE, MODEL, VFI_SETTINGS are link-only, never widget values.
        raise ValueError("Unexpected SGM widget source type")
    if not valid:
        raise ValueError("SGM widget type/selection invalid: " + name)
    if typ in ("INT", "FLOAT"):
        low, high = constraint["min"], constraint["max"]
        if low is None or high is None or not low <= value <= high:
            raise ValueError("SGM numeric widget outside pinned source bounds: " + name)


def check_sgm_widgets_and_image_links(graph: dict, source: str) -> dict:
    """Require model-free widget types/ranges and exact two IMAGE connections."""
    specs = _source_widgets(source)
    nodes = graph.get("nodes")
    links = graph.get("links")
    if not isinstance(nodes, list) or not isinstance(links, list):
        raise ValueError("SGM source graph lacks node/link arrays")
    by_id = {node.get("id"): node for node in nodes if isinstance(node, dict)}
    if len(by_id) != len(nodes):
        raise ValueError("Duplicate or invalid SGM graph nodes")
    for expected in EXPECTED_IMAGE_WIRES:
        if links.count(expected) != 1:
            raise ValueError("SGM IMAGE link source/destination drift")
    video = by_id[4]
    segment = by_id[22]
    output = by_id[31]
    if (17 not in video["outputs"][0].get("links", [])
            or segment["inputs"][0].get("name") != "images"
            or segment["inputs"][0].get("link") != 17
            or segment["outputs"][0].get("name") != "images"
            or segment["outputs"][0].get("links") != [27]
            or output["inputs"][0].get("name") != "frames"
            or output["inputs"][0].get("link") != 27):
        raise ValueError("SGM IMAGE port reverse reference differs from reviewed graph")
    verified = {}
    for node_id in (21, 22):
        node = by_id[node_id]
        inputs = node.get("inputs")
        widgets = node.get("widgets_values")
        if not isinstance(inputs, list) or not isinstance(widgets, list):
            raise ValueError("SGM UI widget structures changed")
        ports = [port for port in inputs if port.get("widget") is not None]
        if len(ports) != len(widgets):
            raise ValueError("SGM widget ordering/count differs")
        names = set()
        for port, value in zip(ports, widgets):
            name = port.get("name")
            if (name in names or name not in specs[node_id]
                    or port["widget"] != {"name": name}
                    or port.get("link") is not None):
                raise ValueError("SGM widget/port provenance changed")
            names.add(name)
            _check_value(value, name, specs[node_id][name])
        expected_widgets = {
            name for name, item in specs[node_id].items()
            if item["type"] in ("INT", "FLOAT", "BOOLEAN", "COMBO")
        }
        if names != expected_widgets:
            raise ValueError("SGM required widget fields changed")
        verified[node["type"]] = len(widgets)
    return {
        "status": "WIDGET_AND_IMAGE_WIRES_SOURCE_ONLY_HOLD",
        "image_links_verified": [17, 27],
        "total_widgets_checked": sum(verified.values()),
        "per_node_widget_counts": verified,
        "all_widget_types_choices_numeric_bounds_verified": True,
        "checkpoint_availability_or_licence_qualified": False,
        "model_or_gpu_inference_qualified": False,
        "workflow_modified": False,
    }


def audit(root: Path, tween: Path) -> dict:
    baseline_result = baseline.audit(root, tween)
    if baseline_result["status"] != "SCHEMA_PARITY_SOURCE_ONLY_HOLD":
        raise ValueError("Pinned baseline SGM source parity has not passed")
    path = root / baseline.GRAPH
    graph = json.loads(path.read_text(encoding="utf-8"))
    source = (tween / "nodes.py").read_text(encoding="utf-8")
    return check_sgm_widgets_and_image_links(graph, source)


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    cli.add_argument("--tween-root", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.output.is_symlink() or args.output.exists():
        raise ValueError("Cannot overwrite SGM source-only evidence")
    result = audit(args.repo_root, args.tween_root)
    with args.output.open("x", encoding="utf-8") as fd:
        json.dump(result, fd, sort_keys=True, indent=2)
        fd.write("\n")
    print("SGM widget bounds and image links: source-only HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
