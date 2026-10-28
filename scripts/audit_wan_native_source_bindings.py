#!/usr/bin/env python3
"""Fail-closed source-only check of five selected Wan UI exports.

Compare Wan-specific node class/input/output contracts with ComfyUI's
exact pinned native nodes_wan.py. Missing classes remain explicit HOLDs.
Does not execute models, expand graphs, import ComfyUI, or read any media.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMFY_SHA = "08cf0284ff45723aa67841c80cabb0e3cb50c9d7"
WAN_FILES = (
    "wan22_fmlf_first_middle_last_frame",
    "video_wan2_2_14B_flf2v",
    "video_wan2_2_14B_fmlf2v",
    "video_wan2_2_14B_i2v",
    "video_wan_vace_14B_v2v",
)
UNRESOLVED_WAN_CLASS_IDS = frozenset({
    "WanFirstMiddleLastFrameToVideo",
    "WanFourFrameReferenceUltimate",
    "WanMultiFrameRefToVideo",
})
NATIVE_WAN_CLASS_IDS = frozenset({
    "WanFirstLastFrameToVideo", "WanVaceToVideo", "TrimVideoLatent",
})


def _literal(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _kw(call: ast.Call, name: str) -> ast.AST | None:
    return next((value.value for value in call.keywords if value.arg == name), None)


def _schema_call(cls: ast.ClassDef) -> ast.Call | None:
    for fn in cls.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or fn.name != "define_schema":
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
                callee = node.value.func
                if isinstance(callee, ast.Attribute) and callee.attr == "Schema":
                    return node.value
    return None


def _schema_ports(node: ast.AST | None, input_port: bool) -> list[str]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        raise ValueError("Native Wan schema does not use a static port list")
    names = []
    for port in node.elts:
        if not isinstance(port, ast.Call) or not isinstance(port.func, ast.Attribute):
            raise ValueError("Unrecognised native Wan socket declaration")
        if port.func.attr != ("Input" if input_port else "Output"):
            raise ValueError("Unexpected native Wan socket kind")
        name = _literal(port.args[0]) if input_port and port.args else None
        if not input_port:
            name = _literal(_kw(port, "display_name"))
            if name is None and isinstance(port.func.value, ast.Attribute):
                name = port.func.value.attr.upper()
        if name is None:
            raise ValueError("Native Wan socket has no literal name")
        if name in names:
            raise ValueError("Duplicate native Wan socket name")
        names.append(name)
    return names


def native_wan_schemas(source: str) -> dict[str, dict]:
    """Extract node_id and literal socket names by AST, not textual guesses."""
    tree = ast.parse(source)
    result = {}
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef):
            continue
        schema = _schema_call(cls)
        if schema is None:
            continue
        node_id = _literal(_kw(schema, "node_id"))
        if not node_id or (not node_id.startswith("Wan") and node_id != "TrimVideoLatent"):
            continue
        if node_id in result:
            raise ValueError("Duplicate native Wan node_id")
        result[node_id] = {
            "inputs": _schema_ports(_kw(schema, "inputs"), True),
            "outputs": _schema_ports(_kw(schema, "outputs"), False),
        }
    return result


def audit_wan_source(source_path: Path, root: Path = ROOT) -> dict:
    if (source_path.is_symlink() or not source_path.is_file()
            or source_path.name != "nodes_wan.py"):
        raise ValueError("Native Wan source file must be a non-symlinked nodes_wan.py")
    source_bytes = source_path.read_bytes()
    native = native_wan_schemas(source_bytes.decode("utf-8"))
    if not NATIVE_WAN_CLASS_IDS.issubset(native):
        raise ValueError("Reviewed native Wan classes not all present in pinned source")
    if UNRESOLVED_WAN_CLASS_IDS.intersection(native):
        raise ValueError("Previously unresolved Wan class is now native: review baseline")

    lock_file = root / "DEPENDENCIES.lock"
    if lock_file.is_symlink() or not lock_file.is_file():
        raise ValueError("Canonical dependency lock unavailable")
    manifest = lock_file.read_text(encoding="utf-8")
    by_graph = {}
    native_uses = Counter()
    missing_uses = Counter()
    for stem in WAN_FILES:
        rel = "workflows/commercial-compatible/" + stem + ".json"
        graph_path = root / rel
        if graph_path.is_symlink() or not graph_path.is_file():
            raise ValueError("Missing/symlinked selected Wan workflow")
        marker = rel + ":\n"
        if manifest.count(marker) != 1:
            raise ValueError("Wan graph not uniquely listed in canonical lock")
        block = manifest.split(marker, 1)[1].split("\nworkflows/", 1)[0]
        if "commercial_status: commercial-compatible" not in block:
            raise ValueError("Wan graph is not in the selected compatible profile")
        graph_bytes = graph_path.read_bytes()
        doc = json.loads(graph_bytes)
        if not isinstance(doc, dict) or not isinstance(doc.get("nodes"), list):
            raise ValueError("Expected a Wan UI/editor graph, not an API prompt")
        checked = []
        for entry in doc["nodes"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("type"), str):
                raise ValueError("Malformed WAN UI node entry")
            cls = entry["type"]
            if not cls.startswith("Wan") and cls != "TrimVideoLatent":
                continue
            if cls not in native:
                if cls not in UNRESOLVED_WAN_CLASS_IDS:
                    raise ValueError("Unknown Wan class beyond reviewed missing set")
                missing_uses[cls] += 1
                checked.append({"class_id": cls, "status": "missing_from_pinned_public_wan_source"})
                continue
            inputs = entry.get("inputs", [])
            outputs = entry.get("outputs", [])
            if not isinstance(inputs, list) or not isinstance(outputs, list):
                raise ValueError("Malformed native Wan UI socket arrays")
            actual_inputs = [item.get("name") if isinstance(item, dict) else None for item in inputs]
            actual_outputs = [item.get("name") if isinstance(item, dict) else None for item in outputs]
            expected = native[cls]
            # UI serialisation carries optional sockets, not just active edges.
            if set(actual_inputs) != set(expected["inputs"]) or len(actual_inputs) != len(expected["inputs"]):
                raise ValueError("Wan input sockets do not match pinned source: " + cls)
            if actual_outputs != expected["outputs"]:
                raise ValueError("Wan output sockets do not match pinned source: " + cls)
            native_uses[cls] += 1
            checked.append({"class_id": cls, "status": "source_input_output_names_match"})
        if not checked:
            raise ValueError("Selected Wan graph contains no relevant Wan nodes")
        by_graph[rel] = {
            "source_sha256": hashlib.sha256(graph_bytes).hexdigest(),
            "wan_class_occurrences": len(checked),
            "checks": checked,
            "api_prompt_execution_verified": False,
        }

    if set(missing_uses) != UNRESOLVED_WAN_CLASS_IDS:
        raise ValueError("Expected missing native Wan set has changed")
    return {
        "schema": "osf-selected-wan-native-source-gate-v1",
        "upstream_comfyui_commit": COMFY_SHA,
        "upstream_nodes_wan_py_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "selected_wan_graphs_checked": len(WAN_FILES),
        "native_class_occurrences_with_socket_name_parity": dict(sorted(native_uses.items())),
        "missing_native_class_occurrences": dict(sorted(missing_uses.items())),
        "per_graph": by_graph,
        "status": "source_audit_complete_with_unresolved_native_classes",
        "all_wan_class_ids_available": False,
        "wan_workflows_executable": False,
        "model_weights_or_gpu_checked": False,
        "source_provider_rights_cleared": False,
    }


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--native-source", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.output.exists() or args.output.is_symlink():
        cli.error("Refusing to replace existing evidence")
    result = audit_wan_source(args.native_source)
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2, sort_keys=True)
        target.write("\n")
    print("Wan source audit complete: %d graphs; %d missing class IDs"
          % (result["selected_wan_graphs_checked"],
             len(result["missing_native_class_occurrences"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
