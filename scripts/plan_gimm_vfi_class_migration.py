#!/usr/bin/env python3
"""Non-destructive source-only two-class GIMM-VFI UI migration candidate.

Input: exact pinned upstream checkouts + the existing selected UI export.
Output: bounded JSON metadata, NOT a rewritten or deployable graph.
This cannot clear the SGM, model, licence or GPU HOLD.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path

import audit_gimm_sgm_source_bindings as source_audit


REMAP = {
    1: ("GIMMVFI_loader", "DownloadAndLoadGIMMVFIModel"),
    2: ("GIMMVFIInterpolate", "GIMMVFI_interpolate"),
}
EXPECTED_OUTPUTS = {
    1: (("GIMMVIF_MODEL",), ("gimmvfi_model",)),
    2: (("IMAGE", "IMAGE"), ("images", "flow_tensors")),
}


def _source_schema(path: Path, class_name: str) -> dict:
    """Parse only static INPUT_TYPES and RETURN_* literals, never import code."""
    parsed = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    klass = next(
        (x for x in parsed.body if isinstance(x, ast.ClassDef)
         and x.name == class_name), None
    )
    if klass is None:
        raise ValueError("Pinned implementation class is absent")
    method = next(
        (x for x in klass.body if isinstance(x, ast.FunctionDef)
         and x.name == "INPUT_TYPES"), None
    )
    if method is None:
        raise ValueError("Pinned implementation lacks INPUT_TYPES")
    returns = [
        x.value for x in ast.walk(method)
        if isinstance(x, ast.Return) and isinstance(x.value, ast.Dict)
    ]
    if len(returns) != 1:
        raise ValueError("Pinned INPUT_TYPES definition is not uniquely literal")
    socket_types = {}
    required = set()
    optional = set()
    for kind_node, contents in zip(returns[0].keys, returns[0].values):
        if not (isinstance(kind_node, ast.Constant)
                and kind_node.value in ("required", "optional")
                and isinstance(contents, ast.Dict)):
            continue
        kind = kind_node.value
        for key, declaration in zip(contents.keys, contents.values):
            if (not isinstance(key, ast.Constant)
                    or not isinstance(key.value, str)
                    or not isinstance(declaration, (ast.Tuple, ast.List))
                    or not declaration.elts):
                raise ValueError("Pinned source socket declaration is not literal")
            first = declaration.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                socket_type = first.value
            elif isinstance(first, (ast.List, ast.Tuple)):
                socket_type = "COMBO"
            else:
                raise ValueError("Pinned source socket type cannot be inspected safely")
            name = key.value
            if name in socket_types:
                raise ValueError("Duplicate upstream input socket")
            socket_types[name] = socket_type
            (required if kind == "required" else optional).add(name)
    if not required:
        raise ValueError("Pinned implementation has no required sockets")
    constants = {}
    for item in klass.body:
        if not isinstance(item, ast.Assign):
            continue
        for target in item.targets:
            if isinstance(target, ast.Name) and target.id in ("RETURN_TYPES", "RETURN_NAMES"):
                constants[target.id] = tuple(ast.literal_eval(item.value))
    if not all(label in constants for label in ("RETURN_TYPES", "RETURN_NAMES")):
        raise ValueError("Missing upstream return contract")
    return {
        "socket_types": socket_types,
        "required_names": required,
        "optional_names": optional,
        "output_types": constants["RETURN_TYPES"],
        "output_names": constants["RETURN_NAMES"],
    }


def construct_candidate(graph: dict, source_schemas: dict[int, dict]) -> dict:
    """Allow only two exact graph type/name substitutions after schema parity."""
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        raise ValueError("Missing selected UI graph nodes")
    candidate = copy.deepcopy(graph)
    selected_ids = set()
    changes = []
    for node in candidate["nodes"]:
        if not isinstance(node, dict):
            raise ValueError("Malformed UI node")
        node_id = node.get("id")
        if node_id not in REMAP:
            continue
        if node_id in selected_ids:
            raise ValueError("Duplicate candidate node id")
        selected_ids.add(node_id)
        historical, intended = REMAP[node_id]
        if node.get("type") != historical:
            raise ValueError("Selected GIMM class or node id differs from reviewed graph")
        schema = source_schemas.get(node_id)
        if not isinstance(schema, dict):
            raise ValueError("Pinned migration source schema unavailable")
        source_inputs = schema["socket_types"]
        inputs = node.get("inputs")
        outputs = node.get("outputs")
        if not isinstance(inputs, list) or not isinstance(outputs, list):
            raise ValueError("Missing original graph node sockets")
        graph_inputs = {}
        for entry in inputs:
            if not isinstance(entry, dict):
                raise ValueError("Malformed selected input socket")
            name = entry.get("name")
            typ = entry.get("type")
            if not isinstance(name, str) or not isinstance(typ, str) or name in graph_inputs:
                raise ValueError("Malformed or duplicate selected input socket")
            graph_inputs[name] = typ
        if graph_inputs != source_inputs:
            raise ValueError("Historical GIMM graph inputs differ from pinned implementation")
        if not schema["required_names"] <= set(graph_inputs):
            raise ValueError("Required pinned GIMM input is absent")
        types = tuple(x.get("type") for x in outputs)
        names = tuple(x.get("name") for x in outputs)
        if (types, names) != EXPECTED_OUTPUTS[node_id]:
            raise ValueError("Historical GIMM output types/names differ from reviewed graph")
        if (types != schema["output_types"] or names != schema["output_names"]):
            raise ValueError("Pinned GIMM output contract differs from graph")
        props = node.get("properties")
        if (not isinstance(props, dict)
                or props.get("Node name for S&R") != historical
                or props.get("ver") != source_audit.GIMM_SHA
                or props.get("cnr_id") != "ComfyUI-GIMM-VFI"):
            raise ValueError("Selected GIMM node provenance/name changed")
        node["type"] = intended
        props["Node name for S&R"] = intended
        changes.append({
            "node_id": node_id,
            "historical_class": historical,
            "pinned_class": intended,
            "source_input_types": {k: source_inputs[k] for k in sorted(source_inputs)},
            "output_types": list(types),
            "output_names": list(names),
        })
    if selected_ids != set(REMAP):
        raise ValueError("Both selected GIMM nodes must exist exactly once")
    # Regression invariant: after undoing precisely two class/name pairs,
    # the entire JSON structure (including links and widgets) is unchanged.
    reversal = copy.deepcopy(candidate)
    for node in reversal["nodes"]:
        if node.get("id") in REMAP:
            original, _ = REMAP[node["id"]]
            node["type"] = original
            node["properties"]["Node name for S&R"] = original
    if reversal != graph:
        raise ValueError("Candidate unexpectedly modified unrelated graph content")
    encoding = json.dumps(candidate, sort_keys=True, separators=(",", ":")).encode()
    return {
        "status": "CANDIDATE_ONLY_HOLD",
        "source_audit_status": "HOLD",
        "graph": source_audit.GRAPH,
        "candidate_only_non_deployable": True,
        "original_graph_untouched": True,
        "changes_count": len(changes),
        "changes": sorted(changes, key=lambda x: x["node_id"]),
        "candidate_canonical_json_sha256": hashlib.sha256(encoding).hexdigest(),
        "link_and_widget_structures_unchanged": True,
        "gimm_interface_name_and_type_parity": True,
        "sgm_gpu_checkpoint_and_rights_qualified": False,
        "gimm_gpu_checkpoint_and_rights_qualified": False,
        "end_to_end_workflow_qualified": False,
        "model_weights_downloaded": False,
    }


def plan(repo_root: Path, gimm_root: Path, tween_root: Path) -> dict:
    baseline = source_audit.audit(repo_root, gimm_root, tween_root)
    if (baseline.get("status") != "HOLD"
            or baseline.get("source_binding_qualified") is not False
            or baseline.get("gimm_loader_missing_from_both_pins") is not True):
        raise ValueError("Source audit no longer matches reviewed HOLD")
    mapping = source_audit.mapping_from_source(gimm_root / "nodes.py")
    schemas = {}
    for node_id, (_, intended) in REMAP.items():
        if intended not in mapping:
            raise ValueError("Target GIMM class is not registered by pinned source")
        schemas[node_id] = _source_schema(
            gimm_root / "nodes.py", mapping[intended],
        )
    graph = json.loads((repo_root / source_audit.GRAPH).read_text(encoding="utf-8"))
    result = construct_candidate(graph, schemas)
    result["gimm_source_commit"] = source_audit.GIMM_SHA
    result["tween_source_commit"] = source_audit.TWEEN_SHA
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--gimm-root", type=Path, required=True)
    parser.add_argument("--tween-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to overwrite candidate metadata")
    result = plan(args.repo_root, args.gimm_root, args.tween_root)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("GIMM source-only two-class migration candidate: HOLD, original graph unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
