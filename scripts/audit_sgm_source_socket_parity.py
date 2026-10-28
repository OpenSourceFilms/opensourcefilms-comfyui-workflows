#!/usr/bin/env python3
"""Fail-closed source-only SGM-VFI UI/socket/link parity audit.

Reads the selected immutable UI graph and one exact pinned public Tween
checkout. Uses AST, never imports upstream Python, runs CUDA/CuPy code,
downloads models or modifies workflow JSON. Passing means source-level
interface parity only. The entire 11-workflow release stays on HOLD.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
GRAPH = "workflows/commercial-compatible/gimm_sgm_vfi_video_interpolate.json"
TWEEN_SHA = "91947c0b8c795cf504d3848274d4217f0432a324"
EXPECTED_CLASSES = {21: "LoadSGMVFIModel", 22: "SGMVFISegmentInterpolate"}
EXPECTED_WIRES = {
    18: (21, 0, 22, 1, "SGM_VFI_MODEL"),
    27: (22, 0, 31, 0, "IMAGE"),
}
EXPECTED_CNR = "comfyui-tween"


def _class(module: ast.Module, name: str) -> ast.ClassDef:
    matches = [x for x in module.body
               if isinstance(x, ast.ClassDef) and x.name == name]
    if len(matches) != 1:
        raise ValueError("Missing/duplicate exact pinned SGM implementation " + name)
    return matches[0]


def _method(cls: ast.ClassDef) -> ast.FunctionDef:
    matches = [x for x in cls.body
               if isinstance(x, ast.FunctionDef) and x.name == "INPUT_TYPES"]
    if len(matches) != 1:
        raise ValueError("Missing/ambiguous pinned SGM INPUT_TYPES")
    return matches[0]


def _declared_inputs(value: ast.Dict) -> tuple[dict[str, str], set[str]]:
    """Accept literal socket names, declaration types, and one known combo call."""
    types: dict[str, str] = {}
    required = set()
    kinds = set()
    for key, val in zip(value.keys, value.values):
        if not isinstance(key, ast.Constant) or key.value not in ("required", "optional"):
            raise ValueError("Unexpected SGM INPUT_TYPES category")
        if key.value in kinds or not isinstance(val, ast.Dict):
            raise ValueError("SGM input category is missing/duplicated")
        kinds.add(key.value)
        for field, decl in zip(val.keys, val.values):
            if not (isinstance(field, ast.Constant) and isinstance(field.value, str)
                    and isinstance(decl, (ast.Tuple, ast.List)) and decl.elts):
                raise ValueError("SGM input declaration no longer statically inspectable")
            name = field.value
            if name in types:
                raise ValueError("Duplicated pinned SGM input socket")
            raw_type = decl.elts[0]
            if isinstance(raw_type, ast.Constant) and isinstance(raw_type.value, str):
                kind = raw_type.value
            elif isinstance(raw_type, ast.List):
                kind = "COMBO"
            elif (isinstance(raw_type, ast.Call) and
                  isinstance(raw_type.func, ast.Name) and
                  raw_type.func.id == "get_available_sgm_models" and
                  not raw_type.args and not raw_type.keywords):
                kind = "COMBO"
            else:
                raise ValueError("Unreviewed dynamic SGM input type")
            types[name] = kind
            if key.value == "required":
                required.add(name)
    if kinds != {"required", "optional"} and kinds != {"required"}:
        raise ValueError("Unexpected pinned SGM socket categories")
    if not required:
        raise ValueError("No required SGM sockets")
    return types, required


def _initial_base_sockets(cls: ast.ClassDef) -> tuple[dict[str, str], set[str]]:
    returns = [s.value for s in _method(cls).body
               if isinstance(s, ast.Return)]
    if len(returns) != 1 or not isinstance(returns[0], ast.Dict):
        raise ValueError("SGM base sockets are no longer a literal mapping")
    return _declared_inputs(returns[0])


def _segment_override(cls: ast.ClassDef,
                      types: dict[str, str], required: set[str]) -> None:
    """Only accept exact inherited-base + two new required inputs."""
    if not (len(cls.bases) == 1 and isinstance(cls.bases[0], ast.Name)
            and cls.bases[0].id == "SGMVFIInterpolate"):
        raise ValueError("SGM segment no longer inherits the reviewed base")
    body = _method(cls).body
    if len(body) != 4:
        raise ValueError("Unexpected segment INPUT_TYPES body")
    first, *assignments, last = body
    if not (isinstance(first, ast.Assign) and len(first.targets) == 1
            and isinstance(first.targets[0], ast.Name)
            and first.targets[0].id == "base"
            and isinstance(first.value, ast.Call)
            and isinstance(first.value.func, ast.Attribute)
            and first.value.func.attr == "INPUT_TYPES"
            and isinstance(first.value.func.value, ast.Name)
            and first.value.func.value.id == "SGMVFIInterpolate"
            and not first.value.args and not first.value.keywords):
        raise ValueError("SGM segment base invocation changed")
    if not (isinstance(last, ast.Return) and isinstance(last.value, ast.Name)
            and last.value.id == "base"):
        raise ValueError("SGM segment does not return reviewed base")
    expected_added = {"segment_index", "segment_size"}
    added = set()
    for statement in assignments:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            raise ValueError("SGM segment socket override changed")
        outer = statement.targets[0]
        if not (isinstance(outer, ast.Subscript)
                and isinstance(outer.value, ast.Subscript)
                and isinstance(outer.value.value, ast.Name)
                and outer.value.value.id == "base"
                and isinstance(outer.value.slice, ast.Constant)
                and outer.value.slice.value == "required"
                and isinstance(outer.slice, ast.Constant)
                and isinstance(outer.slice.value, str)):
            raise ValueError("Unexpected inherited SGM segment socket mutation")
        name = outer.slice.value
        if name not in expected_added or name in added or name in types:
            raise ValueError("Changed/duplicate SGM segment socket")
        if not (isinstance(statement.value, ast.Tuple)
                and statement.value.elts
                and isinstance(statement.value.elts[0], ast.Constant)
                and statement.value.elts[0].value == "INT"):
            raise ValueError("SGM segment socket type differs from reviewed source")
        added.add(name)
        types[name] = "INT"
        required.add(name)
    if added != expected_added:
        raise ValueError("Missing inherited SGM segment socket")


def _returns(cls: ast.ClassDef) -> tuple[tuple[str, ...], tuple[str, ...]]:
    fields = {}
    for item in cls.body:
        if not isinstance(item, ast.Assign):
            continue
        for target in item.targets:
            if isinstance(target, ast.Name) and target.id in ("RETURN_TYPES", "RETURN_NAMES"):
                if target.id in fields:
                    raise ValueError("Duplicate SGM return declaration")
                value = ast.literal_eval(item.value)
                if not isinstance(value, tuple) or not all(isinstance(x, str) for x in value):
                    raise ValueError("Nonliteral SGM output schema")
                fields[target.id] = value
    if set(fields) != {"RETURN_TYPES", "RETURN_NAMES"}:
        raise ValueError("Incomplete pinned SGM return schema")
    return fields["RETURN_TYPES"], fields["RETURN_NAMES"]


def _registry(init_path: Path) -> dict[str, str]:
    tree = ast.parse(init_path.read_text(encoding="utf-8"))
    mapping = [s.value for s in tree.body
               if isinstance(s, ast.Assign) and any(
                   isinstance(target, ast.Name) and target.id == "NODE_CLASS_MAPPINGS"
                   for target in s.targets)]
    if len(mapping) != 1 or not isinstance(mapping[0], ast.Dict):
        raise ValueError("SGM registry no longer literal")
    entries = {}
    for key, value in zip(mapping[0].keys, mapping[0].values):
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)
                and isinstance(value, ast.Name)) or key.value in entries:
            raise ValueError("Unreviewed SGM source registry")
        entries[key.value] = value.id
    return entries


def _check_graph(graph: dict, signatures: dict[int, dict]) -> dict:
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        raise ValueError("Selected GIMM/SGM workflow is no longer UI graph")
    by_id = {}
    for node in graph["nodes"]:
        if not isinstance(node, dict) or type(node.get("id")) is not int:
            raise ValueError("Malformed UI graph node")
        if node["id"] in by_id:
            raise ValueError("Duplicate UI graph node ID")
        by_id[node["id"]] = node
    links = graph.get("links")
    if not isinstance(links, list):
        raise ValueError("Missing UI graph links")
    link_map = {}
    for edge in links:
        if not isinstance(edge, list) or len(edge) != 6 or type(edge[0]) is not int:
            raise ValueError("Malformed UI link")
        if edge[0] in link_map:
            raise ValueError("Duplicate UI link ID")
        link_map[edge[0]] = edge
    for link_id, expected in EXPECTED_WIRES.items():
        if link_map.get(link_id) != [link_id, *expected]:
            raise ValueError("SGM input/output link changed from reviewed graph")
    result = {}
    for nid, name in EXPECTED_CLASSES.items():
        node = by_id.get(nid)
        if not isinstance(node, dict) or node.get("type") != name:
            raise ValueError("SGM node ID/class mismatch")
        props = node.get("properties")
        if not (isinstance(props, dict) and props.get("cnr_id") == EXPECTED_CNR
                and props.get("ver") == TWEEN_SHA
                and props.get("Node name for S&R") == name):
            raise ValueError("SGM UI source provenance changed")
        inputs = node.get("inputs")
        outputs = node.get("outputs")
        if not isinstance(inputs, list) or not isinstance(outputs, list):
            raise ValueError("SGM node sockets missing")
        got = {}
        widget_count = 0
        for i, entry in enumerate(inputs):
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                raise ValueError("Malformed SGM UI input socket")
            n = entry["name"]
            if n in got or not isinstance(entry.get("type"), str):
                raise ValueError("Duplicate or malformed SGM UI socket")
            got[n] = entry["type"]
            if entry.get("widget") is not None:
                if entry["widget"] != {"name": n} or entry.get("link") is not None:
                    raise ValueError("SGM source widget metadata changed")
                widget_count += 1
        schema = signatures[nid]
        if got != schema["input_types"] or not schema["required"] <= got.keys():
            raise ValueError("SGM input name/type parity failed")
        if len(outputs) != len(schema["output_types"]):
            raise ValueError("SGM number of output ports differs")
        for i, entry in enumerate(outputs):
            if (not isinstance(entry, dict)
                    or entry.get("type") != schema["output_types"][i]
                    or entry.get("name") != schema["output_names"][i]):
                raise ValueError("SGM output name/type parity failed")
        widgets = node.get("widgets_values")
        if not isinstance(widgets, list) or len(widgets) != widget_count:
            raise ValueError("SGM node widget count drift")
        result[name] = {"node_id": nid, "input_count": len(got),
                        "required_input_count": len(schema["required"]),
                        "output_count": len(outputs),
                        "widget_count": widget_count}
    loader = by_id[21]
    segment = by_id[22]
    if (loader["outputs"][0].get("links") != [18]
            or segment["inputs"][1].get("name") != "model"
            or segment["inputs"][1].get("link") != 18
            or segment["inputs"][0].get("link") != 17
            or segment["outputs"][0].get("links") != [27]
            or segment["outputs"][1].get("links") is not None):
        raise ValueError("SGM model or image port wiring differs from source")
    return result


def audit(repo: Path, tween: Path) -> dict:
    if tween.is_symlink() or not tween.is_dir():
        raise ValueError("Pinned Tween source checkout missing")
    head = subprocess.run(
        ["git", "-C", str(tween), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    if head != TWEEN_SHA:
        raise ValueError("Pinned Tween source commit differs")
    lock = (repo / "DEPENDENCIES.lock").read_text(encoding="utf-8")
    start = lock.find(GRAPH + ":")
    if start < 0:
        raise ValueError("Selected GIMM/SGM graph missing from lock")
    end = lock.find("\nworkflows/", start + 1)
    block = lock[start:end if end >= 0 else None]
    if ("- name: ComfyUI-Tween (provides SGM-VFI)\n      commit: " + TWEEN_SHA) not in block:
        raise ValueError("Reviewed Tween commit missing from graph dependency lock")
    graph_path = repo / GRAPH
    raw = graph_path.read_bytes()
    graph = json.loads(raw)
    source = ast.parse((tween / "nodes.py").read_text(encoding="utf-8"))
    names = _registry(tween / "__init__.py")
    for name in EXPECTED_CLASSES.values():
        if names.get(name) != name:
            raise ValueError("Pinned SGM node registry differs")
    base = _class(source, "SGMVFIInterpolate")
    loader = _class(source, "LoadSGMVFIModel")
    segment = _class(source, "SGMVFISegmentInterpolate")
    loader_types, loader_required = _initial_base_sockets(loader)
    segment_types, segment_required = _initial_base_sockets(base)
    _segment_override(segment, segment_types, segment_required)
    signatures = {
        21: {"input_types": loader_types, "required": loader_required,
             "output_types": _returns(loader)[0], "output_names": _returns(loader)[1]},
        22: {"input_types": segment_types, "required": segment_required,
             "output_types": _returns(segment)[0], "output_names": _returns(segment)[1]},
    }
    stats = _check_graph(graph, signatures)
    return {
        "status": "SOURCE_INTERFACE_PARITY_ONLY_HOLD",
        "selected_graph": GRAPH,
        "graph_sha256": hashlib.sha256(raw).hexdigest(),
        "tween_source_commit": TWEEN_SHA,
        "method": "AST-only pinned source + exact UI sockets and links",
        "nodes_checked": stats,
        "model_connection_link": 18,
        "image_downstream_link": 27,
        "sgm_loader_and_segment_source_schema_parity": True,
        "gimm_historical_class_mismatch_unresolved": True,
        "checkpoint_provenance_license_and_cupy_qualified": False,
        "whole_workflow_qualified": False,
        "graph_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--tween-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.repo_root, args.tween_root)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, sort_keys=True, indent=2)
        f.write("\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
