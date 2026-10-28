#!/usr/bin/env python3
"""Source-only schema parity for the two selected SGM-VFI UI nodes.

Read exact pinned ComfyUI-Tween Python as AST only. Never import third-party
source, download checkpoints, invoke SGM CuPy or modify the selected graph.
Matching sockets cannot authorize GPU inference or deployment.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

import audit_gimm_sgm_source_bindings as pins

GRAPH = pins.GRAPH
TWEEN_COMMIT = pins.TWEEN_SHA
SGM_CLASSES = {21: "LoadSGMVFIModel", 22: "SGMVFISegmentInterpolate"}
EXPECTED_SOURCE_CLASSES = {
    21: "LoadSGMVFIModel",
    22: "SGMVFISegmentInterpolate",
}
EXPECTED_SOCKETS = {
    21: {"model_path": "COMBO", "tta": "BOOLEAN", "num_key_points": "FLOAT"},
    22: {
        "images": "IMAGE", "model": "SGM_VFI_MODEL",
        "multiplier": "COMBO", "clear_cache_after_n_frames": "INT",
        "keep_device": "BOOLEAN", "all_on_gpu": "BOOLEAN",
        "batch_size": "INT", "chunk_size": "INT", "source_fps": "FLOAT",
        "target_fps": "FLOAT", "settings": "VFI_SETTINGS",
        "segment_index": "INT", "segment_size": "INT",
    },
}
EXPECTED_OUTPUTS = {
    21: (("SGM_VFI_MODEL",), ("model",)),
    22: (("IMAGE", "SGM_VFI_MODEL"), ("images", "model")),
}
EXPECTED_WIDGET_COUNTS = {21: 3, 22: 10}
EXPECTED_MODEL_LINK = [18, 21, 0, 22, 1, "SGM_VFI_MODEL"]


def _class(module: ast.Module, name: str) -> ast.ClassDef:
    classes = [x for x in module.body if isinstance(x, ast.ClassDef)
               and x.name == name]
    if len(classes) != 1:
        raise ValueError("Expected exactly one pinned SGM class: " + name)
    return classes[0]


def _method(klass: ast.ClassDef, name: str) -> ast.FunctionDef:
    methods = [x for x in klass.body if isinstance(x, ast.FunctionDef)
               and x.name == name]
    if len(methods) != 1:
        raise ValueError("Pinned SGM method missing or duplicated: " + name)
    return methods[0]


def _socket_type(node: ast.AST, *, name: str) -> str:
    if not isinstance(node, (ast.Tuple, ast.List)) or not node.elts:
        raise ValueError("SGM source socket declaration is not a tuple")
    first = node.elts[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    if isinstance(first, (ast.List, ast.Tuple)):
        return "COMBO"
    if (name == "model_path" and isinstance(first, ast.Call)
            and isinstance(first.func, ast.Name)
            and first.func.id == "get_available_sgm_models"
            and not first.args and not first.keywords):
        return "COMBO"
    raise ValueError("Unreviewed dynamic SGM socket declaration: " + name)


def _dict_sockets(data: ast.Dict) -> tuple[dict[str, str], set[str], set[str]]:
    sockets: dict[str, str] = {}
    required: set[str] = set()
    optional: set[str] = set()
    for key, value in zip(data.keys, data.values):
        if (not isinstance(key, ast.Constant)
                or key.value not in ("required", "optional")
                or not isinstance(value, ast.Dict)):
            raise ValueError("SGM INPUT_TYPES structure differs")
        dest = required if key.value == "required" else optional
        for name, declaration in zip(value.keys, value.values):
            if (not isinstance(name, ast.Constant)
                    or not isinstance(name.value, str)
                    or name.value in sockets):
                raise ValueError("Malformed or repeated SGM source socket name")
            sockets[name.value] = _socket_type(declaration, name=name.value)
            dest.add(name.value)
    if not required:
        raise ValueError("Pinned SGM has no required sockets")
    return sockets, required, optional


def _literal_inputs(klass: ast.ClassDef) -> tuple[dict[str, str], set[str], set[str]]:
    method = _method(klass, "INPUT_TYPES")
    returns = [node for node in ast.walk(method)
               if isinstance(node, ast.Return)]
    if len(returns) != 1 or not isinstance(returns[0].value, ast.Dict):
        raise ValueError("Pinned SGM INPUT_TYPES no longer uniquely literal")
    return _dict_sockets(returns[0].value)


def _output_contract(klass: ast.ClassDef) -> tuple[tuple[str, ...], tuple[str, ...]]:
    data = {}
    for node in klass.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in (
                    "RETURN_TYPES", "RETURN_NAMES"
                ):
                    if target.id in data:
                        raise ValueError("Duplicated SGM source output declaration")
                    value = ast.literal_eval(node.value)
                    if not isinstance(value, (tuple, list)):
                        raise ValueError("Malformed pinned SGM output declaration")
                    data[target.id] = tuple(value)
    if set(data) != {"RETURN_TYPES", "RETURN_NAMES"}:
        raise ValueError("Missing pinned SGM output declaration")
    return data["RETURN_TYPES"], data["RETURN_NAMES"]


def _segment_schema(module: ast.Module) -> tuple[dict[str, str], set[str], set[str]]:
    base = _class(module, "SGMVFIInterpolate")
    seg = _class(module, "SGMVFISegmentInterpolate")
    if (len(seg.bases) != 1 or not isinstance(seg.bases[0], ast.Name)
            or seg.bases[0].id != "SGMVFIInterpolate"):
        raise ValueError("Segmented SGM no longer inherits reviewed base")
    base_sockets, required, optional = _literal_inputs(base)
    method = _method(seg, "INPUT_TYPES")
    if (not method.body or not isinstance(method.body[0], ast.Assign)
            or len(method.body[0].targets) != 1
            or not isinstance(method.body[0].targets[0], ast.Name)
            or method.body[0].targets[0].id != "base"
            or ast.unparse(method.body[0].value)
            != "SGMVFIInterpolate.INPUT_TYPES()"):
        raise ValueError("Segmented SGM base input inheritance differs")
    added = {}
    for stmt in method.body[1:]:
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Subscript):
                raise ValueError("Unexpected segmented SGM mutation")
            access = ast.unparse(stmt.targets[0])
            if access not in ("base['required']['segment_index']",
                              "base['required']['segment_size']"):
                raise ValueError("Unexpected segmented SGM input mutation")
            name = "segment_index" if "segment_index" in access else "segment_size"
            if name in added:
                raise ValueError("Duplicated segmented SGM input mutation")
            added[name] = _socket_type(stmt.value, name=name)
        elif isinstance(stmt, ast.Return):
            if not isinstance(stmt.value, ast.Name) or stmt.value.id != "base":
                raise ValueError("Segmented SGM no longer returns inherited schema")
        else:
            raise ValueError("Unreviewed segmented SGM INPUT_TYPES operation")
    if added != {"segment_index": "INT", "segment_size": "INT"}:
        raise ValueError("Segmented SGM source extension differs")
    if "segment_index" in base_sockets or "segment_size" in base_sockets:
        raise ValueError("Segmented SGM key collides with base")
    return {**base_sockets, **added}, required | set(added), optional


def inspect_sgm_source(code: str, registry: dict[str, str]) -> dict[int, dict]:
    module = ast.parse(code)
    observed = {}
    for node_id, registered in SGM_CLASSES.items():
        actual = registry.get(registered)
        if actual != EXPECTED_SOURCE_CLASSES[node_id]:
            raise ValueError("Pinned SGM registry class changed: " + registered)
        klass = _class(module, actual)
        if node_id == 22:
            sockets, required, optional = _segment_schema(module)
        else:
            sockets, required, optional = _literal_inputs(klass)
        if sockets != EXPECTED_SOCKETS[node_id]:
            raise ValueError("SGM pinned socket names/types drifted")
        if _output_contract(klass) != EXPECTED_OUTPUTS[node_id]:
            raise ValueError("SGM pinned output types/names drifted")
        observed[node_id] = {
            "class_type": registered,
            "input_types": sockets,
            "required_names": sorted(required),
            "optional_names": sorted(optional),
            "output_types": list(EXPECTED_OUTPUTS[node_id][0]),
            "output_names": list(EXPECTED_OUTPUTS[node_id][1]),
        }
    return observed


def inspect_sgm_graph(graph: dict, schemas: dict[int, dict]) -> dict:
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        raise ValueError("Selected SGM UI graph is malformed")
    matches = [n for n in graph["nodes"]
               if isinstance(n, dict) and (n.get("id") in SGM_CLASSES or
                                            n.get("type") in SGM_CLASSES.values())]
    if len(matches) != 2 or {n.get("id") for n in matches} != set(SGM_CLASSES):
        raise ValueError("Selected SGM graph identities drifted")
    rows = []
    for node in sorted(matches, key=lambda x: x["id"]):
        node_id = node["id"]
        if node.get("type") != SGM_CLASSES[node_id]:
            raise ValueError("Selected SGM graph type changed")
        props = node.get("properties")
        if (not isinstance(props, dict)
                or props.get("ver") != TWEEN_COMMIT
                or props.get("cnr_id") != "comfyui-tween"
                or props.get("aux_id") != "Ethanfel/ComfyUI-Tween"
                or props.get("Node name for S&R") != node["type"]):
            raise ValueError("SGM graph historical source provenance differs")
        inputs = node.get("inputs")
        outputs = node.get("outputs")
        if not isinstance(inputs, list) or not isinstance(outputs, list):
            raise ValueError("Malformed SGM graph socket lists")
        observed_inputs = {}
        for item in inputs:
            if (not isinstance(item, dict)
                    or not isinstance(item.get("name"), str)
                    or not isinstance(item.get("type"), str)
                    or item["name"] in observed_inputs):
                raise ValueError("Malformed or duplicated SGM graph input")
            observed_inputs[item["name"]] = item["type"]
        if observed_inputs != schemas[node_id]["input_types"]:
            raise ValueError("SGM graph input names/types do not match pinned source")
        actual_outputs = (
            tuple(x.get("type") for x in outputs),
            tuple(x.get("name") for x in outputs),
        )
        if actual_outputs != EXPECTED_OUTPUTS[node_id]:
            raise ValueError("SGM graph output names/types differ from source")
        if len(node.get("widgets_values", [])) != EXPECTED_WIDGET_COUNTS[node_id]:
            raise ValueError("SGM historical widget count differs")
        rows.append({
            "node_id": node_id,
            "class_type": node["type"],
            "required_source_socket_count": len(schemas[node_id]["required_names"]),
            "optional_source_socket_count": len(schemas[node_id]["optional_names"]),
            "graph_socket_count": len(inputs),
            "widget_count": len(node["widgets_values"]),
            "output_types": list(actual_outputs[0]),
        })
    if not isinstance(graph.get("links"), list) or (
            graph["links"].count(EXPECTED_MODEL_LINK) != 1):
        raise ValueError("SGM model pass-through link contract differs")
    loader = next(n for n in matches if n["id"] == 21)
    segment = next(n for n in matches if n["id"] == 22)
    if (loader["outputs"][0].get("links") != [18]
            or segment["inputs"][1].get("link") != 18):
        raise ValueError("SGM model link endpoint declarations differ")
    return {
        "selected_nodes": rows,
        "model_link_id": 18,
        "model_type": "SGM_VFI_MODEL",
        "segment_model_pass_through_source_signature_verified": True,
    }


def audit(root: Path, tween_root: Path) -> dict:
    pins.verify_manifest_pins((root / "DEPENDENCIES.lock").read_text(encoding="utf-8"))
    pins.verify_git_head(tween_root, TWEEN_COMMIT)
    source_path = tween_root / "nodes.py"
    registry_path = tween_root / "__init__.py"
    graph_path = root / GRAPH
    if any(p.is_symlink() or not p.is_file()
           for p in (source_path, registry_path, graph_path)):
        raise ValueError("Missing or symlinked SGM source/graph")
    registry = pins.mapping_from_source(registry_path)
    schemas = inspect_sgm_source(
        source_path.read_text(encoding="utf-8"), registry,
    )
    raw = graph_path.read_bytes()
    graph = json.loads(raw)
    evidence = inspect_sgm_graph(graph, schemas)
    return {
        "schema": "osf-sgm-pinned-schema-parity-hold-v1",
        "status": "SCHEMA_PARITY_SOURCE_ONLY_HOLD",
        "selected_workflow": GRAPH,
        "workflow_sha256": hashlib.sha256(raw).hexdigest(),
        "upstream_source_sha": TWEEN_COMMIT,
        **evidence,
        "third_party_imported": False,
        "checkpoint_downloaded": False,
        "inference_executed": False,
        "gpu_runtime_qualified": False,
        "commercial_rights_cleared": False,
        "original_graph_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tween-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to overwrite source audit report")
    report = audit(args.repo_root, args.tween_root)
    with args.output.open("x", encoding="utf-8") as fd:
        json.dump(report, fd, indent=2, sort_keys=True)
        fd.write("\n")
    print("SGM pinned source schema parity: HOLD, no runtime or model clearance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
